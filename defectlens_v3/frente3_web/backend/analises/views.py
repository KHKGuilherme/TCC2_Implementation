"""
Os endpoints da API.
"""

from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from frente2_predicao import analisar

from . import fila
from .models import Analise
from .serializers import (AnaliseDetalheSerializer, AnaliseResumoSerializer,
                          PedidoSerializer)

RECENTES = 8


# =============================================================
# Limite De Pedidos
# -------------------------------------------------------------
# Limita os pedidos de análise por endereço IP
# =============================================================
class LimiteDePedidos(SimpleRateThrottle):
    scope = "pedidos"

    # =============================================================
    # Get Cache Key
    # -------------------------------------------------------------
    # Só conta os POST; as consultas ficam livres
    # =============================================================
    def get_cache_key(self, request, view):
        if request.method != "POST":
            return None
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


# =============================================================
# Saude
# -------------------------------------------------------------
# Resposta simples para o contêiner saber que a API subiu
# =============================================================
class SaudeView(APIView):
    # =============================================================
    # Get
    # -------------------------------------------------------------
    # Devolve ok
    # =============================================================
    def get(self, request):
        return Response({"ok": True})


# =============================================================
# Modelo
# -------------------------------------------------------------
# O que está treinado, e quanto já foi analisado
# =============================================================
class ModeloView(APIView):
    # =============================================================
    # Get
    # -------------------------------------------------------------
    # Devolve o modelo em uso e os números de uso
    # =============================================================
    def get(self, request):
        try:
            modelo = analisar.descrever_modelo()
        except analisar.ErroDeAnalise as erro:
            return Response({"erro": str(erro)},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)

        concluidas = Analise.objects.filter(status=Analise.Status.CONCLUIDA)
        avaliados = sum((a.resumo or {}).get("avaliados", 0)
                        for a in concluidas.only("resumo"))

        return Response({
            **modelo,
            "uso": {
                "analises": concluidas.count(),
                "repositorios": concluidas.values("repositorio")
                                          .distinct().count(),
                "arquivos_avaliados": avaliados,
            },
        })


# =============================================================
# Analises
# -------------------------------------------------------------
# Lista as recentes e recebe pedidos novos
# =============================================================
class AnalisesView(APIView):
    throttle_classes = [LimiteDePedidos]

    # =============================================================
    # Get
    # -------------------------------------------------------------
    # Lista as análises recentes, uma por repositório
    # =============================================================
    def get(self, request):
        vistos, recentes = set(), []
        concluidas = (Analise.objects
                      .filter(status=Analise.Status.CONCLUIDA)
                      .defer("resultado").order_by("-concluida"))

        for analise in concluidas[:50]:
            chave = analise.repositorio.lower()
            if chave in vistos:
                continue
            vistos.add(chave)
            recentes.append(analise)
            if len(recentes) == RECENTES:
                break

        return Response(AnaliseResumoSerializer(recentes, many=True).data)

    # =============================================================
    # Post
    # -------------------------------------------------------------
    # Recebe um pedido, reaproveita ou enfileira
    # =============================================================
    def post(self, request):
        pedido = PedidoSerializer(data=request.data)
        pedido.is_valid(raise_exception=True)

        try:
            repositorio, ramo_da_url = analisar.interpretar_endereco(
                pedido.validated_data["endereco"])
            ramo = pedido.validated_data.get("ramo") or ramo_da_url or ""

            commit = analisar.commit_remoto(repositorio, ramo or None)
        except analisar.ErroDeAnalise as erro:
            return Response({"erro": str(erro)},
                            status=status.HTTP_400_BAD_REQUEST)

        mesmo_repo = Q(repositorio__iexact=repositorio)
        if ramo:
            mesmo_repo &= Q(ramo=ramo)

        if commit:
            pronta = Analise.objects.filter(
                mesmo_repo, commit=commit,
                status=Analise.Status.CONCLUIDA).first()
            if pronta and "porcentagem_estimada" in (pronta.resumo or {}):
                return Response({"id": pronta.id, "reaproveitada": True},
                                status=status.HTTP_200_OK)

        andamento = Analise.objects.filter(
            mesmo_repo, status__in=[Analise.Status.NA_FILA,
                                    Analise.Status.RODANDO]).first()
        if andamento and fila.esta_ativa(andamento.id):
            return Response({"id": andamento.id, "reaproveitada": True},
                            status=status.HTTP_202_ACCEPTED)

        if fila.tamanho() >= settings.FILA_MAXIMA:
            return Response({"erro": "Há muitas análises na fila agora. Tente de novo "
                                     "em alguns minutos."},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)

        analise = Analise.objects.create(repositorio=repositorio,
                                         ramo=ramo, commit=commit or "")
        fila.enfileirar(analise)

        return Response({"id": analise.id, "reaproveitada": False},
                        status=status.HTTP_202_ACCEPTED)


# =============================================================
# Analise
# -------------------------------------------------------------
# Uma análise, consultada pela tela a cada segundo
# =============================================================
class AnaliseView(APIView):
    # =============================================================
    # Get
    # -------------------------------------------------------------
    # Devolve o progresso ou o resultado
    # =============================================================
    def get(self, request, identificador):
        analise = get_object_or_404(Analise, pk=identificador)

        if analise.pendente and not fila.esta_ativa(analise.id):
            analise.status = Analise.Status.ERRO
            analise.erro = ("A análise foi interrompida porque o servidor "
                            "reiniciou. Peça de novo.")
            analise.concluida = timezone.now()
            analise.save(update_fields=["status", "erro", "concluida"])

        return Response(AnaliseDetalheSerializer(analise).data)

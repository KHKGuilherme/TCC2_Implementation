"""
Os endpoints da API.
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from frente2_predicao import prever
from frente2_predicao import repositorio as acesso

from . import fila
from .models import Analise
from .serializers import (AnaliseDetalheSerializer, AnaliseResumoSerializer,
                          PedidoSerializer)

RECENTES = 8


# =============================================================
# Limite de Pedidos
# -------------------------------------------------------------
# Quantas análises novas um mesmo endereço pode pedir por hora
# =============================================================
class LimiteDePedidos(AnonRateThrottle):
    scope = "pedidos"


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
            modelo = prever.descrever_modelo()
        except prever.ErroDeAnalise as erro:
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
                "commits_avaliados": avaliados,
            },
        })


# =============================================================
# Analises
# -------------------------------------------------------------
# Lista as recentes e recebe pedidos novos
# =============================================================
class AnalisesView(APIView):
    # =============================================================
    # Get Throttles
    # -------------------------------------------------------------
    # Limita só os pedidos novos, por endereço de origem
    # =============================================================
    def get_throttles(self):
        return [LimiteDePedidos()] if self.request.method == "POST" else []

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
            repositorio, ramo_da_url = acesso.interpretar_endereco(
                pedido.validated_data["endereco"])
            ramo = pedido.validated_data.get("ramo") or ramo_da_url or ""

            acesso.conferir_tamanho(repositorio)
            commit = acesso.commit_remoto(repositorio, ramo or None)
        except prever.ErroDeAnalise as erro:
            return Response({"erro": str(erro)},
                            status=status.HTTP_400_BAD_REQUEST)

        mesmo_repo = Q(repositorio__iexact=repositorio)
        if ramo:
            mesmo_repo &= Q(ramo=ramo)

        if commit:
            pronta = Analise.objects.filter(
                mesmo_repo, commit=commit,
                status=Analise.Status.CONCLUIDA).first()
            if pronta and (pronta.resultado or {}).get("modelo", {}).get(
                    "versao") == prever.carregar_modelo()["versao"]:
                return Response({"id": pronta.id, "reaproveitada": True},
                                status=status.HTTP_200_OK)

        andamento = Analise.objects.filter(
            mesmo_repo, status__in=[Analise.Status.NA_FILA,
                                    Analise.Status.RODANDO]).first()
        if andamento and fila.esta_ativa(andamento.id):
            return Response({"id": andamento.id, "reaproveitada": True},
                            status=status.HTTP_202_ACCEPTED)

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

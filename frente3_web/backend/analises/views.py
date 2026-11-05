# frente3_web\backend\analises\views.py
"""
Os endpoints da API.

  GET  /api/modelo/          o modelo em uso e números gerais
  GET  /api/analises/        análises concluídas recentes
  POST /api/analises/        pede uma análise {endereco, ramo?}
  GET  /api/analises/<id>/   progresso, e o resultado quando pronto
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from frente2_predicao import prever

from . import fila
from .models import Analise
from .serializers import (AnaliseDetalheSerializer, AnaliseResumoSerializer,
                          PedidoSerializer)

# Quantas análises a lista de recentes mostra
RECENTES = 8


# =============================================================
# Modelo
# -------------------------------------------------------------
# O que está treinado, e quanto já foi analisado
# =============================================================
class ModeloView(APIView):

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
                "arquivos_avaliados": avaliados,
            },
        })


# =============================================================
# Analises
# -------------------------------------------------------------
# Lista as recentes e recebe pedidos novos
# =============================================================
class AnalisesView(APIView):

    def get(self, request):
        # Uma por repositório, a mais nova, para a lista não ficar
        # tomada por várias análises do mesmo projeto
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

    def post(self, request):
        pedido = PedidoSerializer(data=request.data)
        pedido.is_valid(raise_exception=True)

        try:
            repositorio, ramo_da_url = prever.interpretar_endereco(
                pedido.validated_data["endereco"])
            ramo = pedido.validated_data.get("ramo") or ramo_da_url or ""

            # Barato, um segundo: pergunta ao GitHub o commit atual
            # sem clonar. Também já recusa repositório inexistente
            # antes de ocupar a fila.
            commit = prever.commit_remoto(repositorio, ramo or None)
        except prever.ErroDeAnalise as erro:
            return Response({"erro": str(erro)},
                            status=status.HTTP_400_BAD_REQUEST)

        mesmo_repo = Q(repositorio__iexact=repositorio)
        if ramo:
            mesmo_repo &= Q(ramo=ramo)

        # O mesmo commit já analisado dá o mesmo resultado: devolve
        # o pronto em vez de refazer minutos de trabalho
        if commit:
            pronta = Analise.objects.filter(
                mesmo_repo, commit=commit,
                status=Analise.Status.CONCLUIDA).first()
            # Análise gravada antes da revisão por commit tem outra nota
            if pronta and "revisao" in (pronta.resultado or {}):
                return Response({"id": pronta.id, "reaproveitada": True},
                                status=status.HTTP_200_OK)

        # Pedido repetido enquanto a primeira ainda roda
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

    def get(self, request, identificador):
        analise = get_object_or_404(Analise, pk=identificador)

        # Pendente no banco e ausente da fila: o servidor reiniciou
        # no meio. Sem isto a tela esperaria para sempre.
        if analise.pendente and not fila.esta_ativa(analise.id):
            analise.status = Analise.Status.ERRO
            analise.erro = ("A análise foi interrompida porque o servidor "
                            "reiniciou. Peça de novo.")
            analise.concluida = timezone.now()
            analise.save(update_fields=["status", "erro", "concluida"])

        return Response(AnaliseDetalheSerializer(analise).data)
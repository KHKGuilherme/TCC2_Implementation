# frente3_web\backend\analises\fila.py
"""
Roda as análises em segundo plano, uma de cada vez.

Uma análise leva de segundos a vários minutos, e um pedido HTTP não
pode ficar aberto esse tempo todo. O POST só registra o pedido e
devolve; o trabalho acontece numa thread daqui, que vai escrevendo o
progresso no banco, e a tela consulta o banco a cada segundo.

Thread em vez de Celery de propósito: no Windows, Celery pede Redis
e mais um processo aberto, e para um uso de TCC a thread basta. O
limite é que a fila vive na memória do runserver — se ele reiniciar,
a análise em andamento se perde, e a view marca isso como erro.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import close_old_connections, connection
from django.utils import timezone

from frente2_predicao import prever

from .models import Analise

log = logging.getLogger("analises")

_executor = ThreadPoolExecutor(max_workers=settings.ANALISES_SIMULTANEAS,
                               thread_name_prefix="analise")
_ativas: set[str] = set()
_trava = threading.Lock()

# Intervalo mínimo entre duas gravações de progresso. Gravar a cada
# arquivo medido seria milhares de escritas por análise.
INTERVALO_DE_PROGRESSO = 0.7


# =============================================================
# Enfileirar
# -------------------------------------------------------------
# Põe uma análise para rodar assim que houver vaga
# =============================================================
def enfileirar(analise: Analise) -> None:
    with _trava:
        # Fila vazia quer dizer nenhum clone em uso: o que estiver
        # em clones/web sobrou de um servidor derrubado no meio
        if not _ativas:
            prever.limpar_clones_orfaos()
        _ativas.add(str(analise.id))

    _executor.submit(executar, str(analise.id))


# =============================================================
# Esta Ativa
# -------------------------------------------------------------
# Se a análise está na fila DESTE processo
# =============================================================
def esta_ativa(identificador) -> bool:
    with _trava:
        return str(identificador) in _ativas


# =============================================================
# Executar
# -------------------------------------------------------------
# O trabalho de uma análise, dentro da thread
# =============================================================
def executar(identificador: str) -> None:
    close_old_connections()
    consulta = Analise.objects.filter(pk=identificador)
    ultimo_aviso = [0.0]

    def progresso(etapa: str, fracao: float, mensagem: str) -> None:
        agora = time.monotonic()
        if agora - ultimo_aviso[0] < INTERVALO_DE_PROGRESSO and fracao < 1:
            return

        ultimo_aviso[0] = agora
        consulta.update(etapa=etapa, progresso=round(fracao, 4),
                        mensagem=mensagem[:200])

    try:
        analise = consulta.get()
        consulta.update(status=Analise.Status.RODANDO, etapa="clonando",
                        mensagem="começando")

        resultado = prever.analisar(analise.repositorio,
                                    analise.ramo or None, progresso)

        consulta.update(status=Analise.Status.CONCLUIDA,
                        resultado=resultado,
                        resumo=resultado["resumo"],
                        commit=resultado["commit"],
                        ramo=resultado["ramo"] or "",
                        progresso=1.0, etapa="pronto", mensagem="",
                        concluida=timezone.now())

        log.info("análise %s de %s concluída em %.0f s", identificador,
                 analise.repositorio, resultado["duracao_s"])

    except prever.ErroDeAnalise as erro:
        consulta.update(status=Analise.Status.ERRO, erro=str(erro),
                        concluida=timezone.now())

    except Exception as erro:
        # Erro inesperado: o detalhe vai para o terminal do
        # servidor, e a tela recebe uma linha só
        log.exception("análise %s falhou", identificador)
        consulta.update(status=Analise.Status.ERRO,
                        erro=f"Erro interno: {type(erro).__name__}: "
                             f"{str(erro)[:300]}",
                        concluida=timezone.now())

    finally:
        with _trava:
            _ativas.discard(identificador)
        connection.close()
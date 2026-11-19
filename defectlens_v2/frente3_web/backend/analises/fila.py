"""
Roda as análises em segundo plano, uma de cada vez.

A fila vive na memória deste processo: o servidor precisa rodar com UM
processo (por exemplo, gunicorn --workers 1 --threads 8). Com mais de um,
um processo não enxerga a fila do outro e marca a análise como interrompida.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import close_old_connections, connection
from django.utils import timezone

from frente2_predicao import prever
from frente2_predicao import repositorio as acesso

from .models import Analise

log = logging.getLogger("analises")

_executor = ThreadPoolExecutor(max_workers=settings.ANALISES_SIMULTANEAS,
                               thread_name_prefix="analise")
_ativas: set[str] = set()
_trava = threading.Lock()

INTERVALO_DE_PROGRESSO = 0.7


# =============================================================
# Enfileirar
# -------------------------------------------------------------
# Põe uma análise para rodar assim que houver vaga
# =============================================================
def enfileirar(analise: Analise) -> None:
    with _trava:
        if not _ativas:
            acesso.limpar_clones_orfaos()
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
        consulta.update(status=Analise.Status.RODANDO, etapa="conferindo",
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
        log.exception("análise %s falhou", identificador)
        consulta.update(status=Analise.Status.ERRO,
                        erro=f"Erro interno: {type(erro).__name__}: "
                             f"{str(erro)[:300]}",
                        concluida=timezone.now())

    finally:
        with _trava:
            _ativas.discard(identificador)
        connection.close()

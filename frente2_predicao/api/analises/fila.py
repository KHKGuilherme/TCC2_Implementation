import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import close_old_connections, connection
from django.utils import timezone

from predicao import analisar, repositorio
from predicao.erros import ErroDeAnalise

from .models import Analise

log = logging.getLogger("analises")

_executor = ThreadPoolExecutor(max_workers=settings.ANALISES_SIMULTANEAS,
                               thread_name_prefix="analise")
_ativas: set[str] = set()
_trava = threading.Lock()

INTERVALO_DE_PROGRESSO = 0.7


def enfileirar(analise: Analise) -> None:
    with _trava:
        if not _ativas:
            repositorio.limpar_clones_orfaos()
        _ativas.add(str(analise.id))

    _executor.submit(executar, str(analise.id))


def esta_ativa(identificador) -> bool:
    with _trava:
        return str(identificador) in _ativas


def tamanho() -> int:
    with _trava:
        return len(_ativas)


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

        resultado = analisar.analisar(analise.repositorio,
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

    except ErroDeAnalise as erro:
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

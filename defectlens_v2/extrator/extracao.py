"""
Percorre o histórico de um clone uma vez e devolve, por commit, as
medidas do commit e o retrato de histórico de cada .py que ele alterou.
"""

import sys
from collections import Counter, deque
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

from . import features, historico_git, metricas_commit, metricas_historico

COLUNAS_DE_EXPERIENCIA = ["autor_commits", "autor_recentes",
                          "autor_no_subsistema"]

AVISAR_A_CADA = 500


# =============================================================
# EXPERIÊNCIA DO AUTOR (PILOTO)
# =============================================================


# =============================================================
# Experiencia Vazia
# -------------------------------------------------------------
# Cria os contadores de experiência dos autores
# =============================================================
def experiencia_vazia() -> dict:
    return {"total": Counter(), "recentes": {}, "subsistema": Counter()}


# =============================================================
# Medir Experiencia
# -------------------------------------------------------------
# Experiência do autor antes do commit, e atualiza os contadores
# =============================================================
def medir_experiencia(experiencia: dict, commit) -> dict:
    autor = commit.autor
    limite = (commit.instante - config.JANELA_RECENTE_DIAS
              * metricas_historico.SEGUNDOS_POR_DIA)
    recentes = experiencia["recentes"].setdefault(autor, deque())

    while recentes and recentes[0] < limite:
        recentes.popleft()

    topos = {(metricas_historico.normalizar(m.caminho or m.caminho_antigo)
              or "").split("/", 1)[0] for m in commit.mudancas}
    no_subsistema = [experiencia["subsistema"][(autor, t)] for t in topos]

    medidas = {
        "autor_commits": experiencia["total"][autor],
        "autor_recentes": len(recentes),
        "autor_no_subsistema": (sum(no_subsistema) / len(no_subsistema)
                                if no_subsistema else 0.0),
    }

    experiencia["total"][autor] += 1
    recentes.append(commit.instante)
    for topo in topos:
        experiencia["subsistema"][(autor, topo)] += 1

    return medidas


# =============================================================
# EXTRAÇÃO
# =============================================================


# =============================================================
# Retratar Commit
# -------------------------------------------------------------
# O retrato de histórico de cada .py de código alterado pelo commit
# =============================================================
def retratar_commit(acumulado: dict, commit, tocados: list[str]) -> list[dict]:
    linhas = {}
    for mudanca in commit.mudancas:
        caminho = metricas_historico.normalizar(mudanca.caminho)
        if caminho:
            anterior = linhas.get(caminho, (0, 0))
            linhas[caminho] = (anterior[0] + mudanca.adicionadas,
                               anterior[1] + mudanca.removidas)

    retratos = []
    for caminho in tocados:
        if not features.arquivo_no_escopo(caminho):
            continue

        adicionadas, removidas = linhas.get(caminho, (0, 0))
        retratos.append({
            "commit": commit.codigo,
            "arquivo": caminho,
            "arquivo_adicionadas": adicionadas,
            "arquivo_removidas": removidas,
            **metricas_historico.resumir_registro(acumulado[caminho],
                                                  commit.instante),
        })

    return retratos


# =============================================================
# Extrair
# -------------------------------------------------------------
# Uma travessia: medidas e retratos dos commits pedidos
# =============================================================
def extrair(pasta: Path, repositorio: str, ultimos: int | None = None,
            avisar=None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    total = historico_git.contar_commits(pasta)
    acumulado = {}
    experiencia = experiencia_vazia()
    guardados = deque(maxlen=ultimos)
    lidos = 0
    referencia = 0.0

    for commit in historico_git.percorrer_commits(pasta):
        tocados = metricas_historico.aplicar_commit(acumulado, commit)
        vivencia = medir_experiencia(experiencia, commit)
        lidos += 1
        referencia = max(referencia, commit.instante)

        if commit.mudancas:
            guardados.append((
                {"commit": commit.codigo,
                 "instante": commit.instante,
                 "autor": commit.nome_do_autor,
                 "assunto": commit.assunto,
                 **metricas_commit.medir_commit(commit),
                 **vivencia},
                retratar_commit(acumulado, commit, tocados)))

        if avisar and lidos % AVISAR_A_CADA == 0:
            avisar(lidos / max(total, 1), f"{lidos} de {total} commits")

    if avisar:
        avisar(1.0, f"{lidos} de {total} commits")

    medidas = pd.DataFrame([m for m, _ in guardados])
    retratos = pd.DataFrame([r for _, lista in guardados for r in lista])

    for tabela in (medidas, retratos):
        tabela.insert(0, "repositorio", repositorio)

    return medidas, retratos, {"commits": lidos, "referencia": referencia}

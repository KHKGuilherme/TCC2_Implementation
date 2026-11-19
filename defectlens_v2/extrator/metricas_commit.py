"""
Mede o tamanho e a dispersão de um commit, com as mesmas regras do
dataset original (todos os arquivos do commit, de qualquer tipo).
"""

import math

from .metricas_historico import normalizar


# =============================================================
# Entropia
# -------------------------------------------------------------
# Quão espalhada a mudança está entre os arquivos, de 0 a 1
# =============================================================
def entropia(pesos: list[int]) -> float:
    total = sum(pesos)
    quantidade = len(pesos)

    if total <= 0 or quantidade <= 1:
        return 0.0

    soma = sum(p / total * math.log2(p / total) for p in pesos if p > 0)
    return -soma / math.log2(quantidade)


# =============================================================
# Medir Commit
# -------------------------------------------------------------
# As seis medidas de tamanho e dispersão de um commit
# =============================================================
def medir_commit(commit) -> dict:
    mudancas = commit.mudancas
    caminhos = [normalizar(m.caminho or m.caminho_antigo) or ""
                for m in mudancas]
    pastas = {c.rsplit("/", 1)[0] if "/" in c else "" for c in caminhos}
    topos = {c.split("/", 1)[0] for c in caminhos}

    adicionadas = [m.adicionadas for m in mudancas]
    removidas = [m.removidas for m in mudancas]

    return {
        "commit_arquivos":    len(mudancas),
        "commit_pastas":      len(pastas),
        "commit_topos":       len(topos),
        "commit_adicionadas": sum(adicionadas),
        "commit_removidas":   sum(removidas),
        "commit_entropia":    round(entropia(
            [a + r for a, r in zip(adicionadas, removidas)]), 6),
    }

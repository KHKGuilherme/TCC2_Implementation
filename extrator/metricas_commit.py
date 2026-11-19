"""
Mede o tamanho e a dispersão de um commit.
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
# As colunas de features.COLUNAS_COMMIT para um commit
# =============================================================
def medir_commit(commit) -> dict:
    mudancas = commit.modified_files
    caminhos = [normalizar(m.new_path or m.old_path) or "" for m in mudancas]
    pastas = {c.rsplit("/", 1)[0] if "/" in c else "" for c in caminhos}
    topos = {c.split("/", 1)[0] for c in caminhos}

    adicionadas = [m.added_lines or 0 for m in mudancas]
    removidas = [m.deleted_lines or 0 for m in mudancas]

    return {
        "commit_arquivos":    len(mudancas),
        "commit_pastas":      len(pastas),
        "commit_topos":       len(topos),
        "commit_adicionadas": sum(adicionadas),
        "commit_removidas":   sum(removidas),
        "commit_entropia":    round(entropia(
            [a + r for a, r in zip(adicionadas, removidas)]), 6),
    }


# =============================================================
# Registrar Ultimo Commit
# -------------------------------------------------------------
# Anota este commit como o último de cada .py que ele toca
# =============================================================
def registrar_ultimo_commit(ultimos: dict[str, dict], commit) -> None:
    caminhos = {normalizar(m.new_path or m.old_path)
                for m in commit.modified_files}
    caminhos = {c for c in caminhos if c and c.endswith(".py")}

    if not caminhos:
        return

    resumo = {"hash": commit.hash,
              "instante": commit.committer_date.timestamp(),
              **medir_commit(commit)}

    for caminho in caminhos:
        ultimos[caminho] = resumo

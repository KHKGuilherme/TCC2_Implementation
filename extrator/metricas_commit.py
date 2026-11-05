"""
Mede o tamanho e a dispersão de um commit.

O rótulo do Defectors é do commit: todo arquivo que ganhou linhas num
commit marcado herda a marca. Por isso estas medidas descrevem o commit
inteiro, e todos os arquivos dele recebem os mesmos valores.

Contam todos os arquivos do commit, e não só os .py: um commit que
mexe em 30 arquivos de configuração e em um .py continua sendo grande.

Só usam o que existe no próprio commit, então nenhuma olha para frente.
As linhas adicionadas ao arquivo ficam de fora de propósito: elas
repetem a regra do rótulo, e o modelo pareceria acertar sem aprender.

As três frentes usam estas contas sem cópia: a Frente 1 mede os commits
do dataset, e a Frente 2, o último commit de cada arquivo.
"""

import math

from .metricas_historico import normalizar


# =============================================================
# Entropia
# -------------------------------------------------------------
# Quão espalhada a mudança está entre os arquivos, de 0 a 1
# =============================================================
def entropia(pesos: list[int]) -> float:
    # Normalizada pelo número de arquivos para comparar commits de
    # tamanhos diferentes. Com um arquivo só, não há o que espalhar.
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
    # Numa variável porque, no PyDriller, modified_files recalcula
    # o diff a cada acesso
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
    # Commit de merge não traz arquivos, então não muda o que está
    # anotado. A renomeação aparece aqui com o caminho novo.
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

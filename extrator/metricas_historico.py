"""
Mede as 3 features que descrevem como um arquivo .py evoluiu: quantas vezes foi alterado, por quantas pessoas diferentes, e quantas linhas mudaram no total.
"""

from pathlib import Path

from pydriller import Repository
from pydriller.domain.commit import ModificationType


# =============================================================
# normalizar
# -------------------------------------------------------------
# Deixa todo caminho com barra normal
# =============================================================
def normalizar(caminho: str | None) -> str | None:
    if caminho is None:
        return None

    return caminho.replace("\\", "/")


# =============================================================
# Acumulador Vazio
# -------------------------------------------------------------
# Cria o registro inicial de um arquivo
# =============================================================
def acumulador_vazio() -> dict:
    return {"revisoes": 0, "autores": set(), "churn": 0}


# =============================================================
# Transferir
# -------------------------------------------------------------
# Move o histórico de um caminho para outro
# =============================================================
def transferir(destino: dict, origem: dict) -> None:
    destino["revisoes"] += origem["revisoes"]
    destino["autores"] |= origem["autores"]
    destino["churn"] += origem["churn"]


# =============================================================
# Aplicar Commit
# -------------------------------------------------------------
# Incorpora um commit ao acumulador
# =============================================================
def aplicar_commit(acumulado: dict, commit) -> None:

    for mudanca in commit.modified_files:
        caminho = normalizar(mudanca.new_path or mudanca.old_path)
        caminho_antigo = normalizar(mudanca.old_path)

        if not caminho or not caminho.endswith(".py"):
            continue

        if (mudanca.change_type == ModificationType.RENAME
                and caminho_antigo
                and caminho_antigo in acumulado):
            destino = acumulado.setdefault(caminho, acumulador_vazio())
            transferir(destino, acumulado.pop(caminho_antigo))

        registro = acumulado.setdefault(caminho, acumulador_vazio())
        registro["revisoes"] += 1
        registro["autores"].add(commit.author.email)
        registro["churn"] += ((mudanca.added_lines or 0)
                              + (mudanca.deleted_lines or 0))


# =============================================================
# Fotografar
# -------------------------------------------------------------
# Congela o acumulador dos arquivos pedidos
# =============================================================
def fotografar(acumulado: dict, caminhos: set[str]) -> dict:

    resultado = {}

    for pedido in caminhos:
        registro = acumulado.get(normalizar(pedido))
        if registro is None:
            continue

        caminho = pedido
        resultado[caminho] = {
            "revisoes": registro["revisoes"],
            "autores":  len(registro["autores"]),
            "churn":    registro["churn"],
        }

    return resultado


# =============================================================
# Medir nos commits
# -------------------------------------------------------------
# Travessia única com várias fotografias
# =============================================================
def medir_nos_commits(pasta_repo: Path,
                      caminhos_por_commit: dict[str, set[str]],
                      ao_fotografar=None) -> dict[str, dict]:
    acumulado = {}
    fotografias = {}
    pendentes = set(caminhos_por_commit)

    for commit in Repository(str(pasta_repo)).traverse_commits():
        aplicar_commit(acumulado, commit)

        if commit.hash in pendentes:
            fotografias[commit.hash] = fotografar(
                acumulado, caminhos_por_commit[commit.hash])
            pendentes.discard(commit.hash)

            if ao_fotografar:
                ao_fotografar(len(fotografias), len(pendentes))

            if not pendentes:
                break

    return fotografias


# =============================================================
# Medir Estado Atual
# -------------------------------------------------------------
# Histórico até o último commit
# =============================================================
def medir_estado_atual(pasta_repo: Path) -> dict[str, dict]:
    acumulado = {}

    for commit in Repository(str(pasta_repo)).traverse_commits():
        aplicar_commit(acumulado, commit)

    return fotografar(acumulado, set(acumulado))
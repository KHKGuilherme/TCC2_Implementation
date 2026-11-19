"""
testar_caminhos.py
==================

Uso:
    python testes/testar_caminhos.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extrator import metricas_historico
from pydriller.domain.commit import ModificationType


# =============================================================
# MudancaFalsa — imita um arquivo alterado do PyDriller
# -------------------------------------------------------------
# Reproduz os campos de ModifiedFile que o extrator usa
# =============================================================
class MudancaFalsa:
    """Reproduz os campos de ModifiedFile que o extrator usa."""

    def __init__(self, new_path, old_path=None,
                 change_type=ModificationType.MODIFY,
                 added_lines=10, deleted_lines=5):
        self.new_path = new_path
        self.old_path = old_path if old_path is not None else new_path
        self.change_type = change_type
        self.added_lines = added_lines
        self.deleted_lines = deleted_lines


# =============================================================
# AutorFalso / CommitFalso — imitam um commit do PyDriller
# -------------------------------------------------------------
# Autor de commit montado à mão
# =============================================================
class AutorFalso:
    def __init__(self, email):
        self.email = email


class CommitFalso:
    def __init__(self, hash_commit, email, mudancas):
        self.hash = hash_commit
        self.author = AutorFalso(email)
        self.modified_files = mudancas


# =============================================================
# construir_historico — roda o acumulador sobre commits falsos
# -------------------------------------------------------------
# Acumula três commits usando o separador indicado
# =============================================================
def construir_historico(separador: str) -> dict:
    caminho = f"pacote{separador}modulo.py"
    acumulado = {}

    commits = [
        CommitFalso("aaa", "ana@exemplo.com", [MudancaFalsa(caminho)]),
        CommitFalso("bbb", "bia@exemplo.com", [MudancaFalsa(caminho)]),
        CommitFalso("ccc", "ana@exemplo.com", [MudancaFalsa(caminho)]),
    ]

    for commit in commits:
        metricas_historico.aplicar_commit(acumulado, commit)

    return acumulado


# =============================================================
# testar_barra_invertida — Windows e Linux dão o mesmo resultado
# -------------------------------------------------------------
# Busca por barra normal funciona nas duas convenções
# =============================================================
def testar_barra_invertida() -> None:
    esperado = {"revisoes": 3, "autores": 2, "churn": 45}
    pedido = {"pacote/modulo.py"}

    for nome, separador in [("Linux", "/"), ("Windows", "\\")]:
        acumulado = construir_historico(separador)
        obtido = metricas_historico.fotografar(acumulado, pedido)

        assert obtido, (
            f"{nome}: nada encontrado para 'pacote/modulo.py'. "
            f"As chaves do acumulado são {list(acumulado)}"
        )
        assert obtido["pacote/modulo.py"] == esperado, (
            f"{nome}: esperado {esperado}, obtido "
            f"{obtido['pacote/modulo.py']}"
        )
        print(f"  ok  caminho com barra de {nome:<8} -> {esperado}")


# =============================================================
# testar_renomeacao — o histórico acompanha a mudança de pasta
# -------------------------------------------------------------
# Arquivo que troca de pasta mantém o histórico somado
# =============================================================
def testar_renomeacao() -> None:
    for nome, sep in [("Linux", "/"), ("Windows", "\\")]:
        antigo = f"pacote{sep}modulo.py"
        novo = f"src{sep}pacote{sep}modulo.py"
        acumulado = {}

        commits = [
            CommitFalso("aaa", "ana@exemplo.com", [MudancaFalsa(antigo)]),
            CommitFalso("bbb", "bia@exemplo.com", [MudancaFalsa(antigo)]),
            CommitFalso("ccc", "ana@exemplo.com",
                        [MudancaFalsa(novo, antigo,
                                      ModificationType.RENAME)]),
        ]

        for commit in commits:
            metricas_historico.aplicar_commit(acumulado, commit)

        obtido = metricas_historico.fotografar(
            acumulado, {"src/pacote/modulo.py"})

        assert obtido, (
            f"{nome}: o arquivo renomeado não foi encontrado. "
            f"Chaves: {list(acumulado)}"
        )

        medidas = obtido["src/pacote/modulo.py"]
        assert medidas["revisoes"] == 3, (
            f"{nome}: o histórico anterior à renomeação foi perdido. "
            f"Esperado 3 revisões, obtido {medidas['revisoes']}"
        )
        assert "pacote/modulo.py" not in acumulado, (
            f"{nome}: o caminho antigo continuou no acumulado"
        )
        print(f"  ok  renomeação com barra de {nome:<8} -> "
              f"{medidas['revisoes']} revisões somadas")


# =============================================================
# main — roda todos os testes
# -------------------------------------------------------------
# Executa os testes e informa o resultado
# =============================================================
def main() -> None:
    print("Testes de normalização de caminho\n")

    testar_barra_invertida()
    testar_renomeacao()

    print("\nTodos passaram.")


if __name__ == "__main__":
    main()

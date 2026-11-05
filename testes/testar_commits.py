"""
Confere as contas por commit das Frentes 1 e 2.

O rótulo do Defectors é do commit, então as métricas, o ranking por
commit e a lista de revisão precisam olhar para o commit. Um erro aqui
não quebra nada na execução, só muda os números, então vale travar com
um teste.

O teste usa commits montados à mão e não lê arquivo nenhum.

CMD -> python testes/testar_commits.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "frente1_treinamento"))

import config
import divisao
import treinar
from extrator import metricas_commit
from frente2_predicao import prever

DIA = 86400.0


# =============================================================
# Criar Commit
# -------------------------------------------------------------
# Um commit com (caminho, adicionadas, removidas) por arquivo
# =============================================================
def criar_commit(codigo: str, instante: float, mudancas: list[tuple]):
    return SimpleNamespace(
        hash=codigo,
        committer_date=datetime.fromtimestamp(instante, tz=timezone.utc),
        modified_files=[SimpleNamespace(new_path=c, old_path=c,
                                        added_lines=a, deleted_lines=r)
                        for c, a, r in mudancas])


# =============================================================
# Testar Medir Commit
# -------------------------------------------------------------
# Conta todos os tipos de arquivo, e a entropia fica entre 0 e 1
# =============================================================
def testar_medir_commit() -> None:
    medidas = metricas_commit.medir_commit(criar_commit("a", 0, [
        ("src/a/x.py", 5, 1), ("src/b/y.py", 5, 1), ("README.md", 2, 0)]))

    assert medidas["commit_arquivos"] == 3
    assert medidas["commit_pastas"] == 3
    assert medidas["commit_topos"] == 2
    assert medidas["commit_adicionadas"] == 12
    assert medidas["commit_removidas"] == 2
    assert 0 < medidas["commit_entropia"] < 1

    assert metricas_commit.entropia([7]) == 0
    assert metricas_commit.entropia([]) == 0
    assert metricas_commit.entropia([0, 0]) == 0
    assert abs(metricas_commit.entropia([4, 4]) - 1) < 1e-9

    print("ok  métricas do commit")


# =============================================================
# Testar Ultimo Commit
# -------------------------------------------------------------
# Vale o commit mais novo, e merge ou .md não mudam a anotação
# =============================================================
def testar_ultimo_commit() -> None:
    ultimos = {}
    metricas_commit.registrar_ultimo_commit(
        ultimos, criar_commit("velho", 10, [("a.py", 1, 0), ("b.py", 1, 0)]))
    metricas_commit.registrar_ultimo_commit(
        ultimos, criar_commit("novo", 20, [("a.py", 2, 0), ("c.md", 9, 0)]))
    metricas_commit.registrar_ultimo_commit(
        ultimos, criar_commit("merge", 30, []))

    assert ultimos["a.py"]["hash"] == "novo"
    assert ultimos["a.py"]["commit_arquivos"] == 2
    assert ultimos["b.py"]["hash"] == "velho"
    assert "c.md" not in ultimos

    print("ok  último commit de cada arquivo")


# =============================================================
# Testar Risco por Commit
# -------------------------------------------------------------
# Maior nota entre os arquivos, e defeito se algum foi marcado
# =============================================================
def testar_risco_por_commit() -> None:
    previsoes = pd.DataFrame(
        [("p", "c1", 0.2, 0), ("p", "c1", 0.8, 1), ("p", "c2", 0.5, 0)],
        columns=["repositorio", "commit", "probabilidade", "real"])
    risco = treinar.risco_por_commit(previsoes)

    assert risco["commit"].tolist() == ["c1", "c2"]
    assert risco["risco"].tolist() == [0.8, 0.5]
    assert risco["defeito"].tolist() == [1, 0]
    assert risco["arquivos"].tolist() == [2, 1]
    assert treinar.precisao_por_repositorio(risco, 0.5, "defeito") == 1.0

    print("ok  risco por commit")


# =============================================================
# Testar Divisao por Commit
# -------------------------------------------------------------
# Os arquivos de um commit nunca ficam separados
# =============================================================
def testar_divisao_por_commit() -> None:
    commits = np.repeat([f"c{i}" for i in range(40)], 3)
    dados = pd.DataFrame({"repositorio": "p", "commit": commits,
                          "arquivo": [f"f{i}.py" for i in range(120)]})
    particao = divisao.dividir_group_shuffle_split(dados)

    assert particao.groupby(dados["commit"]).nunique().max() == 1
    assert set(particao) == {"treino", "teste"}

    print("ok  divisão por commit")


# =============================================================
# Criar Ultimo
# -------------------------------------------------------------
# O que registrar_ultimo_commit anota, com valores fixos
# =============================================================
def criar_ultimo(codigo: str, instante: float) -> dict:
    return {"hash": codigo, "instante": instante, "commit_arquivos": 2,
            "commit_pastas": 1, "commit_topos": 1, "commit_adicionadas": 10,
            "commit_removidas": 3, "commit_entropia": 0.5}


# =============================================================
# Testar Lista de Revisao
# -------------------------------------------------------------
# Agrupa por commit, ordena por risco e tira os antigos
# =============================================================
def testar_lista_de_revisao() -> None:
    referencia = 1000 * DIA
    dentro = referencia - (config.JANELA_REVISAO_DIAS - 1) * DIA
    fora = referencia - (config.JANELA_REVISAO_DIAS + 1) * DIA
    ultimos = {
        "a.py": criar_ultimo("calmo", referencia),
        "b.py": criar_ultimo("agitado", dentro),
        "c.py": criar_ultimo("agitado", dentro),
        "d.py": criar_ultimo("antigo", fora),
    }
    notas = {"a.py": 0.4, "b.py": 0.6, "c.py": 0.7, "d.py": 0.9, "e.py": 0.8}

    revisao = prever.agrupar_commits(notas, ultimos, referencia)
    commits = revisao["commits"]

    assert [c["hash"] for c in commits] == ["agitado", "calmo"]
    assert commits[0]["risco"] == 0.7
    assert commits[0]["avaliados"] == ["c.py", "b.py"]
    assert commits[0]["adicionadas"] == 10
    assert revisao["recentes"] == 2
    assert revisao["fora_da_janela"] == 1

    print("ok  lista de revisão")


# =============================================================
# Main
# =============================================================
def main() -> None:
    testar_medir_commit()
    testar_ultimo_commit()
    testar_risco_por_commit()
    testar_divisao_por_commit()
    testar_lista_de_revisao()

    print("\nTodos passaram.")


if __name__ == "__main__":
    main()

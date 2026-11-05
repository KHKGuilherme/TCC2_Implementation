"""
Confere o ranking por arquivo da Frente 1.

O rótulo de cada arquivo vem do retrato mais recente. Se voltar a
ser "teve defeito em algum commit", ele cresce com o número de
retratos e a precisão no topo chega a 100% sem medir o modelo. O
erro não quebra nada na execução, só melhora o número, então vale
travar com um teste.

O teste usa previsões montadas à mão e não lê arquivo nenhum.

CMD -> python testes/testar_ranking.py
"""

import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "frente1_treinamento"))

import treinar


# =============================================================
# Montar Previsoes
# -------------------------------------------------------------
# Transforma tuplas na tabela que risco_por_arquivo recebe
# =============================================================
def montar_previsoes(linhas: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(linhas, columns=["repositorio", "arquivo", "idade_dias",
                                         "revisoes", "probabilidade", "real"])


# =============================================================
# Testar Rotulo Mais Recente
# -------------------------------------------------------------
# Defeito antigo não marca o arquivo, e a ordem das linhas não importa
# =============================================================
def testar_rotulo_mais_recente() -> None:
    # O retrato mais recente é a linha do meio, de propósito
    risco = treinar.risco_por_arquivo(montar_previsoes([
        ("p", "a.py", 10, 1, 0.9, 1),
        ("p", "a.py", 30, 3, 0.2, 0),
        ("p", "a.py", 20, 2, 0.8, 1),
    ]))

    linha = risco.iloc[0]
    assert linha["retratos"] == 3
    assert linha["commits_com_defeito"] == 2
    assert linha["defeito_atual"] == 0
    assert linha["risco_atual"] == 0.2
    print("  ok: defeito antigo não marca o arquivo")


# =============================================================
# Testar Desempate
# -------------------------------------------------------------
# Dois commits no mesmo dia são separados por revisoes
# =============================================================
def testar_desempate() -> None:
    risco = treinar.risco_por_arquivo(montar_previsoes([
        ("p", "a.py", 5, 8, 0.7, 1),
        ("p", "a.py", 5, 2, 0.1, 0),
    ]))

    assert risco.iloc[0]["defeito_atual"] == 1
    assert risco.iloc[0]["risco_atual"] == 0.7
    print("  ok: revisoes desempata commits do mesmo dia")


# =============================================================
# Testar Ordem do Ranking
# -------------------------------------------------------------
# A nota é a do retrato mais recente, e não a média
# =============================================================
def testar_ordem_do_ranking() -> None:
    risco = treinar.risco_por_arquivo(montar_previsoes([
        ("p", "media_alta.py", 1, 1, 0.9, 1),
        ("p", "media_alta.py", 2, 2, 0.3, 0),
        ("p", "atual_alta.py", 1, 1, 0.1, 0),
        ("p", "atual_alta.py", 2, 2, 0.6, 1),
    ]))

    assert list(risco["arquivo"]) == ["atual_alta.py", "media_alta.py"]
    print("  ok: o ranking segue a nota atual")


# =============================================================
# Testar Precisao por Repositorio
# -------------------------------------------------------------
# Cada projeto contribui com o seu próprio topo
# =============================================================
def testar_precisao_por_repositorio() -> None:
    risco = treinar.risco_por_arquivo(montar_previsoes(
        [("grande", f"{i}.py", 1, 1, 0.9 - i / 100, int(i < 2))
         for i in range(10)]
        + [("pequeno", "x.py", 1, 1, 0.1, 0)]))

    # 1 de 1 em 'grande' acerta; o de 'pequeno' entra pelo mínimo
    # de um arquivo por projeto e erra
    assert treinar.precisao_por_repositorio(risco, 0.1) == 0.5
    print("  ok: precisão somada por repositório")


# =============================================================
# Testar So Maduros
# -------------------------------------------------------------
# Os retratos recentes saem, e a tupla vazia desliga o filtro
# =============================================================
def testar_so_maduros() -> None:
    dados = pd.DataFrame({
        treinar.features.COLUNA_PARTICAO_DEFECTORS: ["train", "val", "test"]})

    original = treinar.config.PARTICOES_MADURAS
    try:
        treinar.config.PARTICOES_MADURAS = ("train",)
        assert len(treinar.so_maduros(dados)) == 1

        treinar.config.PARTICOES_MADURAS = ()
        assert len(treinar.so_maduros(dados)) == 3
    finally:
        treinar.config.PARTICOES_MADURAS = original

    print("  ok: retratos recentes ficam de fora")


# =============================================================
# Main
# -------------------------------------------------------------
# Roda todos os testes
# =============================================================
def main() -> None:
    print("Testes do ranking por arquivo\n")

    testar_rotulo_mais_recente()
    testar_desempate()
    testar_ordem_do_ranking()
    testar_precisao_por_repositorio()
    testar_so_maduros()

    print("\nTodos passaram.")


if __name__ == "__main__":
    main()

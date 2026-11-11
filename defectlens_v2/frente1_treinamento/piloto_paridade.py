"""
Frente 1, piloto — clona poucos repositórios pequenos para conferir duas
coisas antes de qualquer nova medição dos 24:
  1. paridade: o extrator da Frente 2 reproduz as features do treino?
  2. experiência do autor (EXP, REXP, SEXP de Kamei): melhora o modelo?

CMD -> python defectlens_v2/frente1_treinamento/piloto_paridade.py
       retomável: pula os repositórios já extraídos em resultados/piloto
"""

import os
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupKFold

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
import metricas_avaliacao
from extrator import extracao, features
from frente2_predicao import repositorio as acesso

TOLERANCIA = 1e-6
DOBRAS = 5


# =============================================================
# EXTRAÇÃO
# =============================================================


# =============================================================
# Gravar CSV Atomico
# -------------------------------------------------------------
# Grava de modo que um reinício nunca deixe o CSV pela metade
# =============================================================
def gravar_csv_atomico(tabela: pd.DataFrame, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(destino.name + ".tmp")
    tabela.to_csv(temporario, index=False)
    os.replace(temporario, destino)


# =============================================================
# Extrair Repositorio
# -------------------------------------------------------------
# Clona, extrai todos os commits com o extrator da Frente 2 e apaga
# =============================================================
def extrair_repositorio(nome: str, endereco: str,
                        commits_do_dataset: set[str]) -> pd.DataFrame:
    destino = config.PASTA_PILOTO / f"{nome}__retratos.csv"

    if destino.exists():
        return pd.read_csv(destino)

    pasta = config.PASTA_CLONES / "piloto" / nome
    acesso.apagar_pasta(pasta)
    pasta.parent.mkdir(parents=True, exist_ok=True)
    inicio = time.time()

    try:
        acesso.clonar(endereco, None, pasta)
        medidas, retratos, info = extracao.extrair(pasta, nome)
    finally:
        acesso.apagar_pasta(pasta)

    tabela = features.montar_retratos(medidas, retratos)
    tabela = tabela[tabela["commit"].isin(commits_do_dataset)]
    gravar_csv_atomico(tabela, destino)

    print(f"  {nome}: {info['commits']} commits lidos, {len(tabela)} retratos "
          f"de commits do dataset, {time.time() - inicio:.0f} s", flush=True)
    return tabela


# =============================================================
# PARIDADE
# =============================================================


# =============================================================
# Comparar Retratos
# -------------------------------------------------------------
# Compara, feature a feature, o extrator novo com o dataset de treino
# =============================================================
def comparar_retratos(nome: str, treino: pd.DataFrame,
                      piloto: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    chave = ["commit", "arquivo"]
    juntos = treino.merge(piloto, on=chave, how="outer",
                          suffixes=("_treino", "_git"), indicator=True)
    comuns = juntos[juntos["_merge"] == "both"]

    cobertura = {
        "repositorio": nome,
        "commits_no_dataset": int(treino["commit"].nunique()),
        "commits_achados": int(piloto["commit"].nunique()),
        "retratos_no_dataset": int(len(treino)),
        "retratos_em_comum": int(len(comuns)),
        "so_no_dataset": int((juntos["_merge"] == "left_only").sum()),
        "so_no_git": int((juntos["_merge"] == "right_only").sum()),
    }

    linhas = []
    for coluna in features.FEATURES_MODELO:
        a = comuns[f"{coluna}_treino"].to_numpy(dtype=float)
        b = comuns[f"{coluna}_git"].to_numpy(dtype=float)
        iguais = np.isclose(a, b, rtol=1e-4, atol=TOLERANCIA,
                            equal_nan=True)
        constante = len(set(a)) < 2 or len(set(b)) < 2

        linhas.append({
            "repositorio": nome, "feature": coluna,
            "grupo": features.grupo_da_feature(coluna),
            "iguais": float(iguais.mean()) if len(a) else float("nan"),
            "spearman": float("nan") if constante
                        else float(stats.spearmanr(a, b).statistic),
        })

    return cobertura, pd.DataFrame(linhas)


# =============================================================
# Comparar Notas
# -------------------------------------------------------------
# A nota do modelo final com as features do treino e as do extrator
# =============================================================
def comparar_notas(nome: str, treino: pd.DataFrame,
                   piloto: pd.DataFrame) -> dict:
    if not config.ARQUIVO_MODELO.exists():
        return {}

    pacote = joblib.load(config.ARQUIVO_MODELO)
    notas = {}

    for origem, tabela in (("treino", treino), ("git", piloto)):
        matriz = tabela[pacote["features"]].to_numpy(dtype=float)
        bruta = pacote["modelo"].predict_proba(matriz)[:, 1]
        notas[origem] = features.agregar_nota(tabela, bruta)

    juntas = pd.concat(notas, axis=1, join="inner")

    return {
        "commits_comparados": int(len(juntas)),
        "spearman_da_nota": float(stats.spearmanr(
            juntas["treino"], juntas["git"]).statistic),
        "diferenca_media_da_nota": float((juntas["treino"]
                                          - juntas["git"]).abs().mean()),
        "notas_quase_iguais": float(((juntas["treino"] - juntas["git"])
                                     .abs() < 0.02).mean()),
    }


# =============================================================
# EXPERIÊNCIA DO AUTOR
# =============================================================


# =============================================================
# Nota Por Commit
# -------------------------------------------------------------
# Treina num conjunto de retratos e devolve a nota por commit de outro
# =============================================================
def nota_por_commit(treino: pd.DataFrame, teste: pd.DataFrame,
                    colunas: list[str]) -> pd.Series:
    modelo = HistGradientBoostingClassifier(**config.PARAMETROS_MODELO)
    modelo.fit(treino[colunas].to_numpy(dtype=float),
               treino["defeituoso"].to_numpy(dtype=int))
    bruta = modelo.predict_proba(teste[colunas].to_numpy(dtype=float))[:, 1]
    return features.agregar_nota(teste, bruta)


# =============================================================
# Medir Experiencia
# -------------------------------------------------------------
# AUC por commit com e sem a experiência do autor, nos dois desenhos
# =============================================================
def medir_experiencia(tabela: pd.DataFrame) -> pd.DataFrame:
    conjuntos = {
        "sem_experiencia": features.FEATURES_MODELO,
        "com_experiencia": (features.FEATURES_MODELO
                            + extracao.COLUNAS_DE_EXPERIENCIA),
    }
    rotulo = tabela.groupby(features.CHAVES, sort=False)["defeituoso"].max()
    linhas = []

    for nome, colunas in conjuntos.items():
        for repositorio in sorted(tabela["repositorio"].unique()):
            fora = tabela["repositorio"] == repositorio
            nota = nota_por_commit(tabela[~fora], tabela[fora], colunas)
            linhas.append({
                "desenho": "projeto nunca visto (treina nos outros do piloto)",
                "conjunto": nome, "repositorio": repositorio,
                "commits": int(len(nota)),
                "auc": metricas_avaliacao.auc(rotulo.loc[nota.index], nota)})

        grupos = tabela["repositorio"] + "/" + tabela["commit"]
        partes = []
        for treino, teste in GroupKFold(DOBRAS).split(tabela, groups=grupos):
            partes.append(nota_por_commit(tabela.iloc[treino],
                                          tabela.iloc[teste], colunas))

        nota = pd.concat(partes)
        for repositorio in sorted(tabela["repositorio"].unique()):
            do_repo = nota[nota.index.get_level_values(0) == repositorio]
            linhas.append({
                "desenho": "projeto conhecido (5 dobras por commit)",
                "conjunto": nome, "repositorio": repositorio,
                "commits": int(len(do_repo)),
                "auc": metricas_avaliacao.auc(rotulo.loc[do_repo.index],
                                              do_repo)})

    return pd.DataFrame(linhas)


# =============================================================
# Rodar
# -------------------------------------------------------------
# O piloto inteiro: extrai, compara e mede a experiência
# =============================================================
def rodar() -> None:
    dataset = pd.read_csv(config.ARQUIVO_RETRATOS)
    coberturas, paridades, extraidos = [], [], []

    for nome, endereco in config.REPOSITORIOS_PILOTO.items():
        treino = dataset[dataset["repositorio"] == nome]
        piloto = extrair_repositorio(nome, endereco, set(treino["commit"]))

        cobertura, paridade = comparar_retratos(nome, treino, piloto)
        cobertura.update(comparar_notas(nome, treino, piloto))
        coberturas.append(cobertura)
        paridades.append(paridade)

        rotulos = treino.drop_duplicates("commit")[
            ["commit", "defeituoso", "particao", "no_dominio"]]
        extraidos.append(piloto.merge(rotulos, on="commit"))

    cobertura = pd.DataFrame(coberturas)
    paridade = pd.concat(paridades, ignore_index=True)
    gravar_csv_atomico(cobertura, config.PASTA_PILOTO / "cobertura.csv")
    gravar_csv_atomico(paridade, config.PASTA_PILOTO / "paridade.csv")

    pd.set_option("display.width", 250)
    print("\n  == cobertura e nota")
    print(cobertura.round(4).T.to_string())
    print("\n  == features iguais às do treino (fração dos retratos em comum)")
    print(paridade.pivot(index="feature", columns="repositorio",
                         values="iguais").round(3).to_string())

    tabela = pd.concat(extraidos, ignore_index=True)
    tabela = tabela[tabela["particao"].isin(config.PARTICOES_TREINO)
                    & (tabela["no_dominio"] == 1)]
    experiencia = medir_experiencia(tabela)
    gravar_csv_atomico(experiencia, config.PASTA_PILOTO / "experiencia.csv")

    print("\n  == experiência do autor: AUC por commit")
    print(experiencia.pivot_table(index=["desenho", "repositorio"],
                                  columns="conjunto", values="auc")
          .round(4).to_string())


if __name__ == "__main__":
    rodar()

"""
Frente 1, etapa 1 — monta as tabelas de retratos e de commits a partir
dos dados já medidos na versão original, sem clonar nada.

CMD -> python defectlens_v2/frente1_treinamento/montar_commits.py
       grava defectlens_v2/dados/retratos_dataset.csv e commits_dataset.csv
"""

import os
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import config
from extrator import features

COLUNAS_DO_DATASET = (features.CHAVES
                      + ["arquivo", "particao_defectors", "defeituoso"]
                      + features.COLUNAS_HISTORICO + features.COLUNAS_CODIGO)


# =============================================================
# LEITURA DOS DADOS ORIGINAIS
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
# Ler Retratos
# -------------------------------------------------------------
# Lê os retratos (arquivo, commit) medidos na versão original
# =============================================================
def ler_retratos() -> pd.DataFrame:
    if not config.ARQUIVO_DATASET_ORIGINAL.exists():
        raise SystemExit(f"Não achei {config.ARQUIVO_DATASET_ORIGINAL}.")

    return pd.read_csv(config.ARQUIVO_DATASET_ORIGINAL,
                       usecols=COLUNAS_DO_DATASET)


# =============================================================
# Ler Medidas de Commit
# -------------------------------------------------------------
# Lê as seis medidas de commit gravadas pela versão original
# =============================================================
def ler_medidas_de_commit() -> pd.DataFrame:
    caminhos = sorted(config.PASTA_COMMITS_ORIGINAIS.glob("*.csv"))

    if not caminhos:
        raise SystemExit(f"{config.PASTA_COMMITS_ORIGINAIS} está vazia.")

    return pd.concat([pd.read_csv(c) for c in caminhos], ignore_index=True)


# =============================================================
# Ler Datas
# -------------------------------------------------------------
# A data de cada commit, tirada dos parquets do Defectors
# =============================================================
def ler_datas() -> pd.DataFrame:
    if config.ARQUIVO_DATAS.exists():
        return pd.read_csv(config.ARQUIVO_DATAS)

    partes = []
    for caminho in sorted(config.PASTA_DEFECTORS.glob("*.parquet.gzip")):
        parte = pd.read_parquet(caminho, columns=["datetime", "commit",
                                                  "repo"])
        parte["data"] = (pd.to_datetime(parte["datetime"], utc=True)
                         .dt.strftime("%Y-%m-%d"))
        partes.append(parte[["repo", "commit", "data"]])

    datas = (pd.concat(partes, ignore_index=True)
             .rename(columns={"repo": "repositorio"})
             .drop_duplicates(features.CHAVES))
    gravar_csv_atomico(datas, config.ARQUIVO_DATAS)
    return datas


# =============================================================
# Ler Notas Originais
# -------------------------------------------------------------
# A nota do modelo original em projeto nunca visto, por commit
# =============================================================
def ler_notas_originais() -> pd.DataFrame:
    caminhos = sorted(config.PASTA_VALIDACAO_ORIGINAL.glob("*.csv"))

    if not caminhos:
        return pd.DataFrame(columns=features.CHAVES + ["nota_original"])

    notas = pd.concat([pd.read_csv(c, usecols=features.CHAVES
                                   + ["probabilidade"])
                       for c in caminhos], ignore_index=True)

    return (notas.groupby(features.CHAVES)["probabilidade"].max()
            .rename("nota_original").reset_index())


# =============================================================
# MONTAGEM
# =============================================================


# =============================================================
# Rotular Commits
# -------------------------------------------------------------
# Rótulo e partição de cada commit, a partir dos seus retratos
# =============================================================
def rotular_commits(retratos: pd.DataFrame) -> pd.DataFrame:
    grupos = retratos.groupby(features.CHAVES, sort=False)

    return pd.DataFrame({
        "particao": grupos["particao_defectors"].first(),
        "defeituoso": grupos["defeituoso"].max(),
        "rotulo_misto": (grupos["defeituoso"].max()
                         != grupos["defeituoso"].min()).astype(int),
    }).reset_index()


# =============================================================
# Montar
# -------------------------------------------------------------
# Monta e grava a tabela de retratos e a de commits
# =============================================================
def montar() -> tuple[pd.DataFrame, pd.DataFrame]:
    originais = ler_retratos()
    rotulos = rotular_commits(originais)

    retratos = features.montar_retratos(
        ler_medidas_de_commit(),
        originais.drop(columns=["particao_defectors", "defeituoso"]))
    retratos = retratos.merge(rotulos, on=features.CHAVES,
                              validate="many_to_one")
    retratos["no_dominio"] = features.no_dominio(retratos).astype(int)

    todas = [f for grupo in features.GRUPOS.values() for f in grupo]
    identificacao = ["particao", "defeituoso", "rotulo_misto", "no_dominio"]
    retratos = (retratos[features.CHAVES + ["arquivo"] + identificacao
                         + todas]
                .sort_values(features.CHAVES + ["arquivo"])
                .reset_index(drop=True))

    commits = features.resumir_por_commit(
        retratos, identificacao + features.GRUPOS["commit"])
    commits = commits.merge(ler_datas(), on=features.CHAVES, how="left")
    commits = commits.merge(ler_notas_originais(), on=features.CHAVES,
                            how="left")

    gravar_csv_atomico(retratos, config.ARQUIVO_RETRATOS)
    gravar_csv_atomico(commits, config.ARQUIVO_COMMITS)
    return retratos, commits


# =============================================================
# Resumir
# -------------------------------------------------------------
# Mostra o que a tabela tem
# =============================================================
def resumir(retratos: pd.DataFrame, tabela: pd.DataFrame) -> None:
    print(f"\n  {len(retratos)} retratos, {len(retratos.columns)} colunas "
          f"-> {config.ARQUIVO_RETRATOS}")
    print(f"  {len(tabela)} commits de "
          f"{tabela['repositorio'].nunique()} repositórios, "
          f"{len(tabela.columns)} colunas -> {config.ARQUIVO_COMMITS}")

    por_particao = tabela.groupby("particao").agg(
        commits=("defeituoso", "size"), taxa=("defeituoso", "mean"),
        no_dominio=("no_dominio", "mean"))
    print(por_particao.round(4).to_string())

    fora = tabela[tabela["no_dominio"] == 0]
    print(f"\n  Fora do domínio do rótulo: {len(fora)} commits, "
          f"{int(fora['defeituoso'].sum())} defeituosos")
    print(f"  Commits com rótulo misto entre arquivos: "
          f"{100 * tabela['rotulo_misto'].mean():.2f}%")
    print(f"  Sem data: {int(tabela['data'].isna().sum())}; sem nota do "
          f"modelo original: {int(tabela['nota_original'].isna().sum())}")


if __name__ == "__main__":
    resumir(*montar())

import numpy as np
import pandas as pd

from predicao import config


DIA = 86400

FEATURES_BASE = [
    "revisoes", "autores", "idade_dias", "dias_desde_ultima", "adicionadas", "removidas",
    "churn", "linhas_estimadas", "consertos", "fracao_consertos", "dias_desde_conserto",
    "commits_desde_conserto", "adicionadas_desde_conserto", "fracao_nova_desde_conserto",
    "media_arquivos_commit", "maior_adicao", "fracao_autor_principal", "autores_menores",
    "intervalo_medio_dias", "churn_por_linha", "profundidade", "arquivo_init",
]
FEATURES_JANELA = [f"{nome}_{dias}" for dias in config.JANELAS_DIAS
                   for nome in ("commits", "consertos", "churn", "autores")]
FEATURES_POSICAO = [f"pos_{nome}" for nome in
                    ("revisoes", "linhas_estimadas", "commits_365", "consertos", "churn_365",
                     "adicionadas_desde_conserto", "autores")]
FEATURES_REPO = ["repo_arquivos", "repo_fracao_consertos", "repo_commits_por_arquivo_365",
                 "repo_idade_dias", "repo_fracao_ativos_365"]
FEATURES = FEATURES_BASE + FEATURES_JANELA + FEATURES_POSICAO + FEATURES_REPO


def no_escopo(caminho: str) -> bool:
    partes = caminho.replace("\\", "/").split("/")
    nome = partes[-1]
    if any(parte.lower() in config.PASTAS_FORA_DO_ESCOPO for parte in partes[:-1]):
        return False
    if nome in config.ARQUIVOS_FORA_DO_ESCOPO:
        return False
    return not (nome.startswith("test_") or nome.endswith("_test.py"))


def identificar(historico: pd.DataFrame) -> pd.DataFrame:
    tabela = historico.iloc[::-1].reset_index(drop=True)
    tabela["arquivo_antigo"] = tabela["arquivo_antigo"].fillna("")
    tabela["ordem"] = np.arange(len(tabela))
    tabela["arquivos_commit"] = tabela.groupby("hash")["arquivo"].transform("size")
    mapa = {}
    proximo = 0
    ids = np.empty(len(tabela), dtype=np.int64)
    for i, (situacao, arquivo, antigo) in enumerate(
            zip(tabela["situacao"].values, tabela["arquivo"].values,
                tabela["arquivo_antigo"].values)):
        if situacao == "R" and antigo in mapa:
            identidade = mapa.pop(antigo)
            mapa[arquivo] = identidade
        elif situacao == "D":
            identidade = mapa.pop(arquivo, None)
            if identidade is None:
                identidade = proximo
                proximo += 1
        elif situacao == "A" or arquivo not in mapa:
            identidade = proximo
            proximo += 1
            mapa[arquivo] = identidade
        else:
            identidade = mapa[arquivo]
        ids[i] = identidade
    tabela["id"] = ids
    return tabela


def medir(identificado: pd.DataFrame, instante: int) -> pd.DataFrame:
    passado = identificado[identificado["instante"] <= instante]
    if passado.empty:
        return pd.DataFrame(columns=["id", "arquivo"] + FEATURES)
    grupo = passado.groupby("id", sort=True)
    ultimo = passado.loc[grupo["ordem"].idxmax(), ["id", "situacao", "arquivo"]].set_index("id")
    m = grupo.agg(revisoes=("hash", "size"), autores=("autor", "nunique"),
                  primeiro=("instante", "min"), ultima=("instante", "max"),
                  adicionadas=("adicionadas", "sum"), removidas=("removidas", "sum"),
                  consertos=("conserto", "sum"),
                  media_arquivos_commit=("arquivos_commit", "mean"),
                  maior_adicao=("adicionadas", "max"))
    m["arquivo"] = ultimo["arquivo"]
    m["idade_dias"] = (instante - m["primeiro"]) / DIA
    m["dias_desde_ultima"] = (instante - m["ultima"]) / DIA
    m["churn"] = m["adicionadas"] + m["removidas"]
    m["linhas_estimadas"] = (m["adicionadas"] - m["removidas"]).clip(lower=0)
    m["fracao_consertos"] = m["consertos"] / m["revisoes"]
    m["intervalo_medio_dias"] = (m["ultima"] - m["primeiro"]) / DIA / m["revisoes"]
    m["churn_por_linha"] = m["churn"] / (m["linhas_estimadas"] + 1)

    consertos = passado[passado["conserto"] == 1].groupby("id")["ordem"].max()
    ordem_conserto = passado["id"].map(consertos).fillna(-1)
    instante_conserto = passado[passado["conserto"] == 1].groupby("id")["instante"].max()
    m["dias_desde_conserto"] = (instante - instante_conserto.reindex(m.index)) / DIA
    depois = passado[passado["ordem"] > ordem_conserto].groupby("id")
    m["commits_desde_conserto"] = depois["hash"].size().reindex(m.index).fillna(0)
    m["adicionadas_desde_conserto"] = depois["adicionadas"].sum().reindex(m.index).fillna(0)
    m["fracao_nova_desde_conserto"] = m["adicionadas_desde_conserto"] / (m["adicionadas"] + 1)

    por_autor = passado.groupby(["id", "autor"]).size()
    total = por_autor.groupby(level=0).transform("sum")
    fracao = por_autor / total
    m["fracao_autor_principal"] = fracao.groupby(level=0).max()
    m["autores_menores"] = (fracao < 0.05).groupby(level=0).sum()

    for dias in config.JANELAS_DIAS:
        recente = passado[passado["instante"] > instante - dias * DIA].groupby("id")
        m[f"commits_{dias}"] = recente["hash"].size().reindex(m.index).fillna(0)
        m[f"consertos_{dias}"] = recente["conserto"].sum().reindex(m.index).fillna(0)
        m[f"churn_{dias}"] = (recente["adicionadas"].sum() + recente["removidas"].sum()
                              ).reindex(m.index).fillna(0)
        m[f"autores_{dias}"] = recente["autor"].nunique().reindex(m.index).fillna(0)

    m = m[ultimo["situacao"] != "D"]
    m = m[m["arquivo"].map(no_escopo)]
    m["profundidade"] = m["arquivo"].str.count("/")
    m["arquivo_init"] = m["arquivo"].str.endswith("__init__.py").astype(int)

    for nome in FEATURES_POSICAO:
        m[nome] = m[nome[4:]].rank(pct=True)

    m["repo_arquivos"] = len(m)
    m["repo_fracao_consertos"] = passado.drop_duplicates("hash")["conserto"].mean()
    m["repo_commits_por_arquivo_365"] = m["commits_365"].mean()
    m["repo_idade_dias"] = (instante - passado["instante"].min()) / DIA
    m["repo_fracao_ativos_365"] = (m["commits_365"] > 0).mean()
    return m.reset_index()[["id", "arquivo"] + FEATURES]

"""
Os métodos comparados: ordenações triviais, sem treino, e modelos treinados.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import config
from extrator import features

ALVO = "defeituoso"


# =============================================================
# MÉTODOS SEM TREINO
# =============================================================

SEM_TREINO = {
    "aleatorio":      "Aleatório",
    "la":             "Linhas adicionadas (LA)",
    "churn":          "Linhas alteradas (LA + LD)",
    "nf":             "Número de arquivos (NF)",
    "menor_primeiro": "Menor commit primeiro (ManualUp)",
    "original":       "DefectLens original (82 features, por arquivo)",
}


# =============================================================
# Nota Sem Treino
# -------------------------------------------------------------
# A nota de um método que só ordena por uma medida do commit
# =============================================================
def nota_sem_treino(metodo: str, tabela: pd.DataFrame) -> np.ndarray:
    churn = (tabela["commit_adicionadas"]
             + tabela["commit_removidas"]).to_numpy(dtype=float)

    if metodo == "aleatorio":
        return np.random.default_rng(config.SEMENTE).random(len(tabela))
    if metodo == "la":
        return tabela["commit_adicionadas"].to_numpy(dtype=float)
    if metodo == "churn":
        return churn
    if metodo == "nf":
        return tabela["commit_arquivos"].to_numpy(dtype=float)
    if metodo == "menor_primeiro":
        return -churn
    if metodo == "original":
        return tabela["nota_original"].to_numpy(dtype=float)

    raise ValueError(f"Método sem treino desconhecido: {metodo}")


# =============================================================
# MÉTODOS TREINADOS
# -------------------------------------------------------------
# nivel "commit": uma linha por commit.
# nivel "retrato": uma linha por (commit, arquivo .py), com o
# rótulo do commit; a nota do commit é a maior entre os arquivos.
# =============================================================

TREINADOS = {
    "lapredict": {
        "nome": "LApredict (logística só com LA)",
        "tipo": "logistica", "nivel": "commit",
        "colunas": ["commit_adicionadas"],
    },
    "logistica_commit": {
        "nome": "Logística, medidas do commit",
        "tipo": "logistica", "nivel": "commit",
        "colunas": features.GRUPOS["commit"],
    },
    "boosting_commit": {
        "nome": "Boosting, só medidas do commit",
        "tipo": "boosting", "nivel": "commit",
        "colunas": features.GRUPOS["commit"],
    },
    "modelo_v2": {
        "nome": "DefectLens v2 (commit + histórico)",
        "tipo": "boosting", "nivel": "retrato",
        "colunas": features.FEATURES_MODELO,
    },
    "boosting_completo": {
        "nome": "Boosting, commit + histórico + código",
        "tipo": "boosting", "nivel": "retrato",
        "colunas": features.FEATURES_MODELO + features.GRUPOS["codigo"],
    },
    "v2_sem_dominio": {
        "nome": "v2 treinado sem o filtro de domínio",
        "tipo": "boosting", "nivel": "retrato",
        "colunas": features.FEATURES_MODELO,
        "sem_dominio": True,
    },
    "v2_equilibrado": {
        "nome": "v2 com classes equilibradas por repositório",
        "tipo": "boosting", "nivel": "retrato",
        "colunas": features.FEATURES_MODELO,
        "pesos": True,
    },
}

NOMES = {**SEM_TREINO, **{m: d["nome"] for m, d in TREINADOS.items()}}


# =============================================================
# Pesos por Repositorio
# -------------------------------------------------------------
# Equilibra as duas classes dentro de cada repositório
# =============================================================
def pesos_por_repositorio(tabela: pd.DataFrame) -> np.ndarray:
    contagem = tabela.groupby(["repositorio", ALVO])[ALVO].transform("size")
    total = tabela.groupby("repositorio")[ALVO].transform("size")
    return (total / (2.0 * contagem)).to_numpy(dtype=float)


# =============================================================
# Log Positivo
# -------------------------------------------------------------
# Logaritmo de 1 + x, com negativos tratados como zero
# =============================================================
def log_positivo(x: np.ndarray) -> np.ndarray:
    return np.log1p(np.clip(x, 0, None))


# =============================================================
# Criar Estimador
# -------------------------------------------------------------
# O classificador de um tipo, ainda sem treinar
# =============================================================
def criar_estimador(tipo: str):
    if tipo == "logistica":
        return make_pipeline(FunctionTransformer(log_positivo),
                             StandardScaler(),
                             LogisticRegression(max_iter=2000))

    if tipo == "boosting":
        return HistGradientBoostingClassifier(**config.PARAMETROS_MODELO)

    raise ValueError(f"Tipo de modelo desconhecido: {tipo}")


# =============================================================
# Linhas de Treino
# -------------------------------------------------------------
# As linhas que um método usa para treinar
# =============================================================
def linhas_de_treino(tabela: pd.DataFrame, definicao: dict) -> pd.DataFrame:
    treino = tabela[tabela["particao"].isin(config.PARTICOES_TREINO)]

    if not definicao.get("sem_dominio"):
        treino = treino[treino["no_dominio"] == 1]

    return treino


# =============================================================
# Matriz
# -------------------------------------------------------------
# As colunas do modelo como números, com vazio no lugar de infinito
# =============================================================
def matriz(tabela: pd.DataFrame, definicao: dict) -> np.ndarray:
    valores = tabela[definicao["colunas"]].apply(pd.to_numeric,
                                                 errors="coerce")
    valores = valores.replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)

    if definicao["tipo"] == "logistica":
        valores = np.nan_to_num(valores)

    return valores


# =============================================================
# Treinar
# -------------------------------------------------------------
# Treina um método na tabela do seu nível
# =============================================================
def treinar(metodo: str, retratos: pd.DataFrame, commits: pd.DataFrame):
    definicao = TREINADOS[metodo]
    tabela = retratos if definicao["nivel"] == "retrato" else commits
    treino = linhas_de_treino(tabela, definicao)

    estimador = criar_estimador(definicao["tipo"])
    x = matriz(treino, definicao)
    y = treino[ALVO].to_numpy(dtype=int)

    if definicao.get("pesos"):
        estimador.fit(x, y, sample_weight=pesos_por_repositorio(treino))
    else:
        estimador.fit(x, y)

    return estimador


# =============================================================
# Prever
# -------------------------------------------------------------
# A nota de cada commit, na ordem da tabela de commits
# =============================================================
def prever(metodo: str, estimador, retratos: pd.DataFrame,
           commits: pd.DataFrame) -> np.ndarray:
    definicao = TREINADOS[metodo]

    if definicao["nivel"] == "commit":
        return estimador.predict_proba(matriz(commits, definicao))[:, 1]

    nota = estimador.predict_proba(matriz(retratos, definicao))[:, 1]
    por_commit = features.agregar_nota(retratos, nota)
    chaves = pd.MultiIndex.from_frame(commits[features.CHAVES])
    return por_commit.reindex(chaves).to_numpy(dtype=float)

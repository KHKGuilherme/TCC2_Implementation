import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from treino import config
from treino.medidas import metricas_historico as mh


CONJUNTOS = {
    "processo": mh.FEATURES_BASE + mh.FEATURES_JANELA,
    "posicao": mh.FEATURES_BASE + mh.FEATURES_JANELA + mh.FEATURES_POSICAO,
    "completo": mh.FEATURES,
}

VARIANTES = {
    "processo": ("processo", "gradiente"),
    "posicao": ("posicao", "gradiente"),
    "completo": ("completo", "gradiente"),
    "balanceado": ("posicao", "gradiente_balanceado"),
    "logistica": ("posicao", "logistica"),
}

CALIBRADAS = ("processo", "posicao", "completo")

BASELINES = ["linhas_estimadas", "revisoes", "churn", "commits_365", "consertos",
             "adicionadas_desde_conserto"]


def ler_retratos() -> pd.DataFrame:
    partes = []
    for caminho in sorted(config.PASTA_RETRATOS.glob("*.csv.gz")):
        nome = caminho.name[:-7]
        if "__" in nome or nome in config.REPOSITORIOS_SEM_ROTULO:
            continue
        partes.append(pd.read_csv(caminho))
    return pd.concat(partes, ignore_index=True)


def parte_de_treino(retratos: pd.DataFrame) -> pd.DataFrame:
    maduros = retratos[(retratos["data"] <= config.ULTIMO_RETRATO_ROTULADO)
                       & retratos[config.ROTULO].notna()]
    partes = []
    for _, grupo in maduros.groupby("repositorio"):
        if len(grupo) > config.MAXIMO_RETRATOS_POR_REPO:
            grupo = grupo.sample(config.MAXIMO_RETRATOS_POR_REPO, random_state=config.SEMENTE)
        partes.append(grupo)
    return pd.concat(partes, ignore_index=True)


def criar(nome: str):
    if nome == "logistica":
        return make_pipeline(
            FunctionTransformer(lambda x: np.log1p(np.nan_to_num(np.abs(x), nan=0.0))),
            StandardScaler(), LogisticRegression(max_iter=500, C=0.5))
    return HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=50,
        l2_regularization=1.0, early_stopping=True, validation_fraction=0.1,
        class_weight="balanced" if nome == "gradiente_balanceado" else None,
        random_state=config.SEMENTE)


def treinar(variante: str, treino: pd.DataFrame):
    conjunto, nome = VARIANTES[variante]
    estimador = criar(nome)
    estimador.fit(treino[CONJUNTOS[conjunto]].values, treino[config.ROTULO].values.astype(int))
    return estimador


def prever(estimador, variante: str, dados: pd.DataFrame) -> np.ndarray:
    return estimador.predict_proba(dados[CONJUNTOS[VARIANTES[variante][0]]].values)[:, 1]


def fora_da_dobra(variante: str, treino: pd.DataFrame, dobras: int = 4) -> np.ndarray:
    saida = np.zeros(len(treino))
    grupos = treino["repositorio"].values
    for parte_a, parte_b in GroupKFold(n_splits=dobras).split(treino, groups=grupos):
        estimador = treinar(variante, treino.iloc[parte_a])
        saida[parte_b] = prever(estimador, variante, treino.iloc[parte_b])
    return saida


def logito(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p)).reshape(-1, 1)


def ajustar_calibradores(p: np.ndarray, y: np.ndarray) -> dict:
    platt = LogisticRegression(C=1e6, max_iter=1000).fit(logito(p), y)
    isotonica = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(p, y)
    return {"platt": platt, "isotonica": isotonica}


def calibrar(calibradores: dict, tipo: str, p: np.ndarray) -> np.ndarray:
    if tipo == "platt":
        return calibradores["platt"].predict_proba(logito(p))[:, 1]
    if tipo == "isotonica":
        return calibradores["isotonica"].predict(p)
    return p

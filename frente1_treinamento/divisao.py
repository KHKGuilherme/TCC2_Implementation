"""
Decide como os dados são separados para avaliar o modelo.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.model_selection import (GroupKFold, GroupShuffleSplit,
                                     LeaveOneGroupOut, StratifiedKFold,
                                     train_test_split)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from extrator import features


# =============================================================
# ID de um arquivo
# =============================================================
def chave_de_arquivo(dados: pd.DataFrame) -> np.ndarray:
    return (dados["repositorio"] + "::" + dados["arquivo"]).to_numpy()


# =============================================================
# DIVISÃO TREINO / TESTE
# =============================================================

# -------------------------------------------------------------
# Dividir por Repositorio
# -------------------------------------------------------------
def dividir_por_repositorio(dados: pd.DataFrame) -> pd.Series:
    nomes = dados["repositorio"].str.lower()

    reservado = pd.Series(False, index=dados.index)
    for alvo in config.REPOSITORIOS_TESTE:
        reservado |= nomes.str.contains(alvo.lower(), regex=False, na=False)

    return pd.Series(np.where(reservado, "teste", "treino"),
                     index=dados.index)


# -------------------------------------------------------------
# Dividir Aleatoria ( train_test_split )
# -------------------------------------------------------------
def dividir_aleatoria(dados: pd.DataFrame) -> pd.Series:
    y = dados[features.COLUNA_ALVO]

    estratificar = y if y.nunique() > 1 and y.value_counts().min() >= 2 else None

    indices_treino, indices_teste = train_test_split(
        dados.index,
        test_size=config.FRACAO_TESTE,
        random_state=config.SEMENTE,
        stratify=estratificar,
    )

    particao = pd.Series("treino", index=dados.index)
    particao.loc[indices_teste] = "teste"
    return particao


# -------------------------------------------------------------
# Dividir por Arquivo
# -------------------------------------------------------------
def dividir_por_arquivo(dados: pd.DataFrame) -> pd.Series:
    divisor = GroupShuffleSplit(n_splits=1,
                               test_size=config.FRACAO_TESTE,
                               random_state=config.SEMENTE)

    posicoes_treino, posicoes_teste = next(
        divisor.split(dados, groups=chave_de_arquivo(dados)))

    particao = pd.Series("treino", index=dados.index)
    particao.iloc[posicoes_teste] = "teste"
    return particao


# -------------------------------------------------------------
# Diivir - All Train
# -------------------------------------------------------------
def dividir_sem_reserva(dados: pd.DataFrame) -> pd.Series:
    return pd.Series("treino", index=dados.index)


# =============================================================
# VALIDAÇÃO CRUZADA DENTRO DO TREINO
# =============================================================
# -------------------------------------------------------------
# Validar por Repositorio
# -------------------------------------------------------------
def validar_por_repositorio(treino: pd.DataFrame):
    grupos = treino["repositorio"].to_numpy()
    quantos = len(np.unique(grupos))

    return (grupos, LeaveOneGroupOut(),
            f"deixando um dos {quantos} repositórios de fora por vez")


# -------------------------------------------------------------
# Validar por Arquivo
# -------------------------------------------------------------
def validar_por_arquivo(treino: pd.DataFrame):
    grupos = chave_de_arquivo(treino)
    dobras = min(config.DOBRAS_VALIDACAO, len(np.unique(grupos)))

    return (grupos, GroupKFold(n_splits=dobras),
            f"agrupando por arquivo em {dobras} dobras")


# -------------------------------------------------------------
# Validar Estratificada
# -------------------------------------------------------------
def validar_estratificada(treino: pd.DataFrame):
    y = treino[features.COLUNA_ALVO].to_numpy()
    menor_classe = int(min(np.bincount(y)[np.bincount(y) > 0]))
    dobras = max(2, min(config.DOBRAS_VALIDACAO, menor_classe))

    divisor = StratifiedKFold(n_splits=dobras, shuffle=True,
                              random_state=config.SEMENTE)

    return (None, divisor,
            f"StratifiedKFold em {dobras} dobras, sem agrupamento")


# =============================================================
# REGISTRO DAS ESTRATÉGIAS
# =============================================================

ESTRATEGIAS_DIVISAO = {
    "por_repositorio": dividir_por_repositorio,
    "aleatoria":       dividir_aleatoria,
    "por_arquivo":     dividir_por_arquivo,
    "sem_reserva":     dividir_sem_reserva,
}

ESTRATEGIAS_VALIDACAO = {
    "por_repositorio": validar_por_repositorio,
    "por_arquivo":     validar_por_arquivo,
    "estratificada":   validar_estratificada,
}

# =============================================================
# Dividir
# =============================================================
def dividir(dados: pd.DataFrame) -> pd.Series:
    nome = config.ESTRATEGIA_DIVISAO

    if nome not in ESTRATEGIAS_DIVISAO:
        raise SystemExit(
            f"ESTRATEGIA_DIVISAO = {nome!r} não existe.\n"
            f"Disponíveis: {', '.join(ESTRATEGIAS_DIVISAO)}"
        )

    return ESTRATEGIAS_DIVISAO[nome](dados)


# =============================================================
# Descrever Divisao
# =============================================================
def descrever_divisao() -> str:
    """Devolve uma linha explicando como o teste foi reservado."""
    nome = config.ESTRATEGIA_DIVISAO

    if nome == "por_repositorio":
        return (f"por repositório — reservados: "
                f"{', '.join(config.REPOSITORIOS_TESTE)}")
    if nome == "aleatoria":
        return (f"aleatória estratificada — "
                f"{100 * config.FRACAO_TESTE:.0f}% das linhas")
    if nome == "por_arquivo":
        return (f"por arquivo — "
                f"{100 * config.FRACAO_TESTE:.0f}% dos arquivos")
    return "sem reserva — todas as linhas são de treino"


# =============================================================
# Validação
# =============================================================
def validacao(treino: pd.DataFrame):

    nome = config.ESTRATEGIA_VALIDACAO

    if nome not in ESTRATEGIAS_VALIDACAO:
        raise SystemExit(
            f"ESTRATEGIA_VALIDACAO = {nome!r} não existe.\n"
            f"Disponíveis: {', '.join(ESTRATEGIAS_VALIDACAO)}"
        )

    if nome == "por_repositorio":
        if treino["repositorio"].nunique() < 2:
            grupos, divisor, texto = validar_por_arquivo(treino)
            return (grupos, divisor,
                    f"{texto} — havia só um repositório no treino, então "
                    f"isto NÃO mede generalização entre projetos")

    return ESTRATEGIAS_VALIDACAO[nome](treino)
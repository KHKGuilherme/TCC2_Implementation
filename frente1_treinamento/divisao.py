"""
Separa treino e teste, e monta as dobras da validação.
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
# Chave de Commit
# -------------------------------------------------------------
# Identificador único de um commit
# =============================================================
def chave_de_commit(dados: pd.DataFrame) -> np.ndarray:
    return (dados["repositorio"] + "::" + dados["commit"]).to_numpy()


# =============================================================
# DIVISÃO TREINO / TESTE
# =============================================================


# =============================================================
# Dividir Defectors
# -------------------------------------------------------------
# Usa a divisão oficial do dataset
# =============================================================
def dividir_defectors(dados: pd.DataFrame) -> pd.Series:
    coluna = dados[features.COLUNA_PARTICAO_DEFECTORS].astype(str)
    return pd.Series(np.where(coluna.str.lower() == "train",
                              "treino", "teste"),
                     index=dados.index)


# =============================================================
# Dividir por Repositorio
# -------------------------------------------------------------
# Reserva projetos inteiros para o teste
# =============================================================
def dividir_por_repositorio(dados: pd.DataFrame) -> pd.Series:
    alvos = {nome.lower() for nome in config.REPOSITORIOS_TESTE}
    reservado = dados["repositorio"].str.lower().isin(alvos)

    return pd.Series(np.where(reservado, "teste", "treino"),
                     index=dados.index)


# =============================================================
# Dividir Train Test Split
# -------------------------------------------------------------
# Sorteia linhas, de forma estratificada
# =============================================================
def dividir_train_test_split(dados: pd.DataFrame) -> pd.Series:
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


# =============================================================
# Dividir Group Shuffle Split
# -------------------------------------------------------------
# Sorteia commits inteiros para o teste
# =============================================================
def dividir_group_shuffle_split(dados: pd.DataFrame) -> pd.Series:
    divisor = GroupShuffleSplit(n_splits=1,
                                test_size=config.FRACAO_TESTE,
                                random_state=config.SEMENTE)

    posicoes_treino, posicoes_teste = next(
        divisor.split(dados, groups=chave_de_commit(dados)))

    particao = pd.Series("treino", index=dados.index)
    particao.iloc[posicoes_teste] = "teste"
    return particao


# =============================================================
# Dividir Sem Reserva
# -------------------------------------------------------------
# Deixa todas as linhas no treino
# =============================================================
def dividir_sem_reserva(dados: pd.DataFrame) -> pd.Series:
    return pd.Series("treino", index=dados.index)


# =============================================================
# VALIDAÇÃO CRUZADA DENTRO DO TREINO
# =============================================================


# =============================================================
# Validar Leave One Group Out
# -------------------------------------------------------------
# Dobras com um repositório de fora por vez
# =============================================================
def validar_leave_one_group_out(treino: pd.DataFrame):
    grupos = treino["repositorio"].to_numpy()
    quantos = len(np.unique(grupos))

    return (grupos, LeaveOneGroupOut(),
            f"LeaveOneGroupOut por repositório — deixa um dos "
            f"{quantos} de fora por vez")


# =============================================================
# Validar Group KFold
# -------------------------------------------------------------
# Dobras em que nenhum commit se repete
# =============================================================
def validar_group_kfold(treino: pd.DataFrame):
    grupos = chave_de_commit(treino)
    dobras = min(config.DOBRAS_VALIDACAO, len(np.unique(grupos)))

    return (grupos, GroupKFold(n_splits=dobras),
            f"GroupKFold por commit — {dobras} dobras")


# =============================================================
# Validar Stratified KFold
# -------------------------------------------------------------
# Dobras estratificadas pelo rótulo
# =============================================================
def validar_stratified_kfold(treino: pd.DataFrame):
    y = treino[features.COLUNA_ALVO].to_numpy()

    contagens = np.bincount(y)
    menor_classe = int(contagens[contagens > 0].min())
    dobras = max(2, min(config.DOBRAS_VALIDACAO, menor_classe))

    divisor = StratifiedKFold(n_splits=dobras, shuffle=True,
                              random_state=config.SEMENTE)

    return (None, divisor,
            f"StratifiedKFold — {dobras} dobras, sem agrupamento")


# =============================================================
# REGISTRO DAS ESTRATÉGIAS
# -------------------------------------------------------------
# Para adicionar uma técnica: escreva a função e registre aqui
# =============================================================

ESTRATEGIAS_DIVISAO = {
    "defectors":           dividir_defectors,
    "por_repositorio":     dividir_por_repositorio,
    "train_test_split":    dividir_train_test_split,
    "group_shuffle_split": dividir_group_shuffle_split,
    "sem_reserva":         dividir_sem_reserva,
}

ESTRATEGIAS_VALIDACAO = {
    "leave_one_group_out": validar_leave_one_group_out,
    "group_kfold":         validar_group_kfold,
    "stratified_kfold":    validar_stratified_kfold,
}


# =============================================================
# Dividir
# -------------------------------------------------------------
# Aplica a estratégia de divisão configurada
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
# -------------------------------------------------------------
# Texto da estratégia em uso, para aparecer na saída
# =============================================================
def descrever_divisao() -> str:
    nome = config.ESTRATEGIA_DIVISAO
    fracao = f"{100 * config.FRACAO_TESTE:.0f}%"

    if nome == "defectors":
        return (f"divisão oficial do Defectors, esquema "
                f"{config.ESQUEMA_DEFECTORS!r} — train contra test+val")
    if nome == "por_repositorio":
        return (f"por repositório — reservados: "
                f"{', '.join(config.REPOSITORIOS_TESTE)}")
    if nome == "train_test_split":
        return f"train_test_split estratificado — {fracao} das linhas"
    if nome == "group_shuffle_split":
        return f"GroupShuffleSplit por commit — {fracao} dos commits"
    return "sem reserva — todas as linhas são de treino"


# =============================================================
# Validacao
# -------------------------------------------------------------
# Aplica a estratégia de validação configurada
# =============================================================
def validacao(treino: pd.DataFrame):
    nome = config.ESTRATEGIA_VALIDACAO

    if nome not in ESTRATEGIAS_VALIDACAO:
        raise SystemExit(
            f"ESTRATEGIA_VALIDACAO = {nome!r} não existe.\n"
            f"Disponíveis: {', '.join(ESTRATEGIAS_VALIDACAO)}"
        )

    if nome == "leave_one_group_out":
        if treino["repositorio"].nunique() < 2:
            grupos, divisor, texto = validar_group_kfold(treino)
            return (grupos, divisor,
                    f"{texto} — havia só um repositório no treino, então "
                    f"isto NÃO mede generalização entre projetos")

    return ESTRATEGIAS_VALIDACAO[nome](treino)

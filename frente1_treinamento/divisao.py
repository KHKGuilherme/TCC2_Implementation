"""
Decide como os dados são separados para avaliar o modelo.

São duas decisões distintas:

  Divisão treino/teste -> qual parte fica guardada para a medição final
  Validação cruzada    -> como as dobras são formadas DENTRO do treino

O que diferencia as estratégias é o que elas permitem aparecer nos dois lados:

  por repositório -> nada do mesmo projeto           (mais severa)
  por arquivo     -> mesmo projeto sim, mesmo arquivo não
  por linha       -> qualquer linha em qualquer lado (mais otimista)
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
# Chave de Arquivo
# -------------------------------------------------------------
# Identificador único de um arquivo
# =============================================================
def chave_de_arquivo(dados: pd.DataFrame) -> np.ndarray:
    # Junta o repositório porque quase todo projeto tem um utils.py
    return (dados["repositorio"] + "::" + dados["arquivo"]).to_numpy()


# =============================================================
# DIVISÃO TREINO / TESTE
# =============================================================

# -------------------------------------------------------------
# Dividir Defectors ( divisão oficial do dataset )
# -------------------------------------------------------------
def dividir_defectors(dados: pd.DataFrame) -> pd.Series:
    # O dataset já vem dividido. 'train' vira treino, 'test' e
    # 'val' viram teste.
    #
    # Com ESQUEMA_DEFECTORS = "time", isso é treinar no passado e
    # prever o futuro — e torna o resultado comparável com outros
    # trabalhos que usam o mesmo benchmark.
    coluna = dados[features.COLUNA_PARTICAO_DEFECTORS].astype(str)
    return pd.Series(np.where(coluna.str.lower() == "train",
                              "treino", "teste"),
                     index=dados.index)


# -------------------------------------------------------------
# Dividir por Repositorio
# -------------------------------------------------------------
def dividir_por_repositorio(dados: pd.DataFrame) -> pd.Series:
    # Reserva os projetos listados em REPOSITORIOS_TESTE.
    # É a mais severa: nenhum arquivo e nenhuma convenção de
    # código do projeto reservado foi vista no treino.
    # Comparação exata: 'django' e 'django-rest-framework' são
    # projetos diferentes, e um teste por substring reservaria os
    # dois ao pedir só um
    alvos = {nome.lower() for nome in config.REPOSITORIOS_TESTE}
    reservado = dados["repositorio"].str.lower().isin(alvos)

    return pd.Series(np.where(reservado, "teste", "treino"),
                     index=dados.index)


# -------------------------------------------------------------
# Dividir Train Test Split ( train_test_split )
# -------------------------------------------------------------
def dividir_train_test_split(dados: pd.DataFrame) -> pd.Series:
    # O modo padrão do scikit-learn. Sorteia LINHAS.
    # stratify mantém a mesma proporção de defeituosos nos dois
    # lados, o que estabiliza as métricas entre execuções.
    y = dados[features.COLUNA_ALVO]

    # stratify exige pelo menos duas linhas de cada classe
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
# Dividir Group Shuffle Split ( GroupShuffleSplit )
# -------------------------------------------------------------
def dividir_group_shuffle_split(dados: pd.DataFrame) -> pd.Series:
    # Sorteia ARQUIVOS em vez de linhas. Todos os retratos de um
    # arquivo vão para o mesmo lado, mas projetos continuam
    # misturados.
    divisor = GroupShuffleSplit(n_splits=1,
                                test_size=config.FRACAO_TESTE,
                                random_state=config.SEMENTE)

    posicoes_treino, posicoes_teste = next(
        divisor.split(dados, groups=chave_de_arquivo(dados)))

    particao = pd.Series("treino", index=dados.index)
    particao.iloc[posicoes_teste] = "teste"
    return particao


# -------------------------------------------------------------
# Dividir Sem Reserva
# -------------------------------------------------------------
def dividir_sem_reserva(dados: pd.DataFrame) -> pd.Series:
    # Tudo é treino. Para quando a avaliação vai ser só por
    # validação cruzada.
    return pd.Series("treino", index=dados.index)


# =============================================================
# VALIDAÇÃO CRUZADA DENTRO DO TREINO
# =============================================================

# -------------------------------------------------------------
# Validar Leave One Group Out ( LeaveOneGroupOut )
# -------------------------------------------------------------
def validar_leave_one_group_out(treino: pd.DataFrame):
    # Treina em todos os repositórios menos um, testa no que
    # sobrou. O número de dobras é o número de repositórios, então
    # DOBRAS_VALIDACAO é ignorado. Exige pelo menos dois.
    grupos = treino["repositorio"].to_numpy()
    quantos = len(np.unique(grupos))

    return (grupos, LeaveOneGroupOut(),
            f"LeaveOneGroupOut por repositório — deixa um dos "
            f"{quantos} de fora por vez")


# -------------------------------------------------------------
# Validar Group KFold ( GroupKFold )
# -------------------------------------------------------------
def validar_group_kfold(treino: pd.DataFrame):
    # Nenhum arquivo aparece em duas dobras. Projetos continuam
    # misturados entre elas.
    grupos = chave_de_arquivo(treino)
    dobras = min(config.DOBRAS_VALIDACAO, len(np.unique(grupos)))

    return (grupos, GroupKFold(n_splits=dobras),
            f"GroupKFold por arquivo — {dobras} dobras")


# -------------------------------------------------------------
# Validar Stratified KFold ( StratifiedKFold )
# -------------------------------------------------------------
def validar_stratified_kfold(treino: pd.DataFrame):
    # O padrão do scikit-learn para classificação. Mantém a
    # proporção do rótulo em cada dobra, mas permite retratos do
    # mesmo arquivo em dobras diferentes.
    y = treino[features.COLUNA_ALVO].to_numpy()

    # Não existe estratificação com mais dobras que exemplos
    contagens = np.bincount(y)
    menor_classe = int(contagens[contagens > 0].min())
    dobras = max(2, min(config.DOBRAS_VALIDACAO, menor_classe))

    divisor = StratifiedKFold(n_splits=dobras, shuffle=True,
                              random_state=config.SEMENTE)

    # Devolve None no lugar dos grupos para manter a mesma
    # interface das outras duas
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

    # Para o programa em vez de cair num padrão silencioso: um
    # erro de digitação aqui mudaria o significado de todos os
    # resultados do trabalho
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
        return f"GroupShuffleSplit por arquivo — {fracao} dos arquivos"
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

    # Com um repositório só, deixar um de fora não deixa nada para
    # treinar. Cai para GroupKFold e avisa, para o número não ser
    # lido como se medisse generalização entre projetos.
    if nome == "leave_one_group_out":
        if treino["repositorio"].nunique() < 2:
            grupos, divisor, texto = validar_group_kfold(treino)
            return (grupos, divisor,
                    f"{texto} — havia só um repositório no treino, então "
                    f"isto NÃO mede generalização entre projetos")

    return ESTRATEGIAS_VALIDACAO[nome](treino)
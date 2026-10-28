# ==============================================================
# Este arquivo define as Colunas e sua Ordem.
# ==============================================================

# Relativo porque 'extrator' é um pacote: assim funciona
# independente de quem importa e de onde
from . import derivadas

# -------------------------------------------------------------
# Como o código está escrito (Radon e Lizard)
# -------------------------------------------------------------
COLUNAS_CODIGO = [
    "linhas",               # linhas de código efetivas, sem comentários nem vazias
    "complexidade_media",   # complexidade ciclomática média entre as funções
    "complexidade_maxima",  # complexidade da função mais complexa
    "manutenibilidade",     # índice de 0 a 100, onde 100 é o melhor
    "maior_funcao",         # número de linhas da maior função
    "qtd_funcoes",          # quantas funções o arquivo tem
]

# -------------------------------------------------------------
# Como o código evoluiu (PyDriller)
# -------------------------------------------------------------
COLUNAS_HISTORICO = [
    "revisoes",   # quantos commits alteraram o arquivo
    "autores",    # quantas pessoas diferentes o alteraram
    "churn",      # total de linhas adicionadas mais removidas
]

# =============================================================
# AS DUAS LISTAS, QUE SÃO COISAS DIFERENTES
# =============================================================

# O que está GRAVADO no dataset.csv. É o contrato do arquivo.
COLUNAS_BASE = COLUNAS_CODIGO + COLUNAS_HISTORICO

# O que o MODELO recebe: as medidas mais as derivadas ligadas no
# config.
#
# Separar as duas é o que permite acrescentar features derivadas
# sem invalidar um dataset que levou horas para ser montado: as
# derivadas são calculadas na hora de treinar, a partir das
# medidas, e nunca precisam estar no CSV.
FEATURES = COLUNAS_BASE + derivadas.colunas_ativas(COLUNAS_BASE)

# =============================================================
# O QUE O MODELO PREVÊ
# =============================================================

# 1 para arquivo que contém defeito, 0 para arquivo limpo.
COLUNA_ALVO = "defeituoso"

# =============================================================
# COLUNAS QUE NÃO ENTRAM NO MODELO
# =============================================================
COLUNAS_IDENTIFICACAO = [
    "repositorio",         # nome no GitHub, por exemplo numpy/numpy
    "arquivo",             # caminho do .py dentro do repositório
    "commit",              # commit no qual o arquivo foi medido
    "particao_defectors",  # divisão oficial do dataset: train, test ou val
]


COLUNAS_DIAGNOSTICO = [
    "linhas_defeituosas",
]

# -------------------------------------------------------------
# As duas divisões, que são coisas diferentes
# -------------------------------------------------------------

# A que o próprio Defectors entrega: train, test ou val.
# Permite adotar a divisão oficial em vez de inventar uma.
COLUNA_PARTICAO_DEFECTORS = "particao_defectors"

# A que ESTE trabalho usa. Vale "treino" ou "teste".
# Escolhida em ESTRATEGIA_DIVISAO.
COLUNA_PARTICAO = "particao"

# =============================================================
# A ORDEM DAS COLUNAS NO CSV
# =============================================================

# COLUNAS_BASE e não FEATURES: o CSV guarda só o que foi medido.
# As derivadas são recalculadas a cada treino, de graça.
COLUNAS_CSV = (COLUNAS_IDENTIFICACAO
               + COLUNAS_BASE
               + COLUNAS_DIAGNOSTICO
               + [COLUNA_ALVO, COLUNA_PARTICAO])

# =============================================================
# Conferir Contrato
# -------------------------------------------------------------
# Valida um conjunto de colunas
# =============================================================
def conferir_contrato(colunas) -> None:
    """Interrompe o programa se faltar alguma coluna obrigatória.

    Chamada antes de gravar o dataset e antes de treinar. A ideia
    é que a divergência apareça aqui, de forma visível, em vez de
    virar uma previsão errada mais adiante.
    """
    faltando = [c for c in COLUNAS_CSV if c not in colunas]
    if faltando:
        raise ValueError(f"Colunas faltando no dataset: {faltando}")


# =============================================================
# Conferir Sem Vazamento
# -------------------------------------------------------------
# Valida que o rótulo não é feature
# =============================================================
def conferir_sem_vazamento() -> None:
    """Interrompe o programa se uma coluna de diagnóstico virar feature.

    As colunas de diagnóstico derivam do rótulo. Se uma delas
    entrasse na lista de features, o modelo atingiria acerto
    perfeito e o resultado não significaria nada.
    """
    proibidas = set(FEATURES) & (set(COLUNAS_DIAGNOSTICO)
                                 | {COLUNA_ALVO, COLUNA_PARTICAO})
    if proibidas:
        raise ValueError(
            f"Coluna proibida entre as features: {sorted(proibidas)}")
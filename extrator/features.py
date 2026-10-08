# ==============================================================
# Este arquivo define as Colunas e sua Ordem.
# ==============================================================

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

# A ordem em que o modelo espera receber os valores.
FEATURES = COLUNAS_CODIGO + COLUNAS_HISTORICO

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

COLUNAS_CSV = (COLUNAS_IDENTIFICACAO
               + FEATURES
               + COLUNAS_DIAGNOSTICO
               + [COLUNA_ALVO, COLUNA_PARTICAO])

# =============================================================
# Conferir Contrato
# -------------------------------------------------------------
# Valida um conjunto de colunas
# =============================================================
def conferir_contrato(colunas) -> None:
    faltando = [c for c in COLUNAS_CSV if c not in colunas]
    if faltando:
        raise ValueError(f"Colunas faltando no dataset: {faltando}")


# =============================================================
# Conferir Sem Vazamento
# -------------------------------------------------------------
# Valida que o rótulo não é feature
# =============================================================
def conferir_sem_vazamento() -> None:
    proibidas = set(FEATURES) & (set(COLUNAS_DIAGNOSTICO)
                                 | {COLUNA_ALVO, COLUNA_PARTICAO})
    if proibidas:
        raise ValueError(
            f"Coluna proibida entre as features: {sorted(proibidas)}")
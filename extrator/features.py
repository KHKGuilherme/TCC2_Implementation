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
    "repositorio",   # nome no GitHub, por exemplo numpy/numpy
    "arquivo",       # caminho do .py dentro do repositório
    "commit",        # commit no qual o arquivo foi medido
]


COLUNAS_DIAGNOSTICO = [
    "linhas_defeituosas",
]

# Divisão entre treino e teste. Vale "treino" ou "teste". -> Mexer depois para outros meios como Split
COLUNA_PARTICAO = "particao"

# =============================================================
# A ORDEM DAS COLUNAS NO CSV
# =============================================================

COLUNAS_CSV = (COLUNAS_IDENTIFICACAO
               + FEATURES
               + COLUNAS_DIAGNOSTICO
               + [COLUNA_ALVO, COLUNA_PARTICAO])

# =============================================================
# conferir_contrato — valida um conjunto de colunas
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
# conferir_sem_vazamento — valida que o rótulo não é feature
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

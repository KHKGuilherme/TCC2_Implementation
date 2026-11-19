"""
Define as colunas do dataset e a ordem delas.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

from . import derivadas

# -------------------------------------------------------------
# Como o código está escrito (Radon e Lizard)
# -------------------------------------------------------------
COLUNAS_CODIGO = [
    "linhas",
    "complexidade_media",
    "complexidade_maxima",
    "manutenibilidade",
    "maior_funcao",
    "qtd_funcoes",
]

# -------------------------------------------------------------
# Grupos opcionais de código, ligados no config
# -------------------------------------------------------------
COLUNAS_COMENTARIOS = [
    "comentarios",
    "linhas_em_branco",
]

COLUNAS_HALSTEAD = [
    "halstead_volume",
    "halstead_dificuldade",
    "halstead_esforco",
    "halstead_bugs",
]

COLUNAS_LIZARD = [
    "tokens",
    "parametros_maximo",
    "parametros_media",
]

COLUNAS_AST = [
    "aninhamento_maximo",
    "todos_fixmes",
    "except_pelado",
    "qtd_try",
    "qtd_imports",
    "imports_estrela",
    "qtd_classes",
    "qtd_decoradores",
    "qtd_global",
]

COLUNAS_RUFF = [
    "ruff_total",
    "ruff_bugbear",
    "ruff_seguranca",
    "ruff_excecao",
    "ruff_simplificar",
    "ruff_refatorar",
    "ruff_argumentos",
    "ruff_retorno",
]

# -------------------------------------------------------------
# Como o código evoluiu (PyDriller)
# -------------------------------------------------------------
COLUNAS_HISTORICO = [
    "revisoes",
    "autores",
    "churn",
]

# -------------------------------------------------------------
# Grupos opcionais de histórico, ligados no config
# -------------------------------------------------------------
COLUNAS_TEMPORAL = [
    "insercoes",
    "remocoes",
    "idade_dias",
    "dias_desde_anterior",
    "commits_recentes",
    "autores_recentes",
]

COLUNAS_PROPRIEDADE = [
    "fracao_autor_principal",
    "autores_menores",
    "arquivos_por_commit",
]

COLUNAS_COMMIT = [
    "commit_arquivos",
    "commit_pastas",
    "commit_topos",
    "commit_adicionadas",
    "commit_removidas",
    "commit_entropia",
]

# =============================================================
# AS DUAS LISTAS, QUE SÃO COISAS DIFERENTES
# =============================================================

GRUPOS_MEDIDOS = [
    ("MEDIR_COMENTARIOS",  COLUNAS_COMENTARIOS),
    ("MEDIR_HALSTEAD",     COLUNAS_HALSTEAD),
    ("MEDIR_LIZARD_EXTRA", COLUNAS_LIZARD),
    ("MEDIR_AST",          COLUNAS_AST),
    ("MEDIR_RUFF",         COLUNAS_RUFF),
    ("MEDIR_TEMPORAL",     COLUNAS_TEMPORAL),
    ("MEDIR_PROPRIEDADE",  COLUNAS_PROPRIEDADE),
]


# =============================================================
# Colunas Medidas
# -------------------------------------------------------------
# Tudo que o montador grava no CSV, conforme o config
# =============================================================
def colunas_medidas() -> list[str]:
    colunas = list(COLUNAS_CODIGO) + list(COLUNAS_HISTORICO)

    for chave, grupo in GRUPOS_MEDIDOS:
        if getattr(config, chave, False):
            colunas.extend(grupo)

    return colunas


COLUNAS_BASE = colunas_medidas()

FEATURES = (COLUNAS_BASE + derivadas.colunas_ativas(COLUNAS_BASE)
            + COLUNAS_COMMIT)

# =============================================================
# O QUE O MODELO PREVÊ
# =============================================================

COLUNA_ALVO = "defeituoso"

# =============================================================
# COLUNAS QUE NÃO ENTRAM NO MODELO
# =============================================================
COLUNAS_IDENTIFICACAO = [
    "repositorio",
    "arquivo",
    "commit",
    "particao_defectors",
]


COLUNAS_DIAGNOSTICO = [
    "linhas_defeituosas",
]

# -------------------------------------------------------------
# As duas divisões, que são coisas diferentes
# -------------------------------------------------------------

COLUNA_PARTICAO_DEFECTORS = "particao_defectors"

COLUNA_PARTICAO = "particao"

# =============================================================
# A ORDEM DAS COLUNAS NO CSV
# =============================================================

COLUNAS_CSV = (COLUNAS_IDENTIFICACAO
               + COLUNAS_BASE
               + COLUNAS_DIAGNOSTICO
               + [COLUNA_ALVO, COLUNA_PARTICAO])


# =============================================================
# Origem da Feature
# -------------------------------------------------------------
# De onde a informação daquela coluna veio
# =============================================================
def origem_da_feature(coluna: str) -> str:
    nome = coluna[len(derivadas.PREFIXO_PERCENTIL):] \
        if coluna.startswith(derivadas.PREFIXO_PERCENTIL) else coluna

    if nome in COLUNAS_COMMIT:
        return "commit"

    if nome in COLUNAS_CAMINHO_CONHECIDAS:
        return "caminho"

    de_historico = any(p in nome for p in PALAVRAS_DE_HISTORICO)
    de_codigo = any(p in nome for p in PALAVRAS_DE_CODIGO)

    if de_historico and de_codigo:
        return "misto"
    if de_historico:
        return "histórico Git"
    if de_codigo:
        return "código"

    return "outra"

PALAVRAS_DE_HISTORICO = ("revisoes", "autores", "churn", "insercoes",
                         "remocoes", "idade", "dias", "commits_",
                         "autor_principal", "menores", "por_commit")

PALAVRAS_DE_CODIGO = ("linhas", "complexidade", "manutenibilidade",
                      "funcao", "funcoes", "comentarios", "branco",
                      "aninhamento", "tokens", "parametros", "halstead",
                      "todos", "except", "try", "imports", "classes",
                      "decoradores", "global", "ruff")

COLUNAS_CAMINHO_CONHECIDAS = set(derivadas.COLUNAS_CAMINHO)


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

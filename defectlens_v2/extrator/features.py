"""
Contrato das features por commit: as mesmas funções montam a tabela do
treino (Frente 1) e a de um repositório novo (Frente 2).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config


# =============================================================
# COLUNAS MEDIDAS
# =============================================================

COLUNAS_COMMIT = [
    "commit_arquivos",
    "commit_pastas",
    "commit_topos",
    "commit_adicionadas",
    "commit_removidas",
    "commit_entropia",
]

COLUNAS_HISTORICO = [
    "revisoes",
    "autores",
    "churn",
    "insercoes",
    "remocoes",
    "idade_dias",
    "dias_desde_anterior",
    "commits_recentes",
    "autores_recentes",
    "fracao_autor_principal",
    "autores_menores",
    "arquivos_por_commit",
]

COLUNAS_CODIGO = [
    "linhas", "complexidade_media", "complexidade_maxima",
    "manutenibilidade", "maior_funcao", "qtd_funcoes",
    "comentarios", "linhas_em_branco",
    "halstead_volume", "halstead_dificuldade", "halstead_esforco",
    "halstead_bugs",
    "tokens", "parametros_maximo", "parametros_media",
    "aninhamento_maximo", "todos_fixmes", "except_pelado", "qtd_try",
    "qtd_imports", "imports_estrela", "qtd_classes", "qtd_decoradores",
    "qtd_global",
    "ruff_total", "ruff_bugbear", "ruff_seguranca", "ruff_excecao",
    "ruff_simplificar", "ruff_refatorar", "ruff_argumentos", "ruff_retorno",
]

CHAVES = ["repositorio", "commit"]


# =============================================================
# FEATURES POR GRUPO
# -------------------------------------------------------------
# commit: iguais para todos os arquivos do commit.
# historico: do arquivo, até o commit, só com o passado.
# codigo: do arquivo naquele commit; só entra na ablação.
# =============================================================

DERIVADAS_COMMIT = [
    "commit_churn",
    "fracao_adicionadas",
    "churn_por_arquivo",
    "adicionadas_por_arquivo",
    "py_arquivos",
    "fracao_py",
]

DERIVADAS_HISTORICO = [
    "churn_por_revisao",
    "arquivos_relativo",
]

GRUPOS = {
    "commit":    COLUNAS_COMMIT + DERIVADAS_COMMIT,
    "historico": COLUNAS_HISTORICO + DERIVADAS_HISTORICO,
    "codigo":    COLUNAS_CODIGO,
}

FEATURES_MODELO = GRUPOS["commit"] + GRUPOS["historico"]

FEATURES_CRESCENTES = (
    "commit_arquivos",
    "commit_pastas",
    "commit_topos",
    "commit_adicionadas",
    "commit_churn",
)

NOMES_LEGIVEIS = {
    "commit_arquivos":         "arquivos no commit (NF)",
    "commit_pastas":           "pastas no commit (ND)",
    "commit_topos":            "áreas do projeto no commit (NS)",
    "commit_adicionadas":      "linhas adicionadas (LA)",
    "commit_removidas":        "linhas removidas (LD)",
    "commit_entropia":         "dispersão da mudança (entropia)",
    "commit_churn":            "linhas alteradas (LA + LD)",
    "fracao_adicionadas":      "parcela de linhas adicionadas",
    "churn_por_arquivo":       "linhas alteradas por arquivo",
    "adicionadas_por_arquivo": "linhas adicionadas por arquivo",
    "py_arquivos":             "arquivos .py de código no commit",
    "fracao_py":               "parcela de arquivos .py de código",
    "churn_por_revisao":       "linhas alteradas por commit, no arquivo",
    "arquivos_relativo":       "tamanho do commit frente ao costume do arquivo",
    "revisoes":                "commits que alteraram o arquivo (NUC)",
    "autores":                 "autores do arquivo (NDEV)",
    "churn":                   "linhas alteradas na história do arquivo",
    "insercoes":               "linhas inseridas na história do arquivo",
    "remocoes":                "linhas removidas na história do arquivo",
    "idade_dias":              "idade do arquivo em dias",
    "dias_desde_anterior":     "dias desde a mudança anterior (AGE)",
    "commits_recentes":        "commits no arquivo em 90 dias",
    "autores_recentes":        "autores do arquivo em 90 dias",
    "fracao_autor_principal":  "parcela do autor principal",
    "autores_menores":         "autores com pouca participação",
    "arquivos_por_commit":     "tamanho típico dos commits do arquivo",
}

# =============================================================
# ESCOPO
# =============================================================


# =============================================================
# Arquivo no Escopo
# -------------------------------------------------------------
# Se um caminho é um .py de código como os do dataset de treino
# =============================================================
def arquivo_no_escopo(caminho: str) -> bool:
    if not caminho.endswith(".py"):
        return False

    nome = caminho.rsplit("/", 1)[-1]

    if any(caminho.startswith(p) for p in config.PASTAS_IGNORADAS):
        return False
    if nome in config.ARQUIVOS_IGNORADOS:
        return False

    em_pasta_de_teste = ("/tests/" in f"/{caminho}"
                         or "/test/" in f"/{caminho}")

    return not (em_pasta_de_teste or nome.startswith("test_")
                or nome.endswith("_test.py"))


# =============================================================
# No Dominio
# -------------------------------------------------------------
# Marca os commits dentro dos limites em que o rótulo é observável
# =============================================================
def no_dominio(commits: pd.DataFrame) -> pd.Series:
    churn = commits["commit_adicionadas"] + commits["commit_removidas"]

    return ((churn <= config.MAXIMO_LINHAS_COMMIT)
            & (commits["commit_arquivos"] <= config.MAXIMO_ARQUIVOS_COMMIT)
            & (commits["commit_adicionadas"] >= config.MINIMO_ADICIONADAS))


# =============================================================
# Motivo Fora do Dominio
# -------------------------------------------------------------
# Explica por que um commit ficou fora dos limites do rótulo
# =============================================================
def motivo_fora_do_dominio(commit: dict) -> str | None:
    churn = commit["commit_adicionadas"] + commit["commit_removidas"]

    if commit["commit_arquivos"] > config.MAXIMO_ARQUIVOS_COMMIT:
        return (f"mais de {config.MAXIMO_ARQUIVOS_COMMIT} arquivos: o "
                f"Defectors descarta commits desse tamanho")
    if churn > config.MAXIMO_LINHAS_COMMIT:
        return (f"mais de {config.MAXIMO_LINHAS_COMMIT} linhas alteradas: o "
                f"Defectors descarta commits desse tamanho")
    if commit["commit_adicionadas"] < config.MINIMO_ADICIONADAS:
        return "nenhuma linha adicionada: o SZZ só culpa linhas adicionadas"

    return None


# =============================================================
# MONTAGEM DA TABELA
# =============================================================


# =============================================================
# Dividir
# -------------------------------------------------------------
# Divisão que devolve vazio em vez de infinito
# =============================================================
def dividir(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a / b).replace([np.inf, -np.inf], np.nan)


# =============================================================
# Derivar Commit
# -------------------------------------------------------------
# Acrescenta as razões calculadas com as seis medidas do commit
# =============================================================
def derivar_commit(medidas: pd.DataFrame) -> pd.DataFrame:
    medidas = medidas.copy()
    churn = medidas["commit_adicionadas"] + medidas["commit_removidas"]
    arquivos = medidas["commit_arquivos"].clip(lower=1)

    medidas["commit_churn"] = churn
    medidas["fracao_adicionadas"] = (medidas["commit_adicionadas"]
                                     / churn.clip(lower=1))
    medidas["churn_por_arquivo"] = churn / arquivos
    medidas["adicionadas_por_arquivo"] = (medidas["commit_adicionadas"]
                                          / arquivos)
    return medidas


# =============================================================
# Montar Retratos
# -------------------------------------------------------------
# Uma linha por (commit, arquivo .py), com todas as features
# =============================================================
def montar_retratos(medidas_commit: pd.DataFrame,
                    retratos: pd.DataFrame) -> pd.DataFrame:
    tabela = retratos.merge(derivar_commit(medidas_commit), on=CHAVES,
                            how="inner", validate="many_to_one")

    tabela["py_arquivos"] = (tabela.groupby(CHAVES)["arquivo"]
                             .transform("size"))
    tabela["fracao_py"] = (tabela["py_arquivos"]
                           / tabela["commit_arquivos"].clip(lower=1))
    tabela["churn_por_revisao"] = (tabela["churn"]
                                   / tabela["revisoes"].clip(lower=1))
    tabela["arquivos_relativo"] = dividir(
        tabela["commit_arquivos"],
        tabela["arquivos_por_commit"].clip(lower=1))

    return tabela


# =============================================================
# Resumir Por Commit
# -------------------------------------------------------------
# Uma linha por commit, com as colunas iguais em todos os arquivos
# =============================================================
def resumir_por_commit(retratos: pd.DataFrame,
                       colunas: list[str]) -> pd.DataFrame:
    return (retratos.drop_duplicates(CHAVES)[CHAVES + colunas]
            .reset_index(drop=True))


# =============================================================
# Agregar Nota
# -------------------------------------------------------------
# A nota do commit é a maior entre os arquivos .py que ele alterou
# =============================================================
def agregar_nota(retratos: pd.DataFrame, nota: np.ndarray) -> pd.Series:
    return (retratos[CHAVES].assign(nota=np.asarray(nota, dtype=float))
            .groupby(CHAVES, sort=False)["nota"].max())


# =============================================================
# Nome Legivel
# -------------------------------------------------------------
# Traduz o nome de uma feature para o texto dos gráficos e do site
# =============================================================
def nome_legivel(feature: str) -> str:
    return NOMES_LEGIVEIS.get(feature, feature)


# =============================================================
# Grupo da Feature
# -------------------------------------------------------------
# De qual grupo de medidas a feature veio
# =============================================================
def grupo_da_feature(feature: str) -> str:
    for nome, colunas in GRUPOS.items():
        if feature in colunas:
            return nome

    return "outro"

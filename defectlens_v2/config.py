"""
Parâmetros do DefectLens v2: caminhos, domínio do rótulo, avaliação e site.
"""

from pathlib import Path


# =============================================================
# CAMINHOS
# =============================================================

RAIZ = Path(__file__).resolve().parent

RAIZ_ORIGINAL = RAIZ.parent

PASTA_DADOS_ORIGINAIS = RAIZ_ORIGINAL / "dados"
ARQUIVO_DATASET_ORIGINAL = PASTA_DADOS_ORIGINAIS / "dataset.csv"
PASTA_COMMITS_ORIGINAIS = PASTA_DADOS_ORIGINAIS / "commits"
PASTA_VALIDACAO_ORIGINAL = PASTA_DADOS_ORIGINAIS / "validacao_repos"
PASTA_DEFECTORS = (RAIZ_ORIGINAL / "defectors" / "line_bug_prediction_splits"
                   / "time")

PASTA_DADOS = RAIZ / "dados"
ARQUIVO_RETRATOS = PASTA_DADOS / "retratos_dataset.csv"
ARQUIVO_COMMITS = PASTA_DADOS / "commits_dataset.csv"
ARQUIVO_DATAS = PASTA_DADOS / "datas_defectors.csv"

PASTA_RESULTADOS = RAIZ / "resultados"
PASTA_PREVISOES = PASTA_RESULTADOS / "previsoes_loro"
PASTA_PERMUTACAO = PASTA_RESULTADOS / "permutacao_loro"
PASTA_GRAFICOS = PASTA_RESULTADOS / "graficos"
PASTA_PILOTO = PASTA_RESULTADOS / "piloto"
ARQUIVO_RELATORIO = PASTA_RESULTADOS / "relatorio.html"

PASTA_MODELOS = RAIZ / "modelos"
ARQUIVO_MODELO = PASTA_MODELOS / "modelo_v2.joblib"
ARQUIVO_RESUMO_MODELO = PASTA_MODELOS / "resumo_modelo.json"

PASTA_CLONES = RAIZ / "clones"


# =============================================================
# DOMÍNIO DO RÓTULO
# -------------------------------------------------------------
# O Defectors descarta commits causadores com mais de 1000 linhas
# alteradas ou mais de 100 arquivos (artigo, seção III-D), e o SZZ
# só culpa linhas adicionadas. Fora desses limites o rótulo é
# "limpo" por construção, e não por observação.
# =============================================================

MAXIMO_LINHAS_COMMIT = 1000
MAXIMO_ARQUIVOS_COMMIT = 100
MINIMO_ADICIONADAS = 1


# =============================================================
# PARTIÇÕES DO DEFECTORS
# -------------------------------------------------------------
# train foi reamostrada para perto de 1:1; test e val mantêm a
# proporção original (artigo, seção III-F).
# =============================================================

PARTICOES_TREINO = ("train",)
PARTICOES_NATURAIS = ("test", "val")


# =============================================================
# ESCOPO DOS ARQUIVOS
# =============================================================

PASTAS_IGNORADAS = (
    "docs/",
    "doc/",
    "examples/",
    "benchmarks/",
    "profiling/",
)

ARQUIVOS_IGNORADOS = (
    "setup.py",
    "conftest.py",
    "_version.py",
    "versioneer.py",
)

JANELA_RECENTE_DIAS = 90

FRACAO_AUTOR_MENOR = 0.05


# =============================================================
# AVALIAÇÃO
# =============================================================

SEMENTE = 42

MINIMO_COMMITS_REPO = 30

MINIMO_POSITIVOS_NATURAIS = 10

FRACAO_ESFORCO = 0.20

FRACOES_TOPO = (0.10, 0.20)

METRICA_PRINCIPAL = "auc"

METODO_PRINCIPAL = "modelo_v2"

METODO_REFERENCIA = "la"

METODO_ORIGINAL = "original"

PROCESSOS = 4

REPETICOES_PERMUTACAO = 5

FAIXAS_CALIBRACAO = 10


# =============================================================
# MODELO
# =============================================================

PARAMETROS_MODELO = {
    "max_iter": 400,
    "learning_rate": 0.04,
    "max_leaf_nodes": 15,
    "min_samples_leaf": 80,
    "l2_regularization": 1.0,
    "random_state": SEMENTE,
}

COMPRESSAO_DO_MODELO = 3


# =============================================================
# FRENTE 2
# =============================================================

LIMITE_REPOSITORIO_MB = 600

LIMITE_COMMITS = 150_000

SEGUNDOS_DE_CLONE = 900

JANELA_REVISAO_DIAS = 90

MINIMO_COMMITS_NA_JANELA = 30

MAXIMO_COMMITS_NA_RESPOSTA = 200

MAXIMO_COMMITS_GUARDADOS = 5000

ARQUIVOS_EM_DESTAQUE = 25


# =============================================================
# REPOSITÓRIOS DO PILOTO DE PARIDADE
# =============================================================

REPOSITORIOS_PILOTO = {
    "black":                 "psf/black",
    "poetry":                "python-poetry/poetry",
    "django-rest-framework": "encode/django-rest-framework",
    "scrapy":                "scrapy/scrapy",
}

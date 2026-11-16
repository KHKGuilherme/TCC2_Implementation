"""
Parâmetros do DefectLens v3: defeito latente por arquivo no estado atual do repositório.
"""

import os
from pathlib import Path


# =============================================================
# CAMINHOS
# =============================================================
RAIZ = Path(__file__).resolve().parent
RAIZ_TCC = RAIZ.parent

PASTA_DADOS = RAIZ / "dados"
PASTA_HISTORICO = PASTA_DADOS / "historico"
PASTA_RETRATOS = PASTA_DADOS / "retratos"
PASTA_VALIDACAO = PASTA_DADOS / "validacao"
PASTA_RESULTADOS = RAIZ / "resultados"
PASTA_MODELOS = RAIZ / "modelos"
PASTA_CLONES = Path(os.environ.get("DEFECTLENS_CLONES", RAIZ / "clones"))

ARQUIVO_MODELO = PASTA_MODELOS / "modelo_v3.joblib"
ARQUIVO_RESUMO = PASTA_MODELOS / "resumo_modelo.json"
ARQUIVO_INTERVALOS = PASTA_DADOS / "intervalos_defeito.csv.gz"
ARQUIVO_PREVISOES = PASTA_DADOS / "previsoes_loro.csv.gz"

DATASET_ORIGINAL = RAIZ_TCC / "dados" / "dataset.csv"


# =============================================================
# REPOSITÓRIOS DO DEFECTORS
# =============================================================
NOMES_NO_GITHUB = {
    "airflow":               "apache/airflow",
    "ansible":               "ansible/ansible",
    "black":                 "psf/black",
    "celery":                "celery/celery",
    "core":                  "home-assistant/core",
    "cpython":               "python/cpython",
    "django":                "django/django",
    "django-rest-framework": "encode/django-rest-framework",
    "freqtrade":             "freqtrade/freqtrade",
    "jax":                   "jax-ml/jax",
    "lightning":             "Lightning-AI/pytorch-lightning",
    "localstack":            "localstack/localstack",
    "numpy":                 "numpy/numpy",
    "pandas":                "pandas-dev/pandas",
    "pipenv":                "pypa/pipenv",
    "poetry":                "python-poetry/poetry",
    "ray":                   "ray-project/ray",
    "redash":                "getredash/redash",
    "scikit-learn":          "scikit-learn/scikit-learn",
    "scrapy":                "scrapy/scrapy",
    "sentry":                "getsentry/sentry",
    "spaCy":                 "explosion/spaCy",
    "transformers":          "huggingface/transformers",
    "yolov5":                "ultralytics/yolov5",
}

REPOSITORIOS_SEM_ROTULO = ("freqtrade",)


# =============================================================
# RÓTULO DE DEFEITO LATENTE
# =============================================================
FIM_DEFECTORS = "2022-11-01"

PRIMEIRO_RETRATO = "2012-01-01"

FIM_RETRATOS = "2026-07-01"

HORIZONTES_DIAS = (180, 365, 730, 0)

HORIZONTE_PRINCIPAL = 730

ROTULO = f"latente_{HORIZONTE_PRINCIPAL}"

ULTIMO_RETRATO_ROTULADO = "2020-07-01"

MESES_ENTRE_RETRATOS = 6

PASTAS_FORA_DO_ESCOPO = ("test", "tests", "testing", "docs", "doc", "examples", "benchmarks",
                         "profiling", "vendor", "_vendor", "vendored", "patched", "third_party")

ARQUIVOS_FORA_DO_ESCOPO = ("setup.py", "conftest.py", "_version.py", "versioneer.py")


# =============================================================
# FEATURES
# =============================================================
JANELAS_DIAS = (30, 90, 180, 365)


# =============================================================
# MODELO
# =============================================================
SEMENTE = 42

VARIANTE_FINAL = os.environ.get("DEFECTLENS_VARIANTE", "posicao")

CALIBRACAO_FINAL = "platt"

MAXIMO_RETRATOS_POR_REPO = 60000

MINIMO_ARQUIVOS_RETRATO = 30

PRECISAO_MINIMA = 0.5

REGRA_LIMIAR = "f1"

PROCESSOS = 6


# =============================================================
# PREDIÇÃO E SITE
# =============================================================
TAMANHO_MAXIMO_REPO_KB = int(os.environ.get("DEFECTLENS_MAX_KB", 400_000))

SEGUNDOS_MAXIMOS_CLONE = int(os.environ.get("DEFECTLENS_MAX_CLONE_S", 600))

MAXIMO_ARQUIVOS_NA_RESPOSTA = 3000

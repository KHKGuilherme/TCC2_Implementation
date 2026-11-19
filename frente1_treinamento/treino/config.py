import os
from pathlib import Path


RAIZ = Path(__file__).resolve().parent.parent
RAIZ_REPOSITORIO = RAIZ.parent

PASTA_DATASETS = Path(os.environ.get("DEFECTLENS_DATASETS", RAIZ_REPOSITORIO / "datasets"))
PASTA_HISTORICO = PASTA_DATASETS / "historico"
PASTA_RETRATOS = PASTA_DATASETS / "retratos"
DATASET_ORIGINAL = PASTA_DATASETS / "medidas_de_codigo" / "dataset.csv"

PASTA_CONTRATOS = RAIZ_REPOSITORIO / "contratos"

PASTA_SAIDA = RAIZ / "saida"
PASTA_VALIDACAO = PASTA_SAIDA / "validacao"
PASTA_RESULTADOS = PASTA_SAIDA / "resultados"
PASTA_MODELO = PASTA_SAIDA / "modelo_v3"
PASTA_CLONES = Path(os.environ.get("DEFECTLENS_CLONES", RAIZ / "clones"))

ARQUIVO_MODELO = PASTA_MODELO / "modelo.joblib"
ARQUIVO_MANIFESTO = PASTA_MODELO / "manifesto.json"

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

JANELAS_DIAS = (30, 90, 180, 365)

SEMENTE = 42
VARIANTE_FINAL = os.environ.get("DEFECTLENS_VARIANTE", "posicao")
CALIBRACAO_FINAL = "platt"
MAXIMO_RETRATOS_POR_REPO = 60000
MINIMO_ARQUIVOS_RETRATO = 30
PRECISAO_MINIMA = 0.5
REGRA_LIMIAR = "f1"
PROCESSOS = 6

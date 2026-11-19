"""
Arquivo Responsável para Definir Parâmetros do Projeto
"""

from pathlib import Path


# =============================================================
# CAMINHOS
# =============================================================
PASTA_DADOS = Path("dados")
PASTA_MODELOS = Path("modelos")
PASTA_CLONES = Path("clones")
PASTA_DEFECTORS = Path("defectors")

ARQUIVO_DATASET = PASTA_DADOS / "dataset.csv"

PASTA_PARCIAIS = PASTA_DADOS / "parciais"

PASTA_COMMITS = PASTA_DADOS / "commits"

ARQUIVO_MODELO = PASTA_MODELOS / "modelo.joblib"

ARQUIVO_PREVISOES = PASTA_DADOS / "previsoes.csv"

ARQUIVO_RISCO = PASTA_DADOS / "risco_por_arquivo.csv"

PASTA_VALIDACAO_REPOS = PASTA_DADOS / "validacao_repos"
ARQUIVO_VALIDACAO_REPOS = PASTA_DADOS / "resultado_por_repositorio.csv"

ARQUIVO_RESUMO_PROJETO_NOVO = PASTA_DADOS / "resumo_projeto_novo.json"

ARQUIVO_CORRELACAO = PASTA_DADOS / "correlacao_spearman.csv"
ARQUIVO_CORRELACAO_PEARSON = PASTA_DADOS / "correlacao_pearson.csv"
ARQUIVO_MAPA_DE_CALOR = PASTA_DADOS / "mapa_de_calor.png"

ARQUIVO_GRAFICO_IMPORTANCIA = PASTA_DADOS / "grafico_importancia.png"
ARQUIVO_GRAFICO_PERMUTACAO = PASTA_DADOS / "grafico_permutacao.png"
ARQUIVO_GRAFICO_ARVORE = PASTA_DADOS / "grafico_arvore.png"


# =============================================================
# ESTRUTURA DO DEFECTORS
# =============================================================

SUBPASTA_DEFECTORS = "line_bug_prediction_splits"

ESQUEMA_DEFECTORS = "time"


# =============================================================
# CHAVES DE CONTROLE
# =============================================================

FORCAR_MONTAGEM = False

APAGAR_CLONES = True

EXIGIR_TODOS_OS_REPOSITORIOS = True

REPOSITORIOS_PULADOS = ("openpilot",)

HISTORICO_RAPIDO = True

SEGUNDOS_ENTRE_PONTOS = 120

APAGAR_SEPARADO = True


# =============================================================
# DE QUAL ENDEREÇO CADA PROJETO É CLONADO
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
    "openpilot":             "commaai/openpilot",
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


# =============================================================
# ESCOPO DOS DADOS
# =============================================================

REPOSITORIOS_INCLUIDOS = ()


# =============================================================
# AMOSTRA PILOTO
# =============================================================

TAMANHO_AMOSTRA = 0


# =============================================================
# COMO O CONJUNTO DE TESTE É RESERVADO
# =============================================================

ESTRATEGIA_DIVISAO = "group_shuffle_split"

REPOSITORIOS_TESTE = (
    "redash",
    "black",
)

FRACAO_TESTE = 0.30


# =============================================================
# COMO OS MODELOS SÃO COMPARADOS DENTRO DO TREINO
# =============================================================

ESTRATEGIA_VALIDACAO = "group_kfold"

DOBRAS_VALIDACAO = 5

MODELO_FINAL = "Gradient Boosting"

PROCESSOS_VALIDACAO_REPOS = 12

MINIMO_ARQUIVOS_REPO = 30


# =============================================================
# PARÂMETROS DA MONTAGEM
# =============================================================

SEMENTE = 42

LINHAS_POR_LOTE = 2000

TAMANHO_MAXIMO_BYTES = 262_144

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


# =============================================================
# GRUPOS DE MÉTRICAS MEDIDAS
# =============================================================


MEDIR_COMENTARIOS = True

MEDIR_HALSTEAD = True

MEDIR_LIZARD_EXTRA = True

MEDIR_AST = True

MEDIR_RUFF = True


MEDIR_TEMPORAL = True

MEDIR_PROPRIEDADE = True

JANELA_RECENTE_DIAS = 90

JANELA_REVISAO_DIAS = 90

COMMITS_PARA_REVISAR = 20

FRACAO_AUTOR_MENOR = 0.05


# =============================================================
# FEATURES DERIVADAS
# =============================================================

USAR_RAZOES = True
USAR_DESEQUILIBRIO = True
USAR_PERCENTIL = True
USAR_CAMINHO = True

PERCENTIL_SO_NAS_BASICAS = True

COLUNAS_COM_PERCENTIL = (
    "linhas", "complexidade_media", "complexidade_maxima",
    "manutenibilidade", "maior_funcao", "qtd_funcoes",
    "revisoes", "autores", "churn",
    "tokens", "halstead_volume", "aninhamento_maximo",
    "insercoes", "remocoes", "commits_recentes", "ruff_total",
)


# =============================================================
# PRÉ-PROCESSAMENTO
# =============================================================

FRACAO_MAXIMA_FALTANTE = 0.5

CORRELACAO_ALTA = 0.8

TOPO_PARES = 15

MAXIMO_ANOTADO = 16


# =============================================================
# BALANCEAMENTO DAS CLASSES
# =============================================================

BALANCEAR_TREINO = False

ESTRATEGIA_BALANCEAMENTO = "replicar"


# =============================================================
# PARÂMETROS DO TREINO
# =============================================================

PARTICOES_MADURAS = ("train",)

LIMIAR_DECISAO = 0.6

MINIMO_POR_FOLHA = 50

COMPRESSAO_DO_MODELO = 3


# =============================================================
# GRÁFICOS DO MODELO
# =============================================================

GERAR_GRAFICOS = True

PROFUNDIDADE_DO_GRAFICO = 3

GERAR_PERMUTACAO = True
AMOSTRA_PERMUTACAO = 20_000
REPETICOES_PERMUTACAO = 5

TOPO_RANKING = 20

TOPOS_AVALIADOS = (10, 50, 100, 500)

FRACOES_POR_REPOSITORIO = (0.1, 0.2)


# =============================================================
# Conferir Local
# -------------------------------------------------------------
# Valida que o programa roda na pasta certa
# =============================================================
def conferir_local() -> None:
    if not Path("extrator").is_dir():
        raise SystemExit(
            "Rode os comandos de dentro da pasta do projeto.\n"
            "Exemplo: cd TCC2 && python frente1_treinamento/principal.py"
        )


# =============================================================
# Conferir Nomes
# -------------------------------------------------------------
# Valida os nomes de repositório escolhidos
# =============================================================
def conferir_nomes() -> None:
    escolhidos = tuple(REPOSITORIOS_INCLUIDOS) + tuple(REPOSITORIOS_TESTE)
    desconhecidos = [n for n in escolhidos if n not in NOMES_NO_GITHUB]

    if desconhecidos:
        raise SystemExit(
            f"Nome de repositório que o dataset não usa: "
            f"{', '.join(desconhecidos)}\n"
            f"O Defectors guarda o nome simples, sem o dono. "
            f"Rode --listar para ver os nomes exatos."
        )

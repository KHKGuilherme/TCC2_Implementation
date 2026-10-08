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
# PASTA_DEFECTORS = Path("defectors")
PASTA_DEFECTORS = Path("defectors_amostra")
# O dataset completo
ARQUIVO_DATASET = PASTA_DADOS / "dataset.csv"

# Progresso salvo da montagem. Uma subpasta por configuração.
PASTA_PARCIAIS = PASTA_DADOS / "parciais"

# O modelo treinado
ARQUIVO_MODELO = PASTA_MODELOS / "modelo.joblib"


# =============================================================
# ESTRUTURA DO DEFECTORS
# =============================================================

# Qual das duas tarefas do dataset usar.
#
#   line_bug_prediction_splits -> 'content' é o arquivo. É esta.
#   jit_bug_prediction_splits  -> 'content' é o diff do commit.
#
# As duas têm as MESMAS colunas, então a escolha é pelo caminho.
SUBPASTA_DEFECTORS = "line_bug_prediction_splits"

# Qual divisão do dataset ler.
#
#   time   -> treino nos commits antigos, teste nos recentes
#   random -> divisão aleatória
#
# As duas contêm as mesmas linhas. O programa lê só uma.
ESQUEMA_DEFECTORS = "time"


# =============================================================
# CHAVES DE CONTROLE
# =============================================================

# Montar Dataset independente de já possuir um
FORCAR_MONTAGEM = False

# Quando True, os clones são apagados logo depois de cada repositório ser processado.
APAGAR_CLONES = True


# =============================================================
# DE QUAL ENDEREÇO CADA PROJETO É CLONADO
# =============================================================

# O Defectors guarda o repositório pelo nome simples ('celery'),
# e não pelo caminho do GitHub ('celery/celery'). A Fase 2
# precisa do caminho completo para clonar, então a tradução é
# feita aqui.
#
# São os 25 projetos do dataset, com os 25 endereços conferidos.
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

# Tupla vazia -> todos os 25 projetos.
# Os de REPOSITORIOS_TESTE entram sempre.
#
# Os nomes são os que o dataset usa: simples, sem o dono.
# Use --listar para ver os nomes exatos e quantas linhas cada um
# tem.
#
# Esta seleção é a do experimento piloto: com REPOSITORIOS_TESTE
# são seis projetos de clone leve, para a Fase 2 caber num
# notebook. Os pesados (cpython, pandas, ansible, sentry, core)
# ficam para a rodada final.
REPOSITORIOS_INCLUIDOS = (
    "poetry",
    "scrapy",
    "django-rest-framework",
    "pipenv",
)


# =============================================================
# AMOSTRA PILOTO
# =============================================================

# 0 -> dataset inteiro. Maior que 0 -> monta só essa quantidade
# de linhas, sorteadas de forma estratificada por repositório e
# rótulo.
#
# São linhas reais com rótulo real. O sorteio acontece ANTES de
# medir, então a Fase 1 mede mil arquivos em vez de 213 mil.
TAMANHO_AMOSTRA = 0


# =============================================================
# COMO O CONJUNTO DE TESTE É RESERVADO
# =============================================================

# Cada opção tem o nome da função do scikit-learn que chama:
#
#   "defectors"            -> usa a divisão que já vem no dataset
#   "por_repositorio"      -> reserva projetos inteiros
#   "train_test_split"     -> train_test_split, estratificado
#   "group_shuffle_split"  -> GroupShuffleSplit, por arquivo
#   "sem_reserva"          -> nada reservado, tudo é treino
#
# Trocar não exige remontar o dataset.
ESTRATEGIA_DIVISAO = "por_repositorio"

# Usado apenas por "por_repositorio".
#
# Estes dois somam cerca de 30% das linhas dos seis projetos
# selecionados, então a reserva sai perto de FRACAO_TESTE sem
# precisar sortear nada.
REPOSITORIOS_TESTE = (
    "redash",
    "black",
)

# Usado por "train_test_split" e "group_shuffle_split"
FRACAO_TESTE = 0.30


# =============================================================
# COMO OS MODELOS SÃO COMPARADOS DENTRO DO TREINO
# =============================================================

# Decisão independente da anterior. Aqui são as dobras formadas
# DENTRO do treino, para escolher o modelo.
#
#   "leave_one_group_out" -> LeaveOneGroupOut, por repositório
#   "group_kfold"         -> GroupKFold, por arquivo
#   "stratified_kfold"    -> StratifiedKFold, o padrão do sklearn
ESTRATEGIA_VALIDACAO = "leave_one_group_out"

# Dobras de "group_kfold" e "stratified_kfold"
DOBRAS_VALIDACAO = 5


# =============================================================
# PARÂMETROS DA MONTAGEM
# =============================================================

# Semente de todo sorteio. Fixa para o resultado ser reproduzível.
SEMENTE = 42

# Linhas lidas de uma vez do parquet
LINHAS_POR_LOTE = 2000

# Acima disso não é código escrito à mão, é dado gerado
TAMANHO_MAXIMO_BYTES = 262_144  # 256 KB

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
# PARÂMETROS DO TREINO
# =============================================================

# Probabilidade a partir da qual o arquivo é marcado como defeituoso
LIMIAR_DECISAO = 0.5


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
    # O erro que isto pega: escrever 'numpy/numpy' onde o dataset
    # guarda 'numpy'. Sem esta conferência o projeto simplesmente
    # sai do escopo, a amostra fica vazia e a causa não aparece.
    escolhidos = tuple(REPOSITORIOS_INCLUIDOS) + tuple(REPOSITORIOS_TESTE)
    desconhecidos = [n for n in escolhidos if n not in NOMES_NO_GITHUB]

    if desconhecidos:
        raise SystemExit(
            f"Nome de repositório que o dataset não usa: "
            f"{', '.join(desconhecidos)}\n"
            f"O Defectors guarda o nome simples, sem o dono. "
            f"Rode --listar para ver os nomes exatos."
        )
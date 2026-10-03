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

# O dataset completo
ARQUIVO_DATASET = PASTA_DADOS / "dataset.csv"

# Resultados por repositório, gravados durante a montagem. Permite retomar o trabalho de onde parou.
PASTA_PARCIAIS = PASTA_DADOS / "parciais"

# O modelo treinado
ARQUIVO_MODELO = PASTA_MODELOS / "modelo.joblib"


# =============================================================
# CHAVES DE CONTROLE
# =============================================================

# Montar Dataset independente de já possuir um
FORCAR_MONTAGEM = False

# Quando True, os clones são apagados logo depois de cada repositório ser processado.

APAGAR_CLONES = True


# =============================================================
# ESCOPO DOS DADOS
# =============================================================
REPOSITORIOS_INCLUIDOS = (
    "numpy/numpy",
    "django/django",
    "scrapy/scrapy",
    "explosion/spaCy",
    "poetry",
    "localstack/localstack",
)


# =============================================================
# COMO O CONJUNTO DE TESTE É RESERVADO
# =============================================================

# Estratégia de divisão entre treino e teste. Uma de:
#
#   "por_repositorio"  reserva repositórios inteiros, nomeados em
#                      REPOSITORIOS_TESTE. É a mais severa e a que
#                      corresponde ao uso real da ferramenta, que
#                      recebe a URL de um projeto inédito.
#
#   "aleatoria"        sorteia FRACAO_TESTE das linhas, mantendo a
#                      proporção de defeituosos nos dois lados.
#                      É o train_test_split padrão do scikit-learn.
#                      Dá o resultado mais otimista, porque arquivos
#                      do mesmo projeto ficam dos dois lados.
#
#   "por_arquivo"      sorteia FRACAO_TESTE dos arquivos, não das
#                      linhas. Dois retratos do mesmo arquivo nunca
#                      caem em lados diferentes, mas projetos
#                      continuam misturados. Fica entre as duas
#                      anteriores.
#
#   "sem_reserva"      não reserva nada; tudo é treino. Use quando
#                      a avaliação vai ser feita só por validação
#                      cruzada, sem conjunto separado.
#
# Trocar esta chave NÃO exige remontar o dataset: a divisão é
# recalculada na hora de treinar.
ESTRATEGIA_DIVISAO = "por_repositorio"

# Repositórios reservados. Usado apenas quando a estratégia é "por_repositorio".
REPOSITORIOS_TESTE = (
    "celery/celery",
    "google/jax",
    "psf/black",
)

# Proporção reservada para teste. Usado pelas estratégias "aleatoria" e "por_arquivo".
FRACAO_TESTE = 0.30


# =============================================================
# COMO OS MODELOS SÃO COMPARADOS DENTRO DO TREINO
# =============================================================

# Esta decisão é independente da anterior. A divisão acima separa
# o conjunto que só será tocado no fim; esta aqui diz como as
# dobras são formadas DENTRO do treino para escolher o modelo.
#
#   "por_repositorio"  treina em todos os repositórios menos um e
#                      testa no que sobrou, repetindo para cada um.
#                      Exige pelo menos dois repositórios no treino.
#   
#   "por_arquivo"      GroupKFold agrupando por arquivo. Nenhum
#                      arquivo aparece em duas dobras.
#
#   "estratificada"    StratifiedKFold, o padrão do scikit-learn.
#                      Mantém a proporção de defeituosos em cada
#                      dobra, mas permite que retratos do mesmo
#                      arquivo caiam em dobras diferentes, o que
#                      deixa o resultado otimista.
#
# Se "por_repositorio" for pedido e houver só um repositório no
# treino, o programa avisa e usa "por_arquivo".
ESTRATEGIA_VALIDACAO = "por_repositorio"

# Número de dobras das estratégias "por_arquivo" e "estratificada".
DOBRAS_VALIDACAO = 5


# =============================================================
# PARÂMETROS DA MONTAGEM
# =============================================================

# Seed
SEMENTE = 42

# Quantas linhas do parquet são lidas de uma vez.
LINHAS_POR_LOTE = 2000

# Arquivos maiores que isto são ignorados.
TAMANHO_MAXIMO_BYTES = 262_144  # 256 KB

# Pastas cujo conteúdo não é código de produção.
PASTAS_IGNORADAS = (
    "docs/",
    "doc/",
    "examples/",
    "benchmarks/",
    "profiling/",
)

# Arquivos de empacotamento e configuração. Mudam por motivo administrativo, não por defeito no código.
ARQUIVOS_IGNORADOS = (
    "setup.py",
    "conftest.py",
    "_version.py",
    "versioneer.py",
)


# =============================================================
# PARÂMETROS DO TREINO
# =============================================================
LIMIAR_DECISAO = 0.5


# =============================================================
# Validar Endereço do Program
# =============================================================
def conferir_local() -> None:
    if not Path("extrator").is_dir():
        raise SystemExit(
            "Erro ao definir endereço.\n"
        )
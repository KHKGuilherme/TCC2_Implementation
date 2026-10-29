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

# Progresso salvo da montagem. Uma subpasta por configuração.
PASTA_PARCIAIS = PASTA_DADOS / "parciais"

# O modelo treinado
ARQUIVO_MODELO = PASTA_MODELOS / "modelo.joblib"

# A probabilidade de defeito de cada par (arquivo, commit) do
# conjunto reservado
ARQUIVO_PREVISOES = PASTA_DADOS / "previsoes.csv"

# O mesmo, agregado por arquivo: é esta a saída que responde
# "quanto este arquivo é arriscado"
ARQUIVO_RISCO = PASTA_DADOS / "risco_por_arquivo.csv"

# Saídas do pré-processamento
ARQUIVO_CORRELACAO = PASTA_DADOS / "correlacao_spearman.csv"
ARQUIVO_CORRELACAO_PEARSON = PASTA_DADOS / "correlacao_pearson.csv"
ARQUIVO_MAPA_DE_CALOR = PASTA_DADOS / "mapa_de_calor.png"

# Gráficos do modelo treinado
ARQUIVO_GRAFICO_IMPORTANCIA = PASTA_DADOS / "grafico_importancia.png"
ARQUIVO_GRAFICO_PERMUTACAO = PASTA_DADOS / "grafico_permutacao.png"
ARQUIVO_GRAFICO_ARVORE = PASTA_DADOS / "grafico_arvore.png"


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

# Quando True, um dataset que não tem todos os repositórios é
# tratado como incompleto, e a montagem roda de novo para tentar
# os que faltam.
#
# Desligue quando algum projeto falhar sempre — repositório
# removido do GitHub, por exemplo — e você quiser treinar com o
# que já tem. O relatório continua dizendo quais ficaram de fora.
EXIGIR_TODOS_OS_REPOSITORIOS = True

# Quando True, o parquet separado de cada repositório é apagado
# depois que o CSV daquele projeto está gravado.
#
# Desligue para poder remedir o código de um projeto sem reler os
# parquets grandes; o custo é manter em disco uma segunda cópia do
# recorte do Defectors que está em uso.
APAGAR_SEPARADO = True


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
# Tupla vazia: os 25 projetos, que é o dataset completo.
#
# Cabe num notebook porque a montagem trata um projeto por vez e
# apaga o clone antes de passar ao próximo. O que não cabe é o
# tempo: são horas. Mas o CSV de cada projeto fica gravado, então
# dá para rodar em pedaços, fechar, e continuar depois.
#
# Para voltar ao piloto, liste alguns nomes aqui. Exemplo de uma
# seleção de clone leve:
#
#   ("poetry", "scrapy", "django-rest-framework", "pipenv",
#    "black", "redash")
REPOSITORIOS_INCLUIDOS = ()


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
#
# O padrão é "group_shuffle_split", que sorteia ARQUIVOS: todos os
# retratos de um arquivo caem do mesmo lado, mas projetos ficam
# misturados entre treino e teste.
#
# Isso mede uma pergunta diferente de "por_repositorio", e é
# importante não confundir as duas na monografia:
#
#   group_shuffle_split -> "neste projeto que eu conheço, quais
#                           arquivos são arriscados?"
#   por_repositorio     -> "num projeto que eu nunca vi, quais
#                           arquivos são arriscados?"
#
# A primeira é mais fácil, e o AUC dela é mais alto. Não é
# vazamento: o modelo não vê o arquivo que vai julgar. Mas ele vê
# as convenções do projeto, e isso ajuda.
#
# Vale rodar as duas e relatar as duas.
ESTRATEGIA_DIVISAO = "group_shuffle_split"

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
#
# "group_kfold" acompanha a divisão por arquivo. Nenhum arquivo
# aparece em duas dobras, que é o agrupamento que importa aqui: a
# mesma linha de código entra no dataset em vários commits, com
# métricas quase idênticas, e sem agrupar por arquivo o modelo
# seria testado em cópias do que acabou de treinar.
#
# É por essa razão que "stratified_kfold" não é o padrão, apesar
# de ser o costume do scikit-learn para classificação: ele
# estratifica o rótulo mas não agrupa nada.
ESTRATEGIA_VALIDACAO = "group_kfold"

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
# GRUPOS DE MÉTRICAS MEDIDAS
# =============================================================

# Ligar ou desligar qualquer um destes MUDA O DATASET, porque são
# colunas gravadas no CSV. A montagem detecta a mudança pela
# assinatura e usa uma pasta de parciais própria, então nada se
# mistura — mas a medição tem de ser refeita.
#
# As de código custam uma releitura dos parquets: minutos.
# As de histórico custam reclonar os repositórios: horas.

# --- Código: saem do próprio arquivo, sem clone ---

# Comentários e linhas em branco, do radon.raw
MEDIR_COMENTARIOS = True

# Volume, dificuldade e esforço de Halstead. Baratas, mas muito
# correlacionadas com tamanho: espere pouco.
MEDIR_HALSTEAD = True

# Tokens e número de parâmetros, do Lizard
MEDIR_LIZARD_EXTRA = True

# Aninhamento, TODO/FIXME, except pelado, imports e classes.
# Sai da árvore sintática, sem dependência nova.
MEDIR_AST = True

# Contagens de violação por categoria do ruff.
#
# Exige `pip install ruff`. Se ele não estiver instalado, as
# colunas ficam vazias e um aviso aparece — a montagem não quebra.
#
# Custa cerca de 8 ms por arquivo distinto. No dataset completo
# são uns 15 minutos, e bem menos na prática porque o mesmo
# conteúdo aparece em vários commits e fica em cache.
MEDIR_RUFF = True

# --- Histórico: exigem clonar o repositório ---

# Inserções e remoções separadas, idade do arquivo, intervalo
# entre mudanças e atividade na janela recente.
#
# A literatura é consistente: atividade RECENTE prevê melhor que
# atividade acumulada. O churn total de um arquivo de 10 anos diz
# pouco; o churn dos últimos meses diz muito.
MEDIR_TEMPORAL = True

# Concentração do trabalho entre os autores (Bird et al., "Don't
# touch my code!"): arquivo com muitos contribuidores ocasionais
# tem mais defeito que arquivo com dono claro.
MEDIR_PROPRIEDADE = True

# Tamanho da janela de "atividade recente", em dias
JANELA_RECENTE_DIAS = 90

# Abaixo desta fração das mudanças, o autor conta como ocasional
FRACAO_AUTOR_MENOR = 0.05


# =============================================================
# FEATURES DERIVADAS
# =============================================================

# Grupos de features calculadas a partir das 9 medidas. Ligar ou
# desligar NÃO exige remontar o dataset: elas são recalculadas a
# cada treino, em segundos.
#
# Ligue um de cada vez e compare o AUC. A tabela "Contribuição de
# cada grupo de features" mede exatamente isso, e cada linha dela
# é um resultado para a monografia — inclusive as que não
# melhorarem.
#
#   razões        -> divide pelo tamanho (churn por revisão, etc.)
#   desequilíbrio -> a pior função contra a média delas
#   percentil     -> posição do arquivo dentro do próprio projeto
#   caminho       -> profundidade, é teste, é __init__
USAR_RAZOES = True
USAR_DESEQUILIBRIO = True
USAR_PERCENTIL = True
USAR_CAMINHO = True

# O percentil existe para tirar a ESCALA do projeto, e isso só faz
# sentido em contagem e tamanho. Dar percentil a tudo levaria o
# modelo a 99 features, a maioria redundante.
#
# Desligue para gerar percentil de todas as medidas.
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

# Fração das 9 features que pode faltar numa linha antes de ela
# ser descartada em vez de preenchida.
#
# 0.5 -> até 4 das 9 são preenchidas com a média; a partir de 5 a
# linha sai. O raciocínio: preencher um buraco isolado é estimar,
# preencher a maioria da linha é inventá-la.
FRACAO_MAXIMA_FALTANTE = 0.5

# A partir deste valor duas features são relatadas como
# carregando informação parecida
CORRELACAO_ALTA = 0.8

# Quantos pares redundantes aparecem na tela. A matriz inteira
# continua indo para o CSV.
TOPO_PARES = 15

# Acima de quantas features o mapa de calor deixa de escrever o
# número dentro de cada célula. Passando disso o número não cabe e
# o mapa fica ilegível; a cor continua comunicando.
MAXIMO_ANOTADO = 16


# =============================================================
# BALANCEAMENTO DAS CLASSES
# =============================================================

# Quando ligado, o TREINO passa a ter a mesma quantidade de
# defeituosos e de limpos. O conjunto reservado nunca é tocado:
# ele precisa manter a proporção real para a avaliação valer.
#
# Antes de ligar, saiba duas coisas sobre os seus dados:
#
#   O dataset já está quase equilibrado (47% de defeituosos), e
#   balanceamento resolve desequilíbrio severo, tipo 95/5.
#
#   O AUC quase não muda com isso, porque mede ordenação e
#   ordenação não depende da proporção. O que muda são F1,
#   precisão e revocação no limiar 0,5.
BALANCEAR_TREINO = False

#   "replicar" -> sorteia com reposição da classe menor.
#                 Não perde dado, mas repete linha, e linha
#                 repetida deixa o modelo mais confiante do que os
#                 dados sustentam.
#   "reduzir"  -> descarta da classe maior. Não repete nada, mas
#                 joga dado fora.
ESTRATEGIA_BALANCEAMENTO = "replicar"


# =============================================================
# PARÂMETROS DO TREINO
# =============================================================

# Probabilidade a partir da qual o arquivo é marcado como defeituoso
LIMIAR_DECISAO = 0.5

# Mínimo de linhas em cada folha das árvores.
#
# É o parâmetro que governa o TAMANHO do modelo salvo, e medido no
# dataset de 137 mil linhas a diferença é brutal:
#
#   folha=3   -> AUC 0,616   647,8 MB   8.096.044 nós
#   folha=50  -> AUC 0,615    45,1 MB     562.904 nós
#   folha=200 -> AUC 0,608    11,4 MB     140.780 nós
#
# Com folha=3 cada árvore cresce até sobrarem 3 linhas por folha,
# o que em sinal fraco é decorar ruído. O AUC não melhora e o
# arquivo passa do limite de 100 MB do GitHub.
MINIMO_POR_FOLHA = 50

# Compressão do joblib, de 0 a 9. Corta o modelo pela metade ou
# mais, ao custo de alguns segundos para gravar e carregar.
COMPRESSAO_DO_MODELO = 3


# =============================================================
# GRÁFICOS DO MODELO
# =============================================================

GERAR_GRAFICOS = True

# Níveis da árvore que aparecem no desenho. Uma árvore treinada em
# 97 mil linhas chega a 44 de profundidade e sai como uma mancha
# preta; os primeiros níveis é que mostram por onde o modelo
# começa a decidir.
PROFUNDIDADE_DO_GRAFICO = 3

# A importância por permutação é a medida honesta quando as
# features são correlacionadas, mas custa uma previsão inteira por
# feature e por repetição.
GERAR_PERMUTACAO = True
AMOSTRA_PERMUTACAO = 20_000
REPETICOES_PERMUTACAO = 5

# Quantos arquivos aparecem no ranking de risco impresso na tela.
# O arquivo completo é gravado em ARQUIVO_RISCO de qualquer jeito.
TOPO_RANKING = 20

# Peso da média geral na nota de cada arquivo.
#
# Um arquivo entra no dataset uma vez por commit que o alterou, e
# a nota dele é a média dessas probabilidades. Sem correção, o
# topo do ranking enche de arquivos com UM retrato só: a média de
# uma amostra varia muito mais que a de sete, então os extremos
# são ocupados por quem tem menos evidência.
#
# Este k equivale a "quantos retratos de credibilidade a média
# geral vale". Com 5, um arquivo de 1 retrato fica perto da média
# geral e um de 20 quase não se move.
PESO_DA_PRIOR = 5

# Tamanhos de topo avaliados. Para uma ferramenta que ORDENA
# arquivos, a precisão nos N primeiros é mais honesta que F1 num
# limiar fixo: é o que o desenvolvedor vive se olhar só os N.
TOPOS_AVALIADOS = (10, 50, 100, 500)


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
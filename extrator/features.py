# ==============================================================
# Este arquivo define as Colunas e sua Ordem.
# ==============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

# Relativo porque 'extrator' é um pacote: assim funciona
# independente de quem importa e de onde
from . import derivadas

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
# Grupos opcionais de código, ligados no config
# -------------------------------------------------------------
COLUNAS_COMENTARIOS = [
    "comentarios",       # linhas de comentário
    "linhas_em_branco",
]

COLUNAS_HALSTEAD = [
    "halstead_volume",       # tamanho do vocabulário usado
    "halstead_dificuldade",
    "halstead_esforco",
    "halstead_bugs",         # estimativa de defeitos do próprio Halstead
]

COLUNAS_LIZARD = [
    "tokens",             # símbolos do arquivo, tamanho sem depender de linha
    "parametros_maximo",  # assinatura mais longa
    "parametros_media",
]

COLUNAS_AST = [
    "aninhamento_maximo",  # blocos de controle um dentro do outro
    "todos_fixmes",        # TODO, FIXME, XXX e HACK nos comentários
    "except_pelado",       # 'except:' sem tipo
    "qtd_try",
    "qtd_imports",
    "imports_estrela",     # 'from x import *'
    "qtd_classes",
    "qtd_decoradores",
    "qtd_global",
]

COLUNAS_RUFF = [
    "ruff_total",
    "ruff_bugbear",      # padrões que costumam virar bug
    "ruff_seguranca",
    "ruff_excecao",      # tratamento de erro problemático
    "ruff_simplificar",
    "ruff_refatorar",
    "ruff_argumentos",
    "ruff_retorno",
]

# -------------------------------------------------------------
# Como o código evoluiu (PyDriller)
# -------------------------------------------------------------
COLUNAS_HISTORICO = [
    "revisoes",   # quantos commits alteraram o arquivo
    "autores",    # quantas pessoas diferentes o alteraram
    "churn",      # total de linhas adicionadas mais removidas
]

# -------------------------------------------------------------
# Grupos opcionais de histórico, ligados no config
# -------------------------------------------------------------
COLUNAS_TEMPORAL = [
    "insercoes",            # linhas adicionadas, separadas das removidas
    "remocoes",
    "idade_dias",           # do primeiro commit do arquivo até este
    "dias_desde_anterior",  # intervalo entre as duas últimas mudanças
    "commits_recentes",     # na janela de JANELA_RECENTE_DIAS
    "autores_recentes",
]

COLUNAS_PROPRIEDADE = [
    "fracao_autor_principal",  # parcela das mudanças feita por quem mais mexe
    "autores_menores",         # contribuidores ocasionais
    "arquivos_por_commit",     # tamanho típico dos commits que tocam o arquivo
]

# =============================================================
# AS DUAS LISTAS, QUE SÃO COISAS DIFERENTES
# =============================================================

# Os grupos opcionais, com a chave do config que liga cada um.
# A ordem aqui é a ordem das colunas no CSV.
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


# O que está GRAVADO no dataset.csv. É o contrato do arquivo.
#
# Desligar um grupo de medição muda esta lista, e portanto muda a
# assinatura da montagem — o que faz o dataset ser remontado numa
# pasta de parciais própria, em vez de misturar medições
# diferentes no mesmo arquivo.
COLUNAS_BASE = colunas_medidas()

# O que o MODELO recebe: as medidas mais as derivadas ligadas no
# config.
#
# Separar as duas é o que permite acrescentar features derivadas
# sem invalidar um dataset que levou horas para ser montado: as
# derivadas são calculadas na hora de treinar, a partir das
# medidas, e nunca precisam estar no CSV.
FEATURES = COLUNAS_BASE + derivadas.colunas_ativas(COLUNAS_BASE)

# =============================================================
# O QUE O MODELO PREVÊ
# =============================================================

# 1 para arquivo que contém defeito, 0 para arquivo limpo.
COLUNA_ALVO = "defeituoso"

# =============================================================
# COLUNAS QUE NÃO ENTRAM NO MODELO
# =============================================================
COLUNAS_IDENTIFICACAO = [
    "repositorio",         # nome no GitHub, por exemplo numpy/numpy
    "arquivo",             # caminho do .py dentro do repositório
    "commit",              # commit no qual o arquivo foi medido
    "particao_defectors",  # divisão oficial do dataset: train, test ou val
]


COLUNAS_DIAGNOSTICO = [
    "linhas_defeituosas",
]

# -------------------------------------------------------------
# As duas divisões, que são coisas diferentes
# -------------------------------------------------------------

# A que o próprio Defectors entrega: train, test ou val.
# Permite adotar a divisão oficial em vez de inventar uma.
COLUNA_PARTICAO_DEFECTORS = "particao_defectors"

# A que ESTE trabalho usa. Vale "treino" ou "teste".
# Escolhida em ESTRATEGIA_DIVISAO.
COLUNA_PARTICAO = "particao"

# =============================================================
# A ORDEM DAS COLUNAS NO CSV
# =============================================================

# COLUNAS_BASE e não FEATURES: o CSV guarda só o que foi medido.
# As derivadas são recalculadas a cada treino, de graça.
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
    """Classifica uma feature em código, histórico, caminho ou mista.

    Existe para o relatório de importância não mentir. Somar só as
    colunas cruas de histórico ignora que 'revisoes_por_autor' e
    'pct_churn' também são histórico, e faz parecer que ele parou
    de pesar.
    """
    nome = coluna[len(derivadas.PREFIXO_PERCENTIL):] \
        if coluna.startswith(derivadas.PREFIXO_PERCENTIL) else coluna

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


# Raízes que identificam a origem de uma coluna, inclusive nas
# derivadas: 'churn_por_revisao' casa com churn e com revisoes,
# 'churn_por_linha' casa com churn e com linhas, e por isso sai
# como mista.
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
    """Interrompe o programa se faltar alguma coluna obrigatória.

    Chamada antes de gravar o dataset e antes de treinar. A ideia
    é que a divergência apareça aqui, de forma visível, em vez de
    virar uma previsão errada mais adiante.
    """
    faltando = [c for c in COLUNAS_CSV if c not in colunas]
    if faltando:
        raise ValueError(f"Colunas faltando no dataset: {faltando}")


# =============================================================
# Conferir Sem Vazamento
# -------------------------------------------------------------
# Valida que o rótulo não é feature
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
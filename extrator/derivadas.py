"""
Cria features novas a partir das 9 que já foram medidas.

Nada aqui lê código nem histórico: são contas sobre o dataset
pronto. Por isso acrescentar ou tirar um grupo não exige remontar
nada.

O motivo de existirem é o que a matriz de correlação mostrou: as 9
features medidas são quase todas proxy de TAMANHO. linhas e churn
0,91; linhas e qtd_funcoes 0,91; revisoes e autores 0,88. Arquivo
grande tem mais de tudo, então "tem muito churn" quase sempre quer
dizer só "é grande".

Os quatro grupos atacam isso de ângulos diferentes:

  razoes        -> divide pelo tamanho, sobra o que não é tamanho
  desequilibrio -> o que as médias escondem
  percentil     -> posição dentro do PRÓPRIO projeto
  caminho       -> o que o nome do arquivo diz, sem ler o código
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config


# =============================================================
# AS COLUNAS DE CADA GRUPO
# =============================================================

COLUNAS_RAZOES = [
    "churn_por_revisao",     # tamanho típico de cada alteração
    "churn_por_linha",       # quanto já foi reescrito, relativo ao tamanho
    "revisoes_por_autor",    # concentração do trabalho
    "linhas_por_funcao",     # tamanho médio de função
    "fracao_maior_funcao",   # quanto a maior função domina o arquivo
]

COLUNAS_DESEQUILIBRIO = [
    "desequilibrio_complexidade",  # a pior função contra a média delas
    "complexidade_por_linha",      # densidade de decisão na pior função
]

COLUNAS_CAMINHO = [
    "profundidade",           # quantas pastas até o arquivo
    "eh_teste",               # 1 para arquivo de teste
    "eh_init",                # 1 para __init__.py
    "comprimento_do_caminho",
]

# O prefixo das colunas de percentil. Uma por feature medida.
PREFIXO_PERCENTIL = "pct_"


# =============================================================
# Dividir
# -------------------------------------------------------------
# Divisão que devolve vazio em vez de infinito
# =============================================================
def dividir(a: pd.Series, b: pd.Series) -> pd.Series:
    # Dividir por zero no pandas produz infinito, e infinito faz o
    # StandardScaler devolver NaN na coluna inteira — longe daqui,
    # e sem erro. Virar vazio aqui deixa o preparacao.py preencher
    # com a média do treino, que é o tratamento que já existe.
    return (a / b).replace([np.inf, -np.inf], np.nan)


# =============================================================
# Acrescentar Razoes
# -------------------------------------------------------------
# Features que não escalam com o tamanho do arquivo
# =============================================================
def acrescentar_razoes(dados: pd.DataFrame) -> pd.DataFrame:
    # 100 commits de 2 linhas e 100 commits de 200 linhas dão o
    # mesmo 'revisoes' e são coisas completamente diferentes
    dados["churn_por_revisao"] = dividir(dados["churn"], dados["revisoes"])

    # Arquivo de 50 linhas com 5.000 de churn foi reescrito 100
    # vezes. Um de 5.000 linhas com o mesmo churn, uma vez.
    dados["churn_por_linha"] = dividir(dados["churn"], dados["linhas"])

    dados["revisoes_por_autor"] = dividir(dados["revisoes"],
                                          dados["autores"])

    # O dataset tem a MAIOR função, nunca a média
    dados["linhas_por_funcao"] = dividir(dados["linhas"],
                                         dados["qtd_funcoes"])

    dados["fracao_maior_funcao"] = dividir(dados["maior_funcao"],
                                           dados["linhas"])

    return dados


# =============================================================
# Acrescentar Desequilibrio
# -------------------------------------------------------------
# O caso perigoso que a média esconde
# =============================================================
def acrescentar_desequilibrio(dados: pd.DataFrame) -> pd.DataFrame:
    # Média 2 e máximo 3 é um arquivo uniforme. Média 2 e máximo 40
    # é um monstro escondido entre funções simples. Hoje os dois
    # têm complexidade_media parecida, e o modelo não os distingue.
    dados["desequilibrio_complexidade"] = dividir(
        dados["complexidade_maxima"], dados["complexidade_media"])

    dados["complexidade_por_linha"] = dividir(
        dados["complexidade_maxima"], dados["maior_funcao"])

    return dados


# =============================================================
# Acrescentar Caminho
# -------------------------------------------------------------
# O que o nome do arquivo diz, sem abrir o arquivo
# =============================================================
def acrescentar_caminho(dados: pd.DataFrame) -> pd.DataFrame:
    caminho = dados["arquivo"].astype(str)
    nome = caminho.str.rsplit("/", n=1).str[-1]

    dados["profundidade"] = caminho.str.count("/")
    dados["comprimento_do_caminho"] = caminho.str.len()

    # Teste tem perfil de defeito diferente de código de produção,
    # e o dataset não separa os dois
    pasta_de_teste = caminho.str.contains(r"(?:^|/)tests?/", regex=True,
                                          na=False)
    nome_de_teste = (nome.str.startswith("test_")
                     | nome.str.endswith("_test.py"))
    dados["eh_teste"] = (pasta_de_teste | nome_de_teste).astype(int)

    dados["eh_init"] = (nome == "__init__.py").astype(int)

    return dados


# =============================================================
# Acrescentar Percentil
# -------------------------------------------------------------
# A posição de cada arquivo dentro do próprio projeto
# =============================================================
def acrescentar_percentil(dados: pd.DataFrame,
                          colunas: list[str]) -> pd.DataFrame:
    # Um arquivo de 500 linhas é enorme no black e comum no
    # cpython. O modelo recebe "500" e não sabe em qual dos dois
    # mundos está — e é justamente isso que quebra quando a
    # ferramenta aponta para um projeto que ela nunca viu.
    #
    # O percentil dentro do próprio repositório torna as features
    # comparáveis entre projetos.
    #
    # Não é vazamento: usa só os valores das features, nunca o
    # rótulo. E é reproduzível na previsão, porque a ferramenta
    # clona o repositório inteiro antes de julgar qualquer arquivo.
    por_repositorio = dados.groupby("repositorio")

    for coluna in colunas:
        dados[PREFIXO_PERCENTIL + coluna] = por_repositorio[coluna].rank(
            pct=True, method="average")

    return dados


# =============================================================
# REGISTRO DOS GRUPOS
# -------------------------------------------------------------
# Para acrescentar um grupo: escreva a função e registre aqui
# =============================================================

def colunas_de_percentil(base: list[str]) -> list[str]:
    return [PREFIXO_PERCENTIL + c for c in base]


# Cada entrada diz como se chama a chave no config, quais colunas
# o grupo cria, e qual função as cria.
GRUPOS = {
    "razoes": {
        "chave":   "USAR_RAZOES",
        "colunas": COLUNAS_RAZOES,
        "funcao":  acrescentar_razoes,
    },
    "desequilibrio": {
        "chave":   "USAR_DESEQUILIBRIO",
        "colunas": COLUNAS_DESEQUILIBRIO,
        "funcao":  acrescentar_desequilibrio,
    },
    "caminho": {
        "chave":   "USAR_CAMINHO",
        "colunas": COLUNAS_CAMINHO,
        "funcao":  acrescentar_caminho,
    },
    # O percentil é o único que depende de quais são as features
    # medidas, então recebe a lista em vez de tê-la fixa
    "percentil": {
        "chave":   "USAR_PERCENTIL",
        "colunas": None,
        "funcao":  acrescentar_percentil,
    },
}


# =============================================================
# Grupos Ligados
# -------------------------------------------------------------
# Quais grupos o config manda usar
# =============================================================
def grupos_ligados() -> list[str]:
    return [nome for nome, grupo in GRUPOS.items()
            if getattr(config, grupo["chave"], False)]


# =============================================================
# Colunas do Grupo
# -------------------------------------------------------------
# Os nomes que um grupo cria
# =============================================================
def colunas_do_grupo(nome: str, base: list[str]) -> list[str]:
    if nome == "percentil":
        return colunas_de_percentil(base)

    return list(GRUPOS[nome]["colunas"])


# =============================================================
# Colunas Ativas
# -------------------------------------------------------------
# Todas as derivadas que entram no modelo, na ordem
# =============================================================
def colunas_ativas(base: list[str]) -> list[str]:
    ativas = []
    for nome in GRUPOS:
        if nome in grupos_ligados():
            ativas.extend(colunas_do_grupo(nome, base))

    return ativas


# =============================================================
# Acrescentar
# -------------------------------------------------------------
# Calcula e anexa as derivadas ligadas no config
# =============================================================
def acrescentar(dados: pd.DataFrame, base: list[str]) -> pd.DataFrame:
    """Devolve uma cópia com as colunas derivadas.

    Tem de ser chamada ANTES da divisão treino/teste, porque o
    percentil é calculado dentro de cada repositório e precisa de
    todos os arquivos dele.
    """
    dados = dados.copy()
    ligados = grupos_ligados()

    for nome in GRUPOS:
        if nome not in ligados:
            continue

        if nome == "percentil":
            dados = GRUPOS[nome]["funcao"](dados, base)
        else:
            dados = GRUPOS[nome]["funcao"](dados)

    return dados


# =============================================================
# Descrever
# -------------------------------------------------------------
# Texto dos grupos em uso, para aparecer na saída
# =============================================================
def descrever(base: list[str]) -> str:
    ligados = grupos_ligados()

    if not ligados:
        return "nenhum grupo derivado ligado"

    partes = [f"{nome} ({len(colunas_do_grupo(nome, base))})"
              for nome in ligados]

    return ", ".join(partes)
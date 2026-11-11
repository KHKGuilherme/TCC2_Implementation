"""
Frente 1, etapa 4 — desenha os gráficos da análise a partir das tabelas
gravadas em resultados/.

CMD -> python defectlens_v2/frente1_treinamento/graficos.py
       grava os PNG em resultados/graficos
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import analisar
import config
import metricas_avaliacao
import modelos
from extrator import features

# =============================================================
# APARÊNCIA
# -------------------------------------------------------------
# A cor acompanha o método, e não a posição dele em cada gráfico
# =============================================================

SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
APAGADO = "#898781"
GRADE = "#e1e0d9"
EIXO = "#c3c2b7"

CORES = {
    "modelo_v2":         "#2a78d6",
    "la":                "#eb6834",
    "original":          "#1baf7a",
    "menor_primeiro":    "#eda100",
    "boosting_completo": "#6250d6",
    "aleatorio":         APAGADO,
}

COR_DEFEITO = "#d03b3b"
COR_LIMPO = "#86b6ef"
COR_NEUTRA = "#b7d3f6"

NOMES_CURTOS = {
    "aleatorio":         "Aleatório",
    "la":                "LA (linhas adicionadas)",
    "churn":             "LA + LD",
    "nf":                "Nº de arquivos",
    "menor_primeiro":    "Menor primeiro",
    "original":          "Original (82 features)",
    "lapredict":         "LApredict",
    "logistica_commit":  "Logística (commit)",
    "boosting_commit":   "Boosting (commit)",
    "modelo_v2":         "DefectLens v2",
    "boosting_completo": "v2 + código",
    "v2_sem_dominio":    "v2 sem filtro de domínio",
    "v2_equilibrado":    "v2 equilibrado por repo",
}

DESTAQUES = ["la", "original", "modelo_v2"]

GRADE_DE_ESFORCO = np.linspace(0, 1, 201)

LIMITE_DA_BARRA = 0.04


# =============================================================
# Preparar Estilo
# -------------------------------------------------------------
# Define o estilo comum a todos os gráficos
# =============================================================
def preparar_estilo() -> None:
    plt.rcParams.update({
        "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE,
        "savefig.facecolor": SUPERFICIE, "figure.dpi": 110,
        "font.family": "DejaVu Sans", "font.size": 10,
        "text.color": TINTA, "axes.labelcolor": TINTA_2,
        "axes.edgecolor": EIXO, "axes.linewidth": 0.8,
        "axes.titlesize": 11.5, "axes.titleweight": "bold",
        "axes.titlelocation": "left", "axes.titlepad": 10,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRADE, "grid.linewidth": 0.7,
        "axes.axisbelow": True,
        "xtick.color": APAGADO, "ytick.color": APAGADO,
        "xtick.labelcolor": TINTA_2, "ytick.labelcolor": TINTA_2,
        "legend.frameon": False, "lines.linewidth": 2,
    })


# =============================================================
# Cor do Metodo
# -------------------------------------------------------------
# A cor fixa de um método, ou cinza para os secundários
# =============================================================
def cor_do_metodo(metodo: str) -> str:
    return CORES.get(metodo, EIXO)


# =============================================================
# Salvar
# -------------------------------------------------------------
# Grava a figura com título geral e legenda de leitura
# =============================================================
def salvar(figura, nome: str, titulo: str, leitura: str) -> Path:
    figura.suptitle(titulo, x=0.01, ha="left", fontsize=13.5,
                    fontweight="bold")
    figura.text(0.01, 0.005, leitura, ha="left", va="bottom", fontsize=9,
                color=TINTA_2, wrap=True)
    figura.tight_layout(rect=(0, 0.05, 1, 0.95))

    config.PASTA_GRAFICOS.mkdir(parents=True, exist_ok=True)
    destino = config.PASTA_GRAFICOS / nome
    figura.savefig(destino, dpi=150)
    plt.close(figura)
    return destino


# =============================================================
# Porcento
# -------------------------------------------------------------
# Formata uma fração como porcentagem em português
# =============================================================
def porcento(valor: float, casas: int = 1) -> str:
    return f"{100 * valor:.{casas}f}%".replace(".", ",")


# =============================================================
# Decimal
# -------------------------------------------------------------
# Formata um número com vírgula decimal
# =============================================================
def decimal(valor: float, casas: int = 3) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


# =============================================================
# DATASET
# =============================================================


# =============================================================
# Grafico das Particoes
# -------------------------------------------------------------
# Taxa de defeito por partição e a linha do tempo de test e val
# =============================================================
def grafico_das_particoes() -> Path:
    resumo = pd.read_csv(config.PASTA_RESULTADOS / "particoes.csv")
    mensal = pd.read_csv(config.PASTA_RESULTADOS / "particoes_por_mes.csv")
    resumo = resumo.set_index("particao").loc[["train", "val", "test"]]

    figura, eixos = plt.subplots(1, 3, figsize=(15, 4.8),
                                 gridspec_kw={"width_ratios": [1, 1.5, 1.5]})

    barras = eixos[0].bar(resumo.index, resumo["taxa_de_defeito"],
                          color=[COR_DEFEITO, COR_NEUTRA, COR_NEUTRA],
                          width=0.6)
    for barra, (_, linha) in zip(barras, resumo.iterrows()):
        eixos[0].text(barra.get_x() + barra.get_width() / 2,
                      barra.get_height() + 0.008,
                      f"{porcento(linha['taxa_de_defeito'])}\n"
                      f"{int(linha['commits']):,} commits".replace(",", "."),
                      ha="center", va="bottom", fontsize=9, color=TINTA)
    eixos[0].set_ylim(0, 0.5)
    eixos[0].set_ylabel("commits marcados como defeituosos")
    eixos[0].yaxis.set_major_formatter(lambda v, _: porcento(v, 0))
    eixos[0].set_title("Taxa de defeito por partição")
    eixos[0].grid(axis="x", visible=False)

    for eixo, particao in zip(eixos[1:], ("val", "test")):
        recorte = mensal[(mensal["particao"] == particao)]
        tabela = (recorte.pivot(index="mes", columns="defeituoso",
                                values="commits").fillna(0)
                  .reindex(columns=[0, 1], fill_value=0))
        posicoes = np.arange(len(tabela))
        eixo.bar(posicoes - 0.21, tabela[0], width=0.4, color=COR_LIMPO,
                 label="limpos")
        eixo.bar(posicoes + 0.21, tabela[1], width=0.4, color=COR_DEFEITO,
                 label="defeituosos")
        eixo.set_xticks(posicoes, [m[2:] for m in tabela.index], rotation=45,
                        ha="right", fontsize=8)
        eixo.set_ylabel("commits no mês")
        eixo.set_title(f"Partição {particao}: commits por mês e rótulo")
        eixo.grid(axis="x", visible=False)
        eixo.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncols=2,
                    fontsize=9)
        eixo.set_title(eixo.get_title(), pad=26)

    return salvar(
        figura, "01_particoes_dataset.png",
        "A queda da taxa de defeito em test e val vem da construção do "
        "dataset",
        "O artigo do Defectors reamostra a partição train para perto de 1:1 "
        "e mantém a proporção original em test e val. Em val, os commits "
        "limpos e os defeituosos vêm de meses diferentes:\na partição foi "
        "montada por classe, e não por maturação do rótulo. A hipótese de "
        "\"rótulos imaturos\" da versão original não se sustenta.")


# =============================================================
# Grafico da Taxa por Tamanho
# -------------------------------------------------------------
# Taxa de defeito por tamanho do commit, com o corte do Defectors
# =============================================================
def grafico_da_taxa_por_tamanho() -> Path:
    tabela = pd.read_csv(config.PASTA_RESULTADOS / "taxa_por_tamanho.csv")
    figura, eixos = plt.subplots(1, 2, figsize=(14, 4.9))
    limites = {"linhas alteradas": config.MAXIMO_LINHAS_COMMIT,
               "arquivos": config.MAXIMO_ARQUIVOS_COMMIT}

    for eixo, (medida, grupo) in zip(eixos, tabela.groupby("medida",
                                                           sort=False)):
        fora = grupo["defeituosos"] == 0
        barras = eixo.bar(grupo["faixa"], grupo["taxa"], width=0.72,
                          color=[EIXO if f else CORES["modelo_v2"]
                                 for f in fora])
        for barra, (_, linha) in zip(barras, grupo.iterrows()):
            eixo.text(barra.get_x() + barra.get_width() / 2,
                      barra.get_height() + 0.012,
                      f"{porcento(linha['taxa'], 0)}\nn={int(linha['commits'])}",
                      ha="center", va="bottom", fontsize=8, color=TINTA)

        primeira_fora = int(np.argmax(fora.to_numpy())) if fora.any() else None
        if primeira_fora is not None:
            eixo.axvline(primeira_fora - 0.5, color=COR_DEFEITO,
                         linestyle="--", linewidth=1.4)
            eixo.text(primeira_fora - 0.42, 0.93,
                      f"corte do Defectors:\n> {limites[medida]} {medida}",
                      color=COR_DEFEITO, fontsize=9, va="top")

        eixo.set_ylim(0, 1.0)
        eixo.set_xlabel(f"{medida} no commit")
        eixo.set_ylabel("taxa de defeito (partição train)")
        eixo.yaxis.set_major_formatter(lambda v, _: porcento(v, 0))
        eixo.set_title(f"Por {medida}")
        eixo.grid(axis="x", visible=False)
        eixo.tick_params(axis="x", labelsize=8.5)

    return salvar(
        figura, "02_taxa_por_tamanho.png",
        "A taxa de defeito cresce com o tamanho do commit e cai a zero no "
        "corte do Defectors",
        "O Defectors descarta commits causadores com mais de 1000 linhas "
        "alteradas ou mais de 100 arquivos (artigo, seção III-D), mas mantém "
        "os limpos desse tamanho. Acima do corte o rótulo \"limpo\" é\n"
        "consequência do filtro. A v2 tira esses commits do treino e da "
        "avaliação, e o site avisa que estão fora do domínio do modelo.")


# =============================================================
# COMPARAÇÃO DE MÉTODOS
# =============================================================


# =============================================================
# Ler Medidas
# -------------------------------------------------------------
# As medidas por repositório de um cenário, em formato largo
# =============================================================
def ler_medidas(cenario: str, medida: str) -> pd.DataFrame:
    medidas = pd.read_csv(config.PASTA_RESULTADOS
                          / "metricas_por_repositorio.csv")
    medidas = medidas[medidas["cenario"] == cenario]
    return medidas.pivot(index="repositorio", columns="metodo", values=medida)


# =============================================================
# Grafico por Repositorio
# -------------------------------------------------------------
# AUC de cada repositório: LA, modelo original e v2
# =============================================================
def grafico_por_repositorio() -> Path:
    tabela = ler_medidas("principal", "auc").sort_values("modelo_v2")
    posicoes = np.arange(len(tabela))
    figura, eixo = plt.subplots(figsize=(11, 8.2))

    eixo.hlines(posicoes, tabela[DESTAQUES].min(axis=1),
                tabela[DESTAQUES].max(axis=1), color=GRADE, linewidth=3,
                zorder=1)

    for metodo in DESTAQUES:
        mediana = tabela[metodo].median()
        eixo.scatter(tabela[metodo], posicoes, s=62, zorder=3,
                     color=cor_do_metodo(metodo), edgecolor=SUPERFICIE,
                     linewidth=1.2,
                     label=f"{NOMES_CURTOS[metodo]} — mediana "
                           f"{decimal(mediana)}")
        eixo.axvline(mediana, color=cor_do_metodo(metodo), linestyle=":",
                     linewidth=1.3, zorder=2)

    eixo.set_yticks(posicoes, tabela.index)
    eixo.set_xlabel("AUC por commit em projeto nunca visto")
    eixo.xaxis.set_major_formatter(lambda v, _: decimal(v, 2))
    eixo.grid(axis="y", visible=False)
    eixo.legend(loc="lower right")
    eixo.set_title("Cada ponto é um repositório deixado de fora do treino")

    return salvar(
        figura, "03_auc_por_repositorio.png",
        "Em 23 repositórios nunca vistos, ordenar por linhas adicionadas já "
        "chega perto dos modelos",
        "Cenário principal: partição train, commits dentro do domínio do "
        "rótulo. As linhas pontilhadas são as medianas. O ganho do "
        "aprendizado de máquina sobre a ordenação trivial por LA é pequeno, "
        "não é uniforme entre projetos\ne não é estatisticamente "
        "significativo no AUC (gráfico 14).")


# =============================================================
# Grafico da Comparacao
# -------------------------------------------------------------
# Distribuição do AUC por repositório de todos os métodos
# =============================================================
def grafico_da_comparacao() -> Path:
    tabela = ler_medidas("principal", "auc")
    ordem = tabela.median().sort_values().index.tolist()
    figura, eixo = plt.subplots(figsize=(11.5, 6.6))

    caixas = eixo.boxplot([tabela[m].dropna() for m in ordem],
                          orientation="horizontal",
                          patch_artist=True, widths=0.6,
                          medianprops={"color": TINTA, "linewidth": 1.6},
                          whiskerprops={"color": APAGADO},
                          capprops={"color": APAGADO},
                          flierprops={"marker": "o", "markersize": 4,
                                      "markerfacecolor": APAGADO,
                                      "markeredgecolor": "none"})
    for caixa, metodo in zip(caixas["boxes"], ordem):
        caixa.set_facecolor(cor_do_metodo(metodo))
        caixa.set_edgecolor(SUPERFICIE)
        caixa.set_alpha(0.95)

    for posicao, metodo in enumerate(ordem, 1):
        eixo.text(tabela[metodo].max() + 0.008, posicao,
                  decimal(tabela[metodo].median()), va="center", fontsize=9,
                  color=TINTA)

    eixo.set_yticks(range(1, len(ordem) + 1),
                    [NOMES_CURTOS.get(m, m) for m in ordem])
    eixo.axvline(0.5, color=APAGADO, linestyle="--", linewidth=1)
    eixo.set_xlabel("AUC por commit em cada repositório nunca visto "
                    "(o número é a mediana)")
    eixo.xaxis.set_major_formatter(lambda v, _: decimal(v, 2))
    eixo.grid(axis="y", visible=False)
    eixo.set_title("Baselines triviais, modelos e o modelo original, nos "
                   "mesmos commits")

    return salvar(
        figura, "04_comparacao_metodos.png",
        "Todos os métodos na mesma régua: validação deixando um repositório "
        "de fora",
        "\"Menor primeiro\" fica abaixo de 0,5 de propósito: é a ordenação "
        "que privilegia o esforço, e não a chance de defeito (ver o gráfico "
        "de esforço). LApredict ordena igual a LA dentro de um projeto, por "
        "isso as caixas coincidem.")


# =============================================================
# Grafico das Curvas ROC
# -------------------------------------------------------------
# Curvas ROC com todos os commits juntos, nos dois cenários
# =============================================================
def grafico_das_curvas_roc(previsoes: pd.DataFrame) -> Path:
    figura, eixos = plt.subplots(1, 2, figsize=(13, 5.9))
    cenarios = (("principal", "Partição train (perto de 1:1), no domínio"),
                ("natural", "Partições test e val (proporção original)"))

    for eixo, (cenario, titulo) in zip(eixos, cenarios):
        recorte = analisar.filtrar_cenario(previsoes, cenario)
        rotulo = recorte["defeituoso"].to_numpy()

        for metodo in ("aleatorio", "la", "original", "modelo_v2"):
            nota = recorte[f"nota_{metodo}"]
            if nota.isna().any():
                continue

            falsos, verdadeiros, _ = roc_curve(rotulo, nota)
            eixo.plot(falsos, verdadeiros, color=cor_do_metodo(metodo),
                      linewidth=2.4 if metodo == "modelo_v2" else 1.8,
                      linestyle="--" if metodo == "aleatorio" else "-",
                      label=f"{NOMES_CURTOS[metodo]} — AUC "
                            f"{decimal(metricas_avaliacao.auc(rotulo, nota))}")

        eixo.set_xlabel("commits limpos apontados (falsos positivos)")
        eixo.set_ylabel("commits defeituosos achados")
        eixo.xaxis.set_major_formatter(lambda v, _: porcento(v, 0))
        eixo.yaxis.set_major_formatter(lambda v, _: porcento(v, 0))
        eixo.set_title(f"{titulo}\n{len(recorte):,} commits, ".replace(
            ",", ".") + f"{porcento(rotulo.mean())} defeituosos")
        eixo.legend(loc="lower right")
        eixo.set_aspect("equal")

    return salvar(
        figura, "05_curvas_roc.png",
        "Curvas ROC em projeto nunca visto, com todos os commits juntos",
        "À direita, o teste de sensibilidade: os mesmos modelos avaliados "
        "nos commits de test e val, que mantêm a taxa de defeito original "
        "do Defectors. O modelo original não tem notas gravadas para essas "
        "partições.")


# =============================================================
# ESFORÇO
# =============================================================


# =============================================================
# Curva Media
# -------------------------------------------------------------
# Média, entre repositórios, da curva de defeitos por esforço
# =============================================================
def curva_media(recorte: pd.DataFrame, chave) -> np.ndarray:
    curvas = []

    for _, grupo in recorte.groupby("repositorio"):
        if not analisar.repositorio_avaliavel(grupo, "principal"):
            continue

        rotulo = grupo["defeituoso"].to_numpy()
        esforco = np.maximum((grupo["commit_adicionadas"]
                              + grupo["commit_removidas"]).to_numpy(float),
                             1.0)
        x, y = metricas_avaliacao.curva_de_esforco(
            rotulo, esforco, chave(grupo, rotulo, esforco))
        curvas.append(np.interp(GRADE_DE_ESFORCO, x, y))

    return np.mean(curvas, axis=0)


# =============================================================
# Grafico das Curvas de Esforco
# -------------------------------------------------------------
# Defeitos achados conforme as linhas revisadas, por ordenação
# =============================================================
def grafico_das_curvas_de_esforco(previsoes: pd.DataFrame) -> Path:
    recorte = analisar.filtrar_cenario(previsoes, "principal")
    ordem = metricas_avaliacao.ordem_decrescente

    series = [
        ("Ordem ideal", TINTA_2, ":",
         lambda g, r, e: metricas_avaliacao.ordens_de_referencia(r, e)[0]),
        ("DefectLens v2, por risco por linha", CORES["modelo_v2"], "-",
         lambda g, r, e: ordem(g["nota_modelo_v2"].to_numpy() / e)),
        ("Menor commit primeiro", CORES["menor_primeiro"], "-",
         lambda g, r, e: ordem(-e)),
        ("Aleatório", APAGADO, "--",
         lambda g, r, e: ordem(g["nota_aleatorio"].to_numpy())),
        ("DefectLens v2, por risco", "#104281", "-",
         lambda g, r, e: ordem(g["nota_modelo_v2"].to_numpy())),
        ("LA, maior primeiro", CORES["la"], "-",
         lambda g, r, e: ordem(g["nota_la"].to_numpy())),
    ]

    figura, eixo = plt.subplots(figsize=(10.5, 6.6))
    for nome, cor, traco, chave in series:
        curva = curva_media(recorte, chave)
        aos_vinte = float(np.interp(config.FRACAO_ESFORCO, GRADE_DE_ESFORCO,
                                    curva))
        eixo.plot(GRADE_DE_ESFORCO, curva, color=cor, linestyle=traco,
                  label=f"{nome} — {porcento(aos_vinte, 0)} aos 20%")

    eixo.axvline(config.FRACAO_ESFORCO, color=EIXO, linewidth=1.2)
    eixo.text(config.FRACAO_ESFORCO + 0.01, 0.03, "20% das linhas",
              color=TINTA_2, fontsize=9)
    eixo.set_xlabel("linhas alteradas já revisadas (esforço acumulado)")
    eixo.set_ylabel("commits defeituosos já encontrados")
    eixo.xaxis.set_major_formatter(lambda v, _: porcento(v, 0))
    eixo.yaxis.set_major_formatter(lambda v, _: porcento(v, 0))
    eixo.legend(loc="lower right")
    eixo.set_title("Média das curvas de 23 repositórios nunca vistos")

    return salvar(
        figura, "06_curvas_de_esforco.png",
        "Quando o custo é o número de linhas a revisar, a ordem por risco "
        "puro é a pior escolha",
        "Commits grandes concentram a nota e também o esforço. Ordenar pela "
        "nota dividida pelas linhas (risco por linha) empata com \"menor "
        "primeiro\", o baseline clássico de Yang et al. (FSE 2016):\na "
        "diferença não é significativa (gráfico 14). O site oferece as duas "
        "ordens, maior risco e melhor custo-benefício, e explica o que cada "
        "uma entrega.")


# =============================================================
# Grafico das Medidas de Esforco
# -------------------------------------------------------------
# Recall a 20% do esforço e Popt, por método e ordenação
# =============================================================
def grafico_das_medidas_de_esforco() -> Path:
    resumo = pd.read_csv(config.PASTA_RESULTADOS / "resumo_metodos.csv")
    resumo = resumo[resumo["cenario"] == "principal"].set_index("metodo")
    metodos = ["aleatorio", "la", "original", "boosting_commit", "modelo_v2"]
    medidas = (("revocacao_esforco", "Defeitos achados com 20% das linhas "
                                     "(Recall@20%Effort)"),
               ("popt", "Popt (1 = ordem ideal)"))

    figura, eixos = plt.subplots(1, 2, figsize=(14, 5.4))
    posicoes = np.arange(len(metodos))

    for eixo, (medida, titulo) in zip(eixos, medidas):
        for deslocamento, ordenacao, hachura in ((-0.2, "risco", None),
                                                 (0.2, "densidade", "///")):
            valores = resumo.loc[metodos, f"{medida}_{ordenacao}"]
            barras = eixo.bar(posicoes + deslocamento, valores, width=0.38,
                              color=[cor_do_metodo(m) for m in metodos],
                              hatch=hachura, edgecolor=SUPERFICIE,
                              linewidth=1)
            for barra, valor in zip(barras, valores):
                eixo.text(barra.get_x() + barra.get_width() / 2,
                          valor + 0.012, decimal(valor, 2), ha="center",
                          fontsize=8.5, color=TINTA)

        manual = resumo.loc["menor_primeiro", f"{medida}_risco"]
        eixo.axhline(manual, color=CORES["menor_primeiro"], linewidth=1.6)
        eixo.text(len(metodos) - 0.5, manual + 0.012,
                  f"menor primeiro: {decimal(manual, 2)}", ha="right",
                  fontsize=9, color=TINTA)

        eixo.set_xticks(posicoes, [NOMES_CURTOS[m].replace(" (", "\n(")
                                   for m in metodos], fontsize=8.5)
        eixo.set_ylim(0, 1)
        eixo.set_title(titulo)
        eixo.grid(axis="x", visible=False)

    eixos[0].bar([0], [0], color=EIXO, label="ordem por risco (lisa)")
    eixos[0].bar([0], [0], color=EIXO, hatch="///", edgecolor=SUPERFICIE,
                 label="ordem por risco por linha (hachurada)")
    eixos[0].legend(loc="upper left")

    return salvar(
        figura, "07_medidas_de_esforco.png",
        "Medidas que consideram o esforço: mediana entre 23 repositórios "
        "nunca vistos",
        "Esforço = linhas adicionadas + removidas (Kamei et al., TSE 2013). "
        "Barra lisa: commits na ordem da nota. Barra hachurada: na ordem da "
        "nota dividida pelas linhas. Em LA, dividir pelas linhas apaga a "
        "informação,\ne o resultado equivale ao acaso.")


# =============================================================
# ANTES E DEPOIS
# =============================================================


# =============================================================
# Grafico da Ablacao
# -------------------------------------------------------------
# O que cada grupo de medidas acrescenta, passo a passo
# =============================================================
def grafico_da_ablacao() -> Path:
    passos = [("la", "Só LA\n(sem treino)"),
              ("logistica_commit", "Logística\nmedidas do commit"),
              ("boosting_commit", "Boosting\nmedidas do commit"),
              ("modelo_v2", "v2: commit +\nhistórico do arquivo"),
              ("boosting_completo", "v2 + 32 métricas\nde código"),
              ("original", "Original\n(82 features)")]
    medidas = (("auc", "AUC por commit"),
               ("topo_10", "Taxa de defeito no topo 10%"),
               ("revocacao_esforco_densidade", "Recall@20%Effort "
                                               "(risco por linha)"))

    figura, eixos = plt.subplots(1, 3, figsize=(17, 5.4), sharey=True)
    posicoes = np.arange(len(passos))[::-1]

    for eixo, (medida, titulo) in zip(eixos, medidas):
        tabela = ler_medidas("principal", medida)
        medianas = [tabela[m].median() for m, _ in passos]
        baixos = [tabela[m].median() - tabela[m].quantile(0.25)
                  for m, _ in passos]
        altos = [tabela[m].quantile(0.75) - tabela[m].median()
                 for m, _ in passos]

        eixo.errorbar(medianas, posicoes, xerr=[baixos, altos], fmt="none",
                      ecolor=EIXO, elinewidth=2.5, zorder=1)
        eixo.scatter(medianas, posicoes, s=95, zorder=3,
                     color=[cor_do_metodo(m) if m in CORES else TINTA_2
                            for m, _ in passos],
                     edgecolor=SUPERFICIE, linewidth=1.5)
        for posicao, mediana in zip(posicoes, medianas):
            eixo.text(mediana, posicao + 0.24, decimal(mediana), fontsize=9,
                      ha="center", color=TINTA)

        eixo.set_yticks(posicoes, [rotulo.replace(chr(10), " ")
                                   for _, rotulo in passos])
        eixo.set_ylim(-0.5, len(passos) - 0.3)
        eixo.xaxis.set_major_formatter(lambda v, _: decimal(v, 2))
        eixo.set_title(titulo)
        eixo.grid(axis="y", visible=False)

    return salvar(
        figura, "08_ablacao.png",
        "O que cada mudança acrescenta: mediana e quartis entre 23 "
        "repositórios nunca vistos",
        "Da esquerda para a direita, cada passo acrescenta um grupo de "
        "medidas. Os quartis se sobrepõem em todos os passos: nenhum ganho "
        "de AUC é significativo depois da correção de Holm (gráfico 14).\n"
        "As 32 métricas de código (Radon, Lizard, Ruff) têm efeito "
        "desprezível, e por isso a v2 não mede código: a análise de um "
        "repositório novo usa só o git log.")


# =============================================================
# Grafico do Dominio
# -------------------------------------------------------------
# Efeito do filtro de domínio na avaliação e no treino
# =============================================================
def grafico_do_dominio() -> Path:
    metodos = ["la", "original", "v2_sem_dominio", "modelo_v2"]
    figura, eixos = plt.subplots(1, 2, figsize=(13.5, 5.2))

    for eixo, medida, titulo in ((eixos[0], "auc", "AUC por commit"),
                                 (eixos[1], "topo_10",
                                  "Taxa de defeito no topo 10%")):
        antes = ler_medidas("sem_filtro", medida)
        depois = ler_medidas("principal", medida)
        posicoes = np.arange(len(metodos))

        for deslocamento, tabela, rotulo, cor in (
                (-0.2, antes, "todos os commits (como antes)", COR_NEUTRA),
                (0.2, depois, "só commits no domínio do rótulo",
                 CORES["modelo_v2"])):
            valores = [tabela[m].median() for m in metodos]
            barras = eixo.bar(posicoes + deslocamento, valores, width=0.38,
                              color=cor, label=rotulo, edgecolor=SUPERFICIE)
            for barra, valor in zip(barras, valores):
                eixo.text(barra.get_x() + barra.get_width() / 2,
                          valor + 0.004, decimal(valor), ha="center",
                          fontsize=8.5, color=TINTA)

        eixo.set_xticks(posicoes, [NOMES_CURTOS[m].replace(" (", "\n(")
                                   .replace(" sem ", "\nsem ")
                                   for m in metodos], fontsize=8.5)
        piso = min(antes[metodos].median().min(),
                   depois[metodos].median().min())
        teto = max(antes[metodos].median().max(),
                   depois[metodos].median().max())
        eixo.set_ylim(max(0, piso - 0.08), teto + 0.05)
        eixo.set_title(titulo)
        eixo.grid(axis="x", visible=False)

    eixos[0].legend(loc="upper left", ncols=2, fontsize=9)

    return salvar(
        figura, "09_dominio_antes_depois.png",
        "Tratamento do corte de tamanho: avaliação com e sem os commits "
        "fora do domínio",
        "Mediana entre repositórios nunca vistos. Com todos os commits, um "
        "modelo treinado sem o filtro leva vantagem por aprender o corte do "
        "Defectors, que a ordenação por LA não conhece. Dentro do domínio,\n"
        "essa vantagem artificial some e a comparação fica justa. O eixo "
        "não começa em zero para mostrar diferenças pequenas.")


# =============================================================
# Grafico da Sensibilidade
# -------------------------------------------------------------
# Os mesmos métodos na proporção de treino e na proporção natural
# =============================================================
def grafico_da_sensibilidade() -> Path:
    resumo = pd.read_csv(config.PASTA_RESULTADOS / "resumo_metodos.csv")
    metodos = ["aleatorio", "la", "boosting_commit", "modelo_v2"]
    medidas = (("auc_agregado", "AUC com todos os commits juntos"),
               ("auc", "AUC mediano por repositório"),
               ("topo_10", "Taxa de defeito no topo 10% (mediana)"))

    figura, eixos = plt.subplots(1, 3, figsize=(17, 5.3))
    posicoes = np.arange(len(metodos))

    for eixo, (medida, titulo) in zip(eixos, medidas):
        for deslocamento, cenario, rotulo, hachura in (
                (-0.2, "principal", "train (perto de 1:1)", None),
                (0.2, "natural", "test + val (proporção original)", "///")):
            linhas = resumo[resumo["cenario"] == cenario].set_index("metodo")
            valores = linhas.loc[metodos, medida]
            barras = eixo.bar(posicoes + deslocamento, valores, width=0.38,
                              color=[cor_do_metodo(m) for m in metodos],
                              hatch=hachura, edgecolor=SUPERFICIE,
                              label=rotulo)
            for barra, valor in zip(barras, valores):
                eixo.text(barra.get_x() + barra.get_width() / 2,
                          valor + 0.01, decimal(valor, 2), ha="center",
                          fontsize=8.5, color=TINTA)

            if medida == "topo_10":
                base = float(linhas.loc["modelo_v2", "base"])
                eixo.axhline(base, color=APAGADO, linestyle="--",
                             linewidth=1)
                eixo.text(len(metodos) - 0.55, base + 0.01,
                          f"base {porcento(base, 0)}", fontsize=8,
                          color=TINTA_2, ha="right")

        eixo.set_xticks(posicoes, [NOMES_CURTOS[m].replace(" (", "\n(")
                                   for m in metodos], fontsize=8.5)
        eixo.set_ylim(0, 1)
        eixo.set_title(titulo)
        eixo.grid(axis="x", visible=False)

    manual = [plt.Rectangle((0, 0), 1, 1, facecolor=EIXO),
              plt.Rectangle((0, 0), 1, 1, facecolor=EIXO, hatch="///",
                            edgecolor=SUPERFICIE)]
    eixos[0].legend(manual, ["train (perto de 1:1), barra lisa",
                             "test + val (proporção original), hachurada"],
                    loc="upper left")

    return salvar(
        figura, "10_sensibilidade_natural.png",
        "Sensibilidade: o resultado se mantém nos commits com a proporção "
        "original de defeitos?",
        "Não por inteiro: na proporção original o AUC cai de cerca de 0,77 "
        "para cerca de 0,70, e o v2 não se distingue de LA (11 repositórios "
        "avaliáveis). A taxa de defeito no topo acompanha a base, que cai "
        "de 38% para 10%.\nÉ o cenário mais próximo do uso real, e o número "
        "que o site deve citar.")


# =============================================================
# EXPLICAÇÃO DO MODELO
# =============================================================


# =============================================================
# Grafico da Permutacao
# -------------------------------------------------------------
# Queda do AUC ao embaralhar cada feature, em projeto nunca visto
# =============================================================
def grafico_da_permutacao() -> Path:
    permutacao = pd.read_csv(config.PASTA_RESULTADOS / "permutacao.csv")
    grupos = permutacao[permutacao["feature"].str.startswith("grupo:")]
    simples = permutacao[~permutacao["feature"].str.startswith("grupo:")]

    resumo = simples.groupby("feature")["queda_auc"].quantile(
        [0.25, 0.5, 0.75]).unstack().sort_values(0.5).tail(14)
    figura, eixos = plt.subplots(1, 2, figsize=(15, 6.4),
                                 gridspec_kw={"width_ratios": [2.2, 1]})

    cores = [CORES["modelo_v2"] if features.grupo_da_feature(f) == "commit"
             else CORES["original"] for f in resumo.index]
    eixos[0].barh(range(len(resumo)), resumo[0.5], color=cores, height=0.62)
    eixos[0].hlines(range(len(resumo)), resumo[0.25], resumo[0.75],
                    color=TINTA_2, linewidth=1.3)
    eixos[0].set_yticks(range(len(resumo)),
                        [features.nome_legivel(f) for f in resumo.index],
                        fontsize=9)
    eixos[0].set_xlabel("queda do AUC ao embaralhar a medida (mediana e "
                        "quartis entre repositórios)")
    eixos[0].xaxis.set_major_formatter(lambda v, _: decimal(v, 2))
    eixos[0].grid(axis="y", visible=False)
    eixos[0].set_title("As 14 medidas que mais pesam, uma por vez")
    eixos[0].barh([0], [0], color=CORES["modelo_v2"], label="do commit")
    eixos[0].barh([0], [0], color=CORES["original"],
                  label="do histórico do arquivo")
    eixos[0].legend(loc="lower right")

    por_grupo = grupos.groupby("feature")["queda_auc"].median()
    nomes = {"grupo:commit": "Todas as do commit",
             "grupo:historico": "Todas as do histórico"}
    barras = eixos[1].bar([nomes[g] for g in por_grupo.index], por_grupo,
                          color=[CORES["modelo_v2"], CORES["original"]],
                          width=0.55)
    for barra, valor in zip(barras, por_grupo):
        eixos[1].text(barra.get_x() + barra.get_width() / 2, valor + 0.004,
                      decimal(valor), ha="center", color=TINTA)
    eixos[1].set_ylabel("queda do AUC")
    eixos[1].yaxis.set_major_formatter(lambda v, _: decimal(v, 2))
    eixos[1].grid(axis="x", visible=False)
    eixos[1].set_title("Embaralhando o grupo inteiro")

    return salvar(
        figura, "11_importancia_permutacao.png",
        "Importância por permutação, medida em projeto nunca visto",
        "Cada medida é embaralhada entre os commits do repositório deixado "
        "de fora, e mede-se quanto o AUC cai. Medidas do commit são "
        "correlacionadas entre si (LA, LA + LD, linhas por arquivo), então "
        "o peso individual\nsubestima o grupo: por isso o painel da direita "
        "embaralha o grupo inteiro de uma vez.")


# =============================================================
# Grafico da Calibracao
# -------------------------------------------------------------
# A nota como chance: antes e depois de calibrar
# =============================================================
def grafico_da_calibracao() -> Path:
    curvas = pd.read_csv(config.PASTA_RESULTADOS / "calibracao_curvas.csv")
    resumo = pd.read_csv(config.PASTA_RESULTADOS
                         / "calibracao.csv").set_index("forma")
    formas = (("sem_calibrar", "Nota bruta do modelo", CORES["la"]),
              ("prevalencia", "Correção de prevalência", CORES["original"]),
              ("platt", "Platt (logística)", CORES["modelo_v2"]),
              ("isotonica", "Isotônica", CORES["boosting_completo"]))

    figura, eixos = plt.subplots(1, 2, figsize=(13.5, 6),
                                 gridspec_kw={"width_ratios": [1.25, 1]})
    eixos[0].plot([0, 1], [0, 1], color=APAGADO, linestyle="--",
                  linewidth=1.2, label="calibração perfeita")

    for forma, nome, cor in formas:
        curva = curvas[curvas["forma"] == forma]
        eixos[0].plot(curva["nota_media"], curva["taxa_observada"],
                      marker="o", markersize=6, color=cor,
                      markeredgecolor=SUPERFICIE,
                      label=f"{nome} — erro "
                            f"{decimal(resumo.loc[forma, 'erro_calibracao'])}")

    eixos[0].set_xlabel("chance estimada (média da faixa)")
    eixos[0].set_ylabel("taxa de defeito observada")
    eixos[0].xaxis.set_major_formatter(lambda v, _: porcento(v, 0))
    eixos[0].yaxis.set_major_formatter(lambda v, _: porcento(v, 0))
    eixos[0].legend(loc="upper left")
    eixos[0].set_title("Curva de confiabilidade, test + val")

    nomes = [nome.replace(" (", "\n(").replace(" de ", "\nde ")
             for _, nome, _ in formas]
    valores = [resumo.loc[forma, "brier"] for forma, _, _ in formas]
    barras = eixos[1].bar(nomes, valores, width=0.6,
                          color=[cor for _, _, cor in formas])
    for barra, valor in zip(barras, valores):
        eixos[1].text(barra.get_x() + barra.get_width() / 2, valor + 0.002,
                      decimal(valor), ha="center", color=TINTA)
    eixos[1].set_ylabel("Brier (menor é melhor)")
    eixos[1].yaxis.set_major_formatter(lambda v, _: decimal(v, 2))
    eixos[1].tick_params(axis="x", labelsize=8.5)
    eixos[1].grid(axis="x", visible=False)
    eixos[1].set_title("Erro quadrático da chance estimada")

    return salvar(
        figura, "12_calibracao.png",
        "A nota bruta não é uma chance: o treino tem cerca de 37% de "
        "defeituosos e o uso real, cerca de 10%",
        "Cada calibrador é ajustado só com repositórios diferentes do "
        "avaliado. A nota bruta superestima a chance porque a partição de "
        "treino foi reamostrada. O site mostra a chance calibrada e, mesmo "
        "assim,\na apresenta como estimativa: a taxa natural varia entre "
        "projetos.")


# =============================================================
# Grafico das Faixas
# -------------------------------------------------------------
# Taxa de defeito observada em cada faixa de risco do site
# =============================================================
def grafico_das_faixas() -> Path:
    faixas = pd.read_csv(config.PASTA_RESULTADOS / "faixas_de_risco.csv")
    cores = {"alto": COR_DEFEITO, "médio": "#fab219", "baixo": "#0ca30c"}
    titulos = {"natural": "test + val (proporção original)",
               "principal": "train (perto de 1:1)"}

    figura, eixos = plt.subplots(1, 2, figsize=(12.5, 5), sharey=True)
    for eixo, cenario in zip(eixos, ("natural", "principal")):
        grupo = faixas[faixas["cenario"] == cenario]
        barras = eixo.bar(grupo["faixa"], grupo["taxa_de_defeito"],
                          width=0.58,
                          color=[cores[f] for f in grupo["faixa"]])
        for barra, (_, linha) in zip(barras, grupo.iterrows()):
            eixo.text(barra.get_x() + barra.get_width() / 2,
                      barra.get_height() + 0.012,
                      f"{porcento(linha['taxa_de_defeito'])}\n"
                      f"{porcento(linha['parcela_dos_defeitos'], 0)} dos "
                      f"defeitos\nn={int(linha['commits'])}",
                      ha="center", va="bottom", fontsize=9, color=TINTA)

        base = float(grupo["taxa_geral"].iloc[0])
        eixo.axhline(base, color=APAGADO, linestyle="--", linewidth=1.2)
        eixo.text(2.45, base + 0.012, f"taxa geral {porcento(base)}",
                  ha="right", fontsize=9, color=TINTA_2)
        eixo.set_ylim(0, 1)
        eixo.yaxis.set_major_formatter(lambda v, _: porcento(v, 0))
        eixo.set_title(titulos[cenario])
        eixo.grid(axis="x", visible=False)

    eixos[0].set_ylabel("commits defeituosos na faixa")

    return salvar(
        figura, "13_faixas_de_risco.png",
        "O que significa \"alto\", \"médio\" e \"baixo\" no site",
        "Alto = 10% de notas mais altas; médio = os 20% seguintes; baixo = "
        "os 70% restantes, com os cortes medidos nas notas de projeto nunca "
        "visto. O site usa os cortes e as taxas do painel da esquerda.")


# =============================================================
# Grafico da Significancia
# -------------------------------------------------------------
# Diferença do v2 para cada método, com teste pareado
# =============================================================
def grafico_da_significancia() -> Path:
    testes = pd.read_csv(config.PASTA_RESULTADOS / "significancia.csv")
    testes = testes[testes["cenario"] == "principal"]
    titulos = {"auc": "AUC",
               "topo_10": "Topo 10%",
               "popt_densidade": "Popt (risco por linha)",
               "revocacao_esforco_densidade": "Recall@20%Effort "
                                              "(risco por linha)"}
    outros = [m for m in ("la", "menor_primeiro", "logistica_commit",
                          "boosting_commit", "boosting_completo",
                          "v2_equilibrado", "v2_sem_dominio", "original")
              if m in set(testes["metodo_b"])]

    figura, eixos = plt.subplots(2, 2, figsize=(15, 9.4), sharey=True)
    for eixo, (medida, titulo) in zip(eixos.ravel(), titulos.items()):
        grupo = testes[testes["medida"] == medida].set_index("metodo_b")
        grupo = grupo.loc[outros]
        posicoes = np.arange(len(outros))
        significativo = grupo["valor_p_holm"] < 0.05

        eixo.axvline(0, color=TINTA_2, linewidth=1)
        eixo.barh(posicoes, grupo["diferenca_mediana"].clip(-LIMITE_DA_BARRA,
                                                             LIMITE_DA_BARRA),
                  height=0.56,
                  color=[CORES["modelo_v2"] if s else COR_NEUTRA
                         for s in significativo])
        eixo.set_xlim(-LIMITE_DA_BARRA, LIMITE_DA_BARRA)

        for posicao, (_, linha) in zip(posicoes, grupo.iterrows()):
            cortada = abs(linha["diferenca_mediana"]) > LIMITE_DA_BARRA
            eixo.text(1.02, posicao,
                      f"{linha['diferenca_mediana']:+.3f}".replace(".", ",")
                      + (" (barra cortada)" if cortada else "")
                      + f"   {int(linha['vitorias'])}–"
                      f"{int(linha['derrotas'])}   "
                      f"p={decimal(linha['valor_p_holm'])}   "
                      f"δ={decimal(linha['delta_cliff'], 2)}",
                      transform=eixo.get_yaxis_transform(), va="center",
                      ha="left", fontsize=8.5, color=TINTA)

        eixo.set_yticks(posicoes, [NOMES_CURTOS[m] for m in outros])
        eixo.xaxis.set_major_formatter(lambda v, _: decimal(v, 2))
        eixo.set_title(titulo)
        eixo.grid(axis="y", visible=False)
        eixo.set_xlabel("diferença mediana (v2 − outro)")

    return salvar(
        figura, "14_significancia.png",
        "DefectLens v2 contra cada método: Wilcoxon pareado entre 23 "
        "repositórios, com correção de Holm",
        "Barra para a direita: v2 melhor. Azul forte: p ajustado < 0,05. "
        "Ao lado, vitórias–derrotas entre repositórios, p ajustado e delta "
        "de Cliff (|δ| < 0,147 é desprezível; < 0,33 pequeno; < 0,474 "
        "médio).")


# =============================================================
# Desenhar
# -------------------------------------------------------------
# Gera todos os gráficos
# =============================================================
def desenhar() -> list[Path]:
    preparar_estilo()
    previsoes = analisar.ler_previsoes()

    return [
        grafico_das_particoes(),
        grafico_da_taxa_por_tamanho(),
        grafico_por_repositorio(),
        grafico_da_comparacao(),
        grafico_das_curvas_roc(previsoes),
        grafico_das_curvas_de_esforco(previsoes),
        grafico_das_medidas_de_esforco(),
        grafico_da_ablacao(),
        grafico_do_dominio(),
        grafico_da_sensibilidade(),
        grafico_da_permutacao(),
        grafico_da_calibracao(),
        grafico_das_faixas(),
        grafico_da_significancia(),
    ]


if __name__ == "__main__":
    for caminho in desenhar():
        print(f"  {caminho}")

"""
Limpa o dataset antes do treino e descreve o que as features têm.

CMD -> python frente1_treinamento/preparacao.py
       roda sozinho sobre dados/dataset.csv e só relata, sem treinar
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI))

import config
import divisao
from extrator import derivadas, features


# =============================================================
# DIAGNÓSTICO
# =============================================================


# =============================================================
# Juntar Commits
# -------------------------------------------------------------
# Acrescenta as métricas de commit ao dataset
# =============================================================
def juntar_commits(dados: pd.DataFrame) -> pd.DataFrame:
    caminhos = sorted(config.PASTA_COMMITS.glob("*.csv"))

    if not caminhos:
        raise SystemExit(f"{config.PASTA_COMMITS} está vazia. Rode "
                         f"python frente1_treinamento/medir_commits.py")

    commits = pd.concat([pd.read_csv(c) for c in caminhos],
                        ignore_index=True)
    juntos = dados.merge(commits, on=["repositorio", "commit"], how="left",
                         validate="many_to_one")
    faltando = juntos[juntos[features.COLUNAS_COMMIT[0]].isna()]

    if len(faltando):
        nomes = sorted(faltando["repositorio"].unique())
        raise SystemExit(f"{len(faltando)} retratos sem métricas de commit "
                         f"em: {', '.join(nomes)}. Rode "
                         f"python frente1_treinamento/medir_commits.py")

    return juntos


# =============================================================
# Marcar Invalidos
# -------------------------------------------------------------
# Troca por vazio tudo que não é número utilizável
# =============================================================
def marcar_invalidos(dados: pd.DataFrame) -> pd.DataFrame:
    limpo = dados.copy()

    for coluna in features.FEATURES:
        valores = pd.to_numeric(limpo[coluna], errors="coerce")
        limpo[coluna] = valores.replace([np.inf, -np.inf], np.nan)

    return limpo


# =============================================================
# Diagnosticar
# -------------------------------------------------------------
# Monta uma linha de diagnóstico por feature
# =============================================================
def diagnosticar(dados: pd.DataFrame) -> pd.DataFrame:
    linhas = []

    for coluna in features.FEATURES:
        valores = pd.to_numeric(dados[coluna], errors="coerce")
        infinitos = int(np.isinf(valores.to_numpy(dtype=float)).sum())
        faltando = int(valores.isna().sum()) + infinitos
        finitos = valores.replace([np.inf, -np.inf], np.nan).dropna()

        linhas.append({
            "feature":    coluna,
            "faltando":   faltando,
            "%faltando":  round(100 * faltando / len(dados), 2),
            "infinitos":  infinitos,
            "zeros":      int((finitos == 0).sum()),
            "negativos":  int((finitos < 0).sum()),
            "minimo":     round(float(finitos.min()), 2) if len(finitos) else np.nan,
            "media":      round(float(finitos.mean()), 2) if len(finitos) else np.nan,
            "maximo":     round(float(finitos.max()), 2) if len(finitos) else np.nan,
        })

    return pd.DataFrame(linhas)


# =============================================================
# Mostrar Diagnostico
# -------------------------------------------------------------
# Imprime o quadro de diagnóstico
# =============================================================
def mostrar_diagnostico(quadro: pd.DataFrame) -> None:
    print(f"\n  {'feature':<28} {'faltando':>9} {'%':>7} {'inf':>5} "
          f"{'zeros':>7} {'neg':>5} {'mínimo':>10} {'média':>10} "
          f"{'máximo':>10}")

    for _, l in quadro.iterrows():
        print(f"  {l['feature']:<28} {int(l['faltando']):>9} "
              f"{l['%faltando']:>6.2f}% {int(l['infinitos']):>5} "
              f"{int(l['zeros']):>7} {int(l['negativos']):>5} "
              f"{l['minimo']:>10.2f} {l['media']:>10.2f} "
              f"{l['maximo']:>10.2f}")


# =============================================================
# TRATAMENTO
# =============================================================


# =============================================================
# Descartar Linhas Inaproveitaveis
# -------------------------------------------------------------
# Tira as linhas com features demais faltando
# =============================================================
def descartar_linhas_inaproveitaveis(
        dados: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    quantas = dados[features.FEATURES].isna().sum(axis=1)
    limite = int(len(features.FEATURES) * config.FRACAO_MAXIMA_FALTANTE)

    manter = quantas <= limite
    return dados[manter].reset_index(drop=True), int((~manter).sum())


# =============================================================
# Medias do Treino
# -------------------------------------------------------------
# Calcula as médias só com as linhas de treino
# =============================================================
def medias_do_treino(treino: pd.DataFrame) -> pd.Series:
    medias = treino[features.FEATURES].mean()

    return medias.fillna(0.0)


# =============================================================
# Preencher
# -------------------------------------------------------------
# Preenche os vazios com as médias do treino
# =============================================================
def preencher(dados: pd.DataFrame, medias: pd.Series) -> pd.DataFrame:
    cheio = dados.copy()
    cheio[features.FEATURES] = cheio[features.FEATURES].fillna(medias)
    return cheio


# =============================================================
# Preparar
# -------------------------------------------------------------
# Limpa os dois conjuntos e relata o que foi feito
# =============================================================
def preparar(treino: pd.DataFrame,
             teste: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    print("\n" + "-" * 70)
    print("PRÉ-PROCESSAMENTO")
    print("-" * 70)

    treino = marcar_invalidos(treino)
    teste = marcar_invalidos(teste) if len(teste) else teste

    antes_treino, antes_teste = len(treino), len(teste)

    treino, fora_treino = descartar_linhas_inaproveitaveis(treino)
    if len(teste):
        teste, fora_teste = descartar_linhas_inaproveitaveis(teste)
    else:
        fora_teste = 0

    buracos_treino = int(treino[features.FEATURES].isna().sum().sum())
    buracos_teste = (int(teste[features.FEATURES].isna().sum().sum())
                     if len(teste) else 0)

    medias = medias_do_treino(treino)

    treino = preencher(treino, medias)
    if len(teste):
        teste = preencher(teste, medias)

    limite = int(len(features.FEATURES) * config.FRACAO_MAXIMA_FALTANTE)

    print(f"\n  Descartadas por faltar mais de {limite} das "
          f"{len(features.FEATURES)} features:")
    print(f"    treino : {fora_treino} de {antes_treino}")
    print(f"    teste  : {fora_teste} de {antes_teste}")

    print(f"\n  Valores preenchidos com a média do treino:")
    print(f"    treino : {buracos_treino}")
    print(f"    teste  : {buracos_teste}")

    constantes = [c for c in features.FEATURES
                  if treino[c].nunique(dropna=True) <= 1]
    if constantes:
        print(f"\n  Constantes no treino, sem poder informativo: "
              f"{', '.join(constantes)}")

    if buracos_treino or buracos_teste:
        print("\n  Médias usadas (vindas do treino):")
        for coluna in features.FEATURES:
            print(f"    {coluna:<28} {medias[coluna]:>12.3f}")
    else:
        print("    nenhum buraco: o preenchimento não alterou nada")

    return treino, teste


# =============================================================
# DESCRIÇÃO
# =============================================================


# =============================================================
# Matriz de Correlacao
# -------------------------------------------------------------
# Correlação entre as features e o rótulo
# =============================================================
def matriz_de_correlacao(dados: pd.DataFrame,
                         metodo: str = "spearman") -> pd.DataFrame:
    colunas = features.FEATURES + [features.COLUNA_ALVO]
    return dados[colunas].corr(method=metodo)


# =============================================================
# Salvar Correlacoes
# -------------------------------------------------------------
# Grava as matrizes de Spearman e Pearson
# =============================================================
def salvar_correlacoes(dados: pd.DataFrame) -> pd.DataFrame:
    config.PASTA_DADOS.mkdir(parents=True, exist_ok=True)

    spearman = matriz_de_correlacao(dados, "spearman")
    pearson = matriz_de_correlacao(dados, "pearson")

    spearman.round(4).to_csv(config.ARQUIVO_CORRELACAO, encoding="utf-8")
    pearson.round(4).to_csv(config.ARQUIVO_CORRELACAO_PEARSON,
                            encoding="utf-8")

    return spearman


# =============================================================
# Mostrar Correlacao com o Alvo
# -------------------------------------------------------------
# Imprime a correlação com o rótulo e os pares redundantes
# =============================================================
def mostrar_correlacao_com_alvo(spearman: pd.DataFrame) -> None:
    coluna = spearman[features.COLUNA_ALVO].drop(features.COLUNA_ALVO)

    ordem = coluna.abs().sort_values(ascending=False,
                                     na_position="last").index

    print(f"\n  Correlação de Spearman com '{features.COLUNA_ALVO}'")

    for nome in ordem:
        valor = coluna[nome]

        if pd.isna(valor):
            print(f"    {nome:<28} {'—':>7}  (constante no treino)")
            continue

        barra = "#" * int(round(abs(valor) * 50))
        print(f"    {nome:<28} {valor:>+7.3f}  {barra}")

    sem_alvo = spearman.drop(index=features.COLUNA_ALVO,
                             columns=features.COLUNA_ALVO)
    pares = []

    for i, a in enumerate(sem_alvo.columns):
        for b in sem_alvo.columns[i + 1:]:
            if abs(sem_alvo.loc[a, b]) >= config.CORRELACAO_ALTA:
                pares.append((abs(sem_alvo.loc[a, b]), a, b,
                              sem_alvo.loc[a, b]))

    if pares:
        pares.sort(reverse=True)
        mostrados = pares[:config.TOPO_PARES]

        print(f"\n  Pares de features com |correlação| >= "
              f"{config.CORRELACAO_ALTA} "
              f"({len(mostrados)} de {len(pares)})")
        for _, a, b, valor in mostrados:
            print(f"    {a:<28} {b:<28} {valor:>+7.3f}")
        print("    Elas carregam informação parecida, então a "
              "importância se divide entre elas.")


# =============================================================
# Salvar Mapa de Calor
# -------------------------------------------------------------
# Desenha a matriz de correlação
# =============================================================
def salvar_mapa_de_calor(matriz: pd.DataFrame) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n  Mapa de calor não gerado: falta o matplotlib.")
        print("    pip install matplotlib")
        return False

    nomes = list(matriz.columns)
    valores = matriz.to_numpy(dtype=float)
    quantas = len(nomes)

    lado = max(9.0, 0.42 * quantas + 3.5)
    figura, eixo = plt.subplots(figsize=(lado, lado * 0.85))

    imagem = eixo.imshow(valores, cmap="RdBu_r", vmin=-1, vmax=1)

    fonte = 9 if quantas <= 16 else 7

    eixo.set_xticks(range(quantas))
    eixo.set_yticks(range(quantas))
    eixo.set_xticklabels(nomes, rotation=45, ha="right", fontsize=fonte)
    eixo.set_yticklabels(nomes, fontsize=fonte)

    if quantas <= config.MAXIMO_ANOTADO:
        for i in range(quantas):
            for j in range(quantas):
                valor = valores[i, j]
                if np.isnan(valor):
                    continue
                cor = "white" if abs(valor) > 0.55 else "black"
                eixo.text(j, i, f"{valor:.2f}", ha="center", va="center",
                          color=cor, fontsize=fonte - 1)

    eixo.set_title(f"Correlação de Spearman entre as {quantas - 1} "
                   f"features e o defeito\n(conjunto de treino)",
                   fontsize=12, pad=14)

    figura.colorbar(imagem, ax=eixo, shrink=0.8,
                    label="coeficiente de Spearman")
    figura.tight_layout()

    config.PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    figura.savefig(config.ARQUIVO_MAPA_DE_CALOR, dpi=150)
    plt.close(figura)

    return True


# =============================================================
# Descrever
# -------------------------------------------------------------
# Grava as correlações e o mapa de calor, a partir do treino
# =============================================================
def descrever(treino: pd.DataFrame) -> None:
    print("\n" + "-" * 70)
    print("CORRELAÇÃO ENTRE AS MÉTRICAS")
    print("-" * 70)

    spearman = salvar_correlacoes(treino)
    mostrar_correlacao_com_alvo(spearman)

    print(f"\n  Matriz de Spearman: {config.ARQUIVO_CORRELACAO}")
    print(f"  Matriz de Pearson : {config.ARQUIVO_CORRELACAO_PEARSON}")

    if salvar_mapa_de_calor(spearman):
        print(f"  Mapa de calor     : {config.ARQUIVO_MAPA_DE_CALOR}")


# =============================================================
# Main
# -------------------------------------------------------------
# Modo avulso: só diagnostica e descreve, sem treinar
# =============================================================
def main() -> None:
    if not config.ARQUIVO_DATASET.exists():
        raise SystemExit(
            f"{config.ARQUIVO_DATASET} não existe. Monte o dataset "
            f"primeiro:\n"
            f"  python frente1_treinamento/montar_dataset.py"
        )

    dados = pd.read_csv(config.ARQUIVO_DATASET)
    features.conferir_contrato(dados.columns)
    dados = juntar_commits(dados)

    dados = derivadas.acrescentar(dados, features.COLUNAS_BASE)

    print("=" * 70)
    print("DIAGNÓSTICO DO DATASET")
    print("=" * 70)
    print(f"\n  arquivo : {config.ARQUIVO_DATASET}")
    print(f"  {len(dados)} linhas, "
          f"{dados['repositorio'].nunique()} repositórios")
    print(f"  {len(features.COLUNAS_BASE)} medidas + "
          f"{len(derivadas.colunas_ativas(features.COLUNAS_BASE))} derivadas + "
          f"{len(features.COLUNAS_COMMIT)} de commit")
    print(f"  derivadas: {derivadas.descrever(features.COLUNAS_BASE)}")

    mostrar_diagnostico(diagnosticar(dados))

    dados[features.COLUNA_PARTICAO] = divisao.dividir(dados)
    treino = dados[dados[features.COLUNA_PARTICAO] == "treino"]
    teste = dados[dados[features.COLUNA_PARTICAO] == "teste"]

    treino, _ = preparar(treino, teste)
    descrever(treino)
    print()


if __name__ == "__main__":
    config.conferir_local()
    main()

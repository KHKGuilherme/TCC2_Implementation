"""
Treina o modelo a partir de dados/dataset.csv e grava o resultado em modelos/modelo.joblib.

CMD -> python frente1_treinamento/treinar.py
       python frente1_treinamento/treinar.py --so-ranking
              refaz o ranking por arquivo a partir de dados/previsoes.csv
       python frente1_treinamento/treinar.py --so-final
              pula as comparações e treina só o config.MODELO_FINAL
"""

import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (roc_auc_score, f1_score, matthews_corrcoef,
                             precision_score, recall_score, confusion_matrix)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI))

import balanceamento
import config
import divisao
import graficos
import preparacao
from extrator import derivadas, features

COLUNAS_DE_ORDEM = ("idade_dias", "revisoes")


# =============================================================
# Criar Modelos
# -------------------------------------------------------------
# Monta as Opções a serem comparados
# =============================================================
def criar_modelos() -> dict:
    semente = config.SEMENTE

    return {
        "Regressão Logística": Pipeline([
            ("escala", StandardScaler()),
            ("modelo", LogisticRegression(max_iter=2000,
                                          class_weight="balanced",
                                          random_state=semente)),
        ]),
        "Random Forest": Pipeline([
            ("escala", StandardScaler()),
            ("modelo", RandomForestClassifier(
                n_estimators=300,
                min_samples_leaf=config.MINIMO_POR_FOLHA,
                class_weight="balanced",
                random_state=semente,
                n_jobs=-1)),
        ]),
        "Gradient Boosting": Pipeline([
            ("escala", StandardScaler()),
            ("modelo", GradientBoostingClassifier(random_state=semente)),
        ]),
    }


# =============================================================
# Calcular Metricas
# -------------------------------------------------------------
# Avalia previsões contra o gabarito
# =============================================================
def calcular_metricas(verdade, probabilidade) -> dict:
    previsao = (probabilidade >= config.LIMIAR_DECISAO).astype(int)

    tem_duas_classes = len(np.unique(verdade)) > 1
    auc = roc_auc_score(verdade, probabilidade) if tem_duas_classes else np.nan

    return {
        "AUC":       auc,
        "F1":        f1_score(verdade, previsao, zero_division=0),
        "MCC":       matthews_corrcoef(verdade, previsao),
        "Precisão":  precision_score(verdade, previsao, zero_division=0),
        "Revocação": recall_score(verdade, previsao, zero_division=0),
    }


# =============================================================
# Prever Fora da Amostra
# -------------------------------------------------------------
# Previsões sem ter visto a linha
# =============================================================
def prever_fora_da_amostra(modelo, X, y, grupos, divisor):
    probabilidades = np.full(len(y), np.nan)

    for indices_treino, indices_teste in divisor.split(X, y, groups=grupos):
        if len(np.unique(y[indices_treino])) < 2:
            continue

        modelo.fit(X[indices_treino], y[indices_treino])
        probabilidades[indices_teste] = modelo.predict_proba(
            X[indices_teste])[:, 1]

    return probabilidades


# =============================================================
# Mostrar Tabela
# -------------------------------------------------------------
# Imprime um quadro de métricas
# =============================================================
def mostrar_tabela(titulo: str, resultados: dict) -> None:
    print(f"\n  {titulo}")
    print(f"    {'':<24} {'AUC':>7} {'F1':>7} {'MCC':>7} "
          f"{'Precisão':>9} {'Revocação':>10}")

    for nome, m in resultados.items():
        print(f"    {nome:<24} {m['AUC']:>7.3f} {m['F1']:>7.3f} "
              f"{m['MCC']:>7.3f} {m['Precisão']:>9.3f} "
              f"{m['Revocação']:>10.3f}")


# =============================================================
# So Maduros
# -------------------------------------------------------------
# Tira os retratos recentes, cujo rótulo não é confiável
# =============================================================
def so_maduros(dados: pd.DataFrame) -> pd.DataFrame:
    if not config.PARTICOES_MADURAS:
        return dados

    maduros = dados[features.COLUNA_PARTICAO_DEFECTORS].astype(str).isin(
        config.PARTICOES_MADURAS)
    return dados[maduros]


# =============================================================
# Carregar Dados
# -------------------------------------------------------------
# lê o dataset e aplica a divisão atual
# =============================================================
def carregar_dados() -> tuple[pd.DataFrame, pd.DataFrame]:
    dados = pd.read_csv(config.ARQUIVO_DATASET)
    features.conferir_contrato(dados.columns)
    dados = preparacao.juntar_commits(dados)

    dados = derivadas.acrescentar(dados, features.COLUNAS_BASE)

    gravada = dados[features.COLUNA_PARTICAO]
    atual = divisao.dividir(dados)

    if not gravada.equals(atual):
        print("\n  A divisão gravada no dataset foi feita com outra "
              "configuração.")
        print("  Usando a estratégia atual do config.py.")

    dados[features.COLUNA_PARTICAO] = atual

    treino = so_maduros(dados[dados[features.COLUNA_PARTICAO] == "treino"])
    teste = dados[dados[features.COLUNA_PARTICAO] == "teste"]

    return preparacao.preparar(treino, teste)


# =============================================================
# Comparar Modelos
# -------------------------------------------------------------
# Escolhe o melhor dentro do treino por AUC
# =============================================================
def comparar_modelos(treino: pd.DataFrame, grupos, divisor) -> str:
    y = treino[features.COLUNA_ALVO].to_numpy()
    X = treino[features.FEATURES].to_numpy(dtype=float)

    resultados = {}

    for nome, modelo in criar_modelos().items():
        probabilidade = prever_fora_da_amostra(modelo, X, y, grupos, divisor)
        validas = ~np.isnan(probabilidade)
        resultados[nome] = calcular_metricas(y[validas],
                                             probabilidade[validas])

    apenas_linhas = treino[["linhas"]].to_numpy(dtype=float)
    probabilidade = prever_fora_da_amostra(
        criar_modelos()["Random Forest"], apenas_linhas, y, grupos, divisor)
    validas = ~np.isnan(probabilidade)
    resultados["referência: só linhas"] = calcular_metricas(
        y[validas], probabilidade[validas])

    mostrar_tabela("Comparação dentro do treino", resultados)

    candidatos = {n: m for n, m in resultados.items()
                  if not n.startswith("referência")}
    melhor = max(candidatos, key=lambda n: candidatos[n]["AUC"])

    print(f"\n    Melhor por AUC: {melhor}")
    return melhor


# =============================================================
# Comparar Grupos de Features
# -------------------------------------------------------------
# código contra histórico
# =============================================================
def comparar_grupos_de_features(treino: pd.DataFrame, nome_modelo: str,
                                grupos, divisor) -> None:

    y = treino[features.COLUNA_ALVO].to_numpy()

    base = features.COLUNAS_BASE

    conjuntos = {
        "só 'linhas'":      ["linhas"],
        "só 'revisoes'":    ["revisoes"],
        "só código (6)":    features.COLUNAS_CODIGO,
        "só histórico (3)": features.COLUNAS_HISTORICO,
        f"só commit ({len(features.COLUNAS_COMMIT)})": features.COLUNAS_COMMIT,
        f"medidas ({len(base)})": base,
    }

    for nome in derivadas.grupos_ligados():
        colunas = derivadas.colunas_do_grupo(nome, base)
        conjuntos[f"medidas + {nome} (+{len(colunas)})"] = base + colunas

    if len(features.FEATURES) > len(base):
        conjuntos[f"tudo ({len(features.FEATURES)})"] = features.FEATURES

    print("\n  Contribuição de cada grupo de features")
    print(f"    {'':<30} {'AUC':>7}")

    for nome, colunas in conjuntos.items():
        X = treino[colunas].to_numpy(dtype=float)
        probabilidade = prever_fora_da_amostra(
            criar_modelos()[nome_modelo], X, y, grupos, divisor)
        validas = ~np.isnan(probabilidade)
        auc = calcular_metricas(y[validas], probabilidade[validas])["AUC"]
        print(f"    {nome:<30} {auc:>7.3f}")


# =============================================================
# Mostrar Importancia
# -------------------------------------------------------------
# Peso de cada feature no modelo
# =============================================================
def mostrar_importancias(modelo) -> None:
    interno = modelo.named_steps["modelo"]

    if hasattr(interno, "feature_importances_"):
        pesos = interno.feature_importances_
        origem = "contribuição nas árvores"
    elif hasattr(interno, "coef_"):
        bruto = np.abs(interno.coef_[0])
        total = bruto.sum()
        pesos = bruto / total if total else bruto
        origem = "coeficientes padronizados"
    else:
        print("\n  Importância das features: não disponível "
              "para este modelo.")
        return

    print(f"\n  Importância das features ({origem})")
    for i in np.argsort(pesos)[::-1]:
        barra = "#" * int(round(pesos[i] * 60))
        print(f"    {features.FEATURES[i]:<28} {pesos[i]:.3f}  {barra}")

    por_origem = {}
    for i, coluna in enumerate(features.FEATURES):
        origem = features.origem_da_feature(coluna)
        por_origem[origem] = por_origem.get(origem, 0.0) + pesos[i]

    print("\n    Peso por origem da informação")
    for origem, peso in sorted(por_origem.items(),
                               key=lambda p: -p[1]):
        print(f"      {origem:<22} {100 * peso:>5.1f}%")


# =============================================================
# Gravar Previsoes
# -------------------------------------------------------------
# A probabilidade de cada par (arquivo, commit) reservado
# =============================================================
def gravar_previsoes(teste: pd.DataFrame, probabilidade) -> pd.DataFrame:
    previsoes = pd.DataFrame({
        "repositorio":  teste["repositorio"].to_numpy(),
        "arquivo":      teste["arquivo"].to_numpy(),
        "commit":       teste["commit"].to_numpy(),
        "probabilidade": probabilidade.round(4),
        "previsto":     (probabilidade >= config.LIMIAR_DECISAO).astype(int),
        "real":         teste[features.COLUNA_ALVO].to_numpy(),
    })

    config.PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    previsoes.to_csv(config.ARQUIVO_PREVISOES, index=False,
                     encoding="utf-8")

    return previsoes


# =============================================================
# Acrescentar Ordem
# -------------------------------------------------------------
# Traz do dataset as colunas que ordenam os retratos no tempo
# =============================================================
def acrescentar_ordem(previsoes: pd.DataFrame) -> pd.DataFrame:
    chave = ["repositorio", "arquivo", "commit"]
    ordem = pd.read_csv(config.ARQUIVO_DATASET,
                        usecols=chave + list(COLUNAS_DE_ORDEM))

    return previsoes.merge(ordem, on=chave, how="left",
                           validate="one_to_one")


# =============================================================
# Risco por Arquivo
# -------------------------------------------------------------
# Uma linha por arquivo, pelo seu retrato mais recente
# =============================================================
def risco_por_arquivo(previsoes: pd.DataFrame) -> pd.DataFrame:
    ordenadas = previsoes.sort_values(
        ["repositorio", "arquivo", *COLUNAS_DE_ORDEM], kind="stable")

    risco = ordenadas.groupby(["repositorio", "arquivo"], as_index=False).agg(
        retratos=("probabilidade", "size"),
        risco_atual=("probabilidade", "last"),
        risco_medio=("probabilidade", "mean"),
        risco_maximo=("probabilidade", "max"),
        commits_com_defeito=("real", "sum"),
        defeito_atual=("real", "last"),
    )

    for coluna in ("risco_atual", "risco_medio", "risco_maximo"):
        risco[coluna] = risco[coluna].round(4)

    return risco.sort_values("risco_atual", ascending=False, kind="stable",
                             ignore_index=True)


# =============================================================
# Risco por Commit
# -------------------------------------------------------------
# Uma linha por commit, pela maior nota entre os arquivos dele
# =============================================================
def risco_por_commit(previsoes: pd.DataFrame) -> pd.DataFrame:
    risco = previsoes.groupby(["repositorio", "commit"], as_index=False).agg(
        arquivos=("probabilidade", "size"),
        risco=("probabilidade", "max"),
        defeito=("real", "max"),
    )

    return risco.sort_values("risco", ascending=False, kind="stable",
                             ignore_index=True)


# =============================================================
# Precisao por Repositorio
# -------------------------------------------------------------
# Acerto no topo de cada projeto, somado entre os projetos
# =============================================================
def precisao_por_repositorio(risco: pd.DataFrame, fracao: float,
                             rotulo: str = "defeito_atual") -> float:
    acertos = 0
    total = 0

    for _, grupo in risco.groupby("repositorio", sort=False):
        quantos = max(1, round(len(grupo) * fracao))
        acertos += int(grupo[rotulo].head(quantos).sum())
        total += quantos

    return acertos / total


# =============================================================
# Mostrar Commits
# -------------------------------------------------------------
# O acerto na unidade do rótulo
# =============================================================
def mostrar_commits(risco: pd.DataFrame) -> float:
    y = risco["defeito"].to_numpy()
    auc = roc_auc_score(y, risco["risco"]) if len(np.unique(y)) > 1 else np.nan

    print(f"\n  Por commit — {len(risco)} commits, {int(y.sum())} com defeito "
          f"({100 * y.mean():.1f}%)")
    print(f"    AUC por commit: {auc:.3f}")

    for fracao in config.FRACOES_POR_REPOSITORIO:
        acerto = precisao_por_repositorio(risco, fracao, "defeito")
        print(f"    topo {100 * fracao:>2.0f}% dos commits de cada projeto: "
              f"{100 * acerto:.1f}%")

    return auc


# =============================================================
# Mostrar Ranking de Arquivos
# -------------------------------------------------------------
# Os arquivos mais arriscados, e o acerto nessa granularidade
# =============================================================
def mostrar_ranking(risco: pd.DataFrame) -> None:
    y = risco["defeito_atual"].to_numpy()

    print(f"\n  Por arquivo, no retrato mais recente — {len(risco)} arquivos "
          f"distintos, {int(y.sum())} com defeito ({100 * y.mean():.1f}%)")

    if len(np.unique(y)) > 1:
        print(f"    AUC por arquivo: "
              f"{roc_auc_score(y, risco['risco_atual']):.3f}")

    print(f"\n  Precisão no topo do ranking geral")
    for quantos in config.TOPOS_AVALIADOS:
        if quantos > len(risco):
            continue
        acertos = int(risco["defeito_atual"].head(quantos).sum())
        print(f"    {quantos:>5} primeiros: {acertos:>5} com defeito "
              f"({100 * acertos / quantos:.1f}%)")
    print(f"    {'base':>5}           : {100 * y.mean():.1f}% "
          f"se escolhesse ao acaso")

    print(f"\n  Precisão no topo de cada repositório")
    for fracao in config.FRACOES_POR_REPOSITORIO:
        print(f"    {100 * fracao:>4.0f}% do projeto: "
              f"{100 * precisao_por_repositorio(risco, fracao):.1f}%")

    quantos = min(config.TOPO_RANKING, len(risco))
    print(f"\n  Os {quantos} arquivos mais arriscados")
    print(f"    {'nota':>6} {'média':>7} {'retratos':>9} {'real':>5}  arquivo")

    for _, linha in risco.head(quantos).iterrows():
        marca = "sim" if linha["defeito_atual"] else "-"
        caminho = f"{linha['repositorio']}/{linha['arquivo']}"
        if len(caminho) > 54:
            caminho = "..." + caminho[-51:]
        print(f"    {100 * linha['risco_atual']:>5.1f}% "
              f"{100 * linha['risco_medio']:>6.1f}% "
              f"{int(linha['retratos']):>9} {marca:>5}  {caminho}")

    print(f"\n  Tabela completa: {config.ARQUIVO_RISCO}")
    print(f"  Previsão de cada retrato: {config.ARQUIVO_PREVISOES}")


# =============================================================
# Avaliar Ranking
# -------------------------------------------------------------
# Das previsões por retrato até a tabela por arquivo
# =============================================================
def avaliar_ranking(previsoes: pd.DataFrame) -> float:
    auc_commit = mostrar_commits(risco_por_commit(previsoes))

    risco = risco_por_arquivo(acrescentar_ordem(previsoes))
    risco.to_csv(config.ARQUIVO_RISCO, index=False, encoding="utf-8")
    mostrar_ranking(risco)

    return auc_commit


# =============================================================
# Avaliar no teste
# -------------------------------------------------------------
# A medição final, nos dados reservados
# =============================================================
def avaliar_no_teste(modelo, teste: pd.DataFrame) -> dict:
    y = teste[features.COLUNA_ALVO].to_numpy()
    X = teste[features.FEATURES].to_numpy(dtype=float)
    auc_com_recentes = roc_auc_score(y, modelo.predict_proba(X)[:, 1])

    maduros = so_maduros(teste)
    if len(maduros):
        teste = maduros

    y = teste[features.COLUNA_ALVO].to_numpy()
    X = teste[features.FEATURES].to_numpy(dtype=float)
    probabilidade = modelo.predict_proba(X)[:, 1]

    print("\n" + "=" * 70)
    print("AVALIAÇÃO FINAL — conjunto reservado")
    print("=" * 70)
    print(f"\n  reserva : {divisao.descrever_divisao()}")
    print(f"  {len(teste)} linhas de "
          f"{teste.repositorio.nunique()} repositórios")
    print(f"  {y.sum()} defeituosos ({100 * y.mean():.1f}%)")
    print(f"  AUC contando também os retratos recentes: "
          f"{auc_com_recentes:.3f}")

    resultado = calcular_metricas(y, probabilidade)
    mostrar_tabela("Resultado", {"modelo": resultado})

    previsao = (probabilidade >= config.LIMIAR_DECISAO).astype(int)
    limpos, falsos, perdidos, achados = confusion_matrix(
        y, previsao, labels=[0, 1]).ravel()

    print(f"\n  Contagens (limiar {config.LIMIAR_DECISAO})")
    print(f"    defeitos encontrados     : {achados} de {achados + perdidos}")
    print(f"    defeitos que escaparam   : {perdidos}")
    print(f"    alarmes falsos           : {falsos}")
    print(f"    limpos classificados ok  : {limpos}")

    print("\n  Por repositório")
    print(f"    {'repositório':<32} {'linhas':>7} {'defeitos':>9} "
          f"{'AUC':>7} {'achados':>8}")

    for nome, grupo in teste.groupby("repositorio"):
        yg = grupo[features.COLUNA_ALVO].to_numpy()
        pg = modelo.predict_proba(
            grupo[features.FEATURES].to_numpy(dtype=float))[:, 1]
        auc = (roc_auc_score(yg, pg) if len(np.unique(yg)) > 1 else np.nan)
        encontrados = int(((pg >= config.LIMIAR_DECISAO) & (yg == 1)).sum())
        print(f"    {nome:<32} {len(grupo):>7} {yg.sum():>9} "
              f"{auc:>7.3f} {encontrados:>8}")

    previsoes = gravar_previsoes(teste, probabilidade)
    resultado["AUC por commit"] = avaliar_ranking(previsoes)

    return {nome: round(float(valor), 4)
            for nome, valor in resultado.items()}


# =============================================================
# Salva
# -------------------------------------------------------------
# Grava o modelo junto com a ordem das features
# =============================================================
def salvar(modelo, nome: str, medias: pd.Series,
           metricas: dict | None) -> None:

    config.PASTA_MODELOS.mkdir(parents=True, exist_ok=True)

    temporario = config.ARQUIVO_MODELO.with_name(
        config.ARQUIVO_MODELO.name + ".tmp")

    joblib.dump({
        "modelo":   modelo,
        "nome":     nome,
        "features": features.FEATURES,
        "limiar":   config.LIMIAR_DECISAO,
        "medias":   {c: float(v) for c, v in medias.items()},
        "metricas": metricas,
        "repositorios_treino": int(
            pd.read_csv(config.ARQUIVO_DATASET,
                        usecols=["repositorio"])["repositorio"].nunique()),
        "treinado_em": time.strftime("%Y-%m-%d %H:%M"),
    }, temporario, compress=config.COMPRESSAO_DO_MODELO)
    os.replace(temporario, config.ARQUIVO_MODELO)

    tamanho = config.ARQUIVO_MODELO.stat().st_size / 1e6
    print(f"\n  Modelo gravado: {config.ARQUIVO_MODELO} "
          f"({nome}, {tamanho:.1f} MB)")

    if tamanho > 100:
        print(f"  AVISO: acima do limite de 100 MB do GitHub. "
              f"Aumente MINIMO_POR_FOLHA no config.py.")
    elif tamanho > 50:
        print(f"  AVISO: acima dos 50 MB recomendados pelo GitHub.")


# =============================================================
# Treinar
# -------------------------------------------------------------
# Treina o Modelo
# =============================================================
def treinar(so_final: bool = False) -> None:
    features.conferir_sem_vazamento()

    treino, teste = carregar_dados()

    medias = preparacao.medias_do_treino(treino)

    print("=" * 70)
    print("TREINAMENTO")
    print("=" * 70)
    print(f"\n  dataset  : {config.ARQUIVO_DATASET}")
    print(f"  features : {len(features.COLUNAS_BASE)} medidas + "
          f"{len(derivadas.colunas_ativas(features.COLUNAS_BASE))} derivadas + "
          f"{len(features.COLUNAS_COMMIT)} de commit")
    print(f"  derivadas: {derivadas.descrever(features.COLUNAS_BASE)}")
    print(f"  balanceamento: {balanceamento.descrever()}")
    print(f"  divisão  : {divisao.descrever_divisao()}")
    print(f"  treino   : {len(treino)} linhas, "
          f"{treino.repositorio.nunique()} repositórios, "
          f"{treino[features.COLUNA_ALVO].sum()} defeituosos")
    print(f"  teste    : {len(teste)} linhas, "
          f"{teste.repositorio.nunique()} repositórios, "
          f"{teste[features.COLUNA_ALVO].sum() if len(teste) else 0} "
          f"defeituosos")

    if treino.empty:
        raise SystemExit("Conjunto de treino vazio. Confira config.py.")

    inicio = time.time()

    preparacao.descrever(treino)

    treino = balanceamento.balancear(treino)

    grupos, divisor, descricao = divisao.validacao(treino)
    print(f"\n  Validação: {descricao}")

    if so_final:
        melhor = config.MODELO_FINAL
    else:
        melhor = comparar_modelos(treino, grupos, divisor)
        comparar_grupos_de_features(treino, melhor, grupos, divisor)

    modelo = criar_modelos()[melhor]
    modelo.fit(treino[features.FEATURES].to_numpy(dtype=float),
               treino[features.COLUNA_ALVO].to_numpy())

    mostrar_importancias(modelo)

    metricas = None

    if teste.empty:
        print("\n" + "=" * 70)
        print("SEM CONJUNTO RESERVADO")
        print("=" * 70)
        print("\n  A estratégia de divisão não reservou nada, então a comparação dentro do treino é a única medida de desempenho disponível.")

    else:
        metricas = avaliar_no_teste(modelo, teste)

    salvar(modelo, melhor, medias, metricas)

    if config.GERAR_GRAFICOS:
        graficos.desenhar(modelo, melhor, teste)

    print(f"\n  {time.time() - inicio:.0f} segundos\n")


# =============================================================
# Recalcular Ranking
# -------------------------------------------------------------
# Refaz a tabela por arquivo sem treinar de novo
# =============================================================
def recalcular_ranking() -> None:
    if not config.ARQUIVO_PREVISOES.exists():
        raise SystemExit(f"{config.ARQUIVO_PREVISOES} não existe. "
                         f"Rode o treino completo primeiro.")

    avaliar_ranking(pd.read_csv(config.ARQUIVO_PREVISOES))


if __name__ == "__main__":
    config.conferir_local()

    if "--so-ranking" in sys.argv:
        recalcular_ranking()
    else:
        treinar(so_final="--so-final" in sys.argv)

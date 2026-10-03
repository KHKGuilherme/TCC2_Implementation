"""
Treina o modelo a partir de dados/dataset.csv e grava o resultado em modelos/modelo.joblib.
"""

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

import config
import divisao
from extrator import features


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
            ("modelo", RandomForestClassifier(n_estimators=300,
                                              min_samples_leaf=3,
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
# Carregar Dados
# -------------------------------------------------------------
# lê o dataset e aplica a divisão atual
# =============================================================
def carregar_dados() -> tuple[pd.DataFrame, pd.DataFrame]:

    dados = pd.read_csv(config.ARQUIVO_DATASET)
    features.conferir_contrato(dados.columns)

    gravada = dados[features.COLUNA_PARTICAO]
    atual = divisao.dividir(dados)

    if not gravada.equals(atual):
        print("\n  A divisão gravada no dataset foi feita com outra "
              "configuração.")
        print("  Usando a estratégia atual do config.py.")

    dados[features.COLUNA_PARTICAO] = atual

    treino = dados[dados[features.COLUNA_PARTICAO] == "treino"]
    teste = dados[dados[features.COLUNA_PARTICAO] == "teste"]

    return treino, teste


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

    conjuntos = {
        "só 'linhas'":      ["linhas"],
        "só 'revisoes'":    ["revisoes"],
        "só código (6)":    features.COLUNAS_CODIGO,
        "só histórico (3)": features.COLUNAS_HISTORICO,
        "completo (9)":     features.FEATURES,
    }

    print("\n  Contribuição de cada grupo de features")
    print(f"    {'':<24} {'AUC':>7}")

    for nome, colunas in conjuntos.items():
        X = treino[colunas].to_numpy(dtype=float)
        probabilidade = prever_fora_da_amostra(
            criar_modelos()[nome_modelo], X, y, grupos, divisor)
        validas = ~np.isnan(probabilidade)
        auc = calcular_metricas(y[validas], probabilidade[validas])["AUC"]
        print(f"    {nome:<24} {auc:>7.3f}")


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
        print(f"    {features.FEATURES[i]:<24} {pesos[i]:.3f}  {barra}")

    peso_historico = sum(pesos[features.FEATURES.index(c)]
                         for c in features.COLUNAS_HISTORICO)
    print(f"\n    histórico Git (revisoes + autores + churn): "
          f"{100 * peso_historico:.0f}% do peso total")


# =============================================================
# Avaliar no teste
# -------------------------------------------------------------
# A medição final, nos dados reservados
# =============================================================
def avaliar_no_teste(modelo, teste: pd.DataFrame) -> None:

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

    mostrar_tabela("Resultado",
                   {"modelo": calcular_metricas(y, probabilidade)})

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


# =============================================================
# Salva
# -------------------------------------------------------------
# Grava o modelo junto com a ordem das features
# =============================================================
def salvar(modelo, nome: str) -> None:

    config.PASTA_MODELOS.mkdir(parents=True, exist_ok=True)

    joblib.dump({
        "modelo":   modelo,
        "nome":     nome,
        "features": features.FEATURES,
        "limiar":   config.LIMIAR_DECISAO,
    }, config.ARQUIVO_MODELO)

    tamanho = config.ARQUIVO_MODELO.stat().st_size / 1e6
    print(f"\n  Modelo gravado: {config.ARQUIVO_MODELO} "
          f"({nome}, {tamanho:.1f} MB)")


# =============================================================
# Treinar
# -------------------------------------------------------------
# Treina o Modelo
# =============================================================
def treinar() -> None:

    features.conferir_sem_vazamento()

    treino, teste = carregar_dados()

    print("=" * 70)
    print("TREINAMENTO")
    print("=" * 70)
    print(f"\n  dataset  : {config.ARQUIVO_DATASET}")
    print(f"  features : {len(features.FEATURES)} "
          f"({', '.join(features.FEATURES)})")
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

    grupos, divisor, descricao = divisao.validacao(treino)
    print(f"\n  Validação: {descricao}")

    melhor = comparar_modelos(treino, grupos, divisor)
    comparar_grupos_de_features(treino, melhor, grupos, divisor)

    # O modelo final usa todas as linhas de treino disponíveis.
    modelo = criar_modelos()[melhor]
    modelo.fit(treino[features.FEATURES].to_numpy(dtype=float),
               treino[features.COLUNA_ALVO].to_numpy())

    mostrar_importancias(modelo)

    if teste.empty:
        print("\n" + "=" * 70)
        print("SEM CONJUNTO RESERVADO")
        print("=" * 70)
        print("\n  A estratégia de divisão não reservou nada, então a comparação dentro do treino é a única medida de desempenho disponível.")

    else:
        avaliar_no_teste(modelo, teste)

    salvar(modelo, melhor)
    print(f"\n  {time.time() - inicio:.0f} segundos\n")


if __name__ == "__main__":
    config.conferir_local()
    treinar()
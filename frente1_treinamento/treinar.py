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

import balanceamento
import config
import divisao
import graficos
import preparacao
from extrator import derivadas, features


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
        # min_samples_leaf vem do config porque é ele que decide o
        # tamanho do arquivo salvo: com 3, as 300 árvores somam 8
        # milhões de nós e 648 MB, acima do limite do GitHub, sem
        # ganho de AUC
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
# Carregar Dados
# -------------------------------------------------------------
# lê o dataset e aplica a divisão atual
# =============================================================
def carregar_dados() -> tuple[pd.DataFrame, pd.DataFrame]:

    dados = pd.read_csv(config.ARQUIVO_DATASET)
    features.conferir_contrato(dados.columns)

    # ANTES da divisão, de propósito: o percentil é calculado
    # dentro de cada repositório e precisa de todos os arquivos
    # dele. Usa só valores de feature, nunca o rótulo.
    dados = derivadas.acrescentar(dados, features.COLUNAS_BASE)

    gravada = dados[features.COLUNA_PARTICAO]
    atual = divisao.dividir(dados)

    if not gravada.equals(atual):
        print("\n  A divisão gravada no dataset foi feita com outra "
              "configuração.")
        print("  Usando a estratégia atual do config.py.")

    dados[features.COLUNA_PARTICAO] = atual

    treino = dados[dados[features.COLUNA_PARTICAO] == "treino"]
    teste = dados[dados[features.COLUNA_PARTICAO] == "teste"]

    # O pré-processamento vem DEPOIS da divisão, e não antes: a
    # média que preenche os buracos tem de sair só do treino
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
        f"medidas ({len(base)})": base,
    }

    # Um grupo derivado de cada vez SOBRE as medidas: a linha
    # mostra o que aquele grupo acrescenta, e não o que ele vale
    # sozinho. É esse o número que decide se vale a pena mantê-lo.
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

    # Por ORIGEM, e não só pelas três colunas cruas de histórico.
    #
    # A versão antiga somava revisoes + autores + churn e chamava
    # aquilo de "peso do histórico". Com as derivadas isso passou a
    # mentir: 'revisoes_por_autor' é a feature mais importante do
    # modelo e também é histórico, só que derivada. A soma antiga
    # a ignorava e sugeria que o histórico tinha deixado de pesar.
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
# Risco por Arquivo
# -------------------------------------------------------------
# Junta os retratos de um arquivo numa nota só
# =============================================================
def risco_por_arquivo(previsoes: pd.DataFrame) -> pd.DataFrame:
    # Cada arquivo entra no dataset uma vez por commit em que foi
    # alterado, então o mesmo caminho tem vários retratos com
    # probabilidades diferentes. Esta é a tabela que responde
    # "quanto este arquivo é arriscado", uma linha por arquivo.
    #
    # A média é a nota principal porque usa todos os retratos. A
    # máxima acompanha porque um arquivo que já foi muito suspeito
    # uma vez merece atenção mesmo que a média o dilua.
    risco = previsoes.groupby(["repositorio", "arquivo"], as_index=False).agg(
        retratos=("probabilidade", "size"),
        risco_medio=("probabilidade", "mean"),
        risco_maximo=("probabilidade", "max"),
        commits_com_defeito=("real", "sum"),
    )

    # Rótulo do arquivo: teve defeito em algum dos seus commits.
    # É o gabarito contra o qual a nota por arquivo é medida.
    risco["teve_defeito"] = (risco["commits_com_defeito"] > 0).astype(int)

    # A nota que ordena o ranking.
    #
    # Ordenar pela média crua enche o topo de arquivos com UM
    # retrato só. Não é coincidência: a média de uma amostra varia
    # muito mais que a média de sete, então os extremos são
    # ocupados por quem tem menos evidência, e não por quem tem
    # mais risco.
    #
    # A correção puxa a nota para a média geral na proporção da
    # evidência disponível:
    #
    #     (n * media_do_arquivo + k * media_geral) / (n + k)
    #
    # Com n retratos e k de peso: um arquivo com 1 retrato fica
    # quase na média geral, e um com 20 quase não se move. É a
    # média bayesiana usada em ranking de avaliações.
    geral = previsoes["probabilidade"].mean()
    k = config.PESO_DA_PRIOR
    n = risco["retratos"]

    risco["risco_ajustado"] = (n * risco["risco_medio"] + k * geral) / (n + k)

    for coluna in ("risco_medio", "risco_maximo", "risco_ajustado"):
        risco[coluna] = risco[coluna].round(4)

    risco = risco.sort_values("risco_ajustado", ascending=False,
                              ignore_index=True)

    risco.to_csv(config.ARQUIVO_RISCO, index=False, encoding="utf-8")
    return risco


# =============================================================
# Mostrar Ranking de Arquivos
# -------------------------------------------------------------
# Os arquivos mais arriscados, e o acerto nessa granularidade
# =============================================================
def mostrar_ranking(risco: pd.DataFrame) -> None:
    y = risco["teve_defeito"].to_numpy()

    print(f"\n  Por arquivo — {len(risco)} arquivos distintos, "
          f"{int(y.sum())} com defeito ({100 * y.mean():.1f}%)")

    if len(np.unique(y)) > 1:
        # As duas, porque a diferença entre elas é o efeito do
        # ajuste por evidência
        print(f"    AUC por arquivo, nota crua     : "
              f"{roc_auc_score(y, risco['risco_medio']):.3f}")
        print(f"    AUC por arquivo, nota ajustada : "
              f"{roc_auc_score(y, risco['risco_ajustado']):.3f}")

    # Precisão no topo é a métrica que importa para uma ferramenta
    # que ORDENA: se o desenvolvedor vai olhar os 50 primeiros, o
    # que vale é quantos daqueles 50 têm defeito mesmo
    print(f"\n  Precisão no topo do ranking")
    for quantos in config.TOPOS_AVALIADOS:
        if quantos > len(risco):
            continue
        acertos = int(risco["teve_defeito"].head(quantos).sum())
        print(f"    {quantos:>5} primeiros: {acertos:>5} com defeito "
              f"({100 * acertos / quantos:.1f}%)")
    print(f"    {'base':>5}           : {100 * y.mean():.1f}% "
          f"se escolhesse ao acaso")

    quantos = min(config.TOPO_RANKING, len(risco))
    print(f"\n  Os {quantos} arquivos mais arriscados")
    print(f"    {'nota':>6} {'média':>7} {'retratos':>9} {'real':>5}  arquivo")

    for _, linha in risco.head(quantos).iterrows():
        marca = "sim" if linha["teve_defeito"] else "-"
        caminho = f"{linha['repositorio']}/{linha['arquivo']}"
        if len(caminho) > 54:
            caminho = "..." + caminho[-51:]
        print(f"    {100 * linha['risco_ajustado']:>5.1f}% "
              f"{100 * linha['risco_medio']:>6.1f}% "
              f"{int(linha['retratos']):>9} {marca:>5}  {caminho}")

    print(f"\n  Tabela completa: {config.ARQUIVO_RISCO}")
    print(f"  Previsão de cada retrato: {config.ARQUIVO_PREVISOES}")


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

    # A saída que interessa na prática: uma nota por arquivo, e não
    # um número só por projeto
    previsoes = gravar_previsoes(teste, probabilidade)
    mostrar_ranking(risco_por_arquivo(previsoes))


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
    }, config.ARQUIVO_MODELO, compress=config.COMPRESSAO_DO_MODELO)

    tamanho = config.ARQUIVO_MODELO.stat().st_size / 1e6
    print(f"\n  Modelo gravado: {config.ARQUIVO_MODELO} "
          f"({nome}, {tamanho:.1f} MB)")

    # O GitHub recusa arquivo acima de 100 MB, e a recusa derruba o
    # push inteiro. Avisar aqui é melhor que descobrir depois de
    # dois minutos enviando.
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
def treinar() -> None:

    features.conferir_sem_vazamento()

    treino, teste = carregar_dados()

    print("=" * 70)
    print("TREINAMENTO")
    print("=" * 70)
    print(f"\n  dataset  : {config.ARQUIVO_DATASET}")
    print(f"  features : {len(features.COLUNAS_BASE)} medidas + "
          f"{len(features.FEATURES) - len(features.COLUNAS_BASE)} derivadas")
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

    # A correlação sai ANTES do balanceamento, de propósito: ela
    # descreve os dados, e replicar linha mexe nos coeficientes.
    # Numa medição a diferença foi de -0,075 para -0,166 só por
    # causa das repetições — a tabela da monografia tem de falar
    # dos dados reais, não da cópia reamostrada.
    preparacao.descrever(treino)

    # Depois da divisão: o teste mantém a proporção real, e os
    # grupos da validação cruzada são formados a partir do treino
    # que sai daqui
    treino = balanceamento.balancear(treino)

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

    if config.GERAR_GRAFICOS:
        graficos.desenhar(modelo, melhor, teste)

    print(f"\n  {time.time() - inicio:.0f} segundos\n")


if __name__ == "__main__":
    config.conferir_local()
    treinar()
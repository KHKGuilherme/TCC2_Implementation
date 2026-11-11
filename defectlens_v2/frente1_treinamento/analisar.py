"""
Frente 1, etapa 3 — transforma as notas de projeto nunca visto em tabelas:
medidas por repositório, resumo por método, significância, calibração,
faixas de risco e diagnósticos do dataset.

CMD -> python defectlens_v2/frente1_treinamento/analisar.py
       lê resultados/previsoes_loro e grava CSV e JSON em resultados/
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
import metricas_avaliacao
import modelos

CENARIOS = {
    "principal":  "partição train, dentro do domínio do rótulo",
    "sem_filtro": "partição train, todos os commits (como na versão original)",
    "natural":    "partições test e val (proporção original), no domínio",
}

MEDIDAS_TESTADAS = ["auc", "topo_10", "popt_densidade",
                    "revocacao_esforco_densidade"]

MEDIDAS_RESUMIDAS = ["auc", "precisao_media", "topo_10", "topo_20",
                     "popt_risco", "revocacao_esforco_risco",
                     "esforco_revocacao_risco", "ifa_risco",
                     "popt_densidade", "revocacao_esforco_densidade",
                     "esforco_revocacao_densidade", "ifa_densidade"]

ORDENAM_POR_ESFORCO = ("menor_primeiro",)

FAIXAS_DE_LINHAS =[0, 10, 25, 50, 100, 200, 400, 700, 1000, 2000, 10**9]
FAIXAS_DE_ARQUIVOS = [0, 1, 2, 5, 10, 20, 50, 100, 10**9]

FAIXAS_DE_RISCO = (("alto", 0.90, 1.00), ("médio", 0.70, 0.90),
                   ("baixo", 0.00, 0.70))


# =============================================================
# LEITURA
# =============================================================


# =============================================================
# Ler Previsoes
# -------------------------------------------------------------
# Junta as notas gravadas pela validação de todos os repositórios
# =============================================================
def ler_previsoes() -> pd.DataFrame:
    caminhos = sorted(config.PASTA_PREVISOES.glob("*.csv"))

    if not caminhos:
        raise SystemExit("Rode antes: python defectlens_v2/"
                         "frente1_treinamento/avaliar.py")

    return pd.concat([pd.read_csv(c) for c in caminhos], ignore_index=True)


# =============================================================
# Filtrar Cenario
# -------------------------------------------------------------
# Os commits que entram em cada cenário de avaliação
# =============================================================
def filtrar_cenario(previsoes: pd.DataFrame, cenario: str) -> pd.DataFrame:
    de_treino = previsoes["particao"].isin(config.PARTICOES_TREINO)
    naturais = previsoes["particao"].isin(config.PARTICOES_NATURAIS)
    no_dominio = previsoes["no_dominio"] == 1

    if cenario == "principal":
        return previsoes[de_treino & no_dominio]
    if cenario == "sem_filtro":
        return previsoes[de_treino]
    if cenario == "natural":
        return previsoes[naturais & no_dominio]

    raise ValueError(f"Cenário desconhecido: {cenario}")


# =============================================================
# Metodos
# -------------------------------------------------------------
# Os métodos que têm nota gravada
# =============================================================
def metodos(previsoes: pd.DataFrame) -> list[str]:
    return [c[len("nota_"):] for c in previsoes.columns
            if c.startswith("nota_")]


# =============================================================
# MEDIDAS POR REPOSITÓRIO
# =============================================================


# =============================================================
# Repositorio Avaliavel
# -------------------------------------------------------------
# Se o repositório tem commits e defeitos bastantes para medir
# =============================================================
def repositorio_avaliavel(grupo: pd.DataFrame, cenario: str) -> bool:
    positivos = int(grupo["defeituoso"].sum())

    if len(grupo) < config.MINIMO_COMMITS_REPO:
        return False
    if positivos == 0 or positivos == len(grupo):
        return False
    if cenario == "natural":
        return positivos >= config.MINIMO_POSITIVOS_NATURAIS

    return True


# =============================================================
# Medir Por Repositorio
# -------------------------------------------------------------
# Todas as medidas de cada método em cada repositório e cenário
# =============================================================
def medir_por_repositorio(previsoes: pd.DataFrame) -> pd.DataFrame:
    linhas = []

    for cenario in CENARIOS:
        recorte = filtrar_cenario(previsoes, cenario)

        for repositorio, grupo in recorte.groupby("repositorio"):
            if not repositorio_avaliavel(grupo, cenario):
                continue

            esforco = (grupo["commit_adicionadas"]
                       + grupo["commit_removidas"]).to_numpy()

            for metodo in metodos(previsoes):
                nota = grupo[f"nota_{metodo}"].to_numpy(dtype=float)
                if np.isnan(nota).any():
                    continue

                medidas = metricas_avaliacao.medir_ordenacao(
                    grupo["defeituoso"].to_numpy(), nota, esforco,
                    config.FRACAO_ESFORCO, config.FRACOES_TOPO)

                if metodo in ORDENAM_POR_ESFORCO:
                    for chave in list(medidas):
                        if chave.endswith("_risco"):
                            medidas[chave.replace("_risco", "_densidade")] = (
                                medidas[chave])

                linhas.append({"cenario": cenario, "metodo": metodo,
                               "repositorio": repositorio, **medidas})

    return pd.DataFrame(linhas)


# =============================================================
# Resumir Metodos
# -------------------------------------------------------------
# Mediana entre repositórios e AUC com todos os commits juntos
# =============================================================
def resumir_metodos(previsoes: pd.DataFrame,
                    medidas: pd.DataFrame) -> pd.DataFrame:
    linhas = []

    for (cenario, metodo), grupo in medidas.groupby(["cenario", "metodo"],
                                                    sort=False):
        recorte = filtrar_cenario(previsoes, cenario)
        nota = recorte[f"nota_{metodo}"]
        validos = nota.notna()

        linha = {
            "cenario": cenario, "metodo": metodo,
            "nome": modelos.NOMES.get(metodo, metodo),
            "repositorios": len(grupo),
            "commits": int(validos.sum()),
            "base": float(recorte.loc[validos, "defeituoso"].mean()),
            "auc_agregado": metricas_avaliacao.auc(
                recorte.loc[validos, "defeituoso"], nota[validos]),
            "auc_media": float(grupo["auc"].mean()),
            "auc_minimo": float(grupo["auc"].min()),
            "auc_maximo": float(grupo["auc"].max()),
        }
        linha.update({m: float(grupo[m].median())
                      for m in MEDIDAS_RESUMIDAS})
        linhas.append(linha)

    return pd.DataFrame(linhas)


# =============================================================
# SIGNIFICÂNCIA
# =============================================================


# =============================================================
# Testar Significancia
# -------------------------------------------------------------
# Wilcoxon pareado do método principal contra cada um dos outros
# =============================================================
def testar_significancia(medidas: pd.DataFrame) -> pd.DataFrame:
    linhas = []

    for cenario in ("principal", "natural"):
        do_cenario = medidas[medidas["cenario"] == cenario]

        for medida in MEDIDAS_TESTADAS:
            tabela = do_cenario.pivot(index="repositorio", columns="metodo",
                                      values=medida)
            if config.METODO_PRINCIPAL not in tabela.columns:
                continue

            familia = []
            for outro in tabela.columns:
                if outro == config.METODO_PRINCIPAL:
                    continue

                familia.append({
                    "cenario": cenario, "medida": medida,
                    "metodo_a": config.METODO_PRINCIPAL, "metodo_b": outro,
                    **metricas_avaliacao.comparar_pareado(
                        tabela[config.METODO_PRINCIPAL].to_numpy(),
                        tabela[outro].to_numpy())})

            ajustados = metricas_avaliacao.corrigir_holm(
                [linha["valor_p"] for linha in familia])
            for linha, ajustado in zip(familia, ajustados):
                linha["valor_p_holm"] = ajustado

            linhas.extend(familia)

    return pd.DataFrame(linhas)


# =============================================================
# CALIBRAÇÃO
# =============================================================


# =============================================================
# Logito
# -------------------------------------------------------------
# Converte probabilidade em logaritmo da chance
# =============================================================
def logito(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


# =============================================================
# Corrigir Prevalencia
# -------------------------------------------------------------
# Ajusta a nota para outra taxa de defeito (Saerens et al., 2002)
# =============================================================
def corrigir_prevalencia(nota: np.ndarray, de: float,
                         para: float) -> np.ndarray:
    razao = (para / (1 - para)) / (de / (1 - de))
    chance = np.exp(logito(nota)) * razao
    return chance / (1 + chance)


# =============================================================
# Erro de Calibracao
# -------------------------------------------------------------
# Diferença média entre a nota e a taxa observada, por faixa
# =============================================================
def erro_de_calibracao(rotulo: np.ndarray, nota: np.ndarray) -> float:
    limites = np.linspace(0, 1, config.FAIXAS_CALIBRACAO + 1)
    faixa = np.clip(np.digitize(nota, limites[1:-1]), 0,
                    config.FAIXAS_CALIBRACAO - 1)
    erro = 0.0

    for indice in range(config.FAIXAS_CALIBRACAO):
        dentro = faixa == indice
        if dentro.any():
            erro += dentro.mean() * abs(rotulo[dentro].mean()
                                        - nota[dentro].mean())

    return float(erro)


# =============================================================
# Calibrar Fora do Repositorio
# -------------------------------------------------------------
# Notas calibradas de cada repositório só com dados dos outros
# =============================================================
def calibrar_fora_do_repositorio(previsoes: pd.DataFrame) -> pd.DataFrame:
    coluna = f"nota_{config.METODO_PRINCIPAL}"
    principal = filtrar_cenario(previsoes, "principal")
    natural = filtrar_cenario(previsoes, "natural").copy()
    natural["sem_calibrar"] = natural[coluna]

    for repositorio in natural["repositorio"].unique():
        fora = natural["repositorio"] == repositorio
        outros = natural[~fora]
        taxa_treino = principal.loc[principal["repositorio"] != repositorio,
                                    "defeituoso"].mean()

        natural.loc[fora, "prevalencia"] = corrigir_prevalencia(
            natural.loc[fora, coluna].to_numpy(), taxa_treino,
            outros["defeituoso"].mean())

        logistica = LogisticRegression(C=1e6, max_iter=1000).fit(
            logito(outros[coluna]).reshape(-1, 1), outros["defeituoso"])
        natural.loc[fora, "platt"] = logistica.predict_proba(
            logito(natural.loc[fora, coluna]).reshape(-1, 1))[:, 1]

        isotonica = IsotonicRegression(out_of_bounds="clip", y_min=0,
                                       y_max=1).fit(outros[coluna],
                                                    outros["defeituoso"])
        natural.loc[fora, "isotonica"] = isotonica.predict(
            natural.loc[fora, coluna])

    return natural


# =============================================================
# Medir Calibracao
# -------------------------------------------------------------
# Brier e erro de calibração de cada forma de calibrar
# =============================================================
def medir_calibracao(natural: pd.DataFrame) -> tuple[pd.DataFrame,
                                                     pd.DataFrame]:
    rotulo = natural["defeituoso"].to_numpy(dtype=float)
    limites = np.linspace(0, 1, config.FAIXAS_CALIBRACAO + 1)
    resumo, curvas = [], []

    for forma in ("sem_calibrar", "prevalencia", "platt", "isotonica"):
        nota = natural[forma].to_numpy(dtype=float)
        resumo.append({
            "forma": forma,
            "commits": len(nota),
            "taxa_observada": float(rotulo.mean()),
            "nota_media": float(nota.mean()),
            "brier": float(np.mean((nota - rotulo) ** 2)),
            "erro_calibracao": erro_de_calibracao(rotulo, nota),
        })

        faixa = np.clip(np.digitize(nota, limites[1:-1]), 0,
                        config.FAIXAS_CALIBRACAO - 1)
        for indice in range(config.FAIXAS_CALIBRACAO):
            dentro = faixa == indice
            if dentro.any():
                curvas.append({"forma": forma, "faixa": indice,
                               "commits": int(dentro.sum()),
                               "nota_media": float(nota[dentro].mean()),
                               "taxa_observada": float(rotulo[dentro]
                                                       .mean())})

    return pd.DataFrame(resumo), pd.DataFrame(curvas)


# =============================================================
# Medir Faixas de Risco
# -------------------------------------------------------------
# Taxa de defeito observada em cada faixa de nota, fora do treino
# =============================================================
def medir_faixas(previsoes: pd.DataFrame) -> pd.DataFrame:
    coluna = f"nota_{config.METODO_PRINCIPAL}"
    linhas = []

    for cenario in ("natural", "principal"):
        recorte = filtrar_cenario(previsoes, cenario)
        nota = recorte[coluna].to_numpy(dtype=float)
        rotulo = recorte["defeituoso"].to_numpy(dtype=float)

        for nome, inicio, fim in FAIXAS_DE_RISCO:
            corte_de = float(np.quantile(nota, inicio))
            corte_ate = float(np.quantile(nota, fim))
            dentro = ((nota >= corte_de) & (nota <= corte_ate) if fim >= 1
                      else (nota >= corte_de) & (nota < corte_ate))

            linhas.append({
                "cenario": cenario, "faixa": nome,
                "quantil_de": inicio, "quantil_ate": fim,
                "nota_de": corte_de, "nota_ate": corte_ate,
                "commits": int(dentro.sum()),
                "taxa_de_defeito": float(rotulo[dentro].mean()),
                "taxa_geral": float(rotulo.mean()),
                "parcela_dos_defeitos": float(rotulo[dentro].sum()
                                              / max(rotulo.sum(), 1)),
            })

    return pd.DataFrame(linhas)


# =============================================================
# DIAGNÓSTICOS DO DATASET
# =============================================================


# =============================================================
# Taxa Por Tamanho
# -------------------------------------------------------------
# Taxa de defeito por faixa de linhas e de arquivos do commit
# =============================================================
def taxa_por_tamanho(previsoes: pd.DataFrame) -> pd.DataFrame:
    treino = previsoes[previsoes["particao"].isin(config.PARTICOES_TREINO)]
    churn = treino["commit_adicionadas"] + treino["commit_removidas"]
    partes = []

    for medida, valores, faixas in (
            ("linhas alteradas", churn, FAIXAS_DE_LINHAS),
            ("arquivos", treino["commit_arquivos"], FAIXAS_DE_ARQUIVOS)):
        corte = pd.cut(valores, faixas, include_lowest=True)
        tabela = (treino.groupby(corte, observed=True)["defeituoso"]
                  .agg(commits="size", defeituosos="sum", taxa="mean")
                  .reset_index(names="faixa"))
        tabela["faixa"] = [f"{int(max(f.left, 0)) + (0 if i == 0 else 1)}"
                           f"–{int(f.right)}" if f.right < 10**9
                           else f"> {int(f.left)}"
                           for i, f in enumerate(tabela["faixa"])]
        tabela.insert(0, "medida", medida)
        partes.append(tabela)

    return pd.concat(partes, ignore_index=True)


# =============================================================
# Descrever Particoes
# -------------------------------------------------------------
# Commits, taxa de defeito e datas de cada partição do Defectors
# =============================================================
def descrever_particoes(previsoes: pd.DataFrame) -> tuple[pd.DataFrame,
                                                          pd.DataFrame]:
    resumo = (previsoes.groupby("particao")
              .agg(commits=("defeituoso", "size"),
                   taxa_de_defeito=("defeituoso", "mean"),
                   primeira_data=("data", "min"),
                   ultima_data=("data", "max"),
                   fora_do_dominio=("no_dominio", lambda s: int((s == 0)
                                                                .sum())))
              .reset_index())

    mensal = previsoes.assign(mes=previsoes["data"].str.slice(0, 7))
    mensal = (mensal.groupby(["mes", "particao", "defeituoso"])
              .size().rename("commits").reset_index())

    return resumo, mensal


# =============================================================
# Resumir Permutacao
# -------------------------------------------------------------
# Queda mediana do AUC por feature, entre os repositórios
# =============================================================
def resumir_permutacao() -> pd.DataFrame:
    caminhos = sorted(config.PASTA_PERMUTACAO.glob("*.csv"))
    partes = [pd.read_csv(c) for c in caminhos]
    partes = [p for p in partes if len(p)]

    if not partes:
        return pd.DataFrame()

    return pd.concat(partes, ignore_index=True)


# =============================================================
# SAÍDA
# =============================================================


# =============================================================
# Linha do Resumo
# -------------------------------------------------------------
# As medidas de um método num cenário, prontas para o JSON
# =============================================================
def linha_do_resumo(resumo: pd.DataFrame, cenario: str,
                    metodo: str) -> dict | None:
    linha = resumo[(resumo["cenario"] == cenario)
                   & (resumo["metodo"] == metodo)]

    if linha.empty:
        return None

    return {chave: (round(float(valor), 4)
                    if isinstance(valor, (float, np.floating)) else
                    int(valor) if isinstance(valor, (int, np.integer))
                    else valor)
            for chave, valor in linha.iloc[0].items()}


# =============================================================
# Analisar
# -------------------------------------------------------------
# Calcula e grava todas as tabelas
# =============================================================
def analisar() -> dict:
    previsoes = ler_previsoes()
    pasta = config.PASTA_RESULTADOS

    medidas = medir_por_repositorio(previsoes)
    resumo = resumir_metodos(previsoes, medidas)
    significancia = testar_significancia(medidas)
    natural = calibrar_fora_do_repositorio(previsoes)
    calibracao, curvas = medir_calibracao(natural)
    faixas = medir_faixas(previsoes)
    particoes, mensal = descrever_particoes(previsoes)
    permutacao = resumir_permutacao()

    medidas.to_csv(pasta / "metricas_por_repositorio.csv", index=False)
    resumo.to_csv(pasta / "resumo_metodos.csv", index=False)
    significancia.to_csv(pasta / "significancia.csv", index=False)
    calibracao.to_csv(pasta / "calibracao.csv", index=False)
    curvas.to_csv(pasta / "calibracao_curvas.csv", index=False)
    faixas.to_csv(pasta / "faixas_de_risco.csv", index=False)
    taxa_por_tamanho(previsoes).to_csv(pasta / "taxa_por_tamanho.csv",
                                       index=False)
    particoes.to_csv(pasta / "particoes.csv", index=False)
    mensal.to_csv(pasta / "particoes_por_mes.csv", index=False)
    permutacao.to_csv(pasta / "permutacao.csv", index=False)
    natural[["repositorio", "commit", "defeituoso", "sem_calibrar",
             "prevalencia", "platt", "isotonica"]].to_csv(
        pasta / "notas_calibradas_natural.csv", index=False)

    geral = {
        "cenarios": CENARIOS,
        "metodo_principal": config.METODO_PRINCIPAL,
        "commits": int(len(previsoes)),
        "repositorios": int(previsoes["repositorio"].nunique()),
        "fora_do_dominio": int((previsoes["no_dominio"] == 0).sum()),
        "defeituosos_fora_do_dominio": int(
            previsoes.loc[previsoes["no_dominio"] == 0, "defeituoso"].sum()),
        "metodos": {
            cenario: {metodo: linha_do_resumo(resumo, cenario, metodo)
                      for metodo in metodos(previsoes)
                      if linha_do_resumo(resumo, cenario, metodo)}
            for cenario in CENARIOS},
        "calibracao": calibracao.round(4).to_dict("records"),
        "faixas": faixas.round(4).to_dict("records"),
    }

    (pasta / "resumo.json").write_text(
        json.dumps(geral, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"resumo": resumo, "significancia": significancia,
            "calibracao": calibracao, "faixas": faixas}


# =============================================================
# Mostrar
# -------------------------------------------------------------
# Imprime as tabelas principais no terminal
# =============================================================
def mostrar(tabelas: dict) -> None:
    pd.set_option("display.width", 250)
    resumo = tabelas["resumo"]

    for cenario, descricao in CENARIOS.items():
        print(f"\n  == {cenario}: {descricao}")
        print(resumo[resumo["cenario"] == cenario][
            ["metodo", "repositorios", "commits", "base", "auc_agregado",
             "auc", "auc_media", "topo_10", "popt_risco",
             "revocacao_esforco_risco", "popt_densidade",
             "revocacao_esforco_densidade", "ifa_densidade"]]
            .round(3).to_string(index=False))

    print("\n  == significância (método principal contra os demais)")
    print(tabelas["significancia"][
        ["cenario", "medida", "metodo_b", "repositorios",
         "diferenca_mediana", "vitorias", "derrotas", "valor_p",
         "valor_p_holm", "delta_cliff", "magnitude"]]
        .round(4).to_string(index=False))

    print("\n  == calibração nas partições naturais")
    print(tabelas["calibracao"].round(4).to_string(index=False))
    print("\n  == faixas de risco")
    print(tabelas["faixas"].round(4).to_string(index=False))


if __name__ == "__main__":
    mostrar(analisar())

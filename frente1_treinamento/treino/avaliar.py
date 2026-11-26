import json
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, wilcoxon
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score, roc_curve

from treino import config
from treino import modelo


MINIMO_POR_CLASSE = 3
LIMIARES = np.round(np.arange(0.02, 0.91, 0.01), 2)
ARQUIVO_SAIDA = config.PASTA_RESULTADOS / "avaliacao.json"


def ler_previsoes() -> pd.DataFrame:
    partes = [pd.read_csv(p) for p in sorted(config.PASTA_VALIDACAO.glob("*.csv.gz"))]
    dados = pd.concat(partes, ignore_index=True)
    semente = np.random.default_rng(config.SEMENTE)
    dados["aleatorio"] = semente.random(len(dados))
    return dados


def rotulados(dados: pd.DataFrame, rotulo: str = config.ROTULO) -> pd.DataFrame:
    return dados[(dados["data"] <= config.ULTIMO_RETRATO_ROTULADO) & dados[rotulo].notna()]


def auc_por_retrato(dados: pd.DataFrame, notas: list[str], rotulo: str) -> pd.DataFrame:
    linhas = []
    for (nome, data), grupo in dados.groupby(["repositorio", "data"]):
        y = grupo[rotulo].values
        if y.sum() < MINIMO_POR_CLASSE or (1 - y).sum() < MINIMO_POR_CLASSE:
            continue
        linha = {"repositorio": nome, "data": data, "arquivos": len(grupo), "taxa": y.mean()}
        for nota in notas:
            linha[nota] = roc_auc_score(y, grupo[nota].values)
        linhas.append(linha)
    return pd.DataFrame(linhas)


def topo(dados: pd.DataFrame, nota: str, rotulo: str, fracao: float = 0.10) -> float:
    acertos, total = 0.0, 0
    for _, grupo in dados.groupby(["repositorio", "data"]):
        quantos = max(1, int(round(len(grupo) * fracao)))
        melhores = grupo.nlargest(quantos, nota)
        acertos += melhores[rotulo].sum()
        total += quantos
    return acertos / total


def cliff(a: np.ndarray, b: np.ndarray) -> float:
    diferenca = np.subtract.outer(a, b)
    return float(((diferenca > 0).sum() - (diferenca < 0).sum()) / diferenca.size)


def comparar(por_repo: pd.DataFrame, notas: list[str], referencia: str) -> list[dict]:
    linhas = []
    for nota in notas:
        linha = {"metodo": nota, "auc_mediano": float(por_repo[nota].median()),
                 "auc_medio": float(por_repo[nota].mean()),
                 "auc_minimo": float(por_repo[nota].min())}
        if nota != referencia:
            diferenca = por_repo[referencia] - por_repo[nota]
            linha["referencia_vence"] = int((diferenca > 0).sum())
            linha["repositorios"] = int(len(diferenca))
            linha["wilcoxon_p"] = float(wilcoxon(por_repo[referencia], por_repo[nota]).pvalue)
            linha["cliff"] = cliff(por_repo[referencia].values, por_repo[nota].values)
        linhas.append(linha)
    return linhas


def erro_de_calibracao(y: np.ndarray, p: np.ndarray, faixas: int = 10) -> float:
    ordem = np.argsort(p)
    erro = 0.0
    for pedaco in np.array_split(ordem, faixas):
        erro += abs(y[pedaco].mean() - p[pedaco].mean()) * len(pedaco) / len(y)
    return float(erro)


def curva_de_calibracao(y: np.ndarray, p: np.ndarray, faixas: int = 10) -> list[dict]:
    ordem = np.argsort(p)
    return [{"previsto": float(p[pedaco].mean()), "observado": float(y[pedaco].mean()),
             "quantos": int(len(pedaco))} for pedaco in np.array_split(ordem, faixas)]


def limiar_de_fora(outros: pd.DataFrame, nota: str, rotulo: str) -> dict:
    y = outros[rotulo].values
    p = outros[nota].values
    melhor_f1, limiar_f1, limiar_precisao = -1.0, 0.5, None
    for limiar in LIMIARES:
        marcado = p >= limiar
        if marcado.sum() == 0:
            continue
        precisao = y[marcado].mean()
        revocacao = y[marcado].sum() / max(1, y.sum())
        f1 = 2 * precisao * revocacao / max(1e-9, precisao + revocacao)
        if f1 > melhor_f1:
            melhor_f1, limiar_f1 = f1, float(limiar)
        if limiar_precisao is None and precisao >= config.PRECISAO_MINIMA:
            limiar_precisao = float(limiar)
    return {"f1": limiar_f1, "precisao": limiar_precisao or float(LIMIARES[-1])}


def medir_limiar(y: np.ndarray, marcado: np.ndarray) -> dict:
    vp = float((marcado & (y == 1)).sum())
    precisao = vp / max(1, marcado.sum())
    revocacao = vp / max(1, y.sum())
    return {"precisao": precisao, "revocacao": revocacao,
            "f1": 2 * precisao * revocacao / max(1e-9, precisao + revocacao),
            "marcados": float(marcado.mean()), "base": float(y.mean())}


def matriz_de_confusao(y: np.ndarray, marcado: np.ndarray) -> dict:
    y = y.astype(int)
    marcado = marcado.astype(bool)
    return {"vp": int((marcado & (y == 1)).sum()), "fp": int((marcado & (y == 0)).sum()),
            "fn": int((~marcado & (y == 1)).sum()), "vn": int((~marcado & (y == 0)).sum())}


def curva_roc(y: np.ndarray, p: np.ndarray, pontos: int = 400) -> dict:
    fpr, tpr, _ = roc_curve(y.astype(int), p)
    grade = np.linspace(0, 1, pontos + 1)
    indice = np.searchsorted(fpr, grade, side="right") - 1
    return {"auc": float(roc_auc_score(y.astype(int), p)),
            "fpr": np.round(grade, 4).tolist(), "tpr": np.round(tpr[indice], 4).tolist()}


def porcentagens(dados: pd.DataFrame, nota: str, rotulo: str) -> pd.DataFrame:
    dados = dados.copy()
    limiares = {}
    for nome in dados["repositorio"].unique():
        limiares[nome] = limiar_de_fora(dados[dados["repositorio"] != nome],
                                        f"{nota}_{config.CALIBRACAO_FINAL}", rotulo)
    dados["limiar_f1"] = dados["repositorio"].map(lambda n: limiares[n]["f1"])
    dados["limiar_precisao"] = dados["repositorio"].map(lambda n: limiares[n]["precisao"])
    dados["marcado_f1"] = dados[f"{nota}_{config.CALIBRACAO_FINAL}"] >= dados["limiar_f1"]
    dados["marcado_precisao"] = dados[f"{nota}_{config.CALIBRACAO_FINAL}"] >= dados["limiar_precisao"]
    tabela = dados.groupby(["repositorio", "data"]).agg(
        arquivos=(rotulo, "size"), real=(rotulo, "mean"), soma_bruta=(nota, "mean"),
        soma_platt=(f"{nota}_platt", "mean"), soma_isotonica=(f"{nota}_isotonica", "mean"),
        contagem_f1=("marcado_f1", "mean"), contagem_precisao=("marcado_precisao", "mean"),
        taxa_treino=("taxa_treino", "mean"), limiar_f1=("limiar_f1", "first"),
        limiar_precisao=("limiar_precisao", "first")).reset_index()
    return tabela, dados


def resumir_porcentagem(tabela: pd.DataFrame) -> list[dict]:
    ultimo = tabela.sort_values("data").groupby("repositorio").tail(1)
    linhas = []
    for estimador in ("soma_bruta", "soma_platt", "soma_isotonica", "contagem_f1",
                      "contagem_precisao", "taxa_treino"):
        erro = (tabela[estimador] - tabela["real"]) * 100
        erro_ultimo = (ultimo[estimador] - ultimo["real"]) * 100
        linhas.append({
            "estimador": estimador,
            "erro_absoluto_medio_pp": float(erro.abs().mean()),
            "erro_absoluto_mediano_pp": float(erro.abs().median()),
            "vies_pp": float(erro.mean()),
            "spearman": float(spearmanr(tabela[estimador], tabela["real"]).statistic)
            if tabela[estimador].nunique() > 1 else 0.0,
            "ultimo_erro_absoluto_medio_pp": float(erro_ultimo.abs().mean()),
            "ultimo_spearman": float(spearmanr(ultimo[estimador], ultimo["real"]).statistic)
            if ultimo[estimador].nunique() > 1 else 0.0,
        })
    return linhas


def avaliar() -> dict:
    config.PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    dados = ler_previsoes()
    rotulo = config.ROTULO
    base = rotulados(dados)
    variantes = [f"p_{v}" for v in modelo.VARIANTES]
    notas = ["aleatorio"] + modelo.BASELINES + variantes
    final = f"p_{config.VARIANTE_FINAL}"

    retratos = auc_por_retrato(base, notas, rotulo)
    por_repo = retratos.groupby("repositorio")[notas].mean()
    ultimos = retratos.sort_values("data").groupby("repositorio").tail(1).set_index("repositorio")
    comparacao = comparar(por_repo, notas, final)
    comparacao_ultimo = comparar(ultimos[notas], notas, final)
    for linha in comparacao:
        linha["topo_10"] = topo(base, linha["metodo"], rotulo)
        linha["precisao_media"] = float(average_precision_score(
            base[rotulo].values, base[linha["metodo"]].values))
    retratos.to_csv(config.PASTA_RESULTADOS / "auc_por_retrato.csv", index=False)
    por_repo.join(retratos.groupby("repositorio").agg(
        retratos=("data", "size"), taxa=("taxa", "mean"))).to_csv(
        config.PASTA_RESULTADOS / "auc_por_repositorio.csv")

    y = base[rotulo].values
    calibracao = {}
    for tipo, coluna in (("bruta", final), ("platt", f"{final}_platt"),
                         ("isotonica", f"{final}_isotonica")):
        p = base[coluna].values
        calibracao[tipo] = {"brier": float(brier_score_loss(y, p)),
                            "ece": erro_de_calibracao(y, p),
                            "curva": curva_de_calibracao(y, p)}
    calibracao["taxa_treino"] = {"brier": float(brier_score_loss(y, base["taxa_treino"].values))}

    tabela, marcados = porcentagens(base, final, rotulo)
    tabela = tabela[tabela["arquivos"] >= config.MINIMO_ARQUIVOS_RETRATO]
    tabela.to_csv(config.PASTA_RESULTADOS / "porcentagem_por_retrato.csv", index=False)
    limiares = {
        "maior_f1": medir_limiar(y, marcados["marcado_f1"].values),
        "precisao_minima": medir_limiar(y, marcados["marcado_precisao"].values),
        "faixa_f1": [float(tabela["limiar_f1"].min()), float(tabela["limiar_f1"].max())],
        "faixa_precisao": [float(tabela["limiar_precisao"].min()),
                           float(tabela["limiar_precisao"].max())],
        "curva": [dict(limiar=float(l), **medir_limiar(y, base[f"{final}_{config.CALIBRACAO_FINAL}"].values >= l))
                  for l in LIMIARES],
        "matriz_f1": matriz_de_confusao(y, marcados["marcado_f1"].values),
        "matriz_precisao": matriz_de_confusao(y, marcados["marcado_precisao"].values),
    }

    chance_final = f"{final}_{config.CALIBRACAO_FINAL}"
    roc = {
        "agregado": {metodo: curva_roc(y, base[coluna].values) for metodo, coluna in
                     ((final, chance_final), ("churn", "churn"),
                      ("linhas_estimadas", "linhas_estimadas"), ("commits_365", "commits_365"),
                      ("aleatorio", "aleatorio"))},
        "por_repositorio": {nome: curva_roc(grupo[rotulo].values, grupo[chance_final].values)
                            for nome, grupo in base.groupby("repositorio")},
    }

    horizontes = {}
    for dias in config.HORIZONTES_DIAS:
        coluna = f"latente_{dias}"
        parte = rotulados(dados, coluna)
        aucs = auc_por_retrato(parte, [final, "commits_365", "revisoes"], coluna)
        medias = aucs.groupby("repositorio")[[final, "commits_365", "revisoes"]].mean()
        horizontes[str(dias)] = {"taxa": float(parte[coluna].mean()),
                                 "repositorios": int(len(medias)),
                                 **{k: float(v) for k, v in medias.median().items()}}

    por_data = retratos.groupby("data").agg(
        repositorios=("repositorio", "size"), modelo=(final, "median"),
        commits_365=("commits_365", "median"), revisoes=("revisoes", "median")).reset_index()
    por_data.to_csv(config.PASTA_RESULTADOS / "auc_por_data.csv", index=False)

    recentes = dados[(dados["data"] >= "2023-01-01") & dados["conserto_futuro_180"].notna()]
    externos = auc_por_retrato(recentes, [final, "commits_365", "revisoes", "aleatorio"],
                               "conserto_futuro_180")
    externo = externos.groupby("repositorio")[[final, "commits_365", "revisoes", "aleatorio"]].mean()
    externo.to_csv(config.PASTA_RESULTADOS / "auc_conserto_futuro_2023.csv")
    serie = dados.groupby(["repositorio", "data"]).agg(
        arquivos=("id", "size"), estimada=(f"{final}_{config.CALIBRACAO_FINAL}", "mean"),
        real_730=("latente_730", "mean"), real_sem_horizonte=("latente_0", "mean"),
        conserto_180=("conserto_futuro_180", "mean")).reset_index()
    serie.to_csv(config.PASTA_RESULTADOS / "serie_por_retrato.csv", index=False)

    resumo = {
        "rotulo": rotulo, "variante_final": config.VARIANTE_FINAL,
        "retratos_avaliados": int(len(base)), "repositorios": int(len(por_repo)),
        "taxa_base": float(y.mean()), "datas": [base["data"].min(), base["data"].max()],
        "comparacao": comparacao, "comparacao_ultimo_retrato": comparacao_ultimo,
        "calibracao": calibracao, "porcentagem": resumir_porcentagem(tabela),
        "limiares": limiares, "roc": roc, "horizontes": horizontes,
        "conserto_futuro_2023": {"repositorios": int(len(externo)),
                                 **{k: float(v) for k, v in externo.median().items()}},
    }
    ARQUIVO_SAIDA.write_text(json.dumps(resumo, indent=1, ensure_ascii=False), encoding="utf-8")
    return resumo


def mostrar(resumo: dict) -> None:
    print(f"{resumo['retratos_avaliados']} retratos, {resumo['repositorios']} repositórios, "
          f"taxa base {resumo['taxa_base']:.3f}, datas {resumo['datas']}")
    print("\nAUC por repositório (média dos retratos); referência:", resumo["variante_final"])
    print(pd.DataFrame(resumo["comparacao"]).round(4).to_string(index=False))
    print("\nAUC no último retrato de cada repositório")
    print(pd.DataFrame(resumo["comparacao_ultimo_retrato"]).round(4).to_string(index=False))
    print("\nCalibração:", {k: {a: round(b, 4) for a, b in v.items() if a != "curva"}
                            for k, v in resumo["calibracao"].items()})
    print("\nPorcentagem do repositório (pontos percentuais)")
    print(pd.DataFrame(resumo["porcentagem"]).round(3).to_string(index=False))
    print("\nLimiares:", {k: v for k, v in resumo["limiares"].items() if k != "curva"})
    print("\nAUC agregado (todos os retratos juntos):",
          {k: round(v["auc"], 4) for k, v in resumo["roc"]["agregado"].items()})
    print("\nHorizontes:", json.dumps(resumo["horizontes"], indent=1))
    print("\nConserto futuro em 180 dias, retratos de 2023+:", resumo["conserto_futuro_2023"])


def principal(argumentos: list[str]) -> None:
    mostrar(avaliar())


if __name__ == "__main__":
    principal(sys.argv[1:])

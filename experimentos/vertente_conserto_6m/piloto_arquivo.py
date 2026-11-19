"""
Piloto do rótulo por arquivo: o arquivo recebe um commit de conserto em até H dias depois do retrato?
Avaliação deixando um repositório de fora, com baselines e calibração.
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score

RAIZ = Path(r"D:\Code\TCC2")
SAIDA = Path(__file__).parent / "piloto_arquivo"
DIA = 86400
IDS = ["repositorio", "arquivo", "commit", "particao_defectors", "linhas_defeituosas",
       "defeituoso", "particao"]


# =============================================================
# Rotular
# -------------------------------------------------------------
# Junta cada retrato ao histórico e calcula rótulos e consertos anteriores
# =============================================================
def rotular(dados: pd.DataFrame, janelas: list[int]) -> pd.DataFrame:
    partes = []
    for repo, g in dados.groupby("repositorio"):
        log = pd.read_csv(RAIZ / "dados" / "historico_log" / f"{repo}.csv")
        instante = log.drop_duplicates("hash").set_index("hash").instante
        g = g.assign(instante=g.commit.map(instante)).dropna(subset=["instante"])
        ultimo = log.instante.max()
        consertos = (log[log.conserto == 1].groupby("arquivo").instante
                     .apply(lambda s: np.sort(s.to_numpy())).to_dict())
        todos = log.groupby("arquivo").instante.apply(lambda s: np.sort(s.to_numpy())).to_dict()
        vazio = np.array([], dtype=float)
        t = g.instante.to_numpy()
        arqs = g.arquivo.to_numpy()
        ant = np.zeros(len(g))
        ant_todos = np.zeros(len(g))
        rot = {h: np.zeros(len(g), dtype=int) for h in janelas}
        for i, (a, ti) in enumerate(zip(arqs, t)):
            c = consertos.get(a, vazio)
            ant[i] = np.searchsorted(c, ti, side="left")
            ant_todos[i] = np.searchsorted(todos.get(a, vazio), ti, side="left")
            depois = np.searchsorted(c, ti, side="right")
            for h in janelas:
                rot[h][i] = int(np.searchsorted(c, ti + h * DIA, side="right") > depois)
        g = g.assign(consertos_anteriores=ant,
                     fracao_consertos=ant / np.maximum(ant_todos, 1),
                     censurado=(t + max(janelas) * DIA > ultimo))
        for h in janelas:
            g[f"rotulo_{h}"] = rot[h]
        partes.append(g)
    return pd.concat(partes, ignore_index=True)


# =============================================================
# Cliff
# -------------------------------------------------------------
# Delta de Cliff entre duas amostras pareadas
# =============================================================
def cliff(a, b) -> float:
    a, b = np.asarray(a), np.asarray(b)
    return float(((a[:, None] > b[None, :]).mean() - (a[:, None] < b[None, :]).mean()))


# =============================================================
# Avaliar
# -------------------------------------------------------------
# Deixa um repositório de fora por vez e mede modelos e baselines
# =============================================================
def avaliar(dados, conjuntos, baselines, alvo, calibrar=True):
    repos = [r for r, g in dados.groupby("repositorio")
             if g.arquivo.nunique() >= 30 and g[alvo].nunique() == 2]
    linhas, notas = [], []
    for repo in repos:
        treino = dados[(dados.repositorio != repo) & dados.repositorio.isin(repos)]
        teste = dados[dados.repositorio == repo].copy()
        ultimo = teste.sort_values("instante").groupby("arquivo").tail(1).index
        resultado = {"repositorio": repo, "retratos": len(teste),
                     "arquivos": teste.arquivo.nunique(), "base": teste[alvo].mean()}
        for nome, cols in conjuntos.items():
            base = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05,
                                                  min_samples_leaf=100, random_state=42)
            modelo = CalibratedClassifierCV(base, method="sigmoid", cv=3) if calibrar else base
            modelo.fit(treino[cols], treino[alvo])
            p = modelo.predict_proba(teste[cols])[:, 1]
            teste[f"p_{nome}"] = p
            resultado[f"auc_{nome}"] = roc_auc_score(teste[alvo], p)
            resultado[f"auc_ultimo_{nome}"] = roc_auc_score(teste.loc[ultimo, alvo],
                                                            teste.loc[ultimo, f"p_{nome}"])
            resultado[f"brier_{nome}"] = brier_score_loss(teste[alvo], p)
            k = max(1, int(len(ultimo) * 0.1))
            resultado[f"topo10_{nome}"] = teste.loc[ultimo].nlargest(k, f"p_{nome}")[alvo].mean()
        for b in baselines:
            resultado[f"auc_{b}"] = roc_auc_score(teste[alvo], teste[b])
            resultado[f"auc_ultimo_{b}"] = roc_auc_score(teste.loc[ultimo, alvo],
                                                         teste.loc[ultimo, b])
            k = max(1, int(len(ultimo) * 0.1))
            resultado[f"topo10_{b}"] = teste.loc[ultimo].nlargest(k, b)[alvo].mean()
        linhas.append(resultado)
        notas.append(teste)
        print(f"  {repo:24s} base {resultado['base']:.3f}  " + "  ".join(
            f"{n} {resultado[f'auc_{n}']:.3f}" for n in conjuntos), flush=True)
    return pd.DataFrame(linhas), pd.concat(notas)


if __name__ == "__main__":
    SAIDA.mkdir(exist_ok=True)
    janelas = [90, 180, 365]
    bruto = pd.read_csv(RAIZ / "dados" / "dataset.csv")
    commits = pd.concat(pd.read_csv(f) for f in (RAIZ / "dados" / "commits").glob("*.csv"))
    bruto = bruto.merge(commits, on=["repositorio", "commit"], how="left")
    dados = rotular(bruto, janelas)
    print(f"retratos {len(bruto)} -> com data no log {len(dados)}; censurados "
          f"{dados.censurado.sum()}")
    dados = dados[~dados.censurado]
    for h in janelas:
        print(f"  base {h} dias: {dados[f'rotulo_{h}'].mean():.3f}")

    cols_commit = [c for c in commits.columns if c.startswith("commit_")]
    medidas = [c for c in bruto.columns if c not in IDS + cols_commit + ["commit"]
               and pd.api.types.is_numeric_dtype(bruto[c])]
    conjuntos = {
        "medidas": medidas,
        "medidas_consertos": medidas + ["consertos_anteriores", "fracao_consertos"],
        "tudo": medidas + ["consertos_anteriores", "fracao_consertos"] + cols_commit,
    }
    baselines = ["linhas", "revisoes", "churn", "commits_recentes", "consertos_anteriores"]
    dados["aleatorio"] = np.random.default_rng(42).random(len(dados))
    baselines.append("aleatorio")

    alvo = "rotulo_180"
    print(f"\n{len(medidas)} medidas; alvo {alvo}")
    por_repo, notas = avaliar(dados, conjuntos, baselines, alvo)
    por_repo.to_csv(SAIDA / "por_repositorio.csv", index=False)

    resumo = {"retratos": int(len(dados)), "base_180": float(dados[alvo].mean()),
              "repositorios": int(len(por_repo))}
    print("\nMEDIANAS (23 repositórios nunca vistos)")
    for n in list(conjuntos) + baselines:
        linha = {m: float(por_repo[f"{m}_{n}"].median())
                 for m in ["auc", "auc_ultimo", "topo10"] if f"{m}_{n}" in por_repo}
        if f"brier_{n}" in por_repo:
            linha["brier"] = float(por_repo[f"brier_{n}"].median())
        resumo[n] = linha
        print(f"  {n:22s} " + "  ".join(f"{k} {v:.3f}" for k, v in linha.items()))
    print(f"  base mediana do topo: {por_repo.base.median():.3f}")

    melhor_b = max(baselines, key=lambda b: por_repo[f"auc_{b}"].median())
    for n in conjuntos:
        a, b = por_repo[f"auc_{n}"], por_repo[f"auc_{melhor_b}"]
        p = wilcoxon(a, b).pvalue
        resumo[f"{n}_vs_{melhor_b}"] = {"p": float(p), "cliff": cliff(a, b),
                                        "vitorias": int((a > b).sum())}
        print(f"  {n} vs {melhor_b}: p={p:.4f}  cliff={cliff(a, b):.2f}  "
              f"vitórias {(a > b).sum()}/{len(a)}")

    agregado = {n: roc_auc_score(notas[alvo], notas[f"p_{n}"]) for n in conjuntos}
    resumo["auc_agregado"] = agregado
    print("  AUC agregado:", {k: round(v, 3) for k, v in agregado.items()})
    (SAIDA / "resumo.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False))

    fig, eixos = plt.subplots(1, 2, figsize=(13, 5))
    ordem = por_repo.sort_values("auc_medidas_consertos")
    y = np.arange(len(ordem))
    for col, cor, rot in [("auc_revisoes", "#999999", "só revisões (baseline)"),
                          (f"auc_{melhor_b}", "#e0a030", f"melhor baseline: {melhor_b}"),
                          ("auc_medidas_consertos", "#2a6fdb", "modelo")]:
        eixos[0].scatter(ordem[col], y, label=rot, color=cor, s=30)
    eixos[0].set_yticks(y, ordem.repositorio, fontsize=8)
    eixos[0].axvline(0.5, color="k", lw=0.5, ls="--")
    eixos[0].set_xlabel("AUC por retrato (repositório nunca visto)")
    eixos[0].legend(fontsize=8)
    fr, pm = calibration_curve(notas[alvo], notas["p_medidas_consertos"], n_bins=10,
                               strategy="quantile")
    eixos[1].plot(pm, fr, "o-", color="#2a6fdb", label="modelo calibrado")
    eixos[1].plot([0, 1], [0, 1], "k--", lw=0.8, label="perfeito")
    eixos[1].set_xlabel("chance prevista")
    eixos[1].set_ylabel("fração real que recebeu conserto em 6 meses")
    eixos[1].legend()
    fig.tight_layout()
    fig.savefig(SAIDA / "piloto_arquivo.png", dpi=130)
    print(f"\ngráfico: {SAIDA / 'piloto_arquivo.png'}")

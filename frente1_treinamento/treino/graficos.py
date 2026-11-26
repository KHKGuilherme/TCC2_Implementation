import html
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from treino import config


AZUL = "#2563eb"
LARANJA = "#ea580c"
CINZA = "#6b7280"
VERDE = "#059669"
SAIDA = config.PASTA_RESULTADOS
NOMES = {
    "aleatorio": "Aleatório", "linhas_estimadas": "Tamanho (linhas)", "revisoes": "Revisões",
    "churn": "Churn total", "commits_365": "Commits em 365 dias",
    "consertos": "Consertos anteriores",
    "adicionadas_desde_conserto": "Linhas novas desde o último conserto",
    "p_processo": "Modelo: processo", "p_posicao": "Modelo: processo + posição",
    "p_completo": "Modelo: processo + posição + contexto",
    "p_balanceado": "Modelo: classes balanceadas", "p_logistica": "Regressão logística",
}

plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "figure.dpi": 130})


def salvar(figura, nome: str) -> None:
    figura.tight_layout()
    figura.savefig(SAIDA / nome)
    plt.close(figura)


def grafico_rotulo() -> dict:
    intervalos = pd.concat([pd.read_csv(p) for p in
                            config.PASTA_RETRATOS.glob("*__intervalos.csv.gz")])
    intervalos["ano"] = pd.to_datetime(intervalos["inicio"], unit="s").dt.year
    ok = intervalos[intervalos["situacao"] == "ok"].copy()
    ok["dias"] = (ok["fim"] - ok["inicio"]) / 86400
    antigos = ok[ok["ano"] <= 2016]
    figura, (a, b) = plt.subplots(1, 2, figsize=(11, 4))
    for dados, cor, nome in ((ok, CINZA, "todos os causadores"),
                             (antigos, AZUL, "introduzidos até 2016 (6+ anos observados)")):
        dias = np.sort(dados["dias"].values)
        a.plot(dias, np.arange(1, len(dias) + 1) / len(dias), color=cor, label=nome)
    for horizonte in (180, 365, 730):
        a.axvline(horizonte, color=LARANJA, ls=":", lw=1)
        a.text(horizonte, 0.03, f"{horizonte} d", color=LARANJA, rotation=90, va="bottom", ha="right")
    a.set_xscale("log")
    a.set_xlabel("dias entre o commit causador e o primeiro conserto no arquivo")
    a.set_ylabel("fração acumulada dos defeitos")
    a.set_title("Quanto tempo um defeito fica latente")
    a.legend(loc="upper left", fontsize=8)
    tabela = pd.crosstab(intervalos["ano"], intervalos["situacao"]).reindex(
        columns=["ok", "conserto_tardio", "sem_conserto"], fill_value=0)
    tabela = tabela[tabela.index >= 2010]
    base = np.zeros(len(tabela))
    for coluna, cor, nome in (("ok", AZUL, "conserto até o fim do Defectors"),
                              ("conserto_tardio", LARANJA, "conserto só depois de 11/2022"),
                              ("sem_conserto", CINZA, "nenhum conserto no arquivo")):
        b.bar(tabela.index, tabela[coluna], bottom=base, color=cor, label=nome)
        base += tabela[coluna].values
    b.set_title("Pares (commit causador, arquivo) por ano de introdução")
    b.set_xlabel("ano do commit causador")
    b.legend(fontsize=8)
    salvar(figura, "01_rotulo_tempo_ate_conserto.png")
    return {
        "pares": int(len(intervalos)),
        "situacao": intervalos["situacao"].value_counts(normalize=True).round(4).to_dict(),
        "mediana_dias_antigos": float(antigos["dias"].median()),
        "fracao_em": {str(d): float((antigos["dias"] <= d).mean()) for d in (180, 365, 730, 1095)},
    }


def grafico_prevalencia() -> None:
    serie = pd.read_csv(SAIDA / "serie_por_retrato.csv")
    serie = serie[serie["arquivos"] >= config.MINIMO_ARQUIVOS_RETRATO]
    serie["data"] = pd.to_datetime(serie["data"])
    figura, (a, b) = plt.subplots(1, 2, figsize=(12, 4.2))
    limite = pd.Timestamp(config.ULTIMO_RETRATO_ROTULADO)
    for _, grupo in serie.groupby("repositorio"):
        a.plot(grupo["data"], grupo["real_sem_horizonte"] * 100, color=CINZA, alpha=0.35, lw=0.9)
    mediana = serie.groupby("data")[["real_sem_horizonte", "real_730", "estimada"]].median() * 100
    a.plot(mediana.index, mediana["real_sem_horizonte"], color="black", lw=2,
           label="rótulo sem horizonte (mediana)")
    a.plot(mediana.index, mediana["real_730"], color=AZUL, lw=2,
           label="rótulo com horizonte de 730 dias (mediana)")
    a.axvspan(limite, pd.Timestamp(config.FIM_DEFECTORS), color=LARANJA, alpha=0.12)
    a.text(limite, a.get_ylim()[1] * 0.92, " censura:\n defeitos ainda\n não consertados",
           color=LARANJA, fontsize=8, va="top")
    a.set_xlim(pd.Timestamp("2012-01-01"), pd.Timestamp(config.FIM_DEFECTORS))
    a.set_ylabel("% dos arquivos com defeito latente")
    a.set_title("Rótulo por data do retrato (uma linha cinza por repositório)")
    a.legend(fontsize=8, loc="upper left")
    b.plot(mediana.index, mediana["real_730"], color=AZUL, lw=2, label="real, horizonte de 730 dias")
    b.plot(mediana.index, mediana["estimada"], color=VERDE, lw=2,
           label="estimada pelo modelo (repositório de fora)")
    futuro = serie.groupby("data")["conserto_180"].median() * 100
    b.plot(futuro.index, futuro, color=CINZA, lw=1.2, ls="--",
           label="recebe conserto em 180 dias (vertente reserva)")
    b.axvline(limite, color=LARANJA, ls=":")
    b.set_ylabel("% dos arquivos (mediana dos repositórios)")
    b.set_title("Porcentagem estimada ao longo do tempo, até 2026")
    b.legend(fontsize=8)
    salvar(figura, "02_prevalencia_por_data.png")


def grafico_comparacao(resumo: dict) -> None:
    por_repo = pd.read_csv(SAIDA / "auc_por_repositorio.csv", index_col=0)
    final = f"p_{resumo['variante_final']}"
    metodos = [l["metodo"] for l in resumo["comparacao"]]
    figura, (a, b) = plt.subplots(1, 2, figsize=(13, 5.2), gridspec_kw={"width_ratios": [1, 1.25]})
    dados = [por_repo[m].values for m in metodos]
    caixas = a.boxplot(dados, orientation="horizontal", patch_artist=True, widths=0.6,
                       medianprops={"color": "black"})
    for caixa, metodo in zip(caixas["boxes"], metodos):
        caixa.set_facecolor(AZUL if metodo == final else (VERDE if metodo.startswith("p_") else "#d1d5db"))
    a.set_yticks(range(1, len(metodos) + 1), [NOMES.get(m, m) for m in metodos], fontsize=8)
    a.axvline(0.5, color=CINZA, ls=":")
    a.set_xlabel("AUC por repositório deixado de fora (média dos retratos)")
    a.set_title("Modelo contra baselines triviais")
    melhor = max((m for m in metodos if not m.startswith("p_")), key=lambda m: por_repo[m].median())
    ordem = por_repo.sort_values(final)
    y = np.arange(len(ordem))
    b.barh(y - 0.2, ordem[final], height=0.4, color=AZUL, label=NOMES.get(final, final))
    b.barh(y + 0.2, ordem[melhor], height=0.4, color="#9ca3af",
           label=f"melhor baseline: {NOMES.get(melhor, melhor)}")
    b.set_yticks(y, ordem.index, fontsize=8)
    b.set_xlim(0.4, 1.0)
    b.axvline(0.5, color=CINZA, ls=":")
    b.set_xlabel("AUC")
    b.set_title("Por repositório nunca visto")
    b.legend(fontsize=8, loc="lower right")
    salvar(figura, "03_modelo_vs_baselines.png")


def grafico_tempo(resumo: dict) -> None:
    por_data = pd.read_csv(SAIDA / "auc_por_data.csv")
    por_data["data"] = pd.to_datetime(por_data["data"])
    por_data = por_data[por_data["repositorios"] >= 5]
    figura, (a, b) = plt.subplots(1, 2, figsize=(12, 4))
    a.plot(por_data["data"], por_data["modelo"], color=AZUL, lw=2, label="modelo")
    a.plot(por_data["data"], por_data["commits_365"], color=CINZA, label="commits em 365 dias")
    a.plot(por_data["data"], por_data["revisoes"], color="#d1d5db", label="revisões")
    a.set_ylim(0.45, 1.0)
    a.set_ylabel("AUC mediano entre repositórios")
    a.set_title("Comportamento por janela de tempo (retratos semestrais)")
    a.legend(fontsize=8)
    horizontes = resumo["horizontes"]
    nomes = [("180", "180 dias"), ("365", "365 dias"), ("730", "730 dias"), ("0", "sem limite")]
    x = np.arange(len(nomes))
    final = f"p_{resumo['variante_final']}"
    b.bar(x - 0.25, [horizontes[k][final] for k, _ in nomes], 0.25, color=AZUL, label="modelo")
    b.bar(x, [horizontes[k]["commits_365"] for k, _ in nomes], 0.25, color=CINZA,
          label="commits em 365 dias")
    b.bar(x + 0.25, [horizontes[k]["revisoes"] for k, _ in nomes], 0.25, color="#d1d5db",
          label="revisões")
    for i, (k, _) in enumerate(nomes):
        b.text(i, 0.47, f"base {horizontes[k]['taxa']:.1%}", ha="center", fontsize=8)
    b.set_xticks(x, [n for _, n in nomes])
    b.set_ylim(0.45, 1.0)
    b.set_ylabel("AUC mediano")
    b.set_title("Sensibilidade ao horizonte de observação do rótulo")
    b.legend(fontsize=8)
    salvar(figura, "04_tempo_e_horizonte.png")


def grafico_calibracao(resumo: dict) -> None:
    figura, eixo = plt.subplots(figsize=(5.6, 5))
    eixo.plot([0, 1], [0, 1], color=CINZA, ls=":")
    for tipo, cor, nome in (("bruta", CINZA, "sem calibrar"), ("platt", LARANJA, "Platt"),
                            ("isotonica", AZUL, "isotônica")):
        curva = resumo["calibracao"][tipo]["curva"]
        eixo.plot([c["previsto"] for c in curva], [c["observado"] for c in curva], "o-",
                  color=cor, ms=4,
                  label=f"{nome} (ECE {resumo['calibracao'][tipo]['ece']:.3f}, "
                        f"Brier {resumo['calibracao'][tipo]['brier']:.4f})")
    maximo = max(c["previsto"] for c in resumo["calibracao"]["bruta"]["curva"]) * 1.15
    eixo.set_xlim(0, maximo)
    eixo.set_ylim(0, maximo)
    eixo.set_xlabel("chance prevista (média da faixa)")
    eixo.set_ylabel("fração real com defeito latente")
    eixo.set_title("Calibração em repositórios nunca vistos")
    eixo.legend(fontsize=8)
    salvar(figura, "05_calibracao.png")


def grafico_limiar(resumo: dict) -> None:
    curva = pd.DataFrame(resumo["limiares"]["curva"])
    curva = curva[curva["marcados"] > 0.0005]
    figura, eixo = plt.subplots(figsize=(7, 4.2))
    eixo.plot(curva["limiar"], curva["precisao"], color=AZUL, label="precisão")
    eixo.plot(curva["limiar"], curva["revocacao"], color=LARANJA, label="revocação")
    eixo.plot(curva["limiar"], curva["f1"], color=VERDE, lw=2, label="F1")
    eixo.plot(curva["limiar"], curva["marcados"], color=CINZA, ls="--", label="fração marcada")
    eixo.axhline(curva["base"].iloc[0], color=CINZA, ls=":", lw=1)
    faixa = resumo["limiares"]["faixa_f1"]
    eixo.axvspan(faixa[0] - 0.004, faixa[1] + 0.004, color=VERDE, alpha=0.15)
    eixo.set_xlabel("limiar sobre a chance calibrada")
    eixo.set_title("Escolha do limiar (faixa verde: maior F1 nos outros repositórios)")
    eixo.legend(fontsize=8)
    salvar(figura, "06_limiar.png")


def grafico_porcentagem(resumo: dict) -> None:
    tabela = pd.read_csv(SAIDA / "porcentagem_por_retrato.csv")
    ultimo = tabela.sort_values("data").groupby("repositorio").tail(1)
    erros = {l["estimador"]: l for l in resumo["porcentagem"]}
    figura, eixos = plt.subplots(1, 3, figsize=(14, 4.6))
    for eixo, coluna, nome in zip(
            eixos, (f"soma_{config.CALIBRACAO_FINAL}", "contagem_f1", "taxa_treino"),
            ("Soma das chances calibradas", "Contagem acima do limiar", "Taxa fixa do treino")):
        eixo.scatter(tabela["real"] * 100, tabela[coluna] * 100, s=8, color=CINZA, alpha=0.35,
                     label="cada (repositório, data)")
        eixo.scatter(ultimo["real"] * 100, ultimo[coluna] * 100, s=28, color=AZUL,
                     label="último retrato de cada repositório")
        maximo = max(tabela["real"].max(), tabela[coluna].max()) * 105
        eixo.plot([0, maximo], [0, maximo], color=CINZA, ls=":")
        eixo.set_xlabel("% real de arquivos com defeito latente")
        eixo.set_ylabel("% estimada")
        eixo.set_title(f"{nome}\nerro médio {erros[coluna]['erro_absoluto_medio_pp']:.1f} pp, "
                       f"Spearman {erros[coluna]['spearman']:.2f}", fontsize=10)
    eixos[0].legend(fontsize=8)
    salvar(figura, "07_porcentagem_estimada_vs_real.png")
    figura, eixo = plt.subplots(figsize=(9, 5))
    ordem = ultimo.sort_values("real")
    y = np.arange(len(ordem))
    eixo.barh(y + 0.2, ordem["real"] * 100, 0.4, color=CINZA, label="real")
    eixo.barh(y - 0.2, ordem[f"soma_{config.CALIBRACAO_FINAL}"] * 100, 0.4, color=AZUL, label="estimada")
    eixo.set_yticks(y, [f"{r} ({d[:7]})" for r, d in zip(ordem["repositorio"], ordem["data"])],
                    fontsize=8)
    eixo.set_xlabel("% dos arquivos com defeito latente")
    eixo.set_title("Último retrato rotulado de cada repositório nunca visto")
    eixo.legend()
    salvar(figura, "08_porcentagem_por_repositorio.png")


def grafico_importancia() -> None:
    caminho = SAIDA / "importancia.csv"
    if not caminho.exists():
        return
    tabela = pd.read_csv(caminho).head(15).iloc[::-1]
    figura, eixo = plt.subplots(figsize=(7.5, 4.8))
    eixo.barh(tabela["feature"], tabela["queda_auc"], color=AZUL)
    eixo.set_xlabel("queda do AUC ao embaralhar a feature")
    eixo.set_title("Importância por permutação no modelo final")
    salvar(figura, "09_importancia.png")


def grafico_confusao(resumo: dict) -> None:
    limiares = resumo["limiares"]
    paineis = (("matriz_f1", "faixa_f1", "Limiar de maior F1"),
               ("matriz_precisao", "faixa_precisao", f"Limiar de precisão ≥ {config.PRECISAO_MINIMA:.0%}"))
    figura, eixos = plt.subplots(1, 2, figsize=(11, 4.6))
    for eixo, (chave, faixa, titulo) in zip(eixos, paineis):
        m = limiares[chave]
        celulas = np.array([[m["vp"], m["fn"]], [m["fp"], m["vn"]]])
        por_linha = celulas / celulas.sum(axis=1, keepdims=True)
        eixo.imshow(por_linha, cmap="Blues", vmin=0, vmax=1)
        nomes = [["verdadeiro positivo", "falso negativo"], ["falso positivo", "verdadeiro negativo"]]
        for i in range(2):
            for j in range(2):
                cor = "white" if por_linha[i, j] > 0.55 else "#111827"
                eixo.text(j, i - 0.18, f"{celulas[i, j]:,}".replace(",", "."), ha="center",
                          va="center", fontsize=15, fontweight="bold", color=cor)
                eixo.text(j, i + 0.08, f"{por_linha[i, j]:.1%} da linha".replace(".", ","),
                          ha="center", va="center", fontsize=9, color=cor)
                eixo.text(j, i + 0.30, nomes[i][j], ha="center", va="center", fontsize=8.5, color=cor)
        eixo.set_xticks([0, 1], ["marcado como risco alto", "não marcado"])
        eixo.set_yticks([0, 1], ["com defeito latente", "sem defeito"])
        eixo.set_xlabel("previsão do modelo")
        eixo.set_ylabel("realidade")
        eixo.grid(False)
        precisao = m["vp"] / max(1, m["vp"] + m["fp"])
        revocacao = m["vp"] / max(1, m["vp"] + m["fn"])
        a, b = limiares[faixa]
        eixo.set_title(f"{titulo} ({a:.2f} a {b:.2f})\nprecisão {precisao:.1%} · revocação "
                       f"{revocacao:.1%}".replace(".", ","), fontsize=10)
    figura.suptitle(f"Matriz de confusão em repositórios nunca vistos "
                    f"({resumo['retratos_avaliados']:,} retratos)".replace(",", "."), fontsize=11)
    salvar(figura, "10_matriz_confusao.png")


def grafico_roc(resumo: dict) -> None:
    roc = resumo["roc"]
    final = f"p_{resumo['variante_final']}"
    cores = {final: AZUL, "commits_365": VERDE, "churn": LARANJA, "linhas_estimadas": CINZA,
             "aleatorio": "#9ca3af"}
    figura, (a, b) = plt.subplots(1, 2, figsize=(11, 4.8))
    ordem = sorted(roc["agregado"], key=lambda m: roc["agregado"][m]["auc"], reverse=True)
    for metodo in ordem:
        curva = roc["agregado"][metodo]
        grosso = metodo == final
        a.plot(curva["fpr"], curva["tpr"], color=cores.get(metodo, CINZA), lw=2.2 if grosso else 1.2,
               ls=":" if metodo == "aleatorio" else "-",
               label=f"{NOMES.get(metodo, metodo)} (AUC {curva['auc']:.3f})".replace(".", ","))
    for chave, marcador, nome in (("matriz_f1", "o", "limiar de maior F1"),
                                  ("matriz_precisao", "s", "limiar de precisão ≥ 50%")):
        m = resumo["limiares"][chave]
        a.plot(m["fp"] / (m["fp"] + m["vn"]), m["vp"] / (m["vp"] + m["fn"]), marcador,
               color="#111827", ms=7, label=nome)
    a.set_xlabel("taxa de falsos positivos (arquivos limpos marcados)")
    a.set_ylabel("taxa de verdadeiros positivos (revocação)")
    a.set_title("Curva ROC, todos os retratos juntos")
    a.legend(fontsize=7.5, loc="lower right")
    a.set_xlim(0, 1)
    a.set_ylim(0, 1)
    aucs = []
    for nome, curva in roc["por_repositorio"].items():
        b.plot(curva["fpr"], curva["tpr"], color=AZUL, lw=0.9, alpha=0.45)
        aucs.append(curva["auc"])
    b.plot([0, 1], [0, 1], color="#9ca3af", ls=":", lw=1.2)
    aucs = np.array(aucs)
    b.text(0.97, 0.05, f"AUC por repositório\nmediana {np.median(aucs):.3f}\n"
           f"de {aucs.min():.3f} a {aucs.max():.3f}".replace(".", ","),
           ha="right", va="bottom", fontsize=9, bbox=dict(facecolor="white", edgecolor="#e5e7eb"))
    b.set_xlabel("taxa de falsos positivos")
    b.set_ylabel("taxa de verdadeiros positivos")
    b.set_title(f"Uma curva por repositório nunca visto ({len(aucs)})")
    b.set_xlim(0, 1)
    b.set_ylim(0, 1)
    salvar(figura, "11_curva_roc.png")


def tabela_html(linhas: list[dict], colunas: list[tuple[str, str, str]]) -> str:
    partes = ["<table><tr>" + "".join(f"<th>{html.escape(t)}</th>" for _, t, _ in colunas) + "</tr>"]
    for linha in linhas:
        celulas = []
        for chave, _, formato in colunas:
            valor = linha.get(chave)
            if valor is None:
                celulas.append("<td>n/d</td>")
            elif formato:
                celulas.append(f"<td class='n'>{format(valor, formato).replace('.', ',')}</td>")
            else:
                celulas.append(f"<td>{html.escape(str(NOMES.get(valor, valor)))}</td>")
        partes.append("<tr>" + "".join(celulas) + "</tr>")
    return "".join(partes) + "</table>"


def escrever_relatorio(resumo: dict, rotulo: dict) -> None:
    limiares = resumo["limiares"]
    f1 = limiares["maior_f1"]
    precisao = limiares["precisao_minima"]
    comparacao = tabela_html(resumo["comparacao"], [
        ("metodo", "Método", ""), ("auc_mediano", "AUC mediano", ".3f"),
        ("auc_medio", "AUC médio", ".3f"), ("auc_minimo", "Pior repositório", ".3f"),
        ("topo_10", "Defeito no topo 10%", ".1%"), ("referencia_vence", "Modelo vence em", "d"),
        ("wilcoxon_p", "Wilcoxon p", ".2g"), ("cliff", "Delta de Cliff", ".2f")])
    ultimo = tabela_html(resumo["comparacao_ultimo_retrato"], [
        ("metodo", "Método", ""), ("auc_mediano", "AUC mediano", ".3f"),
        ("referencia_vence", "Modelo vence em", "d"), ("wilcoxon_p", "Wilcoxon p", ".2g"),
        ("cliff", "Delta de Cliff", ".2f")])
    nomes_estimador = {"soma_bruta": "Soma das chances sem calibrar",
                       "soma_platt": "Soma das chances (Platt)",
                       "soma_isotonica": "Soma das chances (isotônica)",
                       "contagem_f1": "Contagem acima do limiar de maior F1",
                       "contagem_precisao": "Contagem acima do limiar de precisão mínima",
                       "taxa_treino": "Baseline: taxa fixa do treino"}
    porcentagem = tabela_html(
        [dict(l, estimador=nomes_estimador[l["estimador"]]) for l in resumo["porcentagem"]], [
            ("estimador", "Estimador da % do repositório", ""),
            ("erro_absoluto_medio_pp", "Erro médio (pp)", ".2f"),
            ("erro_absoluto_mediano_pp", "Erro mediano (pp)", ".2f"),
            ("vies_pp", "Viés (pp)", "+.2f"), ("spearman", "Spearman", ".2f"),
            ("ultimo_erro_absoluto_medio_pp", "Erro no último retrato (pp)", ".2f"),
            ("ultimo_spearman", "Spearman no último", ".2f")])
    externo = resumo["conserto_futuro_2023"]
    final = f"p_{resumo['variante_final']}"
    secoes = [
        ("1. O rótulo: defeito latente no arquivo", "01_rotulo_tempo_ate_conserto.png",
         f"Um arquivo tem defeito latente em T quando recebeu, até T, linhas de um commit que o "
         f"Defectors (SZZ) marcou como causador de defeito, e o primeiro commit de conserto no "
         f"mesmo arquivo vem depois de T, em até {config.HORIZONTE_PRINCIPAL} dias. Foram "
         f"{rotulo['pares']} pares (commit causador, arquivo): "
         f"{rotulo['situacao'].get('ok', 0):.1%} com conserto posterior até o fim do Defectors, "
         f"{rotulo['situacao'].get('sem_conserto', 0):.1%} sem conserto no arquivo e "
         f"{rotulo['situacao'].get('conserto_tardio', 0):.1%} com conserto só depois; os dois "
         f"últimos grupos não contam como defeito. Entre os causadores até 2016, a mediana até o "
         f"conserto é de {rotulo['mediana_dias_antigos']:.0f} dias; "
         f"{rotulo['fracao_em']['365']:.0%} são consertados em 1 ano e "
         f"{rotulo['fracao_em']['730']:.0%} em 2 anos, o que motivou o horizonte de 730 dias.", ""),
        ("2. Janelas de tempo e censura", "02_prevalencia_por_data.png",
         f"Os retratos são semestrais. Perto do fim do Defectors (11/2022) os defeitos ainda não "
         f"tinham sido consertados, e o rótulo sem horizonte despenca. Com horizonte fixo de 730 "
         f"dias, todo retrato até {config.ULTIMO_RETRATO_ROTULADO} é totalmente observável: só "
         f"esses entram no treino e na avaliação. À direita, a porcentagem estimada pelo modelo "
         f"segue até 2026, onde não há rótulo do Defectors.", ""),
        ("3. Modelo contra baselines, em repositório nunca visto", "03_modelo_vs_baselines.png",
         f"{resumo['retratos_avaliados']} retratos de {resumo['repositorios']} repositórios, taxa "
         f"base de {resumo['taxa_base']:.1%}. Cada repositório fica de fora uma vez. O AUC de um "
         f"repositório é a média dos AUCs de seus retratos. Os testes comparam o modelo final "
         f"({NOMES.get(final, final)}) com cada outro método, pareando por repositório.",
         comparacao + "<h3>Só o último retrato rotulado de cada repositório (situação do site)</h3>"
         + ultimo),
        ("4. Comportamento no tempo e horizonte do rótulo", "04_tempo_e_horizonte.png",
         f"O AUC é estável entre as datas. O mesmo modelo, treinado com 730 dias, ordena bem "
         f"qualquer horizonte. Validação auxiliar com a vertente reserva: em retratos de 2023 em "
         f"diante, fora do Defectors, a nota do modelo prevê quem recebe conserto em 180 dias com "
         f"AUC mediano {externo[final]:.3f} em {externo['repositorios']} repositórios (commits em "
         f"365 dias: {externo['commits_365']:.3f}; revisões: {externo['revisoes']:.3f}).", ""),
        ("5. Calibração", "05_calibracao.png",
         "A chance precisa ser uma probabilidade para que a soma dê a porcentagem do repositório. "
         "Os calibradores são ajustados em previsões feitas fora da dobra, por repositório, e "
         "aplicados ao repositório deixado de fora.", ""),
        ("6. Escolha do limiar", "06_limiar.png",
         f"O limiar de cada repositório é escolhido nos outros. Maior F1: limiar entre "
         f"{limiares['faixa_f1'][0]:.2f} e {limiares['faixa_f1'][1]:.2f}, precisão "
         f"{f1['precisao']:.1%}, revocação {f1['revocacao']:.1%}, F1 {f1['f1']:.3f}, marcando "
         f"{f1['marcados']:.1%} dos arquivos (base {f1['base']:.1%}). Precisão mínima de "
         f"{config.PRECISAO_MINIMA:.0%}: limiar entre {limiares['faixa_precisao'][0]:.2f} e "
         f"{limiares['faixa_precisao'][1]:.2f}, precisão {precisao['precisao']:.1%}, revocação "
         f"{precisao['revocacao']:.1%}.", ""),
        ("7. Porcentagem do repositório: estimada contra real", "07_porcentagem_estimada_vs_real.png",
         "Para cada (repositório, data), a porcentagem real é a fração de arquivos com defeito "
         "latente, e a estimada vem de três formas: soma das chances calibradas, contagem acima "
         "do limiar e a taxa fixa do treino (baseline que ignora o repositório).",
         porcentagem + "<img src='08_porcentagem_por_repositorio.png' alt='por repositório'>"),
        ("8. O que o modelo usa", "09_importancia.png",
         "Importância por permutação no modelo final, treinado em todos os repositórios.", ""),
        ("9. Matriz de confusão", "10_matriz_confusao.png",
         f"Contagem de retratos por previsão e realidade, com o limiar de cada repositório "
         f"escolhido nos outros. As linhas somam 100%: a de cima mostra quanto dos arquivos com "
         f"defeito o modelo pega (revocação), e a de baixo quantos arquivos limpos ele marca por "
         f"engano. Com taxa base de {resumo['taxa_base']:.1%}, a precisão do limiar de maior F1 "
         f"({f1['precisao']:.1%}) é {f1['precisao'] / resumo['taxa_base']:.1f} vezes a de marcar "
         f"ao acaso.", ""),
        ("10. Curva ROC", "11_curva_roc.png",
         f"À esquerda, todos os retratos juntos: AUC agregado de "
         f"{resumo['roc']['agregado'][final]['auc']:.3f} para o modelo. Os pontos marcam os dois "
         f"limiares da matriz de confusão. À direita, uma curva por repositório deixado de fora. "
         f"O número principal do trabalho continua sendo o AUC mediano por repositório da seção "
         f"3, calculado retrato a retrato, que não mistura repositórios com taxas de defeito "
         f"diferentes.", ""),
    ]
    corpo = "".join(
        f"<section><h2>{html.escape(titulo)}</h2><p>{texto}</p>"
        f"<img src='{imagem}' alt='{html.escape(titulo)}'>{extra}</section>"
        for titulo, imagem, texto, extra in secoes)
    pagina = f"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DefectLens v3, relatório</title><style>
body{{font-family:system-ui,Segoe UI,sans-serif;max-width:1080px;margin:0 auto;padding:24px;
color:#111827;background:#f9fafb;line-height:1.55}}
section{{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:20px 24px;margin:20px 0}}
h1{{margin-bottom:4px}}h2{{margin-top:0}}img{{max-width:100%;display:block;margin:12px auto}}
table{{border-collapse:collapse;font-size:14px;margin:12px 0;width:100%}}
th,td{{border-bottom:1px solid #e5e7eb;padding:6px 8px;text-align:left}}
td.n{{text-align:right;font-variant-numeric:tabular-nums}}th{{background:#f3f4f6}}
.sub{{color:#6b7280}}</style></head><body>
<h1>DefectLens v3</h1>
<p class="sub">Defeito latente por arquivo no estado atual do repositório. Todos os números
vêm de <code>resultados/avaliacao.json</code>, gerado por
<code>frente1_treinamento/avaliar.py</code>.</p>{corpo}</body></html>"""
    (SAIDA / "relatorio.html").write_text(pagina, encoding="utf-8")


def principal(argumentos: list[str]) -> None:
    resumo = json.loads((SAIDA / "avaliacao.json").read_text(encoding="utf-8"))
    rotulo = grafico_rotulo()
    grafico_prevalencia()
    grafico_comparacao(resumo)
    grafico_tempo(resumo)
    grafico_calibracao(resumo)
    grafico_limiar(resumo)
    grafico_porcentagem(resumo)
    grafico_importancia()
    grafico_confusao(resumo)
    grafico_roc(resumo)
    escrever_relatorio(resumo, rotulo)
    (SAIDA / "rotulo.json").write_text(json.dumps(rotulo, indent=1), encoding="utf-8")
    print("gráficos e relatório gravados em", SAIDA)


if __name__ == "__main__":
    principal(sys.argv[1:])

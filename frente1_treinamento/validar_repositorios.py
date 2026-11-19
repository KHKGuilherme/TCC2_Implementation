"""
Mede o modelo em projetos que ele nunca viu.

CMD -> python frente1_treinamento/validar_repositorios.py
       python frente1_treinamento/validar_repositorios.py --repo NOME
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from joblib import Parallel, delayed
from sklearn.metrics import roc_auc_score

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI))

import config
import preparacao
import treinar
from extrator import derivadas, features
from montar_dataset import gravar_csv_atomico


# =============================================================
# Carregar Dataset
# -------------------------------------------------------------
# Lê o dataset com as derivadas e sem linhas inaproveitáveis
# =============================================================
def carregar_dataset() -> pd.DataFrame:
    dados = pd.read_csv(config.ARQUIVO_DATASET)
    features.conferir_contrato(dados.columns)
    dados = preparacao.juntar_commits(dados)

    dados = derivadas.acrescentar(dados, features.COLUNAS_BASE)
    dados = preparacao.marcar_invalidos(dados)
    dados, _ = preparacao.descartar_linhas_inaproveitaveis(dados)

    return treinar.so_maduros(dados)


# =============================================================
# Prever Repositorio
# -------------------------------------------------------------
# Treina sem o repositório e prevê todos os retratos dele
# =============================================================
def prever_repositorio(dados: pd.DataFrame, nome: str) -> pd.DataFrame:
    de_fora = dados["repositorio"] == nome
    treino = dados[~de_fora]
    teste = dados[de_fora]

    medias = preparacao.medias_do_treino(treino)
    treino = preparacao.preencher(treino, medias)
    teste = preparacao.preencher(teste, medias)

    modelo = treinar.criar_modelos()[config.MODELO_FINAL]
    modelo.fit(treino[features.FEATURES].to_numpy(dtype=float),
               treino[features.COLUNA_ALVO].to_numpy())

    probabilidade = modelo.predict_proba(
        teste[features.FEATURES].to_numpy(dtype=float))[:, 1]

    return pd.DataFrame({
        "repositorio":   teste["repositorio"].to_numpy(),
        "arquivo":       teste["arquivo"].to_numpy(),
        "commit":        teste["commit"].to_numpy(),
        "probabilidade": probabilidade.round(4),
        "real":          teste[features.COLUNA_ALVO].to_numpy(),
        **{c: teste[c].to_numpy() for c in treinar.COLUNAS_DE_ORDEM},
    })


# =============================================================
# Rodar Repositorio
# -------------------------------------------------------------
# Prevê um repositório e grava o CSV dele
# =============================================================
def rodar_repositorio(dados: pd.DataFrame, nome: str) -> None:
    inicio = time.time()
    previsoes = prever_repositorio(dados, nome)
    gravar_csv_atomico(previsoes, config.PASTA_VALIDACAO_REPOS / f"{nome}.csv")
    print(f"  {nome}: {len(previsoes)} linhas, "
          f"{time.time() - inicio:.0f} s", flush=True)


# =============================================================
# Rodar Repositorios
# -------------------------------------------------------------
# Roda em paralelo os repositórios que ainda não têm CSV
# =============================================================
def rodar_repositorios(dados: pd.DataFrame, nomes: list[str]) -> None:
    config.PASTA_VALIDACAO_REPOS.mkdir(parents=True, exist_ok=True)

    pendentes = [n for n in nomes
                 if not (config.PASTA_VALIDACAO_REPOS / f"{n}.csv").exists()]
    print(f"  {len(nomes) - len(pendentes)} repositórios prontos, "
          f"{len(pendentes)} pendentes", flush=True)

    Parallel(n_jobs=config.PROCESSOS_VALIDACAO_REPOS)(
        delayed(rodar_repositorio)(dados, nome) for nome in pendentes)


# =============================================================
# AUC Seguro
# -------------------------------------------------------------
# AUC, ou vazio quando só existe uma classe
# =============================================================
def auc_seguro(verdade, nota) -> float:
    if len(np.unique(verdade)) < 2:
        return np.nan
    return roc_auc_score(verdade, nota)


# =============================================================
# Resumir Repositorio
# -------------------------------------------------------------
# As métricas de um repositório deixado de fora
# =============================================================
def resumir_repositorio(previsoes: pd.DataFrame) -> dict:
    risco = treinar.risco_por_arquivo(previsoes)
    commits = treinar.risco_por_commit(previsoes)
    resumo = {
        "repositorio":     previsoes["repositorio"].iloc[0],
        "commits":         len(commits),
        "base_commit":     commits["defeito"].mean(),
        "auc_commit":      auc_seguro(commits["defeito"], commits["risco"]),
        "linhas":          len(previsoes),
        "auc_linha":       auc_seguro(previsoes["real"],
                                      previsoes["probabilidade"]),
        "arquivos":        len(risco),
        "base_arquivo":    risco["defeito_atual"].mean(),
        "auc_arquivo":     auc_seguro(risco["defeito_atual"],
                                      risco["risco_atual"]),
    }

    for fracao in config.FRACOES_POR_REPOSITORIO:
        resumo[f"topo_{100 * fracao:.0f}"] = (
            treinar.precisao_por_repositorio(risco, fracao))
        resumo[f"topo_commit_{100 * fracao:.0f}"] = (
            treinar.precisao_por_repositorio(commits, fracao, "defeito"))

    return resumo


# =============================================================
# Comparar com Projeto Conhecido
# -------------------------------------------------------------
# AUC por retrato nas linhas que o treino principal reservou
# =============================================================
def comparar_com_conhecido(tudo: pd.DataFrame) -> pd.DataFrame:
    chave = ["repositorio", "arquivo", "commit"]
    conhecido = pd.read_csv(config.ARQUIVO_PREVISOES)
    juntas = conhecido.merge(tudo[chave + ["probabilidade"]], on=chave,
                             suffixes=("_conhecido", "_novo"),
                             validate="one_to_one")

    linhas = []
    for nome, grupo in juntas.groupby("repositorio"):
        linhas.append({
            "repositorio": nome,
            "auc_conhecido": auc_seguro(grupo["real"],
                                        grupo["probabilidade_conhecido"]),
            "auc_novo": auc_seguro(grupo["real"],
                                   grupo["probabilidade_novo"]),
        })

    print(f"\n  Mesmas {len(juntas)} linhas, por retrato")
    print(f"    projeto conhecido: "
          f"{auc_seguro(juntas['real'], juntas['probabilidade_conhecido']):.3f}")
    print(f"    projeto novo     : "
          f"{auc_seguro(juntas['real'], juntas['probabilidade_novo']):.3f}")

    return pd.DataFrame(linhas)


# =============================================================
# Gravar Resumo
# -------------------------------------------------------------
# Os números de projeto novo que a Frente 3 mostra
# =============================================================
def gravar_resumo(tudo: pd.DataFrame, grandes: pd.DataFrame,
                  commits: pd.DataFrame) -> None:
    resumo = {
        "repositorios":   int(tudo["repositorio"].nunique()),
        "auc":            round(float(roc_auc_score(commits["defeito"],
                                                    commits["risco"])), 4),
        "auc_mediano":    round(float(grandes["auc_commit"].median()), 4),
        "auc_retrato":    round(float(roc_auc_score(tudo["real"],
                                                    tudo["probabilidade"])), 4),
        "base":           round(float(commits["defeito"].mean()), 4),
        "precisao_topo":  round(treinar.precisao_por_repositorio(
            commits, config.FRACOES_POR_REPOSITORIO[0], "defeito"), 4),
        "fracao_topo":    config.FRACOES_POR_REPOSITORIO[0],
    }

    destino = config.ARQUIVO_RESUMO_PROJETO_NOVO
    temporario = destino.with_name(destino.name + ".tmp")
    temporario.write_text(json.dumps(resumo, indent=2), encoding="utf-8")
    os.replace(temporario, destino)

    print(f"\n  AUC agregado: por commit {resumo['auc']:.3f}, "
          f"por retrato {resumo['auc_retrato']:.3f}")


# =============================================================
# Mostrar Resultado
# -------------------------------------------------------------
# Junta os CSVs prontos, imprime e grava o quadro final
# =============================================================
def mostrar_resultado() -> None:
    caminhos = sorted(config.PASTA_VALIDACAO_REPOS.glob("*.csv"))
    tudo = pd.concat([pd.read_csv(c) for c in caminhos], ignore_index=True)

    resumo = pd.DataFrame([resumir_repositorio(grupo) for _, grupo
                           in tudo.groupby("repositorio")])
    resumo = resumo.sort_values("arquivos", ascending=False)

    print("\n" + "=" * 70)
    print(f"PROJETO NUNCA VISTO — {len(resumo)} repositórios")
    print("=" * 70)

    if config.ARQUIVO_PREVISOES.exists():
        resumo = resumo.merge(comparar_com_conhecido(tudo),
                              on="repositorio", how="left")

    print(f"\n  {'repositório':<24} {'commits':>7} {'base':>6} "
          f"{'AUC commit':>10} {'topo 10%':>9} {'topo 20%':>9} {'AUC arq.':>9}")
    for _, linha in resumo.iterrows():
        print(f"  {linha['repositorio']:<24} {linha['commits']:>7} "
              f"{100 * linha['base_commit']:>5.1f}% "
              f"{linha['auc_commit']:>10.3f} "
              f"{100 * linha['topo_commit_10']:>8.1f}% "
              f"{100 * linha['topo_commit_20']:>8.1f}% "
              f"{linha['auc_arquivo']:>9.3f}")

    grandes = resumo[resumo["arquivos"] >= config.MINIMO_ARQUIVOS_REPO]
    commits = treinar.risco_por_commit(tudo)
    print(f"\n  Mediana entre os {len(grandes)} repositórios com "
          f"{config.MINIMO_ARQUIVOS_REPO}+ arquivos")
    for coluna, rotulo in (("auc_commit", "AUC por commit"),
                           ("auc_linha", "AUC por retrato"),
                           ("auc_arquivo", "AUC por arquivo")):
        print(f"    {rotulo:<16}: {grandes[coluna].median():.3f}")

    print(f"\n  Todos os {len(commits)} commits, base "
          f"{100 * commits['defeito'].mean():.1f}%")
    for fracao in config.FRACOES_POR_REPOSITORIO:
        acerto = treinar.precisao_por_repositorio(commits, fracao, "defeito")
        print(f"    topo {100 * fracao:.0f}% de cada projeto: "
              f"{100 * acerto:.1f}%")

    risco = treinar.risco_por_arquivo(tudo)
    print(f"\n  Todos os {len(risco)} arquivos, base "
          f"{100 * risco['defeito_atual'].mean():.1f}%")
    for fracao in config.FRACOES_POR_REPOSITORIO:
        print(f"    topo {100 * fracao:.0f}% de cada projeto: "
              f"{100 * treinar.precisao_por_repositorio(risco, fracao):.1f}%")

    gravar_csv_atomico(resumo.round(4), config.ARQUIVO_VALIDACAO_REPOS)
    gravar_resumo(tudo, grandes, commits)
    print(f"\n  Quadro gravado: {config.ARQUIVO_VALIDACAO_REPOS}")


# =============================================================
# Main
# -------------------------------------------------------------
# Lê os argumentos e roda a validação
# =============================================================
def main() -> None:
    config.conferir_local()

    leitor = argparse.ArgumentParser()
    leitor.add_argument("--repo", help="roda só este repositório")
    argumentos = leitor.parse_args()

    dados = carregar_dataset()
    nomes = sorted(dados["repositorio"].unique())

    if argumentos.repo:
        if argumentos.repo not in nomes:
            raise SystemExit(f"Repositório fora do dataset: {argumentos.repo}")
        nomes = [argumentos.repo]

    rodar_repositorios(dados, nomes)
    mostrar_resultado()


if __name__ == "__main__":
    main()

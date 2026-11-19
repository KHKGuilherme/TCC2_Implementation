"""
Frente 1, etapa 2 — projeto nunca visto: deixa um repositório de fora por
vez, treina cada método nos demais e grava a nota de cada commit.

CMD -> python defectlens_v2/frente1_treinamento/avaliar.py
       retomável: pula os repositórios já gravados em resultados/previsoes_loro
       python defectlens_v2/frente1_treinamento/avaliar.py --refazer
"""

import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
import metricas_avaliacao
import modelos
from extrator import features

COLUNAS_DE_CONTEXTO = ["particao", "data", "defeituoso", "no_dominio",
                       "commit_arquivos", "commit_adicionadas",
                       "commit_removidas"]

PREFIXO_GRUPO = "grupo:"


# =============================================================
# LEITURA
# =============================================================


# =============================================================
# Ler Tabelas
# -------------------------------------------------------------
# Lê os retratos e os commits montados na etapa 1
# =============================================================
def ler_tabelas() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not config.ARQUIVO_RETRATOS.exists():
        raise SystemExit("Rode antes: python defectlens_v2/"
                         "frente1_treinamento/montar_commits.py")

    return (pd.read_csv(config.ARQUIVO_RETRATOS),
            pd.read_csv(config.ARQUIVO_COMMITS))


# =============================================================
# Gravar CSV Atomico
# -------------------------------------------------------------
# Grava de modo que um reinício nunca deixe o CSV pela metade
# =============================================================
def gravar_csv_atomico(tabela: pd.DataFrame, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(destino.name + ".tmp")
    tabela.to_csv(temporario, index=False)
    os.replace(temporario, destino)


# =============================================================
# IMPORTÂNCIA POR PERMUTAÇÃO
# =============================================================


# =============================================================
# Embaralhar
# -------------------------------------------------------------
# Embaralha colunas entre commits (ou entre retratos) do repositório
# =============================================================
def embaralhar(retratos: pd.DataFrame, colunas: list[str], por_commit: bool,
               sorteio: np.random.Generator) -> pd.DataFrame:
    copia = retratos.copy()

    if not por_commit:
        ordem = sorteio.permutation(len(copia))
        copia[colunas] = copia[colunas].to_numpy()[ordem]
        return copia

    unicos = copia.drop_duplicates("commit")[["commit"] + colunas]
    trocados = unicos[colunas].to_numpy()[sorteio.permutation(len(unicos))]
    mapa = pd.DataFrame(trocados, columns=colunas,
                        index=unicos["commit"].to_numpy())
    copia[colunas] = mapa.loc[copia["commit"].to_numpy()].to_numpy()
    return copia


# =============================================================
# Medir Permutacao
# -------------------------------------------------------------
# Queda do AUC no repositório de fora ao embaralhar cada feature
# =============================================================
def medir_permutacao(estimador, retratos: pd.DataFrame,
                     commits: pd.DataFrame, repositorio: str) -> pd.DataFrame:
    metodo = config.METODO_PRINCIPAL
    rotulo = commits["defeituoso"].to_numpy()

    if len(commits) < config.MINIMO_COMMITS_REPO or len(set(rotulo)) < 2:
        return pd.DataFrame()

    base = metricas_avaliacao.auc(
        rotulo, modelos.prever(metodo, estimador, retratos, commits))
    sorteio = np.random.default_rng(config.SEMENTE)

    alvos = [(f, [f], features.grupo_da_feature(f) == "commit")
             for f in modelos.TREINADOS[metodo]["colunas"]]
    alvos += [(PREFIXO_GRUPO + g, features.GRUPOS[g], g == "commit")
              for g in ("commit", "historico")]

    linhas = []
    for nome, colunas, por_commit in alvos:
        quedas = []
        for _ in range(config.REPETICOES_PERMUTACAO):
            trocado = embaralhar(retratos, colunas, por_commit, sorteio)
            nota = modelos.prever(metodo, estimador, trocado, commits)
            quedas.append(base - metricas_avaliacao.auc(rotulo, nota))

        linhas.append({"repositorio": repositorio, "feature": nome,
                       "auc_base": base, "queda_auc": float(np.mean(quedas))})

    return pd.DataFrame(linhas)


# =============================================================
# VALIDAÇÃO
# =============================================================


# =============================================================
# Avaliar Repositorio
# -------------------------------------------------------------
# Treina sem um repositório e grava as notas dos commits dele
# =============================================================
def avaliar_repositorio(repositorio: str) -> str:
    inicio = time.time()
    retratos, commits = ler_tabelas()

    fora_retratos = retratos[retratos["repositorio"] == repositorio]
    fora_commits = commits[commits["repositorio"] == repositorio]
    dentro_retratos = retratos[retratos["repositorio"] != repositorio]
    dentro_commits = commits[commits["repositorio"] != repositorio]

    saida = fora_commits[features.CHAVES + COLUNAS_DE_CONTEXTO].copy()

    for metodo in modelos.SEM_TREINO:
        saida[f"nota_{metodo}"] = modelos.nota_sem_treino(metodo,
                                                          fora_commits)

    permutacao = pd.DataFrame()
    for metodo in modelos.TREINADOS:
        estimador = modelos.treinar(metodo, dentro_retratos, dentro_commits)
        saida[f"nota_{metodo}"] = modelos.prever(metodo, estimador,
                                                 fora_retratos, fora_commits)

        if metodo == config.METODO_PRINCIPAL:
            principal = ((fora_commits["particao"]
                          .isin(config.PARTICOES_TREINO))
                         & (fora_commits["no_dominio"] == 1))
            alvo = fora_commits[principal]
            permutacao = medir_permutacao(
                estimador,
                fora_retratos[fora_retratos["commit"].isin(alvo["commit"])],
                alvo, repositorio)

    gravar_csv_atomico(permutacao if len(permutacao) else
                       pd.DataFrame(columns=["repositorio", "feature",
                                             "auc_base", "queda_auc"]),
                       config.PASTA_PERMUTACAO / f"{repositorio}.csv")
    gravar_csv_atomico(saida, config.PASTA_PREVISOES / f"{repositorio}.csv")

    return (f"  {repositorio:<24} {len(saida):>6} commits  "
            f"{time.time() - inicio:>5.0f} s")


# =============================================================
# Avaliar
# -------------------------------------------------------------
# Roda os repositórios que faltam, alguns ao mesmo tempo
# =============================================================
def avaliar(refazer: bool = False) -> None:
    _, commits = ler_tabelas()
    repositorios = sorted(commits["repositorio"].unique())

    if refazer:
        for pasta in (config.PASTA_PREVISOES, config.PASTA_PERMUTACAO):
            for antigo in pasta.glob("*.csv"):
                antigo.unlink()

    pendentes = [r for r in repositorios
                 if not (config.PASTA_PREVISOES / f"{r}.csv").exists()]

    print(f"\n  {len(repositorios)} repositórios, {len(pendentes)} por fazer, "
          f"{len(modelos.TREINADOS)} modelos treinados em cada um")

    if not pendentes:
        return

    tamanho = commits.groupby("repositorio").size()
    pendentes.sort(key=lambda r: tamanho[r])

    resultados = Parallel(n_jobs=config.PROCESSOS, return_as="generator")(
        delayed(avaliar_repositorio)(r) for r in pendentes)

    for linha in resultados:
        print(linha, flush=True)


if __name__ == "__main__":
    avaliar(refazer="--refazer" in sys.argv)

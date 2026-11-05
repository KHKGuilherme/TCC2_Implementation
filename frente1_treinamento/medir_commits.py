"""
Mede os commits do dataset e grava uma tabela por repositório.

As métricas de commit ficam fora de dados/dataset.csv de propósito:
elas pertencem ao commit, e não ao arquivo, e acrescentá-las não pede
refazer as 10 horas de medição de código. A junção com o dataset é
feita em preparacao.juntar_commits.

Cada repositório pronto vira config.PASTA_COMMITS/NOME.csv, e a rodada
seguinte pula os que já existem. O clone é apagado no fim de cada um.

CMD -> python frente1_treinamento/medir_commits.py
       python frente1_treinamento/medir_commits.py --repo NOME
"""

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI))

import config
from extrator import features, metricas_commit
from frente2_predicao import historico_rapido
from montar_dataset import apagar_pasta, clonar, gravar_csv_atomico


# =============================================================
# Medir Repositorio
# -------------------------------------------------------------
# Percorre o histórico e mede só os commits pedidos
# =============================================================
def medir_repositorio(nome: str, pasta: Path,
                      pedidos: set[str]) -> pd.DataFrame:
    linhas = []
    faltam = set(pedidos)

    for commit in historico_rapido.percorrer_commits(pasta):
        if commit.hash in faltam:
            linhas.append({"repositorio": nome, "commit": commit.hash,
                           **metricas_commit.medir_commit(commit)})
            faltam.discard(commit.hash)

            if not faltam:
                break

    if faltam:
        raise RuntimeError(f"{nome}: {len(faltam)} commits do dataset "
                           f"não aparecem no histórico")

    return pd.DataFrame(linhas)


# =============================================================
# Rodar Repositorios
# -------------------------------------------------------------
# Passa por cada repositório, pulando os que já têm CSV
# =============================================================
def rodar_repositorios(pedidos: pd.Series) -> list[str]:
    config.PASTA_COMMITS.mkdir(parents=True, exist_ok=True)
    falhas = []

    for posicao, (nome, commits) in enumerate(pedidos.items(), start=1):
        destino = config.PASTA_COMMITS / f"{nome}.csv"
        rotulo = f"[{posicao}/{len(pedidos)}] {nome}"

        if destino.exists():
            print(f"  {rotulo}: já pronto", flush=True)
            continue

        inicio = time.time()
        pasta = config.PASTA_CLONES / nome
        print(f"  {rotulo}: clonando ({len(commits)} commits)", flush=True)

        if not clonar(nome, pasta):
            print(f"  {rotulo}: FALHOU no clone", flush=True)
            falhas.append(nome)
            continue

        try:
            medidos = medir_repositorio(nome, pasta, commits)
            gravar_csv_atomico(medidos, destino)
            print(f"  {rotulo}: {len(medidos)} commits, "
                  f"{time.time() - inicio:.0f} s", flush=True)
        except RuntimeError as erro:
            print(f"  {rotulo}: FALHOU, {erro}", flush=True)
            falhas.append(nome)

        apagar_pasta(pasta)

    return falhas


# =============================================================
# Main
# -------------------------------------------------------------
# Lê os commits do dataset e mede os que faltam
# =============================================================
def main() -> None:
    config.conferir_local()

    leitor = argparse.ArgumentParser()
    leitor.add_argument("--repo", help="mede só este repositório")
    argumentos = leitor.parse_args()

    dados = pd.read_csv(config.ARQUIVO_DATASET,
                        usecols=["repositorio", "commit"])
    pedidos = dados.groupby("repositorio")["commit"].agg(set)

    if argumentos.repo:
        if argumentos.repo not in pedidos.index:
            raise SystemExit(f"Repositório fora do dataset: {argumentos.repo}")
        pedidos = pedidos[[argumentos.repo]]

    # Do menor para o maior, para um reinício perder o mínimo
    pedidos = pedidos.loc[pedidos.map(len).sort_values().index]

    print(f"  {len(pedidos)} repositórios, colunas: "
          f"{', '.join(features.COLUNAS_COMMIT)}", flush=True)

    falhas = rodar_repositorios(pedidos)

    if falhas:
        raise SystemExit(f"  Falharam: {', '.join(falhas)}. Rode de novo: "
                         f"os prontos são pulados.")

    print("  FIM", flush=True)


if __name__ == "__main__":
    main()

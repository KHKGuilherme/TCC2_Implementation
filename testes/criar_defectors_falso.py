"""
criar_defectors_falso.py
========================

Uso:
"""

import argparse
import random
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config


# =============================================================
# executar_git — roda um comando git e devolve a saída
# -------------------------------------------------------------
# Devolve a saída do comando, ou string vazia se falhar
# =============================================================
def executar_git(pasta: Path, *argumentos: str) -> str:
    resultado = subprocess.run(["git", "-C", str(pasta), *argumentos],
                               capture_output=True, timeout=300)

    if resultado.returncode != 0:
        return ""

    return resultado.stdout.decode("utf-8", errors="ignore")


# =============================================================
# gerar_linhas — monta as linhas falsas de um repositório
# -------------------------------------------------------------
# Devolve linhas no formato do Defectors para um repositório
# =============================================================
def gerar_linhas(pasta: Path, nome_repo: str, qtd_commits: int,
                 arquivos_por_commit: int,
                 sorteio: random.Random) -> list[dict]:
    linhas = []

    saida = executar_git(pasta, "log", "--reverse", "--format=%H|%cI")
    commits = [linha.split("|") for linha in saida.splitlines()
               if "|" in linha]

    if not commits:
        return []

    commits = commits[len(commits) // 5:]
    escolhidos = sorteio.sample(commits, min(qtd_commits, len(commits)))

    for hash_commit, data in escolhidos:
        arquivos = [caminho for caminho in executar_git(
            pasta, "ls-tree", "-r", "--name-only", hash_commit).splitlines()
            if caminho.endswith(".py")]

        if not arquivos:
            continue

        amostra = sorteio.sample(
            arquivos, min(arquivos_por_commit, len(arquivos)))

        for caminho in amostra:
            conteudo = executar_git(pasta, "show",
                                    f"{hash_commit}:{caminho}")
            if not conteudo.strip():
                continue

            total_linhas = conteudo.count("\n") + 1
            if sorteio.random() < 0.44:
                quantas = sorteio.randint(1, 5)
                linhas_do_defeito = sorted(sorteio.sample(
                    range(1, total_linhas + 1), min(quantas, total_linhas)))
            else:
                linhas_do_defeito = []

            linhas.append({
                "datetime":   data,
                "commit":     hash_commit,
                "repo":       nome_repo,
                "filepath":   caminho,
                "content":    conteudo.encode("utf-8"),
                "methods":    [],
                "lines":      linhas_do_defeito,
            })

    return linhas


# =============================================================
# main — gera os parquets falsos
# -------------------------------------------------------------
# Lê os repositórios indicados e grava dois parquets
# =============================================================
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repos", nargs="+", required=True,
                        help="pares caminho_local:nome/no/github")
    parser.add_argument("--commits", type=int, default=40,
                        help="commits sorteados por repositório")
    parser.add_argument("--arquivos", type=int, default=6,
                        help="arquivos sorteados por commit")
    argumentos = parser.parse_args()

    sorteio = random.Random(config.SEMENTE)
    todas = []

    for par in argumentos.repos:
        caminho, _, nome_repo = par.partition(":")
        pasta = Path(caminho)

        if not (pasta / ".git").exists():
            print(f"  {caminho}: não é um repositório Git, ignorado")
            continue

        linhas = gerar_linhas(pasta, nome_repo or pasta.name,
                              argumentos.commits, argumentos.arquivos,
                              sorteio)
        print(f"  {nome_repo or pasta.name:<32} {len(linhas)} linhas")
        todas.extend(linhas)

    if not todas:
        print("Nada gerado.")
        return

    destino = (config.PASTA_DEFECTORS
               / config.SUBPASTA_DEFECTORS
               / config.ESQUEMA_DEFECTORS)
    destino.mkdir(parents=True, exist_ok=True)

    tabela = pd.DataFrame(todas)
    cortes = [len(tabela) * 6 // 10, len(tabela) * 8 // 10]

    partes = {
        "train": tabela.iloc[:cortes[0]],
        "test":  tabela.iloc[cortes[0]:cortes[1]],
        "val":   tabela.iloc[cortes[1]:],
    }

    for nome, parte in partes.items():
        parte.to_parquet(destino / f"{nome}.parquet.gzip",
                         compression="gzip", index=False)

    defeituosos = sum(1 for linha in todas if linha["lines"])

    print(f"\n  {len(tabela)} linhas em 3 parquets em {destino}/")
    print(f"  {defeituosos} defeituosos "
          f"({100 * defeituosos / len(tabela):.0f}%)")
    print(f"  colunas: {list(tabela.columns)}")
    print("\n  Lembre: os rótulos são sorteados. Serve para testar a "
          "mecânica,")
    print("  não para concluir nada sobre o modelo.")


if __name__ == "__main__":
    config.conferir_local()
    main()

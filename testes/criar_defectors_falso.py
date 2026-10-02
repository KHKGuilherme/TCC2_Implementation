"""
criar_defectors_falso.py
========================

Cria uma cópia reduzida e falsa do Defectors, para testar o
pipeline sem precisar baixar os 2,2 GB do dataset verdadeiro.

Gera parquets com exatamente as mesmas colunas do original
(datetime, commit, repo, filepath, content, methods, induce_bug),
preenchidas a partir de repositórios Git de verdade: commits
reais, caminhos reais e conteúdo real de cada arquivo naquele
commit.

O que é falso é apenas o rótulo, que é sorteado. Por isso o
resultado não serve para nenhuma conclusão sobre o modelo —
serve para confirmar que a montagem, o treino e a avaliação
rodam, que o contrato de colunas fecha, e para estimar quanto
tempo cada repositório leva.

Como o rótulo é aleatório, o AUC esperado é próximo de 0,5.
Um valor muito acima disso indica que alguma informação do
rótulo está vazando para as features.

Uso:

    python testes/criar_defectors_falso.py \\
        --repos caminho/do/clone:nome/no/github
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
# =============================================================
def executar_git(pasta: Path, *argumentos: str) -> str:
    """Devolve a saída do comando, ou string vazia se falhar."""
    resultado = subprocess.run(["git", "-C", str(pasta), *argumentos],
                               capture_output=True, timeout=300)

    if resultado.returncode != 0:
        return ""

    return resultado.stdout.decode("utf-8", errors="ignore")


# =============================================================
# gerar_linhas — monta as linhas falsas de um repositório
# =============================================================
def gerar_linhas(pasta: Path, nome_repo: str, qtd_commits: int,
                 arquivos_por_commit: int,
                 sorteio: random.Random) -> list[dict]:
    """Devolve linhas no formato do Defectors para um repositório.

    Sorteia commits do histórico, e dentro de cada um sorteia
    arquivos .py, lendo o conteúdo que eles tinham naquele
    momento.

    Descarta o primeiro quinto do histórico. Commits muito
    iniciais têm pouquíssimos arquivos e histórico quase vazio, o
    que não representa o caso que a ferramenta vai enfrentar.
    """
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

            # Rótulo sorteado, com proporção parecida com a do
            # Defectors real, que tem 44% de arquivos defeituosos.
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
                "content":    conteudo,
                "methods":    [],
                "induce_bug": linhas_do_defeito,
            })

    return linhas


# =============================================================
# main — gera os parquets falsos
# =============================================================
def main() -> None:
    """Lê os repositórios indicados e grava dois parquets."""
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

    destino = config.PASTA_DEFECTORS
    destino.mkdir(parents=True, exist_ok=True)

    # Dois arquivos, para que o leitor seja exercitado lendo mais
    # de um parquet e removendo duplicatas entre eles.
    tabela = pd.DataFrame(todas)
    meio = len(tabela) // 2
    tabela.iloc[:meio].to_parquet(
        destino / "bug_localization_train.parquet", index=False)
    tabela.iloc[meio:].to_parquet(
        destino / "bug_localization_test.parquet", index=False)

    defeituosos = sum(1 for linha in todas if linha["induce_bug"])

    print(f"\n  {len(tabela)} linhas em 2 parquets em {destino}/")
    print(f"  {defeituosos} defeituosos "
          f"({100 * defeituosos / len(tabela):.0f}%)")
    print(f"  colunas: {list(tabela.columns)}")
    print("\n  Lembre: os rótulos são sorteados. Serve para testar a "
          "mecânica,")
    print("  não para concluir nada sobre o modelo.")


if __name__ == "__main__":
    config.conferir_local()
    main()

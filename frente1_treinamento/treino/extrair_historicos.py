import os
import sys
import time

from treino import config
from treino.medidas import historico


def extrair(nome: str) -> None:
    destino = config.PASTA_HISTORICO / f"{nome}.csv.gz"
    if destino.exists():
        print(f"{nome}: pronto", flush=True)
        return
    pasta = config.PASTA_CLONES / f"{nome}__v3"
    inicio = time.time()
    historico.clonar(f"https://github.com/{config.NOMES_NO_GITHUB[nome]}.git", pasta)
    clone = time.time() - inicio
    tabela = historico.ler_historico(pasta)
    temporario = destino.with_name(destino.name + ".tmp")
    tabela.to_csv(temporario, index=False, compression="gzip")
    os.replace(temporario, destino)
    historico.apagar_pasta(pasta)
    print(f"{nome}: {len(tabela)} linhas, clone {clone:.0f} s, total {time.time() - inicio:.0f} s",
          flush=True)


def principal(argumentos: list[str]) -> None:
    config.PASTA_HISTORICO.mkdir(parents=True, exist_ok=True)
    nomes = argumentos or list(config.NOMES_NO_GITHUB)
    for nome in nomes:
        try:
            extrair(nome)
        except Exception as erro:
            print(f"{nome}: FALHOU ({erro})", flush=True)


if __name__ == "__main__":
    principal(sys.argv[1:])

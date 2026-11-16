"""
Frente 1, passo 1: clona cada repositório do Defectors, grava o histórico e apaga o clone.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from extrator import historico  # noqa: E402


# =============================================================
# Extrair
# -------------------------------------------------------------
# Grava dados/historico/NOME.csv.gz; pula o que já está pronto
# =============================================================
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


if __name__ == "__main__":
    config.PASTA_HISTORICO.mkdir(parents=True, exist_ok=True)
    nomes = sys.argv[1:] or list(config.NOMES_NO_GITHUB)
    for nome in nomes:
        try:
            extrair(nome)
        except Exception as erro:
            print(f"{nome}: FALHOU ({erro})", flush=True)

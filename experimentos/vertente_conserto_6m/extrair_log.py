"""
Piloto: extrai o histórico (commit, data, conserto?, arquivo .py) de cada repositório.
Clone sem blobs, um CSV por repositório (retomável), clone apagado no fim.
"""

import csv
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(r"D:\Code\TCC2")
sys.path.insert(0, str(RAIZ))
import config  # noqa: E402

SAIDA = RAIZ / "dados" / "historico_log"
CLONES = RAIZ / "clones"

PADRAO_CONSERTO = re.compile(
    r"\b(fix(e[sd]|ing)?|bugs?|bugfix|defects?|crash(es|ed)?|regressions?|"
    r"errors?|fault|incorrect|wrong|broken)\b", re.IGNORECASE)
PADRAO_FALSO = re.compile(r"\b(typos?|docs?|documentation|readme|spelling|lint|flake8|whitespace)\b",
                          re.IGNORECASE)


# =============================================================
# E Conserto
# -------------------------------------------------------------
# Classifica a mensagem do commit como conserto de defeito
# =============================================================
def e_conserto(mensagem: str) -> int:
    return int(bool(PADRAO_CONSERTO.search(mensagem)) and not PADRAO_FALSO.search(mensagem))


# =============================================================
# Apagar
# -------------------------------------------------------------
# Apaga a pasta, tirando o somente leitura do Windows
# =============================================================
def apagar(pasta: Path) -> None:
    def liberar(funcao, caminho, _erro):
        os.chmod(caminho, stat.S_IWRITE)
        funcao(caminho)
    if pasta.exists():
        shutil.rmtree(pasta, onexc=liberar)


# =============================================================
# Extrair
# -------------------------------------------------------------
# Clona sem blobs, lê o git log e grava o CSV do repositório
# =============================================================
def extrair(nome: str) -> None:
    destino_csv = SAIDA / f"{nome}.csv"
    if destino_csv.exists():
        print(f"{nome}: pronto")
        return
    pasta = CLONES / f"{nome}__log"
    apagar(pasta)
    inicio = time.time()
    subprocess.run(["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout",
                    "--single-branch", "--no-tags",
                    f"https://github.com/{config.NOMES_NO_GITHUB[nome]}.git", str(pasta)],
                   check=True)
    saida = subprocess.run(["git", "-C", str(pasta), "log", "--no-merges", "--no-renames",
                            "--format=@@%H\t%ct\t%s", "--name-only", "--", "*.py"],
                           check=True, capture_output=True).stdout.decode("utf-8", "replace")
    temporario = destino_csv.with_suffix(".tmp")
    linhas = 0
    with open(temporario, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["hash", "instante", "conserto", "arquivo"])
        atual = None
        for linha in saida.splitlines():
            if linha.startswith("@@"):
                h, t, msg = (linha[2:].split("\t", 2) + [""])[:3]
                atual = (h, t, e_conserto(msg))
            elif linha.strip() and atual:
                escritor.writerow([*atual, linha.strip()])
                linhas += 1
    os.replace(temporario, destino_csv)
    apagar(pasta)
    print(f"{nome}: {linhas} linhas em {time.time() - inicio:.0f} s")


if __name__ == "__main__":
    SAIDA.mkdir(parents=True, exist_ok=True)
    for nome in sys.argv[1:]:
        extrair(nome)

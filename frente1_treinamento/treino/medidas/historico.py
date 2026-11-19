import hashlib
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pandas as pd


PADRAO_CONSERTO = re.compile(
    r"\b(fix(e[sd]|ing)?|bugs?|bugfix|defects?|crash(es|ed)?|regressions?|"
    r"errors?|fault|incorrect|wrong|broken)\b", re.IGNORECASE)
PADRAO_FALSO = re.compile(
    r"\b(typos?|docs?|documentation|readme|spelling|lint|flake8|whitespace)\b", re.IGNORECASE)

COLUNAS = ["hash", "instante", "autor", "conserto", "situacao", "arquivo", "arquivo_antigo",
           "adicionadas", "removidas"]


def e_conserto(mensagem: str) -> int:
    return int(bool(PADRAO_CONSERTO.search(mensagem)) and not PADRAO_FALSO.search(mensagem))


def apagar_pasta(pasta: Path) -> None:
    def liberar(funcao, caminho, _erro):
        os.chmod(caminho, stat.S_IWRITE)
        funcao(caminho)
    if Path(pasta).exists():
        shutil.rmtree(pasta, onexc=liberar)


def clonar(endereco: str, pasta: Path, segundos: int | None = None) -> None:
    apagar_pasta(pasta)
    Path(pasta).parent.mkdir(parents=True, exist_ok=True)
    ambiente = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    subprocess.run(["git", "clone", "--quiet", "--no-checkout", "--single-branch", "--no-tags",
                    endereco, str(pasta)], check=True, timeout=segundos, env=ambiente,
                   capture_output=True)


def anonimizar(email: str) -> str:
    return hashlib.sha1(email.strip().lower().encode("utf-8", "replace")).hexdigest()[:10]


def numero(texto: str) -> int:
    return int(texto) if texto.isdigit() else 0


def juntar_commit(cabecalho, brutas, contagens, linhas) -> None:
    if cabecalho is None:
        return
    if len(contagens) != len(brutas):
        contagens = [(0, 0)] * len(brutas)
    for (situacao, arquivo, antigo), (mais, menos) in zip(brutas, contagens):
        if arquivo.endswith(".py"):
            linhas.append((*cabecalho, situacao, arquivo, antigo, mais, menos))


def ler_historico(pasta: Path) -> pd.DataFrame:
    comando = ["git", "-C", str(pasta), "-c", "core.quotepath=off", "log", "--no-merges", "-M",
               "--raw", "--numstat", "--no-abbrev", "--format=@@%H%x09%ct%x09%ae%x09%s",
               "--", "*.py"]
    processo = subprocess.Popen(comando, stdout=subprocess.PIPE)
    linhas = []
    cabecalho = None
    brutas = []
    contagens = []
    for bruta in processo.stdout:
        texto = bruta.decode("utf-8", "replace").rstrip("\n")
        if texto.startswith("@@"):
            juntar_commit(cabecalho, brutas, contagens, linhas)
            partes = (texto[2:].split("\t", 3) + ["", "", ""])[:4]
            cabecalho = (partes[0], int(partes[1]), anonimizar(partes[2]), e_conserto(partes[3]))
            brutas, contagens = [], []
        elif texto.startswith(":"):
            campos = texto.split("\t")
            situacao = campos[0].split(" ")[-1][0]
            if situacao == "R" and len(campos) >= 3:
                brutas.append((situacao, campos[2], campos[1]))
            else:
                brutas.append((situacao, campos[1], ""))
        elif texto.strip():
            campos = texto.split("\t")
            if len(campos) >= 3:
                contagens.append((numero(campos[0]), numero(campos[1])))
    juntar_commit(cabecalho, brutas, contagens, linhas)
    processo.stdout.close()
    processo.wait()
    if processo.returncode != 0:
        raise RuntimeError(f"git log falhou em {pasta}")
    return pd.DataFrame(linhas, columns=COLUNAS)


def commit_atual(pasta: Path) -> tuple[str, int]:
    saida = subprocess.run(["git", "-C", str(pasta), "log", "-1", "--format=%H %ct"],
                           check=True, capture_output=True, text=True).stdout.split()
    return saida[0], int(saida[1])

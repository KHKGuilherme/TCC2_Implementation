"""
Lê o histórico Git de um repositório inteiro com UMA chamada ao git.
"""

import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from pydriller.domain.commit import ModificationType

MARCA = "\x01"
MARCA_EM_BYTES = MARCA.encode("ascii")


@dataclass
class Autor:
    email: str


@dataclass
class Mudanca:
    new_path: str | None
    old_path: str | None
    change_type: ModificationType
    added_lines: int
    deleted_lines: int


@dataclass
class Commit:
    hash: str
    committer_date: datetime
    author: Autor
    modified_files: list[Mudanca] = field(default_factory=list)


# =============================================================
# Contar Commits
# -------------------------------------------------------------
# Quantos commits a travessia vai percorrer
# =============================================================
def contar_commits(pasta: Path) -> int:
    saida = subprocess.run(["git", "-C", str(pasta), "rev-list",
                            "--count", "HEAD"],
                           capture_output=True, text=True, check=True)
    return int(saida.stdout.strip())


# =============================================================
# Listar Commits
# -------------------------------------------------------------
# Os hashes na mesma ordem da travessia, do mais antigo ao novo
# =============================================================
def listar_commits(pasta: Path) -> list[str]:
    saida = subprocess.run(["git", "-C", str(pasta), "rev-list",
                            "--reverse", "HEAD"],
                           capture_output=True, text=True, check=True)
    return saida.stdout.split()


# =============================================================
# Numero
# -------------------------------------------------------------
# '-' é o que o numstat escreve para arquivo binário
# =============================================================
def numero(texto: str) -> int:
    return int(texto) if texto.isdigit() else 0


# =============================================================
# Ler Mudancas
# -------------------------------------------------------------
# Converte o bloco numstat de um commit em lista de Mudanca
# =============================================================
def ler_mudancas(resto: str, trocas: set[str]) -> list[Mudanca]:
    pedacos = resto.lstrip("\n").split("\0")
    mudancas = []
    i = 0

    while i < len(pedacos):
        pedaco = pedacos[i]
        i += 1

        if not pedaco:
            continue

        partes = pedaco.split("\t", 2)
        if len(partes) < 3:
            continue

        adicionadas, removidas, caminho = partes

        if caminho == "" and i + 1 < len(pedacos):
            antigo, novo = pedacos[i], pedacos[i + 1]
            i += 2
            mudancas.append(Mudanca(novo, antigo, ModificationType.RENAME,
                                    numero(adicionadas), numero(removidas)))
            continue

        if caminho in trocas:
            mudancas.append(Mudanca(None, caminho, ModificationType.DELETE,
                                    0, numero(removidas)))
            mudancas.append(Mudanca(caminho, None, ModificationType.ADD,
                                    numero(adicionadas), 0))
            continue

        mudancas.append(Mudanca(caminho, caminho, ModificationType.MODIFY,
                                numero(adicionadas), numero(removidas)))

    return mudancas


# =============================================================
# Mapa de Trocas de Tipo
# -------------------------------------------------------------
# Quais arquivos mudaram de tipo, em cada commit
# =============================================================
def mapa_de_trocas(pasta: Path) -> dict[str, set[str]]:
    saida = subprocess.run(
        ["git", "-C", str(pasta), "-c", "core.quotepath=off", "log",
         "-M", "--diff-filter=T", "--name-only", "-z",
         f"--format={MARCA}%H"],
        capture_output=True, check=True).stdout.decode("utf-8", "replace")

    mapa = {}
    for trecho in saida.split(MARCA):
        partes = [p.strip("\n") for p in trecho.split("\0") if p.strip("\n")]
        if len(partes) > 1:
            mapa[partes[0]] = set(partes[1:])

    return mapa


# =============================================================
# Percorrer Commits
# -------------------------------------------------------------
# Gera os commits do mais antigo ao mais novo
# =============================================================
def percorrer_commits(pasta: Path, hashes: list[str] | None = None,
                      trocas: dict[str, set[str]] | None = None):
    comando = [
        "git", "-C", str(pasta),
        "-c", "core.quotepath=off",
        "-c", "diff.renameLimit=1000",
        "log", "--reverse",
        "-M", "--numstat", "-z",
        f"--format={MARCA}%H%x00%ct%x00%ae",
    ]

    if trocas is None:
        trocas = mapa_de_trocas(pasta)

    entrada = subprocess.DEVNULL
    if hashes is not None:
        comando.remove("--reverse")
        comando += ["--no-walk=unsorted", "--stdin"]
        entrada = tempfile.TemporaryFile()
        entrada.write("\n".join(hashes).encode("ascii") + b"\n")
        entrada.seek(0)

    processo = subprocess.Popen(comando, stdin=entrada,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
    pendente = b""

    try:
        while True:
            bloco = processo.stdout.read(1 << 20)
            if not bloco:
                break

            pendente += bloco
            trechos = pendente.split(MARCA_EM_BYTES)
            pendente = trechos.pop()

            for trecho in trechos:
                commit = montar_commit(trecho.decode("utf-8", "replace"),
                                       trocas)
                if commit is not None:
                    yield commit

        commit = montar_commit(pendente.decode("utf-8", "replace"), trocas)
        if commit is not None:
            yield commit

        processo.wait()
        if processo.returncode != 0:
            raise RuntimeError("o git log falhou ao ler o histórico")
    finally:
        if processo.poll() is None:
            processo.kill()
            processo.wait()

        processo.stdout.close()

        if hashes is not None:
            entrada.close()


# =============================================================
# Montar Commit
# -------------------------------------------------------------
# Um trecho da saída do git log vira um Commit
# =============================================================
def montar_commit(trecho: str,
                  trocas: dict[str, set[str]]) -> Commit | None:
    if not trecho:
        return None

    partes = trecho.split("\0", 3)
    if len(partes) < 3:
        return None

    codigo, instante, email = partes[0], partes[1], partes[2]
    resto = partes[3] if len(partes) > 3 else ""

    return Commit(
        hash=codigo,
        committer_date=datetime.fromtimestamp(int(instante), tz=timezone.utc),
        author=Autor(email),
        modified_files=ler_mudancas(resto, trocas.get(codigo, set())),
    )

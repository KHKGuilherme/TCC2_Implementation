"""
Lê o histórico Git de um repositório inteiro com uma chamada ao git.
"""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

MARCA = "\x01"
MARCA_EM_BYTES = MARCA.encode("ascii")

RENOMEADO = "renomeado"
MODIFICADO = "modificado"
ADICIONADO = "adicionado"
APAGADO = "apagado"


@dataclass
class Mudanca:
    caminho: str | None
    caminho_antigo: str | None
    tipo: str
    adicionadas: int
    removidas: int


@dataclass
class Commit:
    codigo: str
    instante: float
    autor: str
    nome_do_autor: str
    assunto: str
    mudancas: list[Mudanca] = field(default_factory=list)


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
# Numero
# -------------------------------------------------------------
# Converte a contagem do numstat, que usa '-' para binários
# =============================================================
def numero(texto: str) -> int:
    return int(texto) if texto.isdigit() else 0


# =============================================================
# Ler Mudancas
# -------------------------------------------------------------
# Converte o bloco numstat de um commit em lista de Mudanca
# =============================================================
def ler_mudancas(resto: str, trocas: set[str],
                 apagados: set[str]) -> list[Mudanca]:
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
            mudancas.append(Mudanca(novo, antigo, RENOMEADO,
                                    numero(adicionadas), numero(removidas)))
            continue

        if caminho in trocas:
            mudancas.append(Mudanca(None, caminho, APAGADO,
                                    0, numero(removidas)))
            mudancas.append(Mudanca(caminho, None, ADICIONADO,
                                    numero(adicionadas), 0))
            continue

        if caminho in apagados:
            mudancas.append(Mudanca(None, caminho, APAGADO,
                                    0, numero(removidas)))
            continue

        mudancas.append(Mudanca(caminho, caminho, MODIFICADO,
                                numero(adicionadas), numero(removidas)))

    return mudancas


# =============================================================
# Mapa por Filtro
# -------------------------------------------------------------
# Quais arquivos sofreram um tipo de mudança, em cada commit
# =============================================================
def mapa_por_filtro(pasta: Path, filtro: str) -> dict[str, set[str]]:
    saida = subprocess.run(
        ["git", "-C", str(pasta), "-c", "core.quotepath=off",
         "-c", "diff.renameLimit=1000", "log",
         "-M", f"--diff-filter={filtro}", "--name-only", "-z",
         f"--format={MARCA}%H"],
        capture_output=True, check=True).stdout.decode("utf-8", "replace")

    mapa = {}
    for trecho in saida.split(MARCA):
        partes = [p.strip("\n") for p in trecho.split("\0") if p.strip("\n")]
        if len(partes) > 1:
            mapa[partes[0]] = set(partes[1:])

    return mapa


# =============================================================
# Montar Commit
# -------------------------------------------------------------
# Um trecho da saída do git log vira um Commit
# =============================================================
def montar_commit(trecho: str, trocas: dict[str, set[str]],
                  apagados: dict[str, set[str]]) -> Commit | None:
    if not trecho:
        return None

    partes = trecho.split("\0", 5)
    if len(partes) < 5:
        return None

    codigo, instante, email, nome, assunto = partes[:5]
    resto = partes[5] if len(partes) > 5 else ""

    return Commit(
        codigo=codigo,
        instante=float(instante),
        autor=email,
        nome_do_autor=nome,
        assunto=assunto.replace(MARCA, " ")[:200],
        mudancas=ler_mudancas(resto, trocas.get(codigo, set()),
                              apagados.get(codigo, set())),
    )


# =============================================================
# Percorrer Commits
# -------------------------------------------------------------
# Gera os commits do mais antigo ao mais novo
# =============================================================
def percorrer_commits(pasta: Path):
    comando = [
        "git", "-C", str(pasta),
        "-c", "core.quotepath=off",
        "-c", "diff.renameLimit=1000",
        "log", "--reverse",
        "-M", "--numstat", "-z",
        f"--format={MARCA}%H%x00%ct%x00%ae%x00%an%x00%s",
    ]

    trocas = mapa_por_filtro(pasta, "T")
    apagados = mapa_por_filtro(pasta, "D")
    processo = subprocess.Popen(comando, stdin=subprocess.DEVNULL,
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
                                       trocas, apagados)
                if commit is not None:
                    yield commit

        commit = montar_commit(pendente.decode("utf-8", "replace"), trocas,
                               apagados)
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

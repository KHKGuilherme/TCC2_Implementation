# frente2_predicao\historico_rapido.py
"""
Lê o histórico Git de um repositório inteiro com UMA chamada ao git.

Existe porque o PyDriller é lento demais para uma tela web: ele pede
o diff de cada commit separadamente, e um repositório como o django
leva meia hora. Aqui um único 'git log --numstat' entrega as mesmas
informações em segundos.

O que este arquivo NÃO faz é calcular métrica. Ele só produz objetos
com os mesmos atributos que o PyDriller expõe, e quem acumula é o
aplicar_commit do extrator — o MESMO código que montou o dataset.
Assim o modelo recebe na web exatamente o que recebeu no treino.

Atributos imitados, e só eles, porque são os que o extrator lê:

  commit.hash, commit.committer_date, commit.author.email,
  commit.modified_files -> new_path, old_path, change_type,
                           added_lines, deleted_lines

A equivalência foi conferida arquivo a arquivo contra o PyDriller
em psf/black e psf/requests.
"""

import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from pydriller.domain.commit import ModificationType

# Separador de commit escolhido para não aparecer em caminho nem
# em e-mail
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
    # Com -z, cada arquivo vem como "adicionadas\tremovidas\tcaminho\0".
    # Renomeação vem com o caminho vazio, seguida de dois campos:
    # "adicionadas\tremovidas\t\0antigo\0novo\0"
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

        # Arquivo que virou link simbólico, ou o contrário. O
        # PyDriller enxerga isso como duas mudanças, uma remoção e
        # uma criação, e por isso conta duas revisões. O numstat
        # enxerga uma só, então ela é desdobrada aqui.
        if caminho in trocas:
            mudancas.append(Mudanca(None, caminho, ModificationType.DELETE,
                                    0, numero(removidas)))
            mudancas.append(Mudanca(caminho, None, ModificationType.ADD,
                                    numero(adicionadas), 0))
            continue

        # Fora da renomeação o extrator só usa new_path or old_path,
        # então os dois iguais dão o mesmo caminho que o PyDriller
        # daria para arquivo novo, alterado ou apagado
        mudancas.append(Mudanca(caminho, caminho, ModificationType.MODIFY,
                                numero(adicionadas), numero(removidas)))

    return mudancas


# =============================================================
# Mapa de Trocas de Tipo
# -------------------------------------------------------------
# Quais arquivos mudaram de tipo, em cada commit
# =============================================================
def mapa_de_trocas(pasta: Path) -> dict[str, set[str]]:
    # Uma segunda passada, só com os commits que têm troca de tipo.
    # São raríssimos, e ela custa uma fração da primeira.
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
    # Com 'hashes', lê exatamente esses commits, nessa ordem. É o que
    # permite retomar uma travessia: 'antigo..HEAD' não serve, porque
    # numa história com ramos paralelos repetiria commits já lidos.
    comando = [
        "git", "-C", str(pasta),
        # Caminho com acento sai como texto, e não como "\303\251"
        "-c", "core.quotepath=off",
        # Fixa o limite de renomeações em vez de herdar o da
        # máquina, que muda o que conta como renomeação
        "-c", "diff.renameLimit=1000",
        "log", "--reverse",
        # -M explícito: não depende de diff.renames do usuário. É o
        # mesmo critério de 50% de semelhança que o PyDriller usa
        "-M", "--numstat", "-z",
        # %ae e não %aE: o e-mail cru, sem .mailmap, como o
        # PyDriller lê
        f"--format={MARCA}%H%x00%ct%x00%ae",
    ]

    if trocas is None:
        trocas = mapa_de_trocas(pasta)

    # Um arquivo e não um pipe: são até centenas de milhares de
    # hashes, e o git só começa a escrever depois de ler todos
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

    # Quem consome pode parar antes do fim. O finally encerra o git
    # nesse caso, porque no Windows um processo vivo prende a pasta
    # do clone e impede a exclusão.
    try:
        # Lido em blocos para um repositório de 30 mil commits não
        # precisar caber inteiro na memória. O corte é feito em bytes,
        # antes de decodificar: a divisa de um bloco pode cair no meio
        # de uma letra acentuada.
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
        # Commit de merge não traz numstat, e a lista fica vazia,
        # que é o mesmo que o PyDriller devolve para merge
        modified_files=ler_mudancas(resto, trocas.get(codigo, set())),
    )
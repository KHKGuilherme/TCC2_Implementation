"""
Acesso ao repositório do GitHub: endereço, tamanho, clone vigiado e limpeza.
"""

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import config

PADRAO_ENDERECO = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:github\.com/)?"
    r"(?P<dono>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?"
    r"(?:/tree/(?P<ramo>[^?#]+))?/?$")

API_DO_GITHUB = "https://api.github.com/repos/"

INTERVALO_DA_VIGIA = 2.0


class ErroDeAnalise(Exception):
    """Falha que deve chegar ao usuário com a mensagem como está."""


# =============================================================
# ENDEREÇO E TAMANHO
# =============================================================


# =============================================================
# Interpretar Endereco
# -------------------------------------------------------------
# Separa dono/repo e o ramo de qualquer forma de endereço
# =============================================================
def interpretar_endereco(texto: str) -> tuple[str, str | None]:
    encontrado = PADRAO_ENDERECO.match(texto.strip())

    if not encontrado:
        raise ErroDeAnalise(
            "Endereço não reconhecido. Use dono/repositorio ou "
            "https://github.com/dono/repositorio")

    repositorio = f"{encontrado['dono']}/{encontrado['repo']}"
    return repositorio, encontrado["ramo"]


# =============================================================
# Consultar GitHub
# -------------------------------------------------------------
# Tamanho e ramo padrão pela API, ou None se a API não responder
# =============================================================
def consultar_github(repositorio: str) -> dict | None:
    pedido = urllib.request.Request(
        API_DO_GITHUB + repositorio,
        headers={"User-Agent": "defectlens",
                 "Accept": "application/vnd.github+json"})

    chave = os.environ.get("DEFECTLENS_GITHUB_TOKEN")
    if chave:
        pedido.add_header("Authorization", f"Bearer {chave}")

    try:
        with urllib.request.urlopen(pedido, timeout=15) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        if erro.code == 404:
            raise ErroDeAnalise(
                "Repositório não encontrado, ou privado.") from None
        return None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None

    return {
        "tamanho_mb": round(dados.get("size", 0) / 1024.0, 1),
        "ramo_padrao": dados.get("default_branch"),
        "linguagem": dados.get("language"),
    }


# =============================================================
# Conferir Tamanho
# -------------------------------------------------------------
# Recusa, antes de clonar, o repositório acima do limite
# =============================================================
def conferir_tamanho(repositorio: str) -> dict | None:
    informacao = consultar_github(repositorio)

    if informacao and informacao["tamanho_mb"] > config.LIMITE_REPOSITORIO_MB:
        raise ErroDeAnalise(
            f"O repositório tem {informacao['tamanho_mb']:.0f} MB, acima do "
            f"limite de {config.LIMITE_REPOSITORIO_MB} MB desta instalação.")

    return informacao


# =============================================================
# GIT
# =============================================================


# =============================================================
# Rodar Git
# -------------------------------------------------------------
# Executa o git sem nunca pedir senha
# =============================================================
def rodar_git(argumentos: list[str],
              timeout: int) -> subprocess.CompletedProcess:
    ambiente = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    return subprocess.run(["git", *argumentos], capture_output=True,
                          timeout=timeout, env=ambiente)


# =============================================================
# Motivo do Git
# -------------------------------------------------------------
# Extrai uma mensagem legível do erro do git
# =============================================================
def motivo_do_git(saida: bytes) -> str:
    texto = saida.decode("utf-8", errors="replace")

    if "not found" in texto.lower() or "could not read" in texto.lower():
        return "Repositório não encontrado, ou privado."

    for linha in texto.splitlines():
        if linha.startswith(("fatal:", "error:")):
            return linha[:200]

    return texto.strip()[:200] or "o git falhou sem mensagem"


# =============================================================
# Commit Remoto
# -------------------------------------------------------------
# O hash da ponta do ramo, sem clonar, ou None se não der
# =============================================================
def commit_remoto(repositorio: str, ramo: str | None) -> str | None:
    alvo = f"refs/heads/{ramo}" if ramo else "HEAD"

    try:
        resultado = rodar_git(["ls-remote",
                               f"https://github.com/{repositorio}.git",
                               alvo], timeout=30)
    except subprocess.TimeoutExpired:
        return None

    if resultado.returncode != 0:
        raise ErroDeAnalise(motivo_do_git(resultado.stderr))

    linhas = resultado.stdout.decode().split()
    if not linhas:
        if ramo:
            raise ErroDeAnalise(
                f"O ramo '{ramo}' não existe neste repositório.")
        return None

    return linhas[0]


# =============================================================
# Tamanho da Pasta
# -------------------------------------------------------------
# Soma, em MB, o que já foi gravado numa pasta
# =============================================================
def tamanho_da_pasta(pasta: Path) -> float:
    total = 0

    for raiz, _, arquivos in os.walk(pasta):
        for nome in arquivos:
            try:
                total += os.path.getsize(os.path.join(raiz, nome))
            except OSError:
                pass

    return total / (1024.0 * 1024.0)


# =============================================================
# Clonar
# -------------------------------------------------------------
# Clona só o histórico, vigiando o tamanho e o tempo
# =============================================================
def clonar(repositorio: str, ramo: str | None, destino: Path,
           avisar=None) -> None:
    sem_hooks = config.PASTA_CLONES / "_sem_hooks"
    sem_hooks.mkdir(parents=True, exist_ok=True)

    comando = ["git", "-c", f"core.hooksPath={sem_hooks}",
               "clone", "--quiet", f"--template={sem_hooks}",
               "--no-checkout", "--single-branch", "--no-tags"]

    if ramo:
        comando += ["--branch", ramo]

    comando += [f"https://github.com/{repositorio}.git", str(destino)]
    ambiente = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    processo = subprocess.Popen(comando, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, env=ambiente)
    inicio = time.monotonic()

    try:
        while processo.poll() is None:
            time.sleep(INTERVALO_DA_VIGIA)
            decorrido = time.monotonic() - inicio
            tamanho = tamanho_da_pasta(destino) if destino.exists() else 0.0

            if avisar:
                avisar(min(0.95, decorrido / config.SEGUNDOS_DE_CLONE),
                       f"clonando {repositorio}: {tamanho:.0f} MB")

            if tamanho > config.LIMITE_REPOSITORIO_MB:
                raise ErroDeAnalise(
                    f"O clone passou do limite de "
                    f"{config.LIMITE_REPOSITORIO_MB} MB e foi interrompido.")

            if decorrido > config.SEGUNDOS_DE_CLONE:
                raise ErroDeAnalise(
                    f"O clone passou de {config.SEGUNDOS_DE_CLONE // 60} "
                    f"minutos e foi interrompido.")
    finally:
        if processo.poll() is None:
            processo.kill()
            processo.wait()

    erro = processo.stderr.read()
    processo.stderr.close()

    if processo.returncode != 0:
        raise ErroDeAnalise(motivo_do_git(erro))


# =============================================================
# Apagar Pasta
# -------------------------------------------------------------
# Apaga uma pasta, incluindo arquivos somente leitura
# =============================================================
def apagar_pasta(pasta: Path) -> None:
    def liberar(funcao, caminho, _erro):
        try:
            Path(caminho).chmod(stat.S_IWRITE)
            funcao(caminho)
        except OSError:
            pass

    if not pasta.exists():
        return

    shutil.rmtree(pasta, onexc=liberar)


# =============================================================
# Limpar Clones Orfaos
# -------------------------------------------------------------
# Apaga o que sobrou de análises interrompidas
# =============================================================
def limpar_clones_orfaos() -> None:
    pasta = config.PASTA_CLONES / "web"

    if pasta.exists():
        for sobra in pasta.iterdir():
            apagar_pasta(sobra)

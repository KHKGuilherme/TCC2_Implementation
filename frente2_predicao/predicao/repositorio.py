import os
import re
import subprocess
from pathlib import Path

from predicao import config
from predicao.erros import ErroDeAnalise
from predicao.medidas import historico

PADRAO_ENDERECO = re.compile(
    r"^(?:(?:https?://)?(?:www\.)?github\.com/)?(?P<dono>[A-Za-z0-9_.-]+)/"
    r"(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?(?:/tree/(?P<ramo>[^\s?#]+))?/?$")

PASTA_WEB = "web"


def interpretar_endereco(texto: str) -> tuple[str, str | None]:
    encontrado = PADRAO_ENDERECO.match(texto.strip())
    if not encontrado:
        raise ErroDeAnalise("Endereço não reconhecido. Use dono/repositorio ou "
                            "https://github.com/dono/repositorio")
    return f"{encontrado['dono']}/{encontrado['repo']}", encontrado["ramo"]


def rodar_git(argumentos: list[str], segundos: int) -> subprocess.CompletedProcess:
    ambiente = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(["git", *argumentos], capture_output=True, timeout=segundos,
                          env=ambiente)


def motivo_do_git(saida: bytes) -> str:
    texto = saida.decode("utf-8", errors="replace")
    if "not found" in texto.lower() or "could not read" in texto.lower():
        return "Repositório não encontrado, ou privado."
    for linha in texto.splitlines():
        if linha.startswith(("fatal:", "error:")):
            return linha[:200]
    return texto.strip()[:200] or "o git falhou sem mensagem"


def commit_remoto(repositorio: str, ramo: str | None) -> str | None:
    alvo = f"refs/heads/{ramo}" if ramo else "HEAD"
    try:
        resultado = rodar_git(["ls-remote", f"https://github.com/{repositorio}.git", alvo], 15)
    except subprocess.TimeoutExpired:
        return None
    if resultado.returncode != 0:
        raise ErroDeAnalise(motivo_do_git(resultado.stderr))
    linhas = resultado.stdout.decode().split()
    if not linhas:
        if ramo:
            raise ErroDeAnalise(f"O ramo '{ramo}' não existe neste repositório.")
        return None
    return linhas[0]


def clonar(repositorio: str, ramo: str | None, destino: Path) -> None:
    sem_hooks = config.PASTA_CLONES / "_sem_hooks"
    sem_hooks.mkdir(parents=True, exist_ok=True)
    comando = ["-c", f"core.hooksPath={sem_hooks}", "clone", "--quiet",
               f"--template={sem_hooks}", "--no-checkout", "--single-branch", "--no-tags"]
    if ramo:
        comando += ["--branch", ramo]
    comando += [f"https://github.com/{repositorio}.git", str(destino)]
    try:
        resultado = rodar_git(comando, config.SEGUNDOS_MAXIMOS_CLONE)
    except subprocess.TimeoutExpired:
        raise ErroDeAnalise(f"O clone passou de {config.SEGUNDOS_MAXIMOS_CLONE // 60} minutos "
                            f"e foi interrompido.") from None
    if resultado.returncode != 0:
        raise ErroDeAnalise(motivo_do_git(resultado.stderr))


def limpar_clones_orfaos() -> None:
    pasta = config.PASTA_CLONES / PASTA_WEB
    if pasta.exists():
        for sobra in pasta.iterdir():
            historico.apagar_pasta(sobra)

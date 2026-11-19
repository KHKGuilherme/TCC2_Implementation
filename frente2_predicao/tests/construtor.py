import math
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def executar_git(pasta: Path, argumentos: list[str], ambiente: dict | None = None) -> None:
    subprocess.run(["git", "-C", str(pasta), *argumentos], check=True, capture_output=True,
                   env={**os.environ, **(ambiente or {})})


def construir(pasta: Path, espec: dict) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    executar_git(pasta, ["init", "-q", "-b", "main"])
    for commit in espec["commits"]:
        for antigo, novo in commit.get("renomear", {}).items():
            (pasta / novo).parent.mkdir(parents=True, exist_ok=True)
            executar_git(pasta, ["mv", antigo, novo])
        for caminho, conteudo in commit.get("escrever", {}).items():
            destino = pasta / caminho
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text("\n".join(conteudo) + "\n", encoding="utf-8", newline="\n")
        for caminho in commit.get("apagar", []):
            executar_git(pasta, ["rm", "-q", caminho])
        executar_git(pasta, ["add", "-A"])
        executar_git(pasta, ["commit", "-q", "-m", commit["mensagem"]], {
            "GIT_AUTHOR_NAME": commit["autor"], "GIT_AUTHOR_EMAIL": commit["email"],
            "GIT_COMMITTER_NAME": commit["autor"], "GIT_COMMITTER_EMAIL": commit["email"],
            "GIT_AUTHOR_DATE": commit["data"], "GIT_COMMITTER_DATE": commit["data"],
        })


def arredondar(valor):
    if valor is None:
        return None
    numero = float(valor)
    return None if math.isnan(numero) else round(numero, 6)


def instante_em_segundos(texto: str) -> int:
    return int(datetime.fromisoformat(texto).astimezone(timezone.utc).timestamp())

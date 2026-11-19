import json
import os
import urllib.error
import urllib.request

from predicao import config
from predicao.erros import ErroDeAnalise


def consultar_github(repositorio: str) -> dict | None:
    pedido = urllib.request.Request(f"https://api.github.com/repos/{repositorio}",
                                    headers={"User-Agent": "defectlens",
                                             "Accept": "application/vnd.github+json"})
    ficha = os.environ.get("GITHUB_TOKEN")
    if ficha:
        pedido.add_header("Authorization", f"Bearer {ficha}")
    try:
        with urllib.request.urlopen(pedido, timeout=15) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        if erro.code == 404:
            raise ErroDeAnalise("Repositório não encontrado, ou privado.") from None
        return None
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None
    return {"tamanho_kb": int(dados.get("size", 0)), "ramo": dados.get("default_branch"),
            "estrelas": dados.get("stargazers_count"), "linguagem": dados.get("language")}


def conferir_tamanho(repositorio: str) -> dict | None:
    ficha = consultar_github(repositorio)
    if ficha and ficha["tamanho_kb"] > config.TAMANHO_MAXIMO_REPO_KB:
        raise ErroDeAnalise(
            f"Repositório grande demais para este servidor: {ficha['tamanho_kb'] / 1024:.0f} MB "
            f"(limite de {config.TAMANHO_MAXIMO_REPO_KB / 1024:.0f} MB).")
    return ficha

import json
import math
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from treino import config
from treino.medidas import historico, metricas_historico

ARQUIVO_SAIDA = config.PASTA_CONTRATOS / "exemplos" / "golden_medidas.json"


def linhas(prefixo: str, quantidade: int, inicio: int = 0) -> list[str]:
    return [f"def {prefixo}{i}(x): return x + {i}" for i in range(inicio, inicio + quantidade)]


def especificacao() -> dict:
    nucleo = linhas("a", 40)
    return {
        "commits": [
            {"autor": "ana", "email": "ana@exemplo.org", "data": "2023-01-10T10:00:00+00:00",
             "mensagem": "Primeira versao",
             "escrever": {"app/__init__.py": ["VERSAO = 1"], "app/core.py": nucleo,
                          "app/util.py": linhas("u", 10), "tests/test_core.py": linhas("t", 8)}},
            {"autor": "bruno", "email": "bruno@exemplo.org", "data": "2023-03-05T09:30:00+00:00",
             "mensagem": "Add retry logic",
             "escrever": {"app/core.py": nucleo + linhas("r", 12)}},
            {"autor": "ana", "email": "ana@exemplo.org", "data": "2023-05-20T16:45:00+00:00",
             "mensagem": "Fix crash when input is empty",
             "escrever": {"app/util.py": linhas("u", 7) + linhas("v", 3)}},
            {"autor": "bruno", "email": "bruno@exemplo.org", "data": "2023-08-01T11:00:00+00:00",
             "mensagem": "Rename util to helpers",
             "renomear": {"app/util.py": "app/helpers.py"}},
            {"autor": "carla", "email": "carla@exemplo.org", "data": "2023-11-15T14:20:00+00:00",
             "mensagem": "Fix wrong totals in report",
             "escrever": {"app/core.py": nucleo[:35] + linhas("w", 5) + linhas("r", 12),
                          "app/novo.py": linhas("n", 20)}},
            {"autor": "ana", "email": "ana@exemplo.org", "data": "2024-02-02T08:10:00+00:00",
             "mensagem": "Remove novo", "apagar": ["app/novo.py"]},
            {"autor": "bruno", "email": "bruno@exemplo.org", "data": "2024-04-10T17:00:00+00:00",
             "mensagem": "Handle errors",
             "escrever": {"app/core.py": nucleo[:35] + linhas("w", 5) + linhas("r", 12)
                          + linhas("e", 8)}},
        ],
        "instante": "2024-05-01T00:00:00+00:00",
    }


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


def limpar(valor):
    if valor is None:
        return None
    numero = float(valor)
    return None if math.isnan(numero) else round(numero, 6)


def calcular(pasta: Path, instante: int) -> dict:
    tabela = historico.ler_historico(pasta)
    medidas = metricas_historico.medir(metricas_historico.identificar(tabela), instante)
    esperado = {}
    for linha in medidas.to_dict("records"):
        esperado[linha["arquivo"]] = {nome: limpar(linha[nome])
                                      for nome in metricas_historico.FEATURES}
    return {"features": metricas_historico.FEATURES, "esperado": esperado}


def instante_em_segundos(texto: str) -> int:
    return int(datetime.fromisoformat(texto).astimezone(timezone.utc).timestamp())


def principal(argumentos: list[str]) -> None:
    espec = especificacao()
    pasta = Path(tempfile.mkdtemp(prefix="exemplos_"))
    try:
        construir(pasta, espec)
        resultado = calcular(pasta, instante_em_segundos(espec["instante"]))
    finally:
        historico.apagar_pasta(pasta)
    conteudo = {"especificacao": espec, "instante": instante_em_segundos(espec["instante"]),
                **resultado}
    ARQUIVO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_SAIDA.write_text(json.dumps(conteudo, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"exemplos gravados em {ARQUIVO_SAIDA} ({len(resultado['esperado'])} arquivos)")


if __name__ == "__main__":
    import sys

    principal(sys.argv[1:])

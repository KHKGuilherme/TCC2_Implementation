import hashlib
import json

from treino import config

VERSAO_DO_CONTRATO = 1


def sha256_do_modelo() -> str:
    return hashlib.sha256(config.ARQUIVO_MODELO.read_bytes()).hexdigest()


def montar(resumo: dict) -> dict:
    return {
        "contrato": VERSAO_DO_CONTRATO,
        **resumo,
        "modelo": {"arquivo": config.ARQUIVO_MODELO.name, "sha256": sha256_do_modelo()},
    }


def gravar(resumo: dict) -> dict:
    conteudo = montar(resumo)
    config.ARQUIVO_MANIFESTO.write_text(json.dumps(conteudo, indent=1, ensure_ascii=False),
                                        encoding="utf-8")
    return conteudo

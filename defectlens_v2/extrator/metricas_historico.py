"""
Acumula o histórico de cada arquivo .py, commit a commit, com as mesmas
regras que geraram o dataset original.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

from . import historico_git

SEGUNDOS_POR_DIA = 86400.0


# =============================================================
# Normalizar
# -------------------------------------------------------------
# Deixa todo caminho com barra normal
# =============================================================
def normalizar(caminho: str | None) -> str | None:
    if caminho is None:
        return None

    return caminho.replace("\\", "/")


# =============================================================
# Acumulador Vazio
# -------------------------------------------------------------
# Cria o registro inicial de um arquivo
# =============================================================
def acumulador_vazio() -> dict:
    return {
        "revisoes":  0,
        "autores":   set(),
        "churn":     0,
        "insercoes": 0,
        "remocoes":  0,
        "primeira":  None,
        "ultima":    None,
        "penultima": None,
        "por_autor": Counter(),
        "recentes":  [],
        "soma_arquivos_por_commit": 0,
    }


# =============================================================
# Transferir
# -------------------------------------------------------------
# Move o histórico de um caminho para outro, num renomeio
# =============================================================
def transferir(destino: dict, origem: dict) -> None:
    destino["revisoes"] += origem["revisoes"]
    destino["autores"] |= origem["autores"]
    destino["churn"] += origem["churn"]
    destino["insercoes"] += origem["insercoes"]
    destino["remocoes"] += origem["remocoes"]
    destino["por_autor"] += origem["por_autor"]
    destino["recentes"].extend(origem["recentes"])
    destino["soma_arquivos_por_commit"] += origem["soma_arquivos_por_commit"]

    primeiras = [d for d in (destino["primeira"], origem["primeira"])
                 if d is not None]
    destino["primeira"] = min(primeiras) if primeiras else None

    ultimas = sorted(d for d in (destino["ultima"], origem["ultima"],
                                 destino["penultima"], origem["penultima"])
                     if d is not None)
    destino["ultima"] = ultimas[-1] if ultimas else None
    destino["penultima"] = ultimas[-2] if len(ultimas) > 1 else None


# =============================================================
# Podar
# -------------------------------------------------------------
# Descarta o que saiu da janela de tempo
# =============================================================
def podar(registro: dict, instante: float) -> None:
    limite = instante - config.JANELA_RECENTE_DIAS * SEGUNDOS_POR_DIA
    registro["recentes"] = [(q, a) for q, a in registro["recentes"]
                            if q >= limite]


# =============================================================
# Aplicar Commit
# -------------------------------------------------------------
# Incorpora um commit ao acumulador e devolve os .py que ele tocou
# =============================================================
def aplicar_commit(acumulado: dict, commit) -> list[str]:
    tamanho_do_commit = len(commit.mudancas)
    tocados = []

    for mudanca in commit.mudancas:
        caminho = normalizar(mudanca.caminho or mudanca.caminho_antigo)
        caminho_antigo = normalizar(mudanca.caminho_antigo)

        if not caminho or not caminho.endswith(".py"):
            continue

        if (mudanca.tipo == historico_git.RENOMEADO
                and caminho_antigo
                and caminho_antigo in acumulado):
            destino = acumulado.setdefault(caminho, acumulador_vazio())
            transferir(destino, acumulado.pop(caminho_antigo))

        registro = acumulado.setdefault(caminho, acumulador_vazio())

        registro["revisoes"] += 1
        registro["autores"].add(commit.autor)
        registro["churn"] += mudanca.adicionadas + mudanca.removidas
        registro["insercoes"] += mudanca.adicionadas
        registro["remocoes"] += mudanca.removidas
        registro["por_autor"][commit.autor] += 1
        registro["soma_arquivos_por_commit"] += tamanho_do_commit

        if registro["primeira"] is None:
            registro["primeira"] = commit.instante

        registro["penultima"] = registro["ultima"]
        registro["ultima"] = commit.instante

        registro["recentes"].append((commit.instante, commit.autor))
        podar(registro, commit.instante)

        if mudanca.caminho is not None and caminho not in tocados:
            tocados.append(caminho)

    return tocados


# =============================================================
# Resumir Registro
# -------------------------------------------------------------
# Converte um acumulador nas colunas de histórico do dataset
# =============================================================
def resumir_registro(registro: dict, instante: float) -> dict:
    revisoes = registro["revisoes"]
    primeira = registro["primeira"]
    penultima = registro["penultima"]

    limite = instante - config.JANELA_RECENTE_DIAS * SEGUNDOS_POR_DIA
    recentes = [(q, a) for q, a in registro["recentes"] if q >= limite]

    contagens = registro["por_autor"]
    maior = max(contagens.values(), default=0)
    menores = sum(1 for n in contagens.values()
                  if revisoes and n / revisoes < config.FRACAO_AUTOR_MENOR)

    return {
        "revisoes": revisoes,
        "autores":  len(registro["autores"]),
        "churn":    registro["churn"],
        "insercoes": registro["insercoes"],
        "remocoes":  registro["remocoes"],
        "idade_dias": round((instante - primeira) / SEGUNDOS_POR_DIA, 1)
                      if primeira is not None else 0.0,
        "dias_desde_anterior": round(
            (registro["ultima"] - penultima) / SEGUNDOS_POR_DIA, 1)
            if penultima is not None else 0.0,
        "commits_recentes": len(recentes),
        "autores_recentes": len({a for _, a in recentes}),
        "fracao_autor_principal": round(maior / revisoes, 4)
                                  if revisoes else 0.0,
        "autores_menores": menores,
        "arquivos_por_commit": round(
            registro["soma_arquivos_por_commit"] / revisoes, 2)
            if revisoes else 0.0,
    }

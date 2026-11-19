"""
Percorre o histórico de um repositório podendo retomar depois de uma queda.
"""

import hashlib
import json
import os
import pickle
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from extrator import metricas_historico
from frente2_predicao import historico_rapido

VERSAO_DO_PONTO = 1


# =============================================================
# Assinatura do Ponto
# -------------------------------------------------------------
# Identifica o clone e o pedido a que um ponto pertence
# =============================================================
def assinatura_do_ponto(hashes: list[str],
                        caminhos_por_commit: dict[str, set[str]]) -> dict:
    pedido = sorted((c, sorted(a)) for c, a in caminhos_por_commit.items())
    resumo = hashlib.sha1(json.dumps(pedido).encode("utf-8")).hexdigest()

    lista = hashlib.sha1("\n".join(hashes).encode("ascii")).hexdigest()

    return {"versao": VERSAO_DO_PONTO, "commits": lista, "pedido": resumo}


# =============================================================
# Carregar Ponto
# -------------------------------------------------------------
# Lê o ponto de retomada, se ele existir e valer para este pedido
# =============================================================
def carregar_ponto(arquivo: Path, assinatura: dict) -> dict | None:
    if not arquivo.exists():
        return None

    try:
        with open(arquivo, "rb") as entrada:
            ponto = pickle.load(entrada)
    except Exception as erro:
        print(f"ponto de retomada ilegível ({type(erro).__name__}), "
              f"recomeçando... ", end="", flush=True)
        return None

    if ponto.get("assinatura") != assinatura:
        print("ponto de retomada de outro clone, recomeçando... ",
              end="", flush=True)
        return None

    return ponto


# =============================================================
# Gravar Ponto
# -------------------------------------------------------------
# Grava o estado de modo que uma queda nunca deixe o ponto pela metade
# =============================================================
def gravar_ponto(arquivo: Path, ponto: dict) -> None:
    temporario = arquivo.with_name(arquivo.name + ".tmp")

    with open(temporario, "wb") as saida:
        pickle.dump(ponto, saida, protocol=pickle.HIGHEST_PROTOCOL)
        saida.flush()
        os.fsync(saida.fileno())

    os.replace(temporario, arquivo)


# =============================================================
# Medir nos Commits
# -------------------------------------------------------------
# Travessia única com várias fotografias, retomável
# =============================================================
def medir_nos_commits(pasta_repo: Path,
                      caminhos_por_commit: dict[str, set[str]],
                      arquivo_ponto: Path,
                      ao_fotografar=None) -> dict[str, dict]:
    hashes = historico_rapido.listar_commits(pasta_repo)
    assinatura = assinatura_do_ponto(hashes, caminhos_por_commit)
    ponto = carregar_ponto(arquivo_ponto, assinatura)

    if ponto:
        acumulado = ponto["acumulado"]
        fotografias = ponto["fotografias"]
        trocas = ponto["trocas"]
        feitos = ponto["feitos"]
        print(f"retomando do commit {feitos}/{len(hashes)}... ",
              end="", flush=True)
    else:
        acumulado = {}
        fotografias = {}
        trocas = historico_rapido.mapa_de_trocas(pasta_repo)
        feitos = 0

    pendentes = set(caminhos_por_commit) - set(fotografias)
    restantes = hashes[feitos:]

    if not pendentes or not restantes:
        return fotografias

    ultimo_ponto = time.monotonic()

    for posicao, commit in enumerate(
            historico_rapido.percorrer_commits(pasta_repo, restantes, trocas),
            start=feitos + 1):

        if commit.hash != hashes[posicao - 1]:
            raise RuntimeError(f"travessia fora de ordem no commit {posicao}")

        metricas_historico.aplicar_commit(acumulado, commit)

        if commit.hash in pendentes:
            fotografias[commit.hash] = metricas_historico.fotografar(
                acumulado, caminhos_por_commit[commit.hash],
                commit.committer_date.timestamp())
            pendentes.discard(commit.hash)

            if ao_fotografar:
                ao_fotografar(len(fotografias), len(pendentes))

            if not pendentes:
                break

        if time.monotonic() - ultimo_ponto >= config.SEGUNDOS_ENTRE_PONTOS:
            gravar_ponto(arquivo_ponto, {
                "assinatura": assinatura, "feitos": posicao,
                "acumulado": acumulado, "fotografias": fotografias,
                "trocas": trocas,
            })
            ultimo_ponto = time.monotonic()

    return fotografias

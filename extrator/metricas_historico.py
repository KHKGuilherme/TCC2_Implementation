"""
Mede como um arquivo .py evoluiu até um commit, em três grupos.

  base      -> revisões, autores e churn
  temporal  -> idade, intervalo entre mudanças, atividade recente
  propriedade -> concentração do trabalho entre os autores

Tudo sai da MESMA travessia do histórico. Acrescentar um grupo não
custa um segundo a mais de clone: o caro aqui é percorrer os
commits, e isso já é feito uma vez só.

A correção temporal é a regra que não pode ser quebrada: o
acumulador avança commit a commit e é fotografado no commit
rotulado, então cada linha enxerga apenas o passado dela. Nenhuma
métrica olha para frente.
"""

import sys
from collections import Counter
from pathlib import Path

from pydriller import Repository
from pydriller.domain.commit import ModificationType

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

SEGUNDOS_POR_DIA = 86400.0


# =============================================================
# normalizar
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
        # Quantos commits cada pessoa fez neste arquivo
        "por_autor": Counter(),
        # (instante, autor) dentro da janela recente, podado a cada
        # commit para o uso de memória não crescer com a história
        "recentes":  [],
        # Soma dos tamanhos dos commits que tocaram o arquivo
        "soma_arquivos_por_commit": 0,
    }


# =============================================================
# Transferir
# -------------------------------------------------------------
# Move o histórico de um caminho para outro
# =============================================================
def transferir(destino: dict, origem: dict) -> None:
    # Chamado quando o arquivo é renomeado: sem isso, o histórico
    # some e o arquivo renasce com idade zero
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
# Podar Recentes
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
# Incorpora um commit ao acumulador
# =============================================================
def aplicar_commit(acumulado: dict, commit) -> None:
    # Numa variável porque modified_files é uma propriedade que
    # recalcula o diff a cada acesso, e o diff é a parte cara
    mudancas = commit.modified_files
    tamanho_do_commit = len(mudancas)
    instante = commit.committer_date.timestamp()
    autor = commit.author.email

    for mudanca in mudancas:
        caminho = normalizar(mudanca.new_path or mudanca.old_path)
        caminho_antigo = normalizar(mudanca.old_path)

        if not caminho or not caminho.endswith(".py"):
            continue

        if (mudanca.change_type == ModificationType.RENAME
                and caminho_antigo
                and caminho_antigo in acumulado):
            destino = acumulado.setdefault(caminho, acumulador_vazio())
            transferir(destino, acumulado.pop(caminho_antigo))

        registro = acumulado.setdefault(caminho, acumulador_vazio())

        adicionadas = mudanca.added_lines or 0
        removidas = mudanca.deleted_lines or 0

        registro["revisoes"] += 1
        registro["autores"].add(autor)
        registro["churn"] += adicionadas + removidas
        registro["insercoes"] += adicionadas
        registro["remocoes"] += removidas
        registro["por_autor"][autor] += 1
        registro["soma_arquivos_por_commit"] += tamanho_do_commit

        if registro["primeira"] is None:
            registro["primeira"] = instante

        registro["penultima"] = registro["ultima"]
        registro["ultima"] = instante

        registro["recentes"].append((instante, autor))
        podar(registro, instante)


# =============================================================
# Resumir Registro
# -------------------------------------------------------------
# Converte um acumulador nas colunas do dataset
# =============================================================
def resumir_registro(registro: dict, instante: float) -> dict:
    revisoes = registro["revisoes"]

    medidas = {
        "revisoes": revisoes,
        "autores":  len(registro["autores"]),
        "churn":    registro["churn"],
    }

    if config.MEDIR_TEMPORAL:
        primeira = registro["primeira"]
        penultima = registro["penultima"]

        # A janela conta a partir do commit fotografado, não de
        # hoje: é o que o modelo saberia naquele momento
        limite = instante - config.JANELA_RECENTE_DIAS * SEGUNDOS_POR_DIA
        recentes = [(q, a) for q, a in registro["recentes"] if q >= limite]

        medidas.update({
            "insercoes": registro["insercoes"],
            "remocoes":  registro["remocoes"],
            "idade_dias": round((instante - primeira) / SEGUNDOS_POR_DIA, 1)
                          if primeira is not None else 0.0,
            # Intervalo entre as duas últimas alterações. Não uso
            # "dias desde a última" porque o commit fotografado É
            # uma alteração: aquilo daria zero sempre.
            "dias_desde_anterior": round(
                (registro["ultima"] - penultima) / SEGUNDOS_POR_DIA, 1)
                if penultima is not None else 0.0,
            "commits_recentes": len(recentes),
            "autores_recentes": len({a for _, a in recentes}),
        })

    if config.MEDIR_PROPRIEDADE:
        contagens = registro["por_autor"]
        maior = max(contagens.values(), default=0)

        # Bird et al., "Don't touch my code!": arquivo com muitos
        # contribuidores ocasionais tem mais defeito que arquivo
        # com dono claro
        menores = sum(1 for n in contagens.values()
                      if revisoes and n / revisoes < config.FRACAO_AUTOR_MENOR)

        medidas.update({
            "fracao_autor_principal": round(maior / revisoes, 4)
                                      if revisoes else 0.0,
            "autores_menores": menores,
            "arquivos_por_commit": round(
                registro["soma_arquivos_por_commit"] / revisoes, 2)
                if revisoes else 0.0,
        })

    return medidas


# =============================================================
# Fotografar
# -------------------------------------------------------------
# Congela o acumulador dos arquivos pedidos
# =============================================================
def fotografar(acumulado: dict, caminhos: set[str],
               instante: float) -> dict:
    resultado = {}

    for pedido in caminhos:
        registro = acumulado.get(normalizar(pedido))
        if registro is None:
            continue

        resultado[pedido] = resumir_registro(registro, instante)

    return resultado


# =============================================================
# Medir nos commits
# -------------------------------------------------------------
# Travessia única com várias fotografias
# =============================================================
def medir_nos_commits(pasta_repo: Path,
                      caminhos_por_commit: dict[str, set[str]],
                      ao_fotografar=None) -> dict[str, dict]:
    acumulado = {}
    fotografias = {}
    pendentes = set(caminhos_por_commit)

    for commit in Repository(str(pasta_repo)).traverse_commits():
        aplicar_commit(acumulado, commit)

        if commit.hash in pendentes:
            fotografias[commit.hash] = fotografar(
                acumulado, caminhos_por_commit[commit.hash],
                commit.committer_date.timestamp())
            pendentes.discard(commit.hash)

            if ao_fotografar:
                ao_fotografar(len(fotografias), len(pendentes))

            if not pendentes:
                break

    return fotografias


# =============================================================
# Medir Estado Atual
# -------------------------------------------------------------
# Histórico até o último commit
# =============================================================
def medir_estado_atual(pasta_repo: Path) -> dict[str, dict]:
    acumulado = {}
    ultimo = 0.0

    for commit in Repository(str(pasta_repo)).traverse_commits():
        aplicar_commit(acumulado, commit)
        ultimo = commit.committer_date.timestamp()

    return fotografar(acumulado, set(acumulado), ultimo)
"""
Mede um arquivo .py sem olhar o histórico. Usa duas ferramentas:

  Radon  -> Lê a árvore sintática do código e calcula tamanho, complexidade ciclomática e manutenibilidade.

  Lizard -> Mede as funções individualmente — quantas são e qual a maior.

"""

import ast

import numpy as np
import lizard
from radon.raw import analyze
from radon.complexity import cc_visit
from radon.metrics import mi_visit


# =============================================================
# Contador de Funções do Arquivo
# =============================================================
def contar_funcoes(nome: str, codigo: str) -> int | None:
    try:
        ast.parse(codigo)
        resultado = lizard.analyze_file.analyze_source_code(nome, codigo)
    except Exception:
        return None

    return len(resultado.function_list)


# =============================================================
# Calcular 6 Features do ARquivo Atual
# =============================================================
def medir(nome: str, codigo: str) -> dict | None:
    quantidade = contar_funcoes(nome, codigo)

    if quantidade is None or quantidade == 0:
        return None

    try:
        contagem = analyze(codigo)

        blocos = cc_visit(codigo)
        complexidades = [b.complexity for b in blocos] or [0]
        manutenibilidade = mi_visit(codigo, multi=True)
        funcoes = lizard.analyze_file.analyze_source_code(
            nome, codigo).function_list

    except Exception:
        return None

    return {
        "linhas":              contagem.sloc,
        "complexidade_media":  round(float(np.mean(complexidades)), 2),
        "complexidade_maxima": int(max(complexidades)),
        "manutenibilidade":    round(float(manutenibilidade), 1),
        "maior_funcao":        max([f.nloc for f in funcoes], default=0),
        "qtd_funcoes":         len(funcoes),
    }

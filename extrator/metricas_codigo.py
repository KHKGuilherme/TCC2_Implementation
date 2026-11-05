"""
Mede um arquivo .py sem olhar o histórico, em cinco grupos.
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import lizard
from radon.raw import analyze
from radon.complexity import cc_visit
from radon.metrics import mi_visit, h_visit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config


MARCAS_DE_DIVIDA = re.compile(r"#.*\b(TODO|FIXME|XXX|HACK)\b")

CATEGORIAS_RUFF = {
    "ruff_bugbear":      ("B",),
    "ruff_seguranca":    ("S",),
    "ruff_excecao":      ("TRY", "BLE"),
    "ruff_simplificar":  ("SIM",),
    "ruff_refatorar":    ("PLR", "C90"),
    "ruff_argumentos":   ("ARG",),
    "ruff_retorno":      ("RET",),
}

_ruff_disponivel = None


# =============================================================
# Contador de Funções do Arquivo
# -------------------------------------------------------------
# Conta as funções do arquivo, ou None se ele não faz parse
# =============================================================
def contar_funcoes(nome: str, codigo: str) -> int | None:
    try:
        ast.parse(codigo)
        resultado = lizard.analyze_file.analyze_source_code(nome, codigo)
    except Exception:
        return None

    return len(resultado.function_list)


# =============================================================
# Medir Comentarios
# -------------------------------------------------------------
# O que o radon.raw entrega além de sloc
# =============================================================
def medir_comentarios(contagem) -> dict:
    return {
        "comentarios":      int(contagem.comments),
        "linhas_em_branco": int(contagem.blank),
    }


# =============================================================
# Medir Halstead
# -------------------------------------------------------------
# Volume, dificuldade e esforço do vocabulário do código
# =============================================================
def medir_halstead(codigo: str) -> dict:
    try:
        h = h_visit(codigo).total
    except Exception:
        return {c: np.nan for c in ("halstead_volume",
                                    "halstead_dificuldade",
                                    "halstead_esforco", "halstead_bugs")}

    return {
        "halstead_volume":      round(float(h.volume), 2),
        "halstead_dificuldade": round(float(h.difficulty), 2),
        "halstead_esforco":     round(float(h.effort), 2),
        "halstead_bugs":        round(float(h.bugs), 4),
    }


# =============================================================
# Medir Lizard Extra
# -------------------------------------------------------------
# Tokens e parâmetros, que o Lizard já calcula
# =============================================================
def medir_lizard_extra(resultado, funcoes) -> dict:
    parametros = [len(f.parameters) for f in funcoes]

    return {
        "tokens":            int(resultado.token_count),
        "parametros_maximo": int(max(parametros, default=0)),
        "parametros_media":  round(float(np.mean(parametros)), 2)
                             if parametros else 0.0,
    }


BLOCOS_ANINHAVEIS = (ast.If, ast.For, ast.AsyncFor, ast.While,
                     ast.With, ast.AsyncWith, ast.Try)


# =============================================================
# Profundidade de Aninhamento
# -------------------------------------------------------------
# Quantos blocos de controle chegam a ficar um dentro do outro
# =============================================================
def profundidade_de_aninhamento(no: ast.AST, nivel: int = 0) -> int:
    maior = nivel

    for filho in ast.iter_child_nodes(no):
        adiante = nivel + 1 if isinstance(filho, BLOCOS_ANINHAVEIS) else nivel
        maior = max(maior, profundidade_de_aninhamento(filho, adiante))

    return maior


# =============================================================
# Medir AST
# -------------------------------------------------------------
# Estruturas que a árvore sintática revela
# =============================================================
def medir_ast(arvore: ast.AST, codigo: str) -> dict:
    medidas = {
        "aninhamento_maximo": profundidade_de_aninhamento(arvore),
        "todos_fixmes":    len(MARCAS_DE_DIVIDA.findall(codigo)),
        "except_pelado":   0,
        "qtd_try":         0,
        "qtd_imports":     0,
        "imports_estrela": 0,
        "qtd_classes":     0,
        "qtd_decoradores": 0,
        "qtd_global":      0,
    }

    for no in ast.walk(arvore):
        if isinstance(no, ast.Try):
            medidas["qtd_try"] += 1
        elif isinstance(no, ast.ExceptHandler):
            if no.type is None:
                medidas["except_pelado"] += 1
        elif isinstance(no, ast.Import):
            medidas["qtd_imports"] += len(no.names)
        elif isinstance(no, ast.ImportFrom):
            medidas["qtd_imports"] += len(no.names)
            if any(a.name == "*" for a in no.names):
                medidas["imports_estrela"] += 1
        elif isinstance(no, ast.ClassDef):
            medidas["qtd_classes"] += 1
            medidas["qtd_decoradores"] += len(no.decorator_list)
        elif isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            medidas["qtd_decoradores"] += len(no.decorator_list)
        elif isinstance(no, (ast.Global, ast.Nonlocal)):
            medidas["qtd_global"] += 1

    return medidas


# =============================================================
# Ruff Disponivel
# -------------------------------------------------------------
# Procura o ruff uma vez e lembra o resultado
# =============================================================
def ruff_disponivel() -> bool:
    global _ruff_disponivel

    if _ruff_disponivel is None:
        try:
            subprocess.run(["ruff", "--version"], capture_output=True,
                           timeout=30, check=True)
            _ruff_disponivel = True
        except Exception:
            print("\n  AVISO: o ruff não foi encontrado, e as métricas "
                  "dele ficarão vazias.")
            print("         pip install ruff\n")
            _ruff_disponivel = False

    return _ruff_disponivel


# =============================================================
# Medir Ruff
# -------------------------------------------------------------
# Contagens de violação por categoria
# =============================================================
def medir_ruff(nome: str, codigo: str) -> dict:
    colunas = ["ruff_total"] + list(CATEGORIAS_RUFF)
    vazio = {c: np.nan for c in colunas}

    if not ruff_disponivel():
        return vazio

    try:
        processo = subprocess.run(
            ["ruff", "check", "--select", "ALL", "--ignore", "D,ANN,CPY",
             "--output-format", "concise", "--no-cache",
             "--stdin-filename", nome, "-"],
            input=codigo.encode("utf-8", errors="replace"),
            capture_output=True, timeout=30,
        )
    except Exception:
        return vazio

    if processo.returncode not in (0, 1):
        return vazio

    medidas = {c: 0 for c in colunas}
    saida = processo.stdout.decode("utf-8", errors="replace")

    for linha in saida.splitlines():
        partes = linha.split(": ", 1)
        if len(partes) < 2:
            continue

        regra = partes[1].split(" ", 1)[0]
        letras = "".join(c for c in regra if c.isalpha())
        if not letras:
            continue

        medidas["ruff_total"] += 1

        for coluna, prefixos in CATEGORIAS_RUFF.items():
            if letras in prefixos:
                medidas[coluna] += 1
                break

    return medidas


# =============================================================
# Calcular as Features do Arquivo Atual
# -------------------------------------------------------------
# Calcula as métricas de código de um arquivo
# =============================================================
def medir(nome: str, codigo: str) -> dict | None:
    quantidade = contar_funcoes(nome, codigo)

    if quantidade is None or quantidade == 0:
        return None

    try:
        arvore = ast.parse(codigo)
        contagem = analyze(codigo)

        blocos = cc_visit(codigo)
        complexidades = [b.complexity for b in blocos] or [0]
        manutenibilidade = mi_visit(codigo, multi=True)

        resultado = lizard.analyze_file.analyze_source_code(nome, codigo)
        funcoes = resultado.function_list

    except Exception:
        return None

    medidas = {
        "linhas":              contagem.sloc,
        "complexidade_media":  round(float(np.mean(complexidades)), 2),
        "complexidade_maxima": int(max(complexidades)),
        "manutenibilidade":    round(float(manutenibilidade), 1),
        "maior_funcao":        max([f.nloc for f in funcoes], default=0),
        "qtd_funcoes":         len(funcoes),
    }

    if config.MEDIR_COMENTARIOS:
        medidas.update(medir_comentarios(contagem))

    if config.MEDIR_HALSTEAD:
        medidas.update(medir_halstead(codigo))

    if config.MEDIR_LIZARD_EXTRA:
        medidas.update(medir_lizard_extra(resultado, funcoes))

    if config.MEDIR_AST:
        medidas.update(medir_ast(arvore, codigo))

    if config.MEDIR_RUFF:
        medidas.update(medir_ruff(nome, codigo))

    return medidas

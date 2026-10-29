"""
Mede um arquivo .py sem olhar o histórico, em cinco grupos.

  base       -> Radon e Lizard: tamanho, complexidade, funções
  comentario -> Radon raw: comentários e linhas em branco
  halstead   -> Radon: volume, dificuldade, esforço, bugs
  lizard     -> aninhamento, tokens e parâmetros
  ast        -> TODO/FIXME, except pelado, imports, classes
  ruff       -> contagens de violação por categoria

Só o grupo base é obrigatório. Os outros têm chave no config, e
desligar um tira as colunas dele do dataset.

A ordem interna importa por desempenho: o Lizard roda primeiro e
descarta arquivo sem função nenhuma, porque o radon.raw.analyze
trava por minutos em arquivos que são um literal gigante gerado
por máquina, e o Lizard responde "0 funções" em centésimos.
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


# Marcas de dívida técnica autoadmitida. A literatura trata isso
# como sinal próprio: onde o autor escreveu "isto está errado",
# costuma haver defeito depois.
MARCAS_DE_DIVIDA = re.compile(r"#.*\b(TODO|FIXME|XXX|HACK)\b")

# Categorias do ruff que viram coluna. A chave é o nome da coluna,
# o valor são os prefixos de regra que entram nela.
CATEGORIAS_RUFF = {
    "ruff_bugbear":      ("B",),     # padrões que costumam virar bug
    "ruff_seguranca":    ("S",),     # bandit embutido
    "ruff_excecao":      ("TRY", "BLE"),
    "ruff_simplificar":  ("SIM",),
    "ruff_refatorar":    ("PLR", "C90"),
    "ruff_argumentos":   ("ARG",),
    "ruff_retorno":      ("RET",),
}

# Guarda se o ruff já foi procurado, para avisar uma vez só
_ruff_disponivel = None


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


# Nós que abrem um nível de aninhamento
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
            # 'except:' sem tipo engole qualquer erro, inclusive os
            # que não deveria
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

    # 0 = nenhuma violação, 1 = violações encontradas, 2 = o ruff
    # falhou. Sem esta conferência, uma falha dele viraria zero em
    # tudo, e zero quer dizer "arquivo limpo" — o oposto de "não
    # sei". Vazio é preenchido depois com a média do treino.
    if processo.returncode not in (0, 1):
        return vazio

    medidas = {c: 0 for c in colunas}
    saida = processo.stdout.decode("utf-8", errors="replace")

    for linha in saida.splitlines():
        # Formato: caminho:linha:coluna: CÓDIGO mensagem
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
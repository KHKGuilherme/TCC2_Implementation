"""
Métricas de avaliação por commit: ordenação, esforço e significância.
"""

import numpy as np
from scipy import stats
from sklearn.metrics import average_precision_score, roc_auc_score

SEMENTE_DESEMPATE = 42


# =============================================================
# ORDENAÇÃO
# =============================================================


# =============================================================
# Ordem Decrescente
# -------------------------------------------------------------
# Índices da maior para a menor nota, com desempate sorteado fixo
# =============================================================
def ordem_decrescente(nota: np.ndarray) -> np.ndarray:
    sorteio = np.random.default_rng(SEMENTE_DESEMPATE).permutation(len(nota))
    return sorteio[np.argsort(-np.asarray(nota, dtype=float)[sorteio],
                              kind="stable")]


# =============================================================
# AUC
# -------------------------------------------------------------
# Área sob a curva ROC, ou vazio quando só há uma classe
# =============================================================
def auc(rotulo: np.ndarray, nota: np.ndarray) -> float:
    if len(np.unique(rotulo)) < 2:
        return float("nan")

    return float(roc_auc_score(rotulo, nota))


# =============================================================
# Precisao Media
# -------------------------------------------------------------
# Área sob a curva de precisão e revocação
# =============================================================
def precisao_media(rotulo: np.ndarray, nota: np.ndarray) -> float:
    if len(np.unique(rotulo)) < 2:
        return float("nan")

    return float(average_precision_score(rotulo, nota))


# =============================================================
# Precisao no Topo
# -------------------------------------------------------------
# Taxa de defeito na fração de commits com maior nota
# =============================================================
def precisao_no_topo(rotulo: np.ndarray, nota: np.ndarray,
                     fracao: float) -> float:
    quantos = max(1, int(round(fracao * len(rotulo))))
    ordem = ordem_decrescente(nota)[:quantos]
    return float(np.asarray(rotulo)[ordem].mean())


# =============================================================
# ESFORÇO
# =============================================================


# =============================================================
# Curva de Esforco
# -------------------------------------------------------------
# Fração do esforço gasto e dos defeitos achados, commit a commit
# =============================================================
def curva_de_esforco(rotulo: np.ndarray, esforco: np.ndarray,
                     ordem: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rotulo = np.asarray(rotulo, dtype=float)[ordem]
    esforco = np.asarray(esforco, dtype=float)[ordem]

    x = np.concatenate([[0.0], np.cumsum(esforco) / esforco.sum()])
    y = np.concatenate([[0.0], np.cumsum(rotulo) / max(rotulo.sum(), 1.0)])
    return x, y


# =============================================================
# Area
# -------------------------------------------------------------
# Área sob uma curva de esforço, pela regra do trapézio
# =============================================================
def area(x: np.ndarray, y: np.ndarray) -> float:
    return float(np.sum((x[1:] - x[:-1]) * (y[1:] + y[:-1]) / 2.0))


# =============================================================
# Ordens de Referencia
# -------------------------------------------------------------
# A melhor e a pior ordem possíveis para o esforço
# =============================================================
def ordens_de_referencia(rotulo: np.ndarray,
                         esforco: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rotulo = np.asarray(rotulo)
    esforco = np.asarray(esforco, dtype=float)
    melhor = np.lexsort((esforco, -rotulo))
    pior = np.lexsort((-esforco, rotulo))
    return melhor, pior


# =============================================================
# Popt
# -------------------------------------------------------------
# Área da curva de esforço, normalizada entre a pior e a melhor
# =============================================================
def popt(rotulo: np.ndarray, esforco: np.ndarray,
         ordem: np.ndarray) -> float:
    if np.asarray(rotulo).sum() == 0:
        return float("nan")

    melhor, pior = ordens_de_referencia(rotulo, esforco)
    area_modelo = area(*curva_de_esforco(rotulo, esforco, ordem))
    area_melhor = area(*curva_de_esforco(rotulo, esforco, melhor))
    area_pior = area(*curva_de_esforco(rotulo, esforco, pior))

    if area_melhor == area_pior:
        return float("nan")

    return 1.0 - (area_melhor - area_modelo) / (area_melhor - area_pior)


# =============================================================
# Revocacao no Esforco
# -------------------------------------------------------------
# Fração dos defeitos achada ao gastar uma fração do esforço
# =============================================================
def revocacao_no_esforco(rotulo: np.ndarray, esforco: np.ndarray,
                         ordem: np.ndarray, fracao: float) -> float:
    x, y = curva_de_esforco(rotulo, esforco, ordem)
    dentro = np.nonzero(x <= fracao + 1e-12)[0]
    return float(y[dentro[-1]])


# =============================================================
# Esforco na Revocacao
# -------------------------------------------------------------
# Fração do esforço necessária para achar uma fração dos defeitos
# =============================================================
def esforco_na_revocacao(rotulo: np.ndarray, esforco: np.ndarray,
                         ordem: np.ndarray, fracao: float) -> float:
    x, y = curva_de_esforco(rotulo, esforco, ordem)
    atingiu = np.nonzero(y >= fracao - 1e-12)[0]
    return float(x[atingiu[0]]) if len(atingiu) else float("nan")


# =============================================================
# Alarmes Falsos Iniciais
# -------------------------------------------------------------
# Quantos commits limpos aparecem antes do primeiro defeituoso
# =============================================================
def alarmes_falsos_iniciais(rotulo: np.ndarray, ordem: np.ndarray) -> float:
    achados = np.nonzero(np.asarray(rotulo)[ordem] == 1)[0]
    return float(achados[0]) if len(achados) else float("nan")


# =============================================================
# Medir Ordenacao
# -------------------------------------------------------------
# Todas as medidas de um método num repositório
# =============================================================
def medir_ordenacao(rotulo: np.ndarray, nota: np.ndarray,
                    esforco: np.ndarray, fracao_esforco: float,
                    fracoes_topo: tuple[float, ...]) -> dict:
    rotulo = np.asarray(rotulo).astype(int)
    nota = np.asarray(nota, dtype=float)
    esforco = np.maximum(np.asarray(esforco, dtype=float), 1.0)

    por_risco = ordem_decrescente(nota)
    por_densidade = ordem_decrescente(nota / esforco)

    medidas = {
        "commits": int(len(rotulo)),
        "base": float(rotulo.mean()),
        "auc": auc(rotulo, nota),
        "precisao_media": precisao_media(rotulo, nota),
    }

    for fracao in fracoes_topo:
        medidas[f"topo_{int(round(100 * fracao))}"] = precisao_no_topo(
            rotulo, nota, fracao)

    for nome, ordem in (("risco", por_risco), ("densidade", por_densidade)):
        medidas[f"popt_{nome}"] = popt(rotulo, esforco, ordem)
        medidas[f"revocacao_esforco_{nome}"] = revocacao_no_esforco(
            rotulo, esforco, ordem, fracao_esforco)
        medidas[f"esforco_revocacao_{nome}"] = esforco_na_revocacao(
            rotulo, esforco, ordem, fracao_esforco)
        medidas[f"ifa_{nome}"] = alarmes_falsos_iniciais(rotulo, ordem)

    return medidas


# =============================================================
# SIGNIFICÂNCIA
# =============================================================


# =============================================================
# Delta de Cliff
# -------------------------------------------------------------
# Tamanho de efeito: pares em que A supera B, menos o inverso
# =============================================================
def delta_de_cliff(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    diferencas = a[:, None] - b[None, :]
    return float((np.sum(diferencas > 0) - np.sum(diferencas < 0))
                 / diferencas.size)


# =============================================================
# Magnitude do Delta
# -------------------------------------------------------------
# Leitura usual do delta de Cliff (Romano et al., 2006)
# =============================================================
def magnitude_do_delta(delta: float) -> str:
    tamanho = abs(delta)

    if tamanho < 0.147:
        return "desprezível"
    if tamanho < 0.33:
        return "pequeno"
    if tamanho < 0.474:
        return "médio"
    return "grande"


# =============================================================
# Comparar Pareado
# -------------------------------------------------------------
# Wilcoxon pareado entre repositórios, com tamanho de efeito
# =============================================================
def comparar_pareado(a: np.ndarray, b: np.ndarray) -> dict:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    validos = ~(np.isnan(a) | np.isnan(b))
    a, b = a[validos], b[validos]
    diferenca = a - b

    if len(a) < 6 or np.allclose(diferenca, 0.0):
        valor_p = float("nan")
    else:
        valor_p = float(stats.wilcoxon(a, b, zero_method="wilcox",
                                       alternative="two-sided").pvalue)

    delta = delta_de_cliff(a, b) if len(a) else float("nan")

    return {
        "repositorios": int(len(a)),
        "mediana_a": float(np.median(a)) if len(a) else float("nan"),
        "mediana_b": float(np.median(b)) if len(b) else float("nan"),
        "diferenca_mediana": float(np.median(diferenca)) if len(a)
                             else float("nan"),
        "vitorias": int(np.sum(diferenca > 0)),
        "empates": int(np.sum(diferenca == 0)),
        "derrotas": int(np.sum(diferenca < 0)),
        "valor_p": valor_p,
        "delta_cliff": delta,
        "magnitude": magnitude_do_delta(delta) if len(a) else "",
    }


# =============================================================
# Corrigir Holm
# -------------------------------------------------------------
# Ajusta vários valores p pelo método de Holm
# =============================================================
def corrigir_holm(valores_p: list[float]) -> list[float]:
    valores = np.asarray(valores_p, dtype=float)
    corrigidos = np.full(len(valores), np.nan)
    validos = np.nonzero(~np.isnan(valores))[0]
    ordem = validos[np.argsort(valores[validos])]
    maior = 0.0

    for posicao, indice in enumerate(ordem):
        ajustado = min(1.0, (len(ordem) - posicao) * valores[indice])
        maior = max(maior, ajustado)
        corrigidos[indice] = maior

    return corrigidos.tolist()

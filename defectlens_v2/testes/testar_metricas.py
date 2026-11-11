"""
Confere as métricas de avaliação em exemplos pequenos, calculados à mão.

CMD -> python defectlens_v2/testes/testar_metricas.py
"""

import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "frente1_treinamento"))

import analisar
import metricas_avaliacao as medidas

ROTULO = np.array([1, 0, 1, 0])
ESFORCO = np.array([10.0, 10.0, 30.0, 50.0])


# =============================================================
# Testar Curva de Esforco
# -------------------------------------------------------------
# Revocação, esforço e alarmes falsos numa ordem conhecida
# =============================================================
def testar_curva_de_esforco() -> None:
    ordem = np.array([0, 1, 2, 3])

    assert medidas.revocacao_no_esforco(ROTULO, ESFORCO, ordem, 0.20) == 0.5
    assert medidas.revocacao_no_esforco(ROTULO, ESFORCO, ordem, 0.05) == 0.0
    assert medidas.esforco_na_revocacao(ROTULO, ESFORCO, ordem, 0.5) == 0.1
    assert medidas.esforco_na_revocacao(ROTULO, ESFORCO, ordem, 1.0) == 0.5
    assert medidas.alarmes_falsos_iniciais(ROTULO, ordem) == 0
    assert medidas.alarmes_falsos_iniciais(ROTULO, np.array([1, 3, 0, 2])) == 2


# =============================================================
# Testar Popt
# -------------------------------------------------------------
# A ordem ideal vale 1, a pior vale 0 e as demais ficam no meio
# =============================================================
def testar_popt() -> None:
    melhor, pior = medidas.ordens_de_referencia(ROTULO, ESFORCO)

    assert list(melhor) == [0, 2, 1, 3]
    assert list(pior) == [3, 1, 2, 0]
    assert abs(medidas.popt(ROTULO, ESFORCO, melhor) - 1.0) < 1e-12
    assert abs(medidas.popt(ROTULO, ESFORCO, pior)) < 1e-12
    assert 0 < medidas.popt(ROTULO, ESFORCO, np.array([0, 1, 2, 3])) < 1


# =============================================================
# Testar Medir Ordenacao
# -------------------------------------------------------------
# Nota perfeita dá AUC 1; menor primeiro acha defeito pequeno cedo
# =============================================================
def testar_medir_ordenacao() -> None:
    perfeita = medidas.medir_ordenacao(ROTULO, np.array([0.9, 0.1, 0.8, 0.2]),
                                       ESFORCO, 0.2, (0.5,))

    assert perfeita["auc"] == 1.0
    assert perfeita["topo_50"] == 1.0
    assert perfeita["ifa_risco"] == 0
    assert perfeita["commits"] == 4 and perfeita["base"] == 0.5

    menor = medidas.medir_ordenacao(ROTULO, -ESFORCO, ESFORCO, 0.2, (0.5,))
    assert menor["revocacao_esforco_risco"] in (0.0, 0.5)


# =============================================================
# Testar Significancia
# -------------------------------------------------------------
# Delta de Cliff, comparação pareada e correção de Holm
# =============================================================
def testar_significancia() -> None:
    assert medidas.delta_de_cliff([3, 4, 5], [0, 1, 2]) == 1.0
    assert medidas.delta_de_cliff([0, 1, 2], [3, 4, 5]) == -1.0
    assert medidas.delta_de_cliff([1, 2], [1, 2]) == 0.0
    assert medidas.magnitude_do_delta(0.1) == "desprezível"
    assert medidas.magnitude_do_delta(-0.4) == "médio"

    a = np.linspace(0.70, 0.90, 12)
    comparacao = medidas.comparar_pareado(a, a - 0.02)
    assert comparacao["vitorias"] == 12 and comparacao["derrotas"] == 0
    assert comparacao["valor_p"] < 0.01
    assert abs(comparacao["diferenca_mediana"] - 0.02) < 1e-9

    ajustados = medidas.corrigir_holm([0.01, 0.04, 0.03, float("nan")])
    assert np.allclose(ajustados[:3], [0.03, 0.06, 0.06])
    assert np.isnan(ajustados[3])


# =============================================================
# Testar Calibracao
# -------------------------------------------------------------
# A correção de prevalência leva a média para a taxa pedida
# =============================================================
def testar_calibracao() -> None:
    igual = analisar.corrigir_prevalencia(np.array([0.2, 0.7]), 0.4, 0.4)
    assert np.allclose(igual, [0.2, 0.7])

    menor = analisar.corrigir_prevalencia(np.array([0.5]), 0.5, 0.1)
    assert abs(menor[0] - 0.1) < 1e-9


if __name__ == "__main__":
    testes = [testar_curva_de_esforco, testar_popt, testar_medir_ordenacao,
              testar_significancia, testar_calibracao]

    for teste in testes:
        teste()
        print(f"  ok  {teste.__name__}")

    print(f"\n  {len(testes)} testes passaram.")

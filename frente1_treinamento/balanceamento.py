import sys
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

import config
from extrator import features


# =============================================================
# Reduzir
# -------------------------------------------------------------
# Sorteia e descarta da classe maior
# =============================================================
def reduzir(treino: pd.DataFrame, sorteio: int) -> pd.DataFrame:
    alvo = treino[features.COLUNA_ALVO]
    menor = int(alvo.value_counts().min())

    partes = [grupo.sample(n=menor, random_state=sorteio)
              for _, grupo in treino.groupby(alvo)]

    return pd.concat(partes).sample(frac=1, random_state=sorteio)


# =============================================================
# Replicar
# -------------------------------------------------------------
# Sorteia com reposição da classe menor
# =============================================================
def replicar(treino: pd.DataFrame, sorteio: int) -> pd.DataFrame:
    alvo = treino[features.COLUNA_ALVO]
    maior = int(alvo.value_counts().max())

    partes = [grupo.sample(n=maior, replace=len(grupo) < maior,
                           random_state=sorteio)
              for _, grupo in treino.groupby(alvo)]

    return pd.concat(partes).sample(frac=1, random_state=sorteio)


ESTRATEGIAS = {
    "reduzir":  reduzir,
    "replicar": replicar,
}


# =============================================================
# Balancear
# -------------------------------------------------------------
# Aplica a estratégia configurada, só no treino
# =============================================================
def balancear(treino: pd.DataFrame) -> pd.DataFrame:
    if not config.BALANCEAR_TREINO:
        return treino

    nome = config.ESTRATEGIA_BALANCEAMENTO

    # Para o programa em vez de cair num padrão silencioso: um erro
    # de digitação aqui mudaria a composição do treino sem aviso
    if nome not in ESTRATEGIAS:
        raise SystemExit(
            f"ESTRATEGIA_BALANCEAMENTO = {nome!r} não existe.\n"
            f"Disponíveis: {', '.join(ESTRATEGIAS)}"
        )

    antes = treino[features.COLUNA_ALVO]

    print("\n" + "-" * 70)
    print("BALANCEAMENTO DO TREINO")
    print("-" * 70)
    print(f"\n  antes : {len(treino)} linhas, "
          f"{int(antes.sum())} defeituosos ({100 * antes.mean():.1f}%)")

    equilibrado = ESTRATEGIAS[nome](treino, config.SEMENTE).reset_index(
        drop=True)

    depois = equilibrado[features.COLUNA_ALVO]
    print(f"  depois: {len(equilibrado)} linhas, "
          f"{int(depois.sum())} defeituosos ({100 * depois.mean():.1f}%)")
    print(f"  estratégia: {nome}")

    if nome == "reduzir":
        print(f"  {len(treino) - len(equilibrado)} linhas descartadas")
    else:
        repetidas = len(equilibrado) - equilibrado.drop_duplicates(
            subset=["repositorio", "arquivo", "commit"]).shape[0]
        print(f"  {repetidas} linhas repetidas")
        print("  Linha repetida conta mais de uma vez no treino, então o "
              "modelo fica mais confiante do que os dados sustentam.")

    print("  O conjunto reservado NÃO foi tocado: ele tem de manter a "
          "proporção real.")

    return equilibrado


# =============================================================
# Descrever
# -------------------------------------------------------------
# Texto do balanceamento em uso, para aparecer na saída
# =============================================================
def descrever() -> str:
    if not config.BALANCEAR_TREINO:
        return "desligado — o treino mantém a proporção original"

    return f"{config.ESTRATEGIA_BALANCEAMENTO}, só no treino"
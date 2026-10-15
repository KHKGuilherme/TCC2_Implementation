"""
CMD -> Execuç]o: python frente1_treinamento/principal.py
"""

import sys
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI))

import config
import montar_dataset
import treinar as treinamento
from extrator import features


# =============================================================
# Dataset Utilizavel
# -------------------------------------------------------------
#  Verifica se possui CSV
# =============================================================
def dataset_utilizavel() -> bool:
    if not config.ARQUIVO_DATASET.exists():
        print(f"  Dataset não encontrado em {config.ARQUIVO_DATASET}")
        return False

    try:
        dados = pd.read_csv(config.ARQUIVO_DATASET)
    except Exception as erro:
        print(f"  Dataset existe mas não pôde ser lido: {erro}")
        return False

    if dados.empty:
        print("  Dataset existe mas está vazio.")
        return False

    faltando = [c for c in features.COLUNAS_CSV if c not in dados.columns]
    if faltando:
        print(f"  Dataset existe mas faltam colunas: {faltando}")
        return False

    print(f"  Dataset encontrado: {config.ARQUIVO_DATASET} "
          f"({len(dados)} linhas, "
          f"{dados.repositorio.nunique()} repositórios)")

    # Um dataset legível não quer dizer um dataset completo. Se
    # algum repositório falhou na montagem anterior, ele não tem
    # CSV, e sem esta conferência nunca mais seria tentado.
    pendentes = montar_dataset.repositorios_pendentes()

    if pendentes and config.EXIGIR_TODOS_OS_REPOSITORIOS:
        print(f"  Faltam {len(pendentes)} repositórios: "
              f"{', '.join(pendentes)}")
        print("  Montando só eles. Os já prontos são reaproveitados.")
        return False

    if pendentes:
        print(f"  Faltam {len(pendentes)} repositórios, mas "
              f"EXIGIR_TODOS_OS_REPOSITORIOS está desligado: "
              f"{', '.join(pendentes)}")

    return True


# =============================================================
# Preparar Dataset
# -------------------------------------------------------------
#  Montagem / Carregamento de Dataset
# =============================================================
def preparar_dataset() -> None:
    if config.FORCAR_MONTAGEM:
        print("  FORCAR_MONTAGEM está ligado: remontando o dataset.")
        montar_dataset.montar()
        return

    if dataset_utilizavel():
        print("  Usando o dataset existente.")
        return

    print("  Montando o dataset.\n")
    montar_dataset.montar()


# =============================================================
# Main
# =============================================================
def main() -> None:
    """Prepara o dataset e treina o modelo."""
    config.conferir_local()

    print("=" * 66)
    print("FRENTE 1 — TREINAMENTO DO MODELO")
    print("=" * 66)
    print()

    preparar_dataset()

    print()
    treinamento.treinar()


if __name__ == "__main__":
    main()
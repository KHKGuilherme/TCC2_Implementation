"""
Frente 1, passo 3: validação deixando um repositório de fora por vez (retomável).
"""

import os
import sys
import time
from pathlib import Path

import pandas as pd
from joblib import Parallel, delayed

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from frente1_treinamento import modelo  # noqa: E402


# =============================================================
# Validar Repositorio
# -------------------------------------------------------------
# Treina sem o repositório, prevê todos os retratos dele e grava
# =============================================================
def validar_repositorio(nome: str, retratos: pd.DataFrame) -> str:
    destino = config.PASTA_VALIDACAO / f"{nome}.csv.gz"
    if destino.exists():
        return f"{nome}: pronto"
    inicio = time.time()
    treino = modelo.parte_de_treino(retratos[retratos["repositorio"] != nome])
    alvo = retratos[retratos["repositorio"] == nome]
    rotulos = [c for c in alvo.columns if c.startswith("latente_") or c.startswith("conserto_")]
    saida = alvo[["repositorio", "data", "id", "arquivo"] + rotulos + modelo.BASELINES].copy()
    y = treino[config.ROTULO].values.astype(int)
    for variante in modelo.VARIANTES:
        estimador = modelo.treinar(variante, treino)
        bruta = modelo.prever(estimador, variante, alvo)
        saida[f"p_{variante}"] = bruta
        if variante in modelo.CALIBRADAS:
            calibradores = modelo.ajustar_calibradores(modelo.fora_da_dobra(variante, treino), y)
            saida[f"p_{variante}_platt"] = modelo.calibrar(calibradores, "platt", bruta)
            saida[f"p_{variante}_isotonica"] = modelo.calibrar(calibradores, "isotonica", bruta)
    saida["taxa_treino"] = y.mean()
    temporario = destino.with_name(destino.name + ".tmp")
    saida.to_csv(temporario, index=False, compression="gzip", float_format="%.5g")
    os.replace(temporario, destino)
    return f"{nome}: {len(alvo)} retratos previstos, treino {len(treino)}, {time.time() - inicio:.0f} s"


if __name__ == "__main__":
    config.PASTA_VALIDACAO.mkdir(parents=True, exist_ok=True)
    retratos = modelo.ler_retratos()
    nomes = sys.argv[1:] or sorted(retratos["repositorio"].unique())
    print(f"{len(retratos)} retratos, {retratos['repositorio'].nunique()} repositórios", flush=True)
    resultados = Parallel(n_jobs=config.PROCESSOS)(
        delayed(validar_repositorio)(nome, retratos) for nome in nomes)
    print("\n".join(resultados), flush=True)

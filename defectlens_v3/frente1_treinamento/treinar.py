"""
Frente 1, passo 5: treina o modelo final em todos os repositórios, calibra e grava o pacote.
"""

import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.inspection import permutation_importance

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from frente1_treinamento import avaliar, modelo  # noqa: E402


# =============================================================
# Escolher Limiar
# -------------------------------------------------------------
# Limiar de maior F1 nas previsões calibradas feitas fora da dobra
# =============================================================
def escolher_limiar(p: np.ndarray, y: np.ndarray) -> dict:
    tabela = pd.DataFrame({"p": p, "y": y})
    return avaliar.limiar_de_fora(tabela, "p", "y")


# =============================================================
# Medir Importancia
# -------------------------------------------------------------
# Importância por permutação (queda de AUC) em uma amostra do treino
# =============================================================
def medir_importancia(estimador, treino: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    amostra = treino.sample(min(40000, len(treino)), random_state=config.SEMENTE)
    resultado = permutation_importance(
        estimador, amostra[colunas].values, amostra[config.ROTULO].values.astype(int),
        scoring="roc_auc", n_repeats=3, random_state=config.SEMENTE, n_jobs=config.PROCESSOS)
    tabela = pd.DataFrame({"feature": colunas, "queda_auc": resultado.importances_mean})
    return tabela.sort_values("queda_auc", ascending=False)


# =============================================================
# Treinar Final
# -------------------------------------------------------------
# Treina, calibra fora da dobra, escolhe o limiar e grava modelo e resumo
# =============================================================
def treinar_final() -> None:
    inicio = time.time()
    config.PASTA_MODELOS.mkdir(parents=True, exist_ok=True)
    treino = modelo.parte_de_treino(modelo.ler_retratos())
    variante = config.VARIANTE_FINAL
    colunas = modelo.CONJUNTOS[modelo.VARIANTES[variante][0]]
    y = treino[config.ROTULO].values.astype(int)
    fora = modelo.fora_da_dobra(variante, treino, dobras=5)
    calibradores = modelo.ajustar_calibradores(fora, y)
    calibrada = modelo.calibrar(calibradores, config.CALIBRACAO_FINAL, fora)
    limiares = escolher_limiar(calibrada, y)
    estimador = modelo.treinar(variante, treino)
    importancia = medir_importancia(estimador, treino, colunas)
    importancia.to_csv(config.PASTA_RESULTADOS / "importancia.csv", index=False)

    avaliacao = json.loads(avaliar.ARQUIVO_SAIDA.read_text(encoding="utf-8")) \
        if avaliar.ARQUIVO_SAIDA.exists() else {}
    comparacao = {l["metodo"]: l for l in avaliacao.get("comparacao", [])}
    porcentagem = {l["estimador"]: l for l in avaliacao.get("porcentagem", [])}
    resumo = {
        "versao": "v3",
        "pergunta": "defeito latente no estado atual do arquivo",
        "rotulo": config.ROTULO,
        "variante": variante,
        "calibracao": config.CALIBRACAO_FINAL,
        "features": colunas,
        "limiar": limiares[config.REGRA_LIMIAR],
        "regra_limiar": config.REGRA_LIMIAR,
        "limiares": limiares,
        "treino": {"retratos": int(len(treino)), "repositorios": int(treino["repositorio"].nunique()),
                   "taxa_base": float(y.mean()),
                   "datas": [treino["data"].min(), treino["data"].max()]},
        "validacao": {
            "auc_mediano": comparacao.get(f"p_{variante}", {}).get("auc_mediano"),
            "auc_melhor_baseline": max((l["auc_mediano"] for m, l in comparacao.items()
                                        if not m.startswith("p_")), default=None),
            "topo_10": comparacao.get(f"p_{variante}", {}).get("topo_10"),
            "taxa_base": avaliacao.get("taxa_base"),
            "repositorios": avaliacao.get("repositorios"),
            "erro_porcentagem_pp": porcentagem.get(f"soma_{config.CALIBRACAO_FINAL}", {}).get(
                "erro_absoluto_medio_pp"),
            "erro_porcentagem_mediano_pp": porcentagem.get(
                f"soma_{config.CALIBRACAO_FINAL}", {}).get("erro_absoluto_mediano_pp"),
            "limiar": avaliacao.get("limiares", {}).get(config.REGRA_LIMIAR),
        },
        "importancia": importancia.head(12).round(5).to_dict("records"),
        "treinado_em": time.strftime("%Y-%m-%d %H:%M"),
        "sklearn": sklearn.__version__,
    }
    joblib.dump({"estimador": estimador, "calibradores": calibradores, "resumo": resumo},
                config.ARQUIVO_MODELO, compress=3)
    config.ARQUIVO_RESUMO.write_text(json.dumps(resumo, indent=1, ensure_ascii=False),
                                     encoding="utf-8")
    print(f"modelo gravado em {config.ARQUIVO_MODELO} ({time.time() - inicio:.0f} s)")
    print(f"treino: {resumo['treino']}  limiares: {limiares}")
    print(importancia.head(12).round(4).to_string(index=False))


if __name__ == "__main__":
    treinar_final()

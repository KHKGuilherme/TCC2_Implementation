import json
import sys
import time

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.inspection import permutation_importance

from treino import config
from treino import avaliar, manifesto, modelo


def escolher_limiar(p: np.ndarray, y: np.ndarray) -> dict:
    tabela = pd.DataFrame({"p": p, "y": y})
    return avaliar.limiar_de_fora(tabela, "p", "y")


def medir_importancia(estimador, treino: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    amostra = treino.sample(min(40000, len(treino)), random_state=config.SEMENTE)
    resultado = permutation_importance(
        estimador, amostra[colunas].values, amostra[config.ROTULO].values.astype(int),
        scoring="roc_auc", n_repeats=3, random_state=config.SEMENTE, n_jobs=config.PROCESSOS)
    tabela = pd.DataFrame({"feature": colunas, "queda_auc": resultado.importances_mean})
    return tabela.sort_values("queda_auc", ascending=False)


def treinar_final() -> None:
    inicio = time.time()
    config.PASTA_MODELO.mkdir(parents=True, exist_ok=True)
    config.PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
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
    joblib.dump({"estimador": estimador, "calibradores": calibradores},
                config.ARQUIVO_MODELO, compress=3)
    manifesto.gravar(resumo)
    print(f"modelo gravado em {config.ARQUIVO_MODELO} ({time.time() - inicio:.0f} s)")
    print(f"treino: {resumo['treino']}  limiares: {limiares}")
    print(importancia.head(12).round(4).to_string(index=False))


def principal(argumentos: list[str]) -> None:
    treinar_final()


if __name__ == "__main__":
    principal(sys.argv[1:])

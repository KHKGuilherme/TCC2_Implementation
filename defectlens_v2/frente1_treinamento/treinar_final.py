"""
Frente 1, etapa 5 — treina o modelo final em todos os repositórios e grava,
junto com ele, tudo o que a Frente 2 precisa para explicar a nota:
calibração, faixas de risco, distribuição de referência e medianas.

CMD -> python defectlens_v2/frente1_treinamento/treinar_final.py
       grava modelos/modelo_v2.joblib e modelos/resumo_modelo.json
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import analisar
import config
import modelos
from extrator import features

VERSAO = "2.0"

QUANTIS = np.linspace(0, 1, 101)

FORMAS_CALIBRAVEIS = ("platt", "isotonica")


# =============================================================
# CALIBRAÇÃO
# =============================================================


# =============================================================
# Escolher Forma
# -------------------------------------------------------------
# A forma de calibrar com menor Brier em projeto nunca visto
# =============================================================
def escolher_forma() -> tuple[str, dict]:
    medidas = pd.read_csv(config.PASTA_RESULTADOS / "calibracao.csv")
    candidatas = medidas[medidas["forma"].isin(FORMAS_CALIBRAVEIS)]
    melhor = candidatas.sort_values("brier").iloc[0]
    medida = {"brier": round(float(melhor["brier"]), 4),
              "erro_calibracao": round(float(melhor["erro_calibracao"]), 4),
              "commits": int(melhor["commits"])}
    return melhor["forma"], medida


# =============================================================
# Ajustar Calibrador
# -------------------------------------------------------------
# Ajusta o calibrador nas notas fora do treino, de proporção natural
# =============================================================
def ajustar_calibrador(forma: str, nota: np.ndarray,
                       rotulo: np.ndarray) -> dict:
    if forma == "platt":
        logistica = LogisticRegression(C=1e6, max_iter=1000).fit(
            analisar.logito(nota).reshape(-1, 1), rotulo)
        return {"forma": "platt",
                "inclinacao": float(logistica.coef_[0][0]),
                "intercepto": float(logistica.intercept_[0])}

    isotonica = IsotonicRegression(out_of_bounds="clip", y_min=0,
                                   y_max=1).fit(nota, rotulo)
    return {"forma": "isotonica",
            "x": isotonica.X_thresholds_.tolist(),
            "y": isotonica.y_thresholds_.tolist()}


# =============================================================
# Aplicar Calibrador
# -------------------------------------------------------------
# Converte a nota bruta em chance estimada na proporção natural
# =============================================================
def aplicar_calibrador(calibrador: dict, nota: np.ndarray) -> np.ndarray:
    nota = np.asarray(nota, dtype=float)

    if calibrador["forma"] == "platt":
        z = (calibrador["inclinacao"] * analisar.logito(nota)
             + calibrador["intercepto"])
        return 1.0 / (1.0 + np.exp(-z))

    return np.interp(nota, calibrador["x"], calibrador["y"])


# =============================================================
# REFERÊNCIAS PARA A FRENTE 2
# =============================================================


# =============================================================
# Montar Faixas
# -------------------------------------------------------------
# Os cortes de nota de cada faixa e a taxa de defeito medida nela
# =============================================================
def montar_faixas() -> list[dict]:
    medidas = pd.read_csv(config.PASTA_RESULTADOS / "faixas_de_risco.csv")
    naturais = medidas[medidas["cenario"] == "natural"]

    return [{"faixa": linha["faixa"],
             "nota_de": round(float(linha["nota_de"]), 6),
             "quantil_de": float(linha["quantil_de"]),
             "taxa_de_defeito": round(float(linha["taxa_de_defeito"]), 4),
             "taxa_geral": round(float(linha["taxa_geral"]), 4),
             "parcela_dos_defeitos": round(
                 float(linha["parcela_dos_defeitos"]), 4)}
            for _, linha in naturais.iterrows()]


# =============================================================
# Resumir Importancia
# -------------------------------------------------------------
# Queda mediana do AUC ao embaralhar cada feature, entre repositórios
# =============================================================
def resumir_importancia() -> list[dict]:
    caminho = config.PASTA_RESULTADOS / "permutacao.csv"
    if not caminho.exists():
        return []

    permutacao = pd.read_csv(caminho)
    if permutacao.empty:
        return []

    mediana = (permutacao.groupby("feature")["queda_auc"].median()
               .sort_values(ascending=False))

    return [{"feature": nome,
             "nome": (features.nome_legivel(nome)
                      if not nome.startswith("grupo:")
                      else nome.replace("grupo:", "grupo ")),
             "grupo": (nome.replace("grupo:", "")
                       if nome.startswith("grupo:")
                       else features.grupo_da_feature(nome)),
             "queda_auc": round(float(queda), 5)}
            for nome, queda in mediana.items()]


# =============================================================
# Ler Metricas
# -------------------------------------------------------------
# Os números de projeto nunca visto que o site mostra
# =============================================================
def ler_metricas() -> dict:
    resumo = json.loads((config.PASTA_RESULTADOS / "resumo.json")
                        .read_text(encoding="utf-8"))
    escolhidos = (config.METODO_PRINCIPAL, config.METODO_REFERENCIA,
                  config.METODO_ORIGINAL, "aleatorio", "menor_primeiro")

    return {cenario: {metodo: linhas[metodo] for metodo in escolhidos
                      if metodo in linhas}
            for cenario, linhas in resumo["metodos"].items()}


# =============================================================
# TREINO
# =============================================================


# =============================================================
# Treinar Final
# -------------------------------------------------------------
# Treina, calibra e grava o pacote do modelo
# =============================================================
def treinar_final() -> dict:
    retratos = pd.read_csv(config.ARQUIVO_RETRATOS)
    commits = pd.read_csv(config.ARQUIVO_COMMITS)
    metodo = config.METODO_PRINCIPAL
    definicao = modelos.TREINADOS[metodo]
    colunas = definicao["colunas"]

    estimador = modelos.treinar(metodo, retratos, commits)
    treino = modelos.linhas_de_treino(retratos, definicao)

    previsoes = analisar.ler_previsoes()
    natural = analisar.filtrar_cenario(previsoes, "natural")
    nota_natural = natural[f"nota_{metodo}"].to_numpy(dtype=float)
    rotulo_natural = natural["defeituoso"].to_numpy(dtype=int)

    forma, medida_da_forma = escolher_forma()
    calibrador = ajustar_calibrador(forma, nota_natural, rotulo_natural)

    resumo = {
        "nome": definicao["nome"],
        "versao": VERSAO,
        "treinado_em": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "algoritmo": "HistGradientBoostingClassifier (scikit-learn)",
        "parametros": config.PARAMETROS_MODELO,
        "features": colunas,
        "unidade": "retrato (commit, arquivo .py); nota do commit = máxima",
        "repositorios_treino": int(treino["repositorio"].nunique()),
        "retratos_treino": int(len(treino)),
        "commits_treino": int(treino.drop_duplicates(features.CHAVES)
                              .shape[0]),
        "dominio": {
            "maximo_linhas": config.MAXIMO_LINHAS_COMMIT,
            "maximo_arquivos": config.MAXIMO_ARQUIVOS_COMMIT,
            "minimo_adicionadas": config.MINIMO_ADICIONADAS,
        },
        "calibrador": calibrador,
        "calibracao_medida": medida_da_forma,
        "faixas": montar_faixas(),
        "referencia": {
            "descricao": "notas em projeto nunca visto, partições test e "
                         "val do Defectors (proporção original)",
            "commits": int(len(nota_natural)),
            "taxa_de_defeito": round(float(rotulo_natural.mean()), 4),
            "quantis": np.quantile(nota_natural, QUANTIS).round(6).tolist(),
        },
        "medianas": {c: float(treino[c].median()) for c in colunas},
        "quantis_das_features": {
            c: np.nanquantile(treino[c].to_numpy(dtype=float), QUANTIS)
                 .round(6).tolist() for c in colunas},
        "importancia": resumir_importancia(),
        "metricas": ler_metricas(),
    }

    config.PASTA_MODELOS.mkdir(parents=True, exist_ok=True)
    joblib.dump({"modelo": estimador, **resumo}, config.ARQUIVO_MODELO,
                compress=config.COMPRESSAO_DO_MODELO)
    config.ARQUIVO_RESUMO_MODELO.write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")

    return resumo


if __name__ == "__main__":
    final = treinar_final()
    tamanho = config.ARQUIVO_MODELO.stat().st_size / 1024
    print(f"\n  {final['nome']}: {len(final['features'])} features, "
          f"{final['retratos_treino']} retratos de "
          f"{final['commits_treino']} commits, "
          f"{final['repositorios_treino']} repositórios")
    print(f"  calibrador: {final['calibrador']['forma']}  "
          f"{final['calibracao_medida']}")
    print(f"  faixas: {final['faixas']}")
    print(f"  -> {config.ARQUIVO_MODELO} ({tamanho:.0f} KB)")

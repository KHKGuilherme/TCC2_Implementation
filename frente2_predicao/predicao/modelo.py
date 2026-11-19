import hashlib
import json
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import sklearn

from predicao import config
from predicao.erros import ErroDeAnalise
from predicao.medidas import metricas_historico

VERSAO_DO_CONTRATO = 1

CAMPOS_PUBLICOS = ("versao", "pergunta", "rotulo", "variante", "calibracao", "features", "limiar",
                   "regra_limiar", "treino", "validacao", "importancia", "treinado_em")


def versao_principal(versao: str) -> tuple[str, str]:
    partes = versao.split(".")
    return partes[0], partes[1] if len(partes) > 1 else ""


def conferir_manifesto(manifesto: dict, arquivo_modelo: Path) -> None:
    if manifesto.get("contrato") != VERSAO_DO_CONTRATO:
        raise ErroDeAnalise("O manifesto do modelo segue uma versão de contrato que esta "
                            "frente não conhece.")
    desconhecidas = [n for n in manifesto["features"] if n not in metricas_historico.FEATURES]
    if desconhecidas:
        raise ErroDeAnalise("O modelo pede medidas que esta frente não calcula: "
                            + ", ".join(desconhecidas))
    if hashlib.sha256(arquivo_modelo.read_bytes()).hexdigest() != manifesto["modelo"]["sha256"]:
        raise ErroDeAnalise("O arquivo do modelo não corresponde ao manifesto.")
    if versao_principal(manifesto["sklearn"]) != versao_principal(sklearn.__version__):
        raise ErroDeAnalise(f"O modelo foi treinado com scikit-learn {manifesto['sklearn']}, "
                            f"mas esta frente usa {sklearn.__version__}.")


@lru_cache(maxsize=1)
def carregar() -> dict:
    if not config.ARQUIVO_MANIFESTO.exists():
        raise ErroDeAnalise("Modelo não encontrado. Treine na Frente 1 e publique a pasta modelo.")
    manifesto = json.loads(config.ARQUIVO_MANIFESTO.read_text(encoding="utf-8"))
    arquivo = config.PASTA_MODELO / manifesto["modelo"]["arquivo"]
    if not arquivo.exists():
        raise ErroDeAnalise(f"O manifesto aponta para {arquivo.name}, que não existe.")
    conferir_manifesto(manifesto, arquivo)
    pacote = joblib.load(arquivo)
    return {"estimador": pacote["estimador"], "calibradores": pacote["calibradores"],
            "manifesto": manifesto}


def descrever() -> dict:
    manifesto = carregar()["manifesto"]
    return {campo: manifesto.get(campo) for campo in CAMPOS_PUBLICOS}


def prever(medidas) -> tuple[np.ndarray, np.ndarray]:
    pacote = carregar()
    manifesto = pacote["manifesto"]
    bruta = pacote["estimador"].predict_proba(medidas[manifesto["features"]].values)[:, 1]
    tipo = manifesto["calibracao"]
    if tipo == "platt":
        recortada = np.clip(bruta, 1e-6, 1 - 1e-6)
        logito = np.log(recortada / (1 - recortada)).reshape(-1, 1)
        chance = pacote["calibradores"]["platt"].predict_proba(logito)[:, 1]
    elif tipo == "isotonica":
        chance = pacote["calibradores"]["isotonica"].predict(bruta)
    else:
        chance = bruta
    return bruta, chance

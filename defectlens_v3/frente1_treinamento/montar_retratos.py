"""
Frente 1, passo 2: monta os intervalos de defeito latente e os retratos (arquivo, instante T).
"""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from extrator import metricas_historico  # noqa: E402


# =============================================================
# LEITURA
# =============================================================

# =============================================================
# Ler Causadores
# -------------------------------------------------------------
# Pares (commit, arquivo) que o Defectors marcou como causadores de defeito
# =============================================================
def ler_causadores() -> pd.DataFrame:
    dados = pd.read_csv(config.DATASET_ORIGINAL,
                        usecols=["repositorio", "arquivo", "commit", "defeituoso"])
    return dados[dados["defeituoso"] == 1].drop(columns="defeituoso")


# =============================================================
# Ler Identificado
# -------------------------------------------------------------
# Lê o histórico gravado de um repositório, já com a identidade dos arquivos
# =============================================================
def ler_identificado(nome: str) -> pd.DataFrame:
    historico = pd.read_csv(config.PASTA_HISTORICO / f"{nome}.csv.gz", keep_default_na=False)
    return metricas_historico.identificar(historico)


# =============================================================
# RÓTULO
# =============================================================

# =============================================================
# Montar Intervalos
# -------------------------------------------------------------
# Para cada par causador, acha o primeiro conserto posterior no mesmo arquivo
# =============================================================
def montar_intervalos(nome: str, identificado: pd.DataFrame,
                      causadores: pd.DataFrame) -> pd.DataFrame:
    fim_dados = int(pd.Timestamp(config.FIM_DEFECTORS).timestamp())
    pares = causadores[causadores["repositorio"] == nome]
    achados = pares.merge(identificado[["hash", "arquivo", "id", "ordem", "instante"]],
                          left_on=["commit", "arquivo"], right_on=["hash", "arquivo"])
    consertos = identificado[identificado["conserto"] == 1].sort_values("ordem")
    por_id = {i: (g["ordem"].values, g["instante"].values) for i, g in consertos.groupby("id")}
    fins = np.full(len(achados), np.nan)
    for k, (identidade, ordem) in enumerate(zip(achados["id"].values, achados["ordem"].values)):
        if identidade in por_id:
            ordens, instantes = por_id[identidade]
            posicao = np.searchsorted(ordens, ordem, side="right")
            if posicao < len(ordens):
                fins[k] = instantes[posicao]
    saida = pd.DataFrame({"repositorio": nome, "id": achados["id"].values,
                          "arquivo": achados["arquivo"].values, "commit": achados["commit"].values,
                          "inicio": achados["instante"].values, "fim": fins})
    saida["situacao"] = np.where(saida["fim"].isna(), "sem_conserto",
                                 np.where(saida["fim"] > fim_dados, "conserto_tardio", "ok"))
    saida.attrs["pares"] = len(pares)
    return saida


# =============================================================
# Rotular
# -------------------------------------------------------------
# Marca arquivos com defeito introduzido até T e consertado depois, dentro do horizonte
# =============================================================
def rotular(retrato: pd.DataFrame, intervalos: pd.DataFrame, instante: int,
            horizonte_dias: int) -> np.ndarray:
    fim_dados = int(pd.Timestamp(config.FIM_DEFECTORS).timestamp())
    limite = instante + horizonte_dias * 86400 if horizonte_dias else fim_dados
    if limite > fim_dados:
        return np.full(len(retrato), np.nan)
    validos = intervalos[intervalos["situacao"] == "ok"]
    abertos = validos[(validos["inicio"] <= instante) & (validos["fim"] > instante)
                      & (validos["fim"] <= limite)]
    return retrato["id"].isin(set(abertos["id"])).astype(float).values


# =============================================================
# Conserto Futuro
# -------------------------------------------------------------
# Marca arquivos que recebem algum commit de conserto nos dias seguintes a T
# =============================================================
def conserto_futuro(retrato: pd.DataFrame, identificado: pd.DataFrame, instante: int,
                    dias: int) -> np.ndarray:
    if instante + dias * 86400 > identificado["instante"].max():
        return np.full(len(retrato), np.nan)
    futuros = identificado[(identificado["conserto"] == 1) & (identificado["instante"] > instante)
                           & (identificado["instante"] <= instante + dias * 86400)]
    return retrato["id"].isin(set(futuros["id"])).astype(float).values


# =============================================================
# RETRATOS
# =============================================================

# =============================================================
# Instantes
# -------------------------------------------------------------
# Datas dos retratos, de PRIMEIRO_RETRATO a FIM_RETRATOS
# =============================================================
def instantes() -> list[pd.Timestamp]:
    return list(pd.date_range(config.PRIMEIRO_RETRATO, config.FIM_RETRATOS,
                              freq=f"{config.MESES_ENTRE_RETRATOS}MS"))


# =============================================================
# Montar Repositorio
# -------------------------------------------------------------
# Grava os intervalos e os retratos de um repositório; pula se já existe
# =============================================================
def montar_repositorio(nome: str, causadores: pd.DataFrame) -> None:
    destino = config.PASTA_RETRATOS / f"{nome}.csv.gz"
    if destino.exists():
        print(f"{nome}: pronto", flush=True)
        return
    identificado = ler_identificado(nome)
    intervalos = montar_intervalos(nome, identificado, causadores)
    partes = []
    for data in instantes():
        instante = int(data.timestamp())
        retrato = metricas_historico.medir(identificado, instante)
        if len(retrato) < config.MINIMO_ARQUIVOS_RETRATO:
            continue
        for horizonte in config.HORIZONTES_DIAS:
            retrato[f"latente_{horizonte}"] = rotular(retrato, intervalos, instante, horizonte)
        retrato["conserto_futuro_180"] = conserto_futuro(retrato, identificado, instante, 180)
        retrato.insert(0, "data", data.date().isoformat())
        retrato.insert(0, "repositorio", nome)
        partes.append(retrato)
    intervalos.to_csv(config.PASTA_RETRATOS / f"{nome}__intervalos.csv.gz", index=False)
    if partes:
        tudo = pd.concat(partes, ignore_index=True)
        temporario = destino.with_name(destino.name + ".tmp")
        tudo.to_csv(temporario, index=False, compression="gzip", float_format="%.5g")
        os.replace(temporario, destino)
        print(f"{nome}: {len(tudo)} retratos em {len(partes)} datas, "
              f"{intervalos.attrs['pares']} pares causadores, "
              f"{dict(intervalos['situacao'].value_counts())}", flush=True)
    else:
        print(f"{nome}: sem retratos com {config.MINIMO_ARQUIVOS_RETRATO} arquivos", flush=True)


if __name__ == "__main__":
    config.PASTA_RETRATOS.mkdir(parents=True, exist_ok=True)
    causadores = ler_causadores()
    nomes = sys.argv[1:] or [n for n in config.NOMES_NO_GITHUB
                             if (config.PASTA_HISTORICO / f"{n}.csv.gz").exists()]
    for nome in nomes:
        montar_repositorio(nome, causadores)

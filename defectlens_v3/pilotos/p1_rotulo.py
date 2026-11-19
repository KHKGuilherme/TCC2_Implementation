"""
Piloto 1: comportamento do rótulo latente (tempo até o conserto, censura, prevalência por data).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

DIA = 86400
intervalos = pd.concat([pd.read_csv(p) for p in config.PASTA_RETRATOS.glob("*__intervalos.csv.gz")])
print("pares causadores achados no log:", len(intervalos))
print(intervalos["situacao"].value_counts(normalize=True).round(3).to_string())
ok = intervalos[intervalos["situacao"] == "ok"].copy()
ok["dias"] = (ok["fim"] - ok["inicio"]) / DIA
ok["ano"] = pd.to_datetime(ok["inicio"], unit="s").dt.year
print("\ndias até o primeiro conserto (todos):", ok["dias"].quantile([.1, .25, .5, .75, .9, .95]).round(0).to_dict())
antigos = ok[ok["ano"] <= 2016]
print("causadores até 2016 (6+ anos de observação):",
      antigos["dias"].quantile([.5, .75, .9, .95]).round(0).to_dict())
for limite in (180, 365, 730, 1095):
    print(f"  consertados em até {limite} dias: {(antigos['dias'] <= limite).mean():.3f}")
print("\npares causadores por ano de introdução e situação:")
intervalos["ano"] = pd.to_datetime(intervalos["inicio"], unit="s").dt.year
print(pd.crosstab(intervalos["ano"], intervalos["situacao"]).tail(10).to_string())

partes = []
for caminho in config.PASTA_RETRATOS.glob("*.csv.gz"):
    if "__" in caminho.name:
        continue
    partes.append(pd.read_csv(caminho, usecols=["repositorio", "data", "latente"]))
retratos = pd.concat(partes)
tabela = retratos.groupby(["data", "repositorio"])["latente"].mean().unstack().round(3)
print("\nprevalência latente por data (linhas) e repositório:")
print(tabela.tail(14).to_string())
print("\narquivos por repositório no retrato de 2020-01-01:")
print(retratos[retratos["data"] == "2020-01-01"].groupby("repositorio")["latente"].agg(["size", "sum", "mean"]).round(3).to_string())

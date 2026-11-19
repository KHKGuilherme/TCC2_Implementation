"""
Piloto 0: cobertura do Defectors no histórico e tempo até o primeiro conserto.
"""
import pandas as pd, numpy as np
from pathlib import Path
R = Path(r"D:\Code\TCC2")
d = pd.read_csv(R/"dados/dataset.csv", usecols=["repositorio","arquivo","commit","particao_defectors","defeituoso","linhas_defeituosas"])
print(d.groupby("particao_defectors").defeituoso.agg(["size","mean"]))
for nome in ["black","poetry","django","core","pandas"]:
    h = pd.read_csv(R/f"dados/historico_log/{nome}.csv")
    h["t"] = pd.to_datetime(h.instante, unit="s")
    x = d[d.repositorio==nome].merge(h[["hash","t"]].drop_duplicates("hash"), left_on="commit", right_on="hash", how="left")
    print("\n==", nome, "retratos", len(x), "sem data no log", x.t.isna().mean().round(3))
    print(" log:", h.t.min().date(), h.t.max().date(), "commits", h.hash.nunique(), " defectors:", x.t.min(), x.t.max())
    hc = h.drop_duplicates("hash").set_index("t").resample("YS").hash.count()
    dc = x.drop_duplicates("commit").set_index("t").resample("YS").agg(n=("commit","count"), ind=("defeituoso","sum"))
    xc = x.groupby("commit").agg(t=("t","first"), ind=("defeituoso","max"), p=("particao_defectors","first"))
    dc = xc.set_index("t").resample("YS").agg(n=("ind","size"), ind=("ind","sum"))
    print(pd.concat([hc.rename("log"), dc], axis=1).tail(9).to_string())
    print(xc.groupby("p").t.agg(["min","max","size"]))

import numpy as np

from predicao import modelo
from predicao.erros import ErroDeAnalise
from predicao.medidas import metricas_historico

EXIBIDAS = ["revisoes", "autores", "linhas_estimadas", "idade_dias", "dias_desde_ultima",
            "consertos", "dias_desde_conserto", "commits_desde_conserto",
            "adicionadas_desde_conserto", "commits_365", "churn_365"]

MOTIVOS = {
    "pos_adicionadas_desde_conserto": "muito código novo desde o último conserto",
    "pos_commits_365": "muito alterado no último ano",
    "pos_churn_365": "muitas linhas mexidas no último ano",
    "pos_revisoes": "muitas revisões no histórico",
    "pos_consertos": "muitos consertos anteriores",
    "pos_linhas_estimadas": "arquivo grande",
    "pos_autores": "muitos autores",
}


def nivel(chance: float, limiar: float) -> str:
    if chance >= limiar:
        return "alto"
    if chance >= limiar / 2:
        return "medio"
    return "baixo"


def motivos(linha: dict) -> list[str]:
    candidatos = sorted(((linha[nome], texto) for nome, texto in MOTIVOS.items()
                         if linha.get(nome, 0) >= 0.8), reverse=True)
    return [f"{texto} (acima de {int(posicao * 100)}% dos arquivos)"
            for posicao, texto in candidatos[:3]]


def avaliar_historico(tabela_historico, instante: int) -> tuple[dict, list[dict]]:
    manifesto = modelo.carregar()["manifesto"]
    identificado = metricas_historico.identificar(tabela_historico)
    medidas = metricas_historico.medir(identificado, instante)
    if medidas.empty:
        raise ErroDeAnalise("Nenhum arquivo .py de produção foi encontrado neste repositório.")
    bruta, chance = modelo.prever(medidas)
    limiar = float(manifesto["limiar"])
    medidas = medidas.assign(chance=chance, bruta=bruta)
    medidas = medidas.sort_values(["chance", "bruta"], ascending=False).reset_index(drop=True)
    arquivos = []
    for posicao, linha in enumerate(medidas.to_dict("records"), start=1):
        arquivos.append({
            "caminho": linha["arquivo"], "situacao": "avaliado",
            "probabilidade": round(float(linha["chance"]), 4),
            "nivel": nivel(linha["chance"], limiar), "posicao": posicao,
            "motivos": motivos(linha),
            "metricas": {nome: (None if linha[nome] != linha[nome] else round(float(linha[nome]), 1))
                         for nome in EXIBIDAS},
        })
    erro = (manifesto.get("validacao") or {}).get("erro_porcentagem_pp") or 0.0
    estimada = float(chance.mean())
    contagens, _ = np.histogram(chance, bins=np.linspace(0, 1, 11))
    todos = identificado[identificado["instante"] <= instante]
    resumo = {
        "avaliados": int(len(medidas)),
        "porcentagem_estimada": round(estimada * 100, 2),
        "porcentagem_minima": round(max(0.0, estimada * 100 - erro), 2),
        "porcentagem_maxima": round(min(100.0, estimada * 100 + erro), 2),
        "arquivos_esperados": round(float(chance.sum()), 1),
        "risco_alto": int((chance >= limiar).sum()),
        "porcentagem_acima_do_limiar": round(float((chance >= limiar).mean()) * 100, 2),
        "risco_maximo": round(float(chance.max()), 4),
        "limiar": limiar,
        "erro_validacao_pp": round(float(erro), 2),
        "distribuicao": [int(c) for c in contagens],
        "commits": int(todos["hash"].nunique()),
        "consertos": int(todos.drop_duplicates("hash")["conserto"].sum()),
        "autores": int(todos["autor"].nunique()),
    }
    return resumo, arquivos

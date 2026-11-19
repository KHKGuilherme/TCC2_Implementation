"""
Frente 2 — avalia os commits recentes de um repositório inédito: clona só
o histórico, mede com o mesmo extrator do treino e devolve os commits em
ordem de prioridade para revisão, com a explicação de cada nota.

CMD -> python defectlens_v2/frente2_predicao/prever.py pallets/flask
       mostra os commits mais arriscados no terminal
"""

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import config
from extrator import extracao, features
from frente2_predicao import repositorio as acesso
from frente2_predicao.repositorio import ErroDeAnalise

SEGUNDOS_POR_DIA = 86400.0

FATORES_POR_COMMIT = 4

PONTOS_DA_CURVA = 50

FAIXAS_DO_HISTOGRAMA = 10

ARQUIVOS_POR_COMMIT = 12


# =============================================================
# MODELO
# =============================================================


# =============================================================
# Carregar Modelo
# -------------------------------------------------------------
# Lê o pacote do modelo uma vez e confere as features
# =============================================================
@lru_cache(maxsize=1)
def carregar_modelo() -> dict:
    if not config.ARQUIVO_MODELO.exists():
        raise ErroDeAnalise(
            "Modelo não encontrado. Rode a Frente 1: python "
            "defectlens_v2/frente1_treinamento/principal.py")

    pacote = joblib.load(config.ARQUIVO_MODELO)

    if list(pacote["features"]) != list(features.FEATURES_MODELO):
        raise ErroDeAnalise(
            "O modelo foi treinado com outras features. Treine de novo "
            "com a Frente 1.")

    return pacote


# =============================================================
# Descrever Modelo
# -------------------------------------------------------------
# O que o site mostra sobre o modelo, sem o estimador
# =============================================================
def descrever_modelo() -> dict:
    pacote = carregar_modelo()
    descricao = {chave: valor for chave, valor in pacote.items()
                 if chave not in ("modelo", "quantis_das_features",
                                  "medianas", "calibrador")}
    descricao["features"] = len(pacote["features"])
    descricao["importancia"] = pacote["importancia"][:12]
    return descricao


# =============================================================
# Calibrar
# -------------------------------------------------------------
# Converte a nota bruta em chance estimada na proporção natural
# =============================================================
def calibrar(pacote: dict, nota: np.ndarray) -> np.ndarray:
    calibrador = pacote["calibrador"]
    nota = np.clip(np.asarray(nota, dtype=float), 1e-6, 1 - 1e-6)

    if calibrador["forma"] == "platt":
        z = (calibrador["inclinacao"] * np.log(nota / (1 - nota))
             + calibrador["intercepto"])
        return 1.0 / (1.0 + np.exp(-z))

    return np.interp(nota, calibrador["x"], calibrador["y"])


# =============================================================
# Faixa da Nota
# -------------------------------------------------------------
# Em qual faixa de risco a nota cai, pelos cortes medidos no treino
# =============================================================
def faixa_da_nota(pacote: dict, nota: float) -> str:
    for faixa in pacote["faixas"]:
        if nota >= faixa["nota_de"]:
            return faixa["faixa"]

    return pacote["faixas"][-1]["faixa"]


# =============================================================
# Posicao na Referencia
# -------------------------------------------------------------
# Fração dos commits de referência com nota menor que esta
# =============================================================
def posicao_na_referencia(quantis: list[float],
                          valores: np.ndarray) -> np.ndarray:
    return (np.searchsorted(np.asarray(quantis), valores, side="right")
            / len(quantis)).clip(0, 1)


# =============================================================
# MEDIÇÃO
# =============================================================


# =============================================================
# Escolher Janela
# -------------------------------------------------------------
# Os commits recentes, ou os últimos quando o período tem poucos
# =============================================================
def escolher_janela(medidas: pd.DataFrame, com_py: set[str],
                    referencia: float) -> tuple[pd.DataFrame, dict]:
    limite = referencia - config.JANELA_REVISAO_DIAS * SEGUNDOS_POR_DIA
    recentes = medidas[medidas["instante"] >= limite]
    avaliaveis = recentes["commit"].isin(com_py).sum()
    estendida = False

    if avaliaveis < config.MINIMO_COMMITS_NA_JANELA:
        ordenados = medidas.sort_values("instante")
        ultimos = ordenados[ordenados["commit"].isin(com_py)].tail(
            config.MINIMO_COMMITS_NA_JANELA)
        if len(ultimos) > avaliaveis:
            recentes = ordenados[ordenados["instante"]
                                 >= ultimos["instante"].min()]
            estendida = True

    return recentes, {
        "dias": config.JANELA_REVISAO_DIAS,
        "referencia": dia_do_instante(referencia),
        "inicio": dia_do_instante(float(recentes["instante"].min()))
                  if len(recentes) else dia_do_instante(referencia),
        "estendida": estendida,
        "commits_no_periodo": int(len(recentes)),
    }


# =============================================================
# Dia do Instante
# -------------------------------------------------------------
# Converte um instante na data em formato ISO
# =============================================================
def dia_do_instante(instante: float) -> str:
    return (datetime.fromtimestamp(instante, tz=timezone.utc)
            .date().isoformat())


# =============================================================
# Valor Limpo
# -------------------------------------------------------------
# Converte um número para o formato do JSON
# =============================================================
def valor_limpo(valor, casas: int = 4):
    if valor is None or (isinstance(valor, float) and not np.isfinite(valor)):
        return None
    if isinstance(valor, (np.integer, int)):
        return int(valor)

    valor = float(valor)
    return int(valor) if valor.is_integer() else round(valor, casas)


# =============================================================
# EXPLICAÇÃO
# =============================================================


# =============================================================
# Explicar Notas
# -------------------------------------------------------------
# Quanto a nota muda se cada medida valesse a mediana do treino
# =============================================================
def explicar_notas(pacote: dict, decisivos: pd.DataFrame) -> list[list[dict]]:
    colunas = pacote["features"]
    matriz = decisivos[colunas].to_numpy(dtype=float)
    nota = pacote["modelo"].predict_proba(matriz)[:, 1]
    efeitos = np.zeros_like(matriz)

    for indice, coluna in enumerate(colunas):
        trocada = matriz.copy()
        trocada[:, indice] = pacote["medianas"][coluna]
        efeitos[:, indice] = nota - pacote["modelo"].predict_proba(
            trocada)[:, 1]

    explicacoes = []
    for linha in range(len(matriz)):
        ordem = np.argsort(-np.abs(efeitos[linha]))[:FATORES_POR_COMMIT]
        fatores = []

        for indice in ordem:
            coluna = colunas[indice]
            if abs(efeitos[linha, indice]) < 0.005:
                continue

            posicao = posicao_na_referencia(
                pacote["quantis_das_features"][coluna],
                np.array([matriz[linha, indice]]))[0]
            fatores.append({
                "feature": coluna,
                "nome": features.nome_legivel(coluna),
                "grupo": features.grupo_da_feature(coluna),
                "valor": valor_limpo(matriz[linha, indice], 2),
                "mediana_do_treino": valor_limpo(
                    pacote["medianas"][coluna], 2),
                "percentil": round(float(posicao), 3),
                "efeito": round(float(efeitos[linha, indice]), 4),
            })

        explicacoes.append(fatores)

    return explicacoes


# =============================================================
# PREVISÃO
# =============================================================


# =============================================================
# Avaliar Commits
# -------------------------------------------------------------
# Nota, chance, faixa e explicação de cada commit no domínio
# =============================================================
def avaliar_commits(pacote: dict, retratos: pd.DataFrame) -> pd.DataFrame:
    matriz = retratos[pacote["features"]].to_numpy(dtype=float)
    retratos = retratos.assign(
        nota=pacote["modelo"].predict_proba(matriz)[:, 1])

    decisivos = (retratos.sort_values("nota", ascending=False)
                 .drop_duplicates("commit").reset_index(drop=True))

    decisivos["chance"] = calibrar(pacote, decisivos["nota"].to_numpy())
    decisivos["percentil"] = posicao_na_referencia(
        pacote["referencia"]["quantis"], decisivos["nota"].to_numpy())
    decisivos["faixa"] = [faixa_da_nota(pacote, n)
                          for n in decisivos["nota"]]
    decisivos["fatores"] = explicar_notas(pacote, decisivos)
    decisivos["chance_por_linha"] = (decisivos["chance"]
                                     / decisivos["commit_churn"].clip(lower=1))
    return decisivos


# =============================================================
# Descrever Arquivos
# -------------------------------------------------------------
# Os .py de código que cada commit alterou, com o histórico de cada um
# =============================================================
def descrever_arquivos(retratos: pd.DataFrame) -> dict[str, list[dict]]:
    por_commit = {}

    for commit, grupo in retratos.groupby("commit", sort=False):
        grupo = grupo.sort_values("arquivo_adicionadas", ascending=False)
        por_commit[commit] = [{
            "caminho": linha["arquivo"],
            "adicionadas": int(linha["arquivo_adicionadas"]),
            "removidas": int(linha["arquivo_removidas"]),
            "revisoes": int(linha["revisoes"]),
            "autores": int(linha["autores"]),
            "idade_dias": valor_limpo(linha["idade_dias"], 1),
            "novo": bool(linha["revisoes"] <= 1),
        } for _, linha in grupo.head(ARQUIVOS_POR_COMMIT).iterrows()]

    return por_commit


# =============================================================
# Montar Commit
# -------------------------------------------------------------
# Um commit no formato que o site mostra
# =============================================================
def montar_commit(linha: pd.Series, arquivos: list[dict]) -> dict:
    return {
        "hash": linha["commit"],
        "data": dia_do_instante(float(linha["instante"])),
        "autor": linha["autor"],
        "assunto": linha["assunto"],
        "arquivos": int(linha["commit_arquivos"]),
        "arquivos_py": int(linha["py_arquivos"]),
        "adicionadas": int(linha["commit_adicionadas"]),
        "removidas": int(linha["commit_removidas"]),
        "nota": round(float(linha["nota"]), 4),
        "chance": round(float(linha["chance"]), 4),
        "percentil": round(float(linha["percentil"]), 3),
        "faixa": linha["faixa"],
        "posicao_risco": int(linha["posicao_risco"]),
        "posicao_custo": int(linha["posicao_custo"]),
        "arquivo_decisivo": linha["arquivo"],
        "fatores": linha["fatores"],
        "arquivos_alterados": arquivos,
    }


# =============================================================
# Curvas de Esforco
# -------------------------------------------------------------
# Risco estimado coberto conforme as linhas revisadas, por ordem
# =============================================================
def curvas_de_esforco(avaliados: pd.DataFrame) -> dict:
    ordens = {
        "risco": avaliados.sort_values("nota", ascending=False),
        "custo": avaliados.sort_values("chance_por_linha", ascending=False),
        "cronologica": avaliados.sort_values("instante", ascending=False),
    }
    curvas = {}

    for nome, ordenado in ordens.items():
        linhas = ordenado["commit_churn"].clip(lower=1).to_numpy(dtype=float)
        chance = ordenado["chance"].to_numpy(dtype=float)
        x = np.concatenate([[0.0], np.cumsum(linhas) / linhas.sum()])
        y = np.concatenate([[0.0], np.cumsum(chance) / chance.sum()])
        grade = np.linspace(0, 1, PONTOS_DA_CURVA + 1)
        curvas[nome] = [[round(float(g), 3),
                         round(float(np.interp(g, x, y)), 4)]
                        for g in grade]

    return curvas


# =============================================================
# Distribuir Notas
# -------------------------------------------------------------
# Histograma das notas do repositório ao lado do da referência
# =============================================================
def distribuir_notas(pacote: dict, notas: np.ndarray) -> list[dict]:
    limites = np.linspace(0, 1, FAIXAS_DO_HISTOGRAMA + 1)
    contagem, _ = np.histogram(notas, bins=limites)
    quantis = pacote["referencia"]["quantis"]
    acumulada = posicao_na_referencia(quantis, limites)
    acumulada[0], acumulada[-1] = 0.0, 1.0

    return [{"de": round(float(limites[i]), 2),
             "ate": round(float(limites[i + 1]), 2),
             "repositorio": round(float(contagem[i] / max(len(notas), 1)), 4),
             "referencia": round(float(acumulada[i + 1] - acumulada[i]), 4)}
            for i in range(FAIXAS_DO_HISTOGRAMA)]


# =============================================================
# Destacar Arquivos
# -------------------------------------------------------------
# Os arquivos que mais concentram risco estimado no período
# =============================================================
def destacar_arquivos(retratos: pd.DataFrame,
                      avaliados: pd.DataFrame) -> list[dict]:
    chance = avaliados.set_index("commit")["chance"]
    tabela = retratos[retratos["commit"].isin(chance.index)].copy()
    tabela["chance"] = tabela["commit"].map(chance)

    resumo = (tabela.groupby("arquivo")
              .agg(commits=("commit", "nunique"),
                   risco_somado=("chance", "sum"),
                   maior_chance=("chance", "max"),
                   adicionadas=("arquivo_adicionadas", "sum"),
                   removidas=("arquivo_removidas", "sum"),
                   revisoes=("revisoes", "max"),
                   autores=("autores", "max"))
              .sort_values(["risco_somado", "maior_chance"],
                           ascending=False)
              .head(config.ARQUIVOS_EM_DESTAQUE).reset_index())

    return [{"caminho": linha["arquivo"],
             "commits": int(linha["commits"]),
             "risco_somado": round(float(linha["risco_somado"]), 4),
             "maior_chance": round(float(linha["maior_chance"]), 4),
             "adicionadas": int(linha["adicionadas"]),
             "removidas": int(linha["removidas"]),
             "revisoes": int(linha["revisoes"]),
             "autores": int(linha["autores"])}
            for _, linha in resumo.iterrows()]


# =============================================================
# Listar Fora do Dominio
# -------------------------------------------------------------
# Os commits do período que o modelo não pode avaliar, e por quê
# =============================================================
def listar_fora_do_dominio(fora: pd.DataFrame) -> list[dict]:
    fora = fora.sort_values("commit_churn", ascending=False)

    return [{"hash": linha["commit"],
             "data": dia_do_instante(float(linha["instante"])),
             "autor": linha["autor"],
             "assunto": linha["assunto"],
             "arquivos": int(linha["commit_arquivos"]),
             "adicionadas": int(linha["commit_adicionadas"]),
             "removidas": int(linha["commit_removidas"]),
             "motivo": features.motivo_fora_do_dominio(linha.to_dict())}
            for _, linha in fora.head(50).iterrows()]


# =============================================================
# Montar Resultado
# -------------------------------------------------------------
# Transforma as medidas do período no resultado que o site mostra
# =============================================================
def montar_resultado(pacote: dict, medidas: pd.DataFrame,
                     retratos: pd.DataFrame, referencia: float) -> dict:
    if medidas.empty or retratos.empty:
        raise ErroDeAnalise(
            "Nenhum commit deste repositório alterou arquivos .py de código.")

    recentes, janela = escolher_janela(medidas, set(retratos["commit"]),
                                       referencia)
    tabela = features.montar_retratos(
        recentes, retratos[retratos["commit"].isin(recentes["commit"])])

    if tabela.empty:
        raise ErroDeAnalise(
            "Nenhum commit recente alterou arquivos .py de código.")

    no_dominio = features.no_dominio(tabela)
    fora = tabela[~no_dominio].drop_duplicates("commit")
    dentro = tabela[no_dominio]

    if dentro.empty:
        raise ErroDeAnalise(
            "Todos os commits recentes estão fora do domínio do modelo "
            "(grandes demais ou sem linhas adicionadas).")

    avaliados = avaliar_commits(pacote, dentro)
    avaliados["posicao_risco"] = avaliados["nota"].rank(
        ascending=False, method="first").astype(int)
    avaliados["posicao_custo"] = avaliados["chance_por_linha"].rank(
        ascending=False, method="first").astype(int)
    avaliados = avaliados.sort_values("posicao_risco")

    arquivos = descrever_arquivos(dentro)
    visiveis = avaliados[
        (avaliados["posicao_risco"] <= config.MAXIMO_COMMITS_NA_RESPOSTA)
        | (avaliados["posicao_custo"] <= config.MAXIMO_COMMITS_NA_RESPOSTA)]
    contagem = avaliados["faixa"].value_counts()

    janela.update({
        "sem_py": int(len(recentes) - tabela["commit"].nunique()),
        "fora_do_dominio": int(len(fora)),
        "avaliados": int(len(avaliados)),
    })

    return {
        "janela": janela,
        "resumo": {
            "avaliados": int(len(avaliados)),
            "risco_alto": int(contagem.get("alto", 0)),
            "risco_medio": int(contagem.get("médio", 0)),
            "risco_baixo": int(contagem.get("baixo", 0)),
            "risco_maximo": round(float(avaliados["nota"].max()), 4),
            "chance_maxima": round(float(avaliados["chance"].max()), 4),
            "defeitos_esperados": round(float(avaliados["chance"].sum()), 2),
            "linhas_alteradas": int(avaliados["commit_churn"].sum()),
            "fora_do_dominio": int(len(fora)),
        },
        "commits": [montar_commit(linha, arquivos.get(linha["commit"], []))
                    for _, linha in visiveis.iterrows()],
        "linha_do_tempo": [
            {"hash": linha["commit"][:10],
             "data": dia_do_instante(float(linha["instante"])),
             "nota": round(float(linha["nota"]), 4),
             "linhas": int(linha["commit_churn"]),
             "faixa": linha["faixa"]}
            for _, linha in avaliados.sort_values("instante").iterrows()],
        "curvas": curvas_de_esforco(avaliados),
        "distribuicao": distribuir_notas(pacote,
                                         avaliados["nota"].to_numpy()),
        "arquivos": destacar_arquivos(dentro, avaliados),
        "fora_do_dominio": listar_fora_do_dominio(fora),
    }


# =============================================================
# Analisar
# -------------------------------------------------------------
# A Frente 2 inteira: endereço entra, commits para revisar saem
# =============================================================
def analisar(endereco: str, ramo: str | None = None,
             ao_progresso=None) -> dict:
    inicio = time.time()
    repositorio, ramo_da_url = acesso.interpretar_endereco(endereco)
    ramo = ramo or ramo_da_url

    faixas = {"conferindo": (0.0, 0.05), "clonando": (0.05, 0.55),
              "historico": (0.55, 0.92), "prevendo": (0.92, 1.0)}

    def etapa(nome: str):
        comeco, fim = faixas[nome]

        def avisar(fracao: float, mensagem: str) -> None:
            if ao_progresso:
                ao_progresso(nome, comeco + (fim - comeco) * fracao,
                             mensagem)

        return avisar

    pacote = carregar_modelo()

    etapa("conferindo")(0.0, f"conferindo o tamanho de {repositorio}")
    informacao = acesso.conferir_tamanho(repositorio)

    pasta = (config.PASTA_CLONES / "web"
             / f"{repositorio.replace('/', '__')}__{uuid.uuid4().hex[:8]}")
    pasta.parent.mkdir(parents=True, exist_ok=True)

    try:
        etapa("clonando")(0.0, f"clonando {repositorio}")
        acesso.clonar(repositorio, ramo, pasta, etapa("clonando"))

        commit = acesso.rodar_git(["-C", str(pasta), "rev-parse", "HEAD"],
                                  timeout=30).stdout.decode().strip()
        ramo_real = acesso.rodar_git(
            ["-C", str(pasta), "branch", "--show-current"],
            timeout=30).stdout.decode().strip()

        medidas, retratos, info = extracao.extrair(
            pasta, repositorio, ultimos=config.MAXIMO_COMMITS_GUARDADOS,
            avisar=etapa("historico"))
    finally:
        acesso.apagar_pasta(pasta)

    if info["commits"] > config.LIMITE_COMMITS:
        raise ErroDeAnalise(
            f"O repositório tem {info['commits']} commits, acima do limite "
            f"de {config.LIMITE_COMMITS} desta instalação.")

    etapa("prevendo")(0.0, "aplicando o modelo")
    resultado = montar_resultado(pacote, medidas, retratos,
                                 info["referencia"])
    etapa("prevendo")(1.0, "pronto")

    return {
        "repositorio": repositorio,
        "ramo": ramo_real or ramo or (informacao or {}).get("ramo_padrao"),
        "commit": commit,
        "commits_no_historico": info["commits"],
        "tamanho_mb": (informacao or {}).get("tamanho_mb"),
        "modelo": {
            "nome": pacote["nome"],
            "versao": pacote["versao"],
            "features": len(pacote["features"]),
            "faixas": pacote["faixas"],
            "taxa_de_referencia": pacote["referencia"]["taxa_de_defeito"],
            "dominio": pacote["dominio"],
        },
        **resultado,
        "duracao_s": round(time.time() - inicio, 1),
    }


# =============================================================
# Mostrar
# -------------------------------------------------------------
# Uso da Frente 2 sem a web
# =============================================================
def mostrar(resultado: dict, quantos: int = 15) -> None:
    janela, resumo = resultado["janela"], resultado["resumo"]
    print(f"\n  {resultado['repositorio']} @ {resultado['ramo']} "
          f"({resultado['commit'][:10]}, "
          f"{resultado['commits_no_historico']} commits, "
          f"{resultado['duracao_s']} s)")
    print(f"  Período: {janela['inicio']} a {janela['referencia']}"
          f"{' (estendido)' if janela['estendida'] else ''}: "
          f"{janela['commits_no_periodo']} commits, "
          f"{resumo['avaliados']} avaliados, {janela['sem_py']} sem .py de "
          f"código, {resumo['fora_do_dominio']} fora do domínio")
    print(f"  Faixas: {resumo['risco_alto']} alto, {resumo['risco_medio']} "
          f"médio, {resumo['risco_baixo']} baixo; defeitos esperados: "
          f"{resumo['defeitos_esperados']}")

    print(f"\n  {'#':>3} {'nota':>6} {'chance':>7} {'faixa':<6} "
          f"{'commit':<11} {'data':<11} {'+':>5} {'-':>5}  assunto")
    for commit in sorted(resultado["commits"],
                         key=lambda c: c["posicao_risco"])[:quantos]:
        print(f"  {commit['posicao_risco']:>3} {commit['nota']:>6.3f} "
              f"{100 * commit['chance']:>6.1f}% {commit['faixa']:<6} "
              f"{commit['hash'][:10]:<11} {commit['data']:<11} "
              f"{commit['adicionadas']:>5} {commit['removidas']:>5}  "
              f"{commit['assunto'][:60]}")
        for fator in commit["fatores"][:2]:
            print(f"        {fator['efeito']:+.3f}  {fator['nome']} = "
                  f"{fator['valor']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("uso: python defectlens_v2/frente2_predicao/"
                         "prever.py dono/repositorio [ramo] [--json]")

    def progresso(etapa: str, fracao: float, mensagem: str) -> None:
        print(f"\r  {100 * fracao:5.1f}%  {etapa:<10} {mensagem:<50}",
              end="", flush=True, file=sys.stderr)

    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]

    try:
        final = analisar(argumentos[0],
                         argumentos[1] if len(argumentos) > 1 else None,
                         progresso)
    except ErroDeAnalise as erro:
        raise SystemExit(f"\n  {erro}") from None

    if "--json" in sys.argv:
        print(json.dumps(final, ensure_ascii=False, indent=1))
    else:
        mostrar(final)

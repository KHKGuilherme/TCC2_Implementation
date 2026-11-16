"""
Frente 2: recebe o endereço de um repositório do GitHub e estima o defeito latente por arquivo.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from extrator import historico, metricas_historico  # noqa: E402


# =============================================================
# CONSTANTES
# =============================================================
PADRAO_ENDERECO = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:github\.com/)?(?P<dono>[A-Za-z0-9_.-]+)/"
    r"(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?(?:/tree/(?P<ramo>[^\s?#]+))?/?$")

PASTA_WEB = "web"

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


class ErroDeAnalise(Exception):
    """Falha que deve chegar ao usuário com a mensagem como está."""


# =============================================================
# ENDEREÇO E MODELO
# =============================================================

# =============================================================
# Interpretar Endereco
# -------------------------------------------------------------
# Separa dono/repo e o ramo de qualquer forma de endereço
# =============================================================
def interpretar_endereco(texto: str) -> tuple[str, str | None]:
    encontrado = PADRAO_ENDERECO.match(texto.strip())
    if not encontrado:
        raise ErroDeAnalise("Endereço não reconhecido. Use dono/repositorio ou "
                            "https://github.com/dono/repositorio")
    return f"{encontrado['dono']}/{encontrado['repo']}", encontrado["ramo"]


# =============================================================
# Carregar Modelo
# -------------------------------------------------------------
# Lê o pacote do modelo uma vez
# =============================================================
@lru_cache(maxsize=1)
def carregar_modelo() -> dict:
    if not config.ARQUIVO_MODELO.exists():
        raise ErroDeAnalise("Modelo não encontrado. Rode a Frente 1 primeiro.")
    return joblib.load(config.ARQUIVO_MODELO)


# =============================================================
# Descrever Modelo
# -------------------------------------------------------------
# Resumo do modelo em uso, para a tela inicial
# =============================================================
def descrever_modelo() -> dict:
    return carregar_modelo()["resumo"]


# =============================================================
# GITHUB E GIT
# =============================================================

# =============================================================
# Consultar Github
# -------------------------------------------------------------
# Pergunta à API o tamanho do repositório; None se a API não responder
# =============================================================
def consultar_github(repositorio: str) -> dict | None:
    pedido = urllib.request.Request(f"https://api.github.com/repos/{repositorio}",
                                    headers={"User-Agent": "defectlens",
                                             "Accept": "application/vnd.github+json"})
    ficha = os.environ.get("GITHUB_TOKEN")
    if ficha:
        pedido.add_header("Authorization", f"Bearer {ficha}")
    try:
        with urllib.request.urlopen(pedido, timeout=15) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        if erro.code == 404:
            raise ErroDeAnalise("Repositório não encontrado, ou privado.") from None
        return None
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None
    return {"tamanho_kb": int(dados.get("size", 0)), "ramo": dados.get("default_branch"),
            "estrelas": dados.get("stargazers_count"), "linguagem": dados.get("language")}


# =============================================================
# Conferir Tamanho
# -------------------------------------------------------------
# Recusa, antes de clonar, o repositório acima do limite
# =============================================================
def conferir_tamanho(repositorio: str) -> dict | None:
    ficha = consultar_github(repositorio)
    if ficha and ficha["tamanho_kb"] > config.TAMANHO_MAXIMO_REPO_KB:
        raise ErroDeAnalise(
            f"Repositório grande demais para este servidor: {ficha['tamanho_kb'] / 1024:.0f} MB "
            f"(limite de {config.TAMANHO_MAXIMO_REPO_KB / 1024:.0f} MB).")
    return ficha


# =============================================================
# Rodar Git
# -------------------------------------------------------------
# Executa o git sem nunca pedir senha
# =============================================================
def rodar_git(argumentos: list[str], segundos: int) -> subprocess.CompletedProcess:
    ambiente = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(["git", *argumentos], capture_output=True, timeout=segundos,
                          env=ambiente)


# =============================================================
# Motivo Do Git
# -------------------------------------------------------------
# Extrai uma mensagem legível do erro do git
# =============================================================
def motivo_do_git(saida: bytes) -> str:
    texto = saida.decode("utf-8", errors="replace")
    if "not found" in texto.lower() or "could not read" in texto.lower():
        return "Repositório não encontrado, ou privado."
    for linha in texto.splitlines():
        if linha.startswith(("fatal:", "error:")):
            return linha[:200]
    return texto.strip()[:200] or "o git falhou sem mensagem"


# =============================================================
# Commit Remoto
# -------------------------------------------------------------
# O hash da ponta do ramo, sem clonar; None se não der
# =============================================================
def commit_remoto(repositorio: str, ramo: str | None) -> str | None:
    alvo = f"refs/heads/{ramo}" if ramo else "HEAD"
    try:
        resultado = rodar_git(["ls-remote", f"https://github.com/{repositorio}.git", alvo], 15)
    except subprocess.TimeoutExpired:
        return None
    if resultado.returncode != 0:
        raise ErroDeAnalise(motivo_do_git(resultado.stderr))
    linhas = resultado.stdout.decode().split()
    if not linhas:
        if ramo:
            raise ErroDeAnalise(f"O ramo '{ramo}' não existe neste repositório.")
        return None
    return linhas[0]


# =============================================================
# Clonar
# -------------------------------------------------------------
# Clona o histórico do ramo, sem checkout e sem hooks, com limite de tempo
# =============================================================
def clonar(repositorio: str, ramo: str | None, destino: Path) -> None:
    sem_hooks = config.PASTA_CLONES / "_sem_hooks"
    sem_hooks.mkdir(parents=True, exist_ok=True)
    comando = ["-c", f"core.hooksPath={sem_hooks}", "clone", "--quiet",
               f"--template={sem_hooks}", "--no-checkout", "--single-branch", "--no-tags"]
    if ramo:
        comando += ["--branch", ramo]
    comando += [f"https://github.com/{repositorio}.git", str(destino)]
    try:
        resultado = rodar_git(comando, config.SEGUNDOS_MAXIMOS_CLONE)
    except subprocess.TimeoutExpired:
        raise ErroDeAnalise(f"O clone passou de {config.SEGUNDOS_MAXIMOS_CLONE // 60} minutos "
                            f"e foi interrompido.") from None
    if resultado.returncode != 0:
        raise ErroDeAnalise(motivo_do_git(resultado.stderr))


# =============================================================
# Limpar Clones Orfaos
# -------------------------------------------------------------
# Apaga o que sobrou de análises interrompidas
# =============================================================
def limpar_clones_orfaos() -> None:
    pasta = config.PASTA_CLONES / PASTA_WEB
    if pasta.exists():
        for sobra in pasta.iterdir():
            historico.apagar_pasta(sobra)


# =============================================================
# AVALIAÇÃO
# =============================================================

# =============================================================
# Nivel
# -------------------------------------------------------------
# Traduz a chance em faixa de leitura, a partir do limiar do modelo
# =============================================================
def nivel(chance: float, limiar: float) -> str:
    if chance >= limiar:
        return "alto"
    if chance >= limiar / 2:
        return "medio"
    return "baixo"


# =============================================================
# Motivos
# -------------------------------------------------------------
# Até três características em que o arquivo está no topo do repositório
# =============================================================
def motivos(linha: dict) -> list[str]:
    candidatos = sorted(((linha[nome], texto) for nome, texto in MOTIVOS.items()
                         if linha.get(nome, 0) >= 0.8), reverse=True)
    return [f"{texto} (acima de {int(posicao * 100)}% dos arquivos)"
            for posicao, texto in candidatos[:3]]


# =============================================================
# Avaliar Historico
# -------------------------------------------------------------
# Mede os arquivos no instante dado e aplica o modelo calibrado
# =============================================================
def avaliar_historico(tabela_historico, instante: int) -> tuple[dict, list[dict]]:
    pacote = carregar_modelo()
    resumo_modelo = pacote["resumo"]
    identificado = metricas_historico.identificar(tabela_historico)
    medidas = metricas_historico.medir(identificado, instante)
    if medidas.empty:
        raise ErroDeAnalise("Nenhum arquivo .py de produção foi encontrado neste repositório.")
    bruta = pacote["estimador"].predict_proba(medidas[resumo_modelo["features"]].values)[:, 1]
    if resumo_modelo["calibracao"] == "platt":
        logito = np.log(np.clip(bruta, 1e-6, 1 - 1e-6) / (1 - np.clip(bruta, 1e-6, 1 - 1e-6)))
        chance = pacote["calibradores"]["platt"].predict_proba(logito.reshape(-1, 1))[:, 1]
    elif resumo_modelo["calibracao"] == "isotonica":
        chance = pacote["calibradores"]["isotonica"].predict(bruta)
    else:
        chance = bruta
    limiar = float(resumo_modelo["limiar"])
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
    erro = (resumo_modelo.get("validacao") or {}).get("erro_porcentagem_pp") or 0.0
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


# =============================================================
# Analisar
# -------------------------------------------------------------
# Do endereço ao resultado: confere o tamanho, clona, mede, avalia e apaga
# =============================================================
def analisar(endereco: str, ramo: str | None = None, progresso=None) -> dict:
    avisar = progresso or (lambda etapa, fracao, mensagem: None)
    inicio = time.time()
    repositorio, ramo_da_url = interpretar_endereco(endereco)
    ramo = ramo or ramo_da_url
    carregar_modelo()
    avisar("conferindo", 0.02, "conferindo o tamanho no GitHub")
    ficha = conferir_tamanho(repositorio)
    destino = config.PASTA_CLONES / PASTA_WEB / uuid.uuid4().hex
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        avisar("clonando", 0.10, "baixando o histórico do repositório")
        clonar(repositorio, ramo, destino)
        commit, instante = historico.commit_atual(destino)
        avisar("historico", 0.55, "lendo o histórico de cada arquivo")
        tabela = historico.ler_historico(destino)
    finally:
        historico.apagar_pasta(destino)
    if tabela.empty:
        raise ErroDeAnalise("Este repositório não tem arquivos .py no histórico.")
    avisar("avaliando", 0.85, "medindo os arquivos e aplicando o modelo")
    resumo, arquivos = avaliar_historico(tabela, instante)
    cortado = len(arquivos) > config.MAXIMO_ARQUIVOS_NA_RESPOSTA
    avisar("pronto", 1.0, "")
    return {
        "repositorio": repositorio, "ramo": ramo or (ficha or {}).get("ramo") or "",
        "commit": commit, "data_commit": time.strftime("%Y-%m-%d", time.gmtime(instante)),
        "github": ficha, "resumo": resumo,
        "arquivos": arquivos[:config.MAXIMO_ARQUIVOS_NA_RESPOSTA], "lista_cortada": cortado,
        "commits": resumo["commits"],
        "modelo": {"nome": "Gradient Boosting calibrado (v3)", "limiar": resumo["limiar"],
                   **{k: carregar_modelo()["resumo"].get(k)
                      for k in ("versao", "rotulo", "treinado_em", "validacao", "regra_limiar")}},
        "duracao_s": round(time.time() - inicio, 1),
    }


# =============================================================
# Mostrar
# -------------------------------------------------------------
# Imprime o resumo e os arquivos de maior chance
# =============================================================
def mostrar(resultado: dict, quantos: int = 20) -> None:
    resumo = resultado["resumo"]
    print(f"\n{resultado['repositorio']} @ {resultado['commit'][:10]} "
          f"({resultado['data_commit']}), {resultado['duracao_s']} s")
    print(f"  arquivos avaliados: {resumo['avaliados']}")
    print(f"  % estimada do repositório com defeito latente: {resumo['porcentagem_estimada']}% "
          f"(faixa {resumo['porcentagem_minima']}% a {resumo['porcentagem_maxima']}%)")
    print(f"  acima do limiar de {resumo['limiar']:.0%}: {resumo['risco_alto']} arquivos "
          f"({resumo['porcentagem_acima_do_limiar']}%)\n")
    for item in resultado["arquivos"][:quantos]:
        print(f"  {item['probabilidade']:6.1%}  {item['nivel']:<6} {item['caminho']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: python frente2_predicao/analisar.py https://github.com/dono/repositorio")
        sys.exit(1)
    try:
        mostrar(analisar(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
    except ErroDeAnalise as erro:
        print(f"Erro: {erro}")
        sys.exit(2)

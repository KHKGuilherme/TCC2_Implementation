"""
Frente 2 — estima o risco de o último commit de cada arquivo ter
introduzido um defeito, num repositório inédito.

CMD -> python frente2_predicao/prever.py psf/black
       mostra os arquivos mais arriscados no terminal
"""

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
import warnings
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import config
from extrator import (derivadas, features, metricas_codigo, metricas_commit,
                      metricas_historico)
from frente2_predicao import historico_rapido


# =============================================================
# O QUE A TELA MOSTRA DE CADA ARQUIVO
# =============================================================

METRICAS_EXIBIDAS = [
    ("linhas",                 "Linhas de código",            "menor"),
    ("complexidade_maxima",    "Complexidade máxima",         "menor"),
    ("complexidade_media",     "Complexidade média",          "menor"),
    ("maior_funcao",           "Maior função (linhas)",       "menor"),
    ("aninhamento_maximo",     "Aninhamento máximo",          "menor"),
    ("manutenibilidade",       "Manutenibilidade (0–100)",    "maior"),
    ("ruff_total",             "Avisos do Ruff",              "menor"),
    ("revisoes",               "Commits que o alteraram",     "menor"),
    ("autores",                "Autores",                     "menor"),
    ("churn",                  "Linhas alteradas (churn)",    "menor"),
    ("fracao_autor_principal", "Parcela do autor principal",  "maior"),
    ("commits_recentes",       "Commits nos últimos 90 dias", "menor"),
    ("dias_desde_anterior",    "Dias entre as 2 últimas mudanças", "maior"),
    ("idade_dias",             "Idade (dias)",                "maior"),
]

SITUACOES = {
    "avaliado":    "avaliado pelo modelo",
    "teste":       "arquivo de teste: o Defectors não tem testes, "
                   "então o modelo nunca viu um",
    "ignorado":    "fora do escopo do treino (docs, exemplos, setup)",
    "vazio":       "arquivo vazio",
    "grande":      "acima do tamanho máximo medido no treino",
    "sem_parse":   "não pôde ser lido pelo ast do Python",
    "sem_funcoes": "não tem nenhuma função, como no treino",
}

PADRAO_ENDERECO = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:github\.com/)?"
    r"(?P<dono>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?"
    r"(?:/tree/(?P<ramo>[^?#]+))?/?$")

PASTA_DE_TESTE = re.compile(r"(?:^|/)tests?/")


class ErroDeAnalise(Exception):
    """Falha que deve chegar ao usuário com a mensagem como está."""


# =============================================================
# Interpretar Endereco
# -------------------------------------------------------------
# Separa dono/repo e o ramo de qualquer forma de endereço
# =============================================================
def interpretar_endereco(texto: str) -> tuple[str, str | None]:
    encontrado = PADRAO_ENDERECO.match(texto.strip())

    if not encontrado:
        raise ErroDeAnalise(
            "Endereço não reconhecido. Use dono/repositorio ou "
            "https://github.com/dono/repositorio")

    repositorio = f"{encontrado['dono']}/{encontrado['repo']}"
    return repositorio, encontrado["ramo"]


# =============================================================
# CARREGAMENTO DO MODELO
# =============================================================


# =============================================================
# Carregar Modelo
# -------------------------------------------------------------
# Lê o modelo uma vez e confere as features
# =============================================================
@lru_cache(maxsize=1)
def carregar_modelo() -> dict:
    caminho = RAIZ / config.ARQUIVO_MODELO

    if not caminho.exists():
        raise ErroDeAnalise(
            f"Modelo não encontrado em {config.ARQUIVO_MODELO}. "
            f"Rode a Frente 1 primeiro.")

    pacote = joblib.load(caminho)

    if list(pacote["features"]) != list(features.FEATURES):
        raise ErroDeAnalise(
            "O modelo foi treinado com outra configuração de features. "
            "Treine de novo com a Frente 1 ou volte o config.py.")

    return pacote


# =============================================================
# Importancias
# -------------------------------------------------------------
# As features de maior peso no modelo
# =============================================================
def importancias(pacote: dict, quantas: int = 10) -> list[dict]:
    modelo = pacote["modelo"]
    final = modelo[-1] if hasattr(modelo, "steps") else modelo

    if not hasattr(final, "feature_importances_"):
        return []

    pares = sorted(zip(pacote["features"], final.feature_importances_,
                       strict=True),
                   key=lambda par: -par[1])

    return [{"feature": nome, "peso": round(float(peso), 4),
             "origem": features.origem_da_feature(nome)}
            for nome, peso in pares[:quantas]]


# =============================================================
# Ler Resumo de Projeto Novo
# -------------------------------------------------------------
# Lê os números de projeto nunca visto
# =============================================================
def ler_resumo_projeto_novo() -> dict | None:
    caminho = RAIZ / config.ARQUIVO_RESUMO_PROJETO_NOVO

    if not caminho.exists():
        return None

    return json.loads(caminho.read_text(encoding="utf-8"))


# =============================================================
# Descrever Modelo
# -------------------------------------------------------------
# Reúne o que a tela mostra sobre o modelo
# =============================================================
def descrever_modelo() -> dict:
    pacote = carregar_modelo()

    return {
        "nome":        pacote["nome"],
        "features":    len(pacote["features"]),
        "limiar":      pacote["limiar"],
        "metricas":    pacote.get("metricas"),
        "projeto_novo": ler_resumo_projeto_novo(),
        "treinado_em": pacote.get("treinado_em"),
        "repositorios_treino": pacote.get("repositorios_treino"),
        "tem_medias":  "medias" in pacote,
        "importancias": importancias(pacote),
    }


# =============================================================
# GIT
# =============================================================


# =============================================================
# Rodar Git
# -------------------------------------------------------------
# Executa o git sem nunca pedir senha
# =============================================================
def rodar_git(argumentos: list[str], timeout: int) -> subprocess.CompletedProcess:
    ambiente = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    return subprocess.run(["git", *argumentos], capture_output=True,
                          timeout=timeout, env=ambiente)


# =============================================================
# Motivo do Erro do Git
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
# O hash da ponta do ramo, sem clonar. None se não der
# =============================================================
def commit_remoto(repositorio: str, ramo: str | None) -> str | None:
    alvo = f"refs/heads/{ramo}" if ramo else "HEAD"

    try:
        resultado = rodar_git(["ls-remote",
                               f"https://github.com/{repositorio}.git",
                               alvo], timeout=30)
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
# Clona o repositório com o histórico completo
# =============================================================
def clonar(repositorio: str, ramo: str | None, destino: Path) -> None:
    sem_hooks = RAIZ / config.PASTA_CLONES / "_sem_hooks"
    sem_hooks.mkdir(parents=True, exist_ok=True)

    comando = ["-c", f"core.hooksPath={sem_hooks}",
               "clone", "--quiet", f"--template={sem_hooks}",
               "--single-branch", "--no-tags"]

    if ramo:
        comando += ["--branch", ramo]

    comando += [f"https://github.com/{repositorio}.git", str(destino)]

    try:
        resultado = rodar_git(comando, timeout=1800)
    except subprocess.TimeoutExpired:
        raise ErroDeAnalise(
            "O clone passou de 30 minutos e foi interrompido.") from None

    if resultado.returncode != 0:
        raise ErroDeAnalise(motivo_do_git(resultado.stderr))


# =============================================================
# Apagar Pasta
# -------------------------------------------------------------
# Apaga uma pasta, incluindo arquivos somente leitura
# =============================================================
def apagar_pasta(pasta: Path) -> None:
    def liberar(funcao, caminho, _erro):
        try:
            Path(caminho).chmod(stat.S_IWRITE)
            funcao(caminho)
        except OSError:
            pass

    if not pasta.exists():
        return

    if sys.version_info >= (3, 12):
        shutil.rmtree(pasta, onexc=liberar)
    else:
        shutil.rmtree(pasta, onerror=liberar)


# =============================================================
# Limpar Clones Orfaos
# -------------------------------------------------------------
# Apaga o que sobrou de análises interrompidas
# =============================================================
def limpar_clones_orfaos() -> None:
    pasta = RAIZ / config.PASTA_CLONES / "web"
    if pasta.exists():
        for sobra in pasta.iterdir():
            apagar_pasta(sobra)


# =============================================================
# Listar Arquivos Python
# -------------------------------------------------------------
# Lista os .py rastreados pelo git
# =============================================================
def listar_arquivos_python(pasta: Path) -> list[str]:
    resultado = rodar_git(["-C", str(pasta), "-c", "core.quotepath=off",
                           "ls-files", "-z", "--", "*.py"], timeout=120)

    return sorted(c for c in resultado.stdout.decode("utf-8", "replace")
                  .split("\0") if c)


# =============================================================
# MEDIÇÃO
# =============================================================


# =============================================================
# Classificar Caminho
# -------------------------------------------------------------
# A situação decidida só pelo nome, ou None se precisa medir
# =============================================================
def classificar_caminho(caminho: str) -> str | None:
    nome = caminho.rsplit("/", 1)[-1]

    if any(caminho.startswith(p) for p in config.PASTAS_IGNORADAS):
        return "ignorado"
    if nome in config.ARQUIVOS_IGNORADOS:
        return "ignorado"

    if (PASTA_DE_TESTE.search(caminho) or nome.startswith("test_")
            or nome.endswith("_test.py")):
        return "teste"

    return None


# =============================================================
# Medir Um Arquivo
# -------------------------------------------------------------
# Mede um arquivo, ou diz por que não mediu
# =============================================================
def medir_um_arquivo(pasta: Path, caminho: str) -> tuple[str, dict | None]:
    situacao = classificar_caminho(caminho)
    if situacao:
        return situacao, None

    try:
        codigo = (pasta / caminho).read_bytes().decode("utf-8",
                                                       errors="ignore")
    except OSError:
        return "sem_parse", None

    if not codigo.strip():
        return "vazio", None

    if len(codigo) > config.TAMANHO_MAXIMO_BYTES:
        return "grande", None

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message=".*invalid escape sequence.*")

        quantidade = metricas_codigo.contar_funcoes(caminho, codigo)
        if quantidade is None:
            return "sem_parse", None
        if quantidade == 0:
            return "sem_funcoes", None

        medidas = metricas_codigo.medir(caminho, codigo)

    if medidas is None:
        return "sem_parse", None

    return "avaliado", medidas


# =============================================================
# Medir Codigo
# -------------------------------------------------------------
# Mede todos os arquivos e avisa o progresso
# =============================================================
def medir_codigo(pasta: Path, caminhos: list[str],
                 avisar) -> tuple[dict, dict]:
    medidos, situacoes = {}, {}

    for numero, caminho in enumerate(caminhos, 1):
        situacao, medidas = medir_um_arquivo(pasta, caminho)
        situacoes[caminho] = situacao
        if medidas is not None:
            medidos[caminho] = medidas

        if numero % 20 == 0 or numero == len(caminhos):
            avisar(numero / max(len(caminhos), 1),
                   f"{numero} de {len(caminhos)} arquivos")

    return medidos, situacoes


# =============================================================
# Medir Historico
# -------------------------------------------------------------
# Percorre o histórico e anota o último commit de cada arquivo
# =============================================================
def medir_historico(pasta: Path, caminhos: set[str],
                    avisar) -> tuple[dict, dict, float, int]:
    total = historico_rapido.contar_commits(pasta)
    acumulado = {}
    ultimos = {}
    ultimo = 0.0
    lidos = 0

    for commit in historico_rapido.percorrer_commits(pasta):
        metricas_historico.aplicar_commit(acumulado, commit)
        metricas_commit.registrar_ultimo_commit(ultimos, commit)
        ultimo = commit.committer_date.timestamp()
        lidos += 1

        if lidos % 500 == 0:
            avisar(lidos / max(total, 1), f"{lidos} de {total} commits")

    avisar(1.0, f"{total} de {total} commits")

    historicos = metricas_historico.fotografar(acumulado, caminhos, ultimo)
    return historicos, ultimos, ultimo, total


# =============================================================
# PREVISÃO
# =============================================================


# =============================================================
# Montar Tabela
# -------------------------------------------------------------
# Junta código, histórico e commit numa tabela
# =============================================================
def montar_tabela(repositorio: str, medidos: dict, historicos: dict,
                  ultimos: dict) -> pd.DataFrame:
    linhas = []
    for caminho, medidas in medidos.items():
        ultimo = ultimos.get(caminho, {})
        linhas.append({"repositorio": repositorio, "arquivo": caminho,
                       **medidas, **historicos.get(caminho, {}),
                       **{c: ultimo[c] for c in features.COLUNAS_COMMIT
                          if c in ultimo}})

    tabela = pd.DataFrame(linhas)

    for coluna in features.COLUNAS_BASE + features.COLUNAS_COMMIT:
        if coluna not in tabela.columns:
            tabela[coluna] = np.nan

    return derivadas.acrescentar(tabela, features.COLUNAS_BASE)


# =============================================================
# Preparar Para o Modelo
# -------------------------------------------------------------
# Limpa a tabela com as médias do treino
# =============================================================
def preparar_para_o_modelo(tabela: pd.DataFrame,
                           pacote: dict) -> tuple[np.ndarray, str | None]:
    colunas = pacote["features"]
    matriz = tabela[colunas].apply(pd.to_numeric, errors="coerce")
    matriz = matriz.replace([np.inf, -np.inf], np.nan)

    aviso = None
    medias = pacote.get("medias")

    if medias is None:
        medias = {c: 0.0 for c in colunas}
        if matriz.isna().any().any():
            aviso = ("Modelo sem as médias do treino: valores faltantes "
                     "foram preenchidos com zero. Treine de novo.")

    return matriz.fillna(pd.Series(medias)).to_numpy(dtype=float), aviso


# =============================================================
# Percentis Exibidos
# -------------------------------------------------------------
# Calcula a posição de cada medida no repositório
# =============================================================
def percentis_exibidos(tabela: pd.DataFrame) -> pd.DataFrame:
    colunas = [c for c, _, _ in METRICAS_EXIBIDAS if c in tabela.columns]
    return tabela[colunas].rank(pct=True, method="average")


# =============================================================
# Valor Limpo
# -------------------------------------------------------------
# Converte um número para o formato do JSON
# =============================================================
def valor_limpo(valor):
    if valor is None or (isinstance(valor, float) and not np.isfinite(valor)):
        return None
    if isinstance(valor, (np.integer, int)):
        return int(valor)
    return round(float(valor), 3)


# =============================================================
# Dia do Instante
# -------------------------------------------------------------
# Converte um instante na data em formato ISO
# =============================================================
def dia_do_instante(instante: float) -> str:
    return (datetime.fromtimestamp(instante, tz=timezone.utc)
            .date().isoformat())


# =============================================================
# Descrever Commit
# -------------------------------------------------------------
# Os dados do commit que a tela mostra
# =============================================================
def descrever_commit(ultimo: dict) -> dict:
    return {
        "hash":        ultimo["hash"],
        "data":        dia_do_instante(ultimo["instante"]),
        "arquivos":    ultimo["commit_arquivos"],
        "adicionadas": ultimo["commit_adicionadas"],
        "removidas":   ultimo["commit_removidas"],
    }


# =============================================================
# Agrupar Commits
# -------------------------------------------------------------
# Os commits recentes, do mais para o menos arriscado
# =============================================================
def agrupar_commits(notas: dict[str, float], ultimos: dict,
                    referencia: float) -> dict:
    limite = referencia - config.JANELA_REVISAO_DIAS * 86400.0
    grupos = {}

    for caminho, nota in notas.items():
        ultimo = ultimos.get(caminho)
        if ultimo is None:
            continue

        grupo = grupos.setdefault(ultimo["hash"], {
            **descrever_commit(ultimo),
            "recente": ultimo["instante"] >= limite,
            "risco": 0.0, "avaliados": [],
        })
        grupo["risco"] = max(grupo["risco"], round(nota, 4))
        grupo["avaliados"].append(caminho)

    recentes = [g for g in grupos.values() if g.pop("recente")]
    recentes.sort(key=lambda g: (-g["risco"], g["hash"]))

    for grupo in recentes:
        grupo["avaliados"].sort(key=lambda c: (-notas[c], c))

    return {
        "janela_dias":   config.JANELA_REVISAO_DIAS,
        "referencia":    dia_do_instante(referencia),
        "recentes":      len(recentes),
        "fora_da_janela": len(grupos) - len(recentes),
        "commits":       recentes[:config.COMMITS_PARA_REVISAR],
    }


# =============================================================
# Analisar
# -------------------------------------------------------------
# A Frente 2 inteira: endereço entra, commits para revisar saem
# =============================================================
def analisar(endereco: str, ramo: str | None = None,
             ao_progresso=None) -> dict:
    inicio = time.time()
    repositorio, ramo_da_url = interpretar_endereco(endereco)
    ramo = ramo or ramo_da_url

    faixas = {"clonando": (0.0, 0.25), "medindo": (0.25, 0.70),
              "historico": (0.70, 0.95), "prevendo": (0.95, 1.0)}

    def etapa(nome: str):
        comeco, fim = faixas[nome]

        def avisar(fracao: float, mensagem: str) -> None:
            if ao_progresso:
                ao_progresso(nome, comeco + (fim - comeco) * fracao,
                             mensagem)

        return avisar

    pacote = carregar_modelo()
    pasta = (RAIZ / config.PASTA_CLONES / "web"
             / f"{repositorio.replace('/', '__')}__{uuid.uuid4().hex[:8]}")
    pasta.parent.mkdir(parents=True, exist_ok=True)

    try:
        etapa("clonando")(0.0, f"clonando {repositorio}")
        clonar(repositorio, ramo, pasta)

        commit = rodar_git(["-C", str(pasta), "rev-parse", "HEAD"],
                           timeout=30).stdout.decode().strip()
        ramo_real = rodar_git(["-C", str(pasta), "branch", "--show-current"],
                              timeout=30).stdout.decode().strip()

        caminhos = listar_arquivos_python(pasta)
        if not caminhos:
            raise ErroDeAnalise("Nenhum arquivo .py neste repositório.")

        medidos, situacoes = medir_codigo(pasta, caminhos, etapa("medindo"))
        if not medidos:
            raise ErroDeAnalise(
                "Nenhum arquivo pôde ser avaliado: todos são testes, "
                "estão fora do escopo ou não têm funções.")

        historicos, ultimos, referencia, total_commits = medir_historico(
            pasta, set(medidos), etapa("historico"))

    finally:
        apagar_pasta(pasta)

    etapa("prevendo")(0.0, "aplicando o modelo")
    tabela = montar_tabela(repositorio, medidos, historicos, ultimos)
    matriz, aviso = preparar_para_o_modelo(tabela, pacote)
    tabela["probabilidade"] = pacote["modelo"].predict_proba(matriz)[:, 1]
    tabela["posicao"] = tabela["probabilidade"].rank(
        ascending=False, method="first").astype(int)

    percentis = percentis_exibidos(tabela)
    exibidas = [c for c, _, _ in METRICAS_EXIBIDAS if c in tabela.columns]

    por_caminho = {}
    for indice, linha in tabela.iterrows():
        por_caminho[linha["arquivo"]] = {
            "probabilidade": round(float(linha["probabilidade"]), 4),
            "posicao": int(linha["posicao"]),
            "ultimo_commit": (descrever_commit(ultimos[linha["arquivo"]])
                              if linha["arquivo"] in ultimos else None),
            "metricas": {c: [valor_limpo(linha[c]),
                             valor_limpo(percentis.at[indice, c])]
                         for c in exibidas},
        }

    arquivos = []
    for caminho in caminhos:
        item = {"caminho": caminho, "situacao": situacoes[caminho]}
        item.update(por_caminho.get(caminho, {}))
        arquivos.append(item)

    probabilidades = tabela["probabilidade"]
    contagem = pd.Series(situacoes).value_counts().to_dict()
    etapa("prevendo")(1.0, "pronto")

    return {
        "repositorio": repositorio,
        "ramo":        ramo_real or ramo,
        "commit":      commit,
        "commits":     total_commits,
        "modelo":      {"nome": pacote["nome"], "limiar": pacote["limiar"]},
        "resumo": {
            "arquivos_py":   len(caminhos),
            "avaliados":     int(len(tabela)),
            "risco_alto":    int((probabilidades >= pacote["limiar"]).sum()),
            "risco_maximo":  round(float(probabilidades.max()), 4),
            "risco_medio":   round(float(probabilidades.mean()), 4),
            "por_situacao":  {k: int(v) for k, v in contagem.items()},
        },
        "metricas_exibidas": [
            {"coluna": c, "rotulo": r, "melhor": m}
            for c, r, m in METRICAS_EXIBIDAS if c in exibidas],
        "situacoes": SITUACOES,
        "revisao":   agrupar_commits(
            dict(zip(tabela["arquivo"], tabela["probabilidade"])),
            ultimos, referencia),
        "arquivos":  arquivos,
        "aviso":     aviso,
        "duracao_s": round(time.time() - inicio, 1),
    }


# =============================================================
# Mostrar no Terminal
# -------------------------------------------------------------
# Uso da Frente 2 sem a web
# =============================================================
def mostrar(resultado: dict, quantos: int = 20) -> None:
    resumo = resultado["resumo"]
    print(f"\n  {resultado['repositorio']} @ {resultado['ramo']} "
          f"({resultado['commit'][:10]}, {resultado['commits']} commits)")
    print(f"  {resumo['avaliados']} de {resumo['arquivos_py']} arquivos "
          f"avaliados, {resumo['risco_alto']} acima do limiar, "
          f"{resultado['duracao_s']} s")
    if resultado["aviso"]:
        print(f"  AVISO: {resultado['aviso']}")

    revisao = resultado["revisao"]
    print(f"\n  Commits para revisar: {revisao['recentes']} nos "
          f"{revisao['janela_dias']} dias até {revisao['referencia']}, "
          f"{revisao['fora_da_janela']} mais antigos fora da lista")
    for commit in revisao["commits"][:quantos]:
        print(f"    {100 * commit['risco']:>5.1f}%  {commit['hash'][:10]}  "
              f"{commit['data']}  {commit['arquivos']} arquivos, "
              f"+{commit['adicionadas']} -{commit['removidas']}")

    avaliados = sorted((a for a in resultado["arquivos"]
                        if a["situacao"] == "avaliado"),
                       key=lambda a: a["posicao"])

    print(f"\n  {'#':>4} {'risco':>7}  arquivo")
    for arquivo in avaliados[:quantos]:
        print(f"  {arquivo['posicao']:>4} "
              f"{100 * arquivo['probabilidade']:>6.1f}%  {arquivo['caminho']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("uso: python frente2_predicao/prever.py dono/repositorio [ramo]")

    def progresso(etapa: str, fracao: float, mensagem: str) -> None:
        print(f"\r  {100 * fracao:5.1f}%  {etapa:<10} {mensagem:<40}",
              end="", flush=True)

    try:
        mostrar(analisar(sys.argv[1], sys.argv[2] if len(sys.argv) > 2
                         else None, progresso))
    except ErroDeAnalise as erro:
        raise SystemExit(f"\n  {erro}") from None

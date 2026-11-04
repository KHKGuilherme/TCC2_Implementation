# frente2_predicao\prever.py
"""
Frente 2 — avalia um repositório inédito, arquivo por arquivo.

  endereço -> clone -> mede cada .py -> lê o histórico -> derivadas
           -> mesmo pré-processamento do treino -> modelo -> probabilidade

Usa o MESMO extrator da Frente 1 para tudo que vira feature. A única
peça própria daqui é a leitura do histórico (historico_rapido.py),
que entrega ao extrator os mesmos dados que o PyDriller entregaria,
só que de uma vez.

Cada arquivo é fotografado no último commit do repositório: é o
estado que o usuário tem hoje nas mãos.

CMD -> python frente2_predicao/prever.py psf/black
       mostra os arquivos mais arriscados no terminal
"""

import os
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
import warnings
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import config
from extrator import derivadas, features, metricas_codigo, metricas_historico
from frente2_predicao import historico_rapido


# =============================================================
# O QUE A TELA MOSTRA DE CADA ARQUIVO
# =============================================================

# Medidas exibidas no painel do arquivo, com o percentil dele
# dentro do repositório. "melhor" diz para que lado o valor é bom,
# só para a tela pintar a barra; o modelo não usa isso.
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

# Por que um arquivo não recebeu nota. A tela usa o texto.
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

# dono/repo, com ou sem https://github.com/, com ou sem .git, e
# opcionalmente /tree/<ramo> no fim, como o navegador mostra
PADRAO_ENDERECO = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:github\.com/)?"
    r"(?P<dono>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?"
    r"(?:/tree/(?P<ramo>[^?#]+))?/?$")

# O mesmo critério de derivadas.acrescentar_caminho
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

# -------------------------------------------------------------
# Carregar Modelo
# -------------------------------------------------------------
@lru_cache(maxsize=1)
def carregar_modelo() -> dict:
    # Uma vez por processo: o servidor web chama isto a cada
    # análise, e ler o joblib leva alguns segundos
    caminho = RAIZ / config.ARQUIVO_MODELO

    if not caminho.exists():
        raise ErroDeAnalise(
            f"Modelo não encontrado em {config.ARQUIVO_MODELO}. "
            f"Rode a Frente 1 primeiro.")

    pacote = joblib.load(caminho)

    # O modelo espera as colunas na ordem do treino. Se o config
    # mudou depois, o extrator produziria outra lista, e o modelo
    # receberia valores trocados sem reclamar.
    if list(pacote["features"]) != list(features.FEATURES):
        raise ErroDeAnalise(
            "O modelo foi treinado com outra configuração de features. "
            "Treine de novo com a Frente 1 ou volte o config.py.")

    return pacote


# -------------------------------------------------------------
# Importancias
# -------------------------------------------------------------
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


# -------------------------------------------------------------
# Descrever Modelo
# -------------------------------------------------------------
def descrever_modelo() -> dict:
    pacote = carregar_modelo()

    return {
        "nome":        pacote["nome"],
        "features":    len(pacote["features"]),
        "limiar":      pacote["limiar"],
        "metricas":    pacote.get("metricas"),
        "treinado_em": pacote.get("treinado_em"),
        "repositorios_treino": pacote.get("repositorios_treino"),
        # Modelo gravado antes das médias irem para o joblib
        "tem_medias":  "medias" in pacote,
        "importancias": importancias(pacote),
    }


# =============================================================
# GIT
# =============================================================

# -------------------------------------------------------------
# Rodar Git
# -------------------------------------------------------------
def rodar_git(argumentos: list[str], timeout: int) -> subprocess.CompletedProcess:
    # GIT_TERMINAL_PROMPT=0: repositório privado ou inexistente
    # pede usuário e senha, e sem isto o servidor ficaria parado
    # esperando alguém digitar
    ambiente = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    return subprocess.run(["git", *argumentos], capture_output=True,
                          timeout=timeout, env=ambiente)


# -------------------------------------------------------------
# Motivo do Erro do Git
# -------------------------------------------------------------
def motivo_do_git(saida: bytes) -> str:
    texto = saida.decode("utf-8", errors="replace")

    if "not found" in texto.lower() or "could not read" in texto.lower():
        return "Repositório não encontrado, ou privado."

    for linha in texto.splitlines():
        if linha.startswith(("fatal:", "error:")):
            return linha[:200]

    return texto.strip()[:200] or "o git falhou sem mensagem"


# -------------------------------------------------------------
# Commit Remoto
# -------------------------------------------------------------
def commit_remoto(repositorio: str, ramo: str | None) -> str | None:
    """O hash da ponta do ramo, sem clonar. None se não der.

    Serve para reaproveitar uma análise já feita: se o commit não
    mudou, o resultado também não muda.
    """
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


# -------------------------------------------------------------
# Clonar
# -------------------------------------------------------------
def clonar(repositorio: str, ramo: str | None, destino: Path) -> None:
    # Pasta vazia para os hooks, pelo mesmo motivo do montador da
    # Frente 1: um init.templateDir com post-checkout aborta o clone
    sem_hooks = RAIZ / config.PASTA_CLONES / "_sem_hooks"
    sem_hooks.mkdir(parents=True, exist_ok=True)

    comando = ["-c", f"core.hooksPath={sem_hooks}",
               "clone", "--quiet", f"--template={sem_hooks}",
               # Só o ramo analisado: o histórico percorrido é o
               # dele, os outros ramos seriam download à toa
               "--single-branch", "--no-tags"]

    if ramo:
        comando += ["--branch", ramo]

    # Sem --depth: um clone raso deixaria as features de histórico
    # todas iguais a 1
    comando += [f"https://github.com/{repositorio}.git", str(destino)]

    try:
        resultado = rodar_git(comando, timeout=1800)
    except subprocess.TimeoutExpired:
        raise ErroDeAnalise(
            "O clone passou de 30 minutos e foi interrompido.") from None

    if resultado.returncode != 0:
        raise ErroDeAnalise(motivo_do_git(resultado.stderr))


# -------------------------------------------------------------
# Apagar Pasta
# -------------------------------------------------------------
def apagar_pasta(pasta: Path) -> None:
    # No Windows o git grava os objetos como somente leitura, e o
    # rmtree comum apaga metade e desiste em silêncio. Aqui cada
    # arquivo recusado perde a marca e é apagado de novo.
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


# -------------------------------------------------------------
# Limpar Clones Orfaos
# -------------------------------------------------------------
def limpar_clones_orfaos() -> None:
    """Apaga o que sobrou de análises interrompidas.

    Só pode ser chamada com nenhuma análise rodando: apaga tudo
    em clones/web. O servidor chama quando a fila está vazia.
    """
    pasta = RAIZ / config.PASTA_CLONES / "web"
    if pasta.exists():
        for sobra in pasta.iterdir():
            apagar_pasta(sobra)


# -------------------------------------------------------------
# Listar Arquivos Python
# -------------------------------------------------------------
def listar_arquivos_python(pasta: Path) -> list[str]:
    resultado = rodar_git(["-C", str(pasta), "-c", "core.quotepath=off",
                           "ls-files", "-z", "--", "*.py"], timeout=120)

    return sorted(c for c in resultado.stdout.decode("utf-8", "replace")
                  .split("\0") if c)


# =============================================================
# MEDIÇÃO
# =============================================================

# -------------------------------------------------------------
# Classificar Caminho
# -------------------------------------------------------------
def classificar_caminho(caminho: str) -> str | None:
    """A situação decidida só pelo nome, ou None se precisa medir."""
    nome = caminho.rsplit("/", 1)[-1]

    # Os mesmos filtros do montador da Frente 1
    if any(caminho.startswith(p) for p in config.PASTAS_IGNORADAS):
        return "ignorado"
    if nome in config.ARQUIVOS_IGNORADOS:
        return "ignorado"

    if (PASTA_DE_TESTE.search(caminho) or nome.startswith("test_")
            or nome.endswith("_test.py")):
        return "teste"

    return None


# -------------------------------------------------------------
# Medir Um Arquivo
# -------------------------------------------------------------
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

    # O mesmo filtro de aviso do montador: código antigo com "\d"
    # sem r"" encheria o log do servidor
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


# -------------------------------------------------------------
# Medir Codigo
# -------------------------------------------------------------
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


# -------------------------------------------------------------
# Medir Historico
# -------------------------------------------------------------
def medir_historico(pasta: Path, caminhos: set[str],
                    avisar) -> tuple[dict, int]:
    total = historico_rapido.contar_commits(pasta)
    acumulado = {}
    ultimo = 0.0
    lidos = 0

    # aplicar_commit e fotografar são os do extrator, sem cópia:
    # é isso que garante a mesma conta do treino
    for commit in historico_rapido.percorrer_commits(pasta):
        metricas_historico.aplicar_commit(acumulado, commit)
        ultimo = commit.committer_date.timestamp()
        lidos += 1

        if lidos % 500 == 0:
            avisar(lidos / max(total, 1), f"{lidos} de {total} commits")

    avisar(1.0, f"{total} de {total} commits")

    return metricas_historico.fotografar(acumulado, caminhos, ultimo), total


# =============================================================
# PREVISÃO
# =============================================================

# -------------------------------------------------------------
# Montar Tabela
# -------------------------------------------------------------
def montar_tabela(repositorio: str, medidos: dict,
                  historicos: dict) -> pd.DataFrame:
    linhas = []
    for caminho, medidas in medidos.items():
        linhas.append({"repositorio": repositorio, "arquivo": caminho,
                       **medidas, **historicos.get(caminho, {})})

    tabela = pd.DataFrame(linhas)

    # Coluna ausente vira vazio, e vazio é preenchido com a média
    # do treino logo adiante
    for coluna in features.COLUNAS_BASE:
        if coluna not in tabela.columns:
            tabela[coluna] = np.nan

    # Percentil dentro do repositório: aqui o repositório é este,
    # e todos os arquivos medidos entram na conta
    return derivadas.acrescentar(tabela, features.COLUNAS_BASE)


# -------------------------------------------------------------
# Preparar Para o Modelo
# -------------------------------------------------------------
def preparar_para_o_modelo(tabela: pd.DataFrame,
                           pacote: dict) -> tuple[np.ndarray, str | None]:
    colunas = pacote["features"]
    matriz = tabela[colunas].apply(pd.to_numeric, errors="coerce")
    matriz = matriz.replace([np.inf, -np.inf], np.nan)

    aviso = None
    medias = pacote.get("medias")

    if medias is None:
        # Modelo antigo, gravado antes das médias irem junto
        medias = {c: 0.0 for c in colunas}
        if matriz.isna().any().any():
            aviso = ("Modelo sem as médias do treino: valores faltantes "
                     "foram preenchidos com zero. Treine de novo.")

    return matriz.fillna(pd.Series(medias)).to_numpy(dtype=float), aviso


# -------------------------------------------------------------
# Percentis Exibidos
# -------------------------------------------------------------
def percentis_exibidos(tabela: pd.DataFrame) -> pd.DataFrame:
    colunas = [c for c, _, _ in METRICAS_EXIBIDAS if c in tabela.columns]
    return tabela[colunas].rank(pct=True, method="average")


# -------------------------------------------------------------
# Valor Limpo
# -------------------------------------------------------------
def valor_limpo(valor):
    if valor is None or (isinstance(valor, float) and not np.isfinite(valor)):
        return None
    if isinstance(valor, (np.integer, int)):
        return int(valor)
    return round(float(valor), 3)


# =============================================================
# Analisar
# -------------------------------------------------------------
# A Frente 2 inteira: endereço entra, nota por arquivo sai
# =============================================================
def analisar(endereco: str, ramo: str | None = None,
             ao_progresso=None) -> dict:
    """Devolve um dicionário pronto para virar JSON.

    ao_progresso(etapa, fracao, mensagem) é chamado durante o
    trabalho, com fracao de 0 a 1 sobre a análise inteira.
    """
    inicio = time.time()
    repositorio, ramo_da_url = interpretar_endereco(endereco)
    ramo = ramo or ramo_da_url

    # Pesos aproximados de cada etapa no tempo total, só para a
    # barra de progresso andar de forma honesta
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

        historicos, total_commits = medir_historico(
            pasta, set(medidos), etapa("historico"))

    finally:
        # Sempre, inclusive com erro: um clone esquecido por análise
        # enche o disco em poucos dias de uso
        apagar_pasta(pasta)

    etapa("prevendo")(0.0, "aplicando o modelo")
    tabela = montar_tabela(repositorio, medidos, historicos)
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
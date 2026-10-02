"""
montar_dataset.py
=================

Monta dados/dataset.csv a partir do Defectors.

O Defectors
* 213 mil arquivos de 24 projetos
* 93 mil defeituosos e 120 mil limpo.


A montagem acontece em duas fases, nessa ordem:

    Fase 1   Lê os parquets e calcula as 6 features de código a partir do conteúdo que já vem no dataset.

    Fase 2   Clona cada repositório e calcula as 3 features de histórico, medindo o passado de cada arquivo até o commit em que ele foi rotulado.
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI))

import config
import divisao
from extrator import features, metricas_codigo, metricas_historico


# Colunas do parquet que o programa usa.
COLUNAS_DO_PARQUET = ["repo", "commit", "filepath", "content", "induce_bug"]


# =============================================================
# Selecionar Parquets
# -------------------------------------------------------------
#  Acha os arquivos úteis do Defectors
# =============================================================
def selecionar_parquets(pasta: Path) -> list[Path]:
    encontrados = sorted(pasta.rglob("*.parquet"))
    uteis = []

    for caminho in encontrados:
        try:
            colunas = set(pq.ParquetFile(caminho).schema_arrow.names)
        except Exception:
            continue
        if {"filepath", "content", "induce_bug"}.issubset(colunas):
            uteis.append(caminho)

    return uteis


# =============================================================
# Exigir Parquets
# -------------------------------------------------------------
# Garante que o Defectors está no lugar
# =============================================================
def exigir_parquets() -> list[Path]:
    """Devolve os parquets úteis, ou interrompe com instruções."""
    parquets = selecionar_parquets(config.PASTA_DEFECTORS)

    if not parquets:
        raise SystemExit(
            f"Nenhum parquet de predição por arquivo em "
            f"{config.PASTA_DEFECTORS}/.\n"
            f"Baixe defectors.zip de https://zenodo.org/records/7708984 "
            f"e descompacte nessa pasta."
        )

    return parquets


# =============================================================
# Repositorio Incluido
# -------------------------------------------------------------
#  Decide se um repositório entra
# =============================================================
def repositorio_incluido(repositorio: str) -> bool:
    if not config.REPOSITORIOS_INCLUIDOS:
        return True

    nome = repositorio.lower()
    alvos = tuple(config.REPOSITORIOS_INCLUIDOS) + tuple(
        config.REPOSITORIOS_TESTE)

    return any(alvo.lower() in nome for alvo in alvos)


# =============================================================
# Arquivo Ignorado
# -------------------------------------------------------------
# Aplica os filtros de caminho
# =============================================================
def arquivo_ignorado(caminho: str) -> bool:
    """Diz se o arquivo deve ficar fora do dataset pelo caminho.

    Descarta documentação, exemplos e arquivos de empacotamento.
    Eles não são código de produção: mudam por motivo
    administrativo, e um arquivo de configuração com centenas de
    revisões ensinaria o modelo a associar movimentação a defeito
    onde não há.
    """
    normalizado = caminho.replace("\\", "/")

    if any(normalizado.startswith(p) for p in config.PASTAS_IGNORADAS):
        return True

    if Path(normalizado).name in config.ARQUIVOS_IGNORADOS:
        return True

    return False


# =============================================================
# Rotulo do Registro
# -------------------------------------------------------------
# Converte induce_bug em rótulo
# =============================================================
def rotulo_do_registro(induce_bug) -> tuple[int, int]:
    if induce_bug is None:
        return 0, 0

    try:
        quantidade = len(induce_bug)
    except TypeError:
        return 0, 0

    return quantidade, int(quantidade > 0)


# =============================================================
# Listar Repositorios
# ------------------------------------------------------------- 
# Modo de consulta, sem clonar nem medir
# =============================================================
def listar_repositorios() -> None:
    parquets = exigir_parquets()

    print("=" * 70)
    print("REPOSITÓRIOS DISPONÍVEIS NO DEFECTORS")
    print("=" * 70)
    print(f"\n  lendo {len(parquets)} parquets "
          f"(apenas as colunas de nome e rótulo)\n")

    partes = []
    for caminho in parquets:
        for lote in pq.ParquetFile(caminho).iter_batches(
                batch_size=20000, columns=["repo", "induce_bug"]):
            tabela = lote.to_pandas()
            tabela["defeituoso"] = [
                rotulo_do_registro(v)[1] for v in tabela["induce_bug"]]
            partes.append(tabela[["repo", "defeituoso"]])
        print(f"    {caminho.name}")

    dados = pd.concat(partes, ignore_index=True)
    resumo = dados.groupby("repo")["defeituoso"].agg(["size", "sum", "mean"])
    resumo = resumo.sort_values("size", ascending=False)

    print(f"\n  {len(dados)} linhas, {len(resumo)} repositórios\n")
    print(f"    {'nome exato (use este no config)':<34} {'linhas':>8} "
          f"{'defeituosos':>12} {'%':>7} {'no escopo':>10}")

    for nome, linha in resumo.iterrows():
        dentro = "sim" if repositorio_incluido(nome) else "-"
        print(f"    {nome:<34} {int(linha['size']):>8} "
              f"{int(linha['sum']):>12} {100 * linha['mean']:>6.1f}% "
              f"{dentro:>10}")

    print(f"\n  Escopo atual: "
          f"{', '.join(config.REPOSITORIOS_INCLUIDOS) or 'todos'}")
    print(f"  Reservados para teste: "
          f"{', '.join(config.REPOSITORIOS_TESTE)}")
    print("\n  Ajuste REPOSITORIOS_INCLUIDOS e REPOSITORIOS_TESTE no "
          "config.py\n  usando os nomes exatos da coluna acima.\n")


# =============================================================
# Medir Codigo
# -------------------------------------------------------------
# Fase 1: lê os parquets e mede o código
# =============================================================
def medir_codigo() -> pd.DataFrame:
    parquets = exigir_parquets()

    print(f"  {len(parquets)} parquets encontrados:")
    for caminho in parquets:
        print(f"    {caminho.name}  "
              f"({caminho.stat().st_size / 1e6:.0f} MB)")

    cache = {}
    contagem = {"lidas": 0, "fora_do_escopo": 0, "caminho_ignorado": 0,
                "sem_conteudo": 0, "grande_demais": 0,
                "nao_faz_parse": 0, "sem_funcoes": 0}
    linhas = []

    for caminho in parquets:
        print(f"\n  lendo {caminho.name}", end=" ", flush=True)

        for lote in pq.ParquetFile(caminho).iter_batches(
                batch_size=config.LINHAS_POR_LOTE,
                columns=COLUNAS_DO_PARQUET):

            for registro in lote.to_pandas().itertuples(index=False):
                contagem["lidas"] += 1

                if not repositorio_incluido(registro.repo):
                    contagem["fora_do_escopo"] += 1
                    continue

                if arquivo_ignorado(registro.filepath):
                    contagem["caminho_ignorado"] += 1
                    continue

                codigo = registro.content
                if isinstance(codigo, bytes):
                    codigo = codigo.decode("utf-8", errors="ignore")
                if not isinstance(codigo, str) or not codigo.strip():
                    contagem["sem_conteudo"] += 1
                    continue

                if len(codigo) > config.TAMANHO_MAXIMO_BYTES:
                    contagem["grande_demais"] += 1
                    continue

                chave = hash(codigo)
                if chave in cache:
                    medidas = cache[chave]
                else:
                    medidas = medir_um_arquivo(registro.filepath, codigo)
                    cache[chave] = medidas

                if medidas == "nao_faz_parse":
                    contagem["nao_faz_parse"] += 1
                    continue
                if medidas == "sem_funcoes":
                    contagem["sem_funcoes"] += 1
                    continue

                quantidade, rotulo = rotulo_do_registro(registro.induce_bug)

                linhas.append({
                    "repositorio": registro.repo,
                    "arquivo":     registro.filepath.replace("\\", "/"),
                    "commit":      str(registro.commit),
                    **medidas,
                    "linhas_defeituosas": quantidade,
                    features.COLUNA_ALVO: rotulo,
                })

            print(".", end="", flush=True)

    relatar_fase1(contagem, len(linhas))

    if not linhas:
        raise SystemExit(
            "Nenhuma linha medida. Rode com --listar e confira "
            "REPOSITORIOS_INCLUIDOS no config.py contra os nomes "
            "que aparecem no dataset."
        )

    tabela = pd.DataFrame(linhas)

    return tabela.drop_duplicates(
        subset=["repositorio", "arquivo", "commit"])


# =============================================================
# Medir um arquivo
# -------------------------------------------------------------
# Mede ou diz por que não mediu
# =============================================================
def medir_um_arquivo(caminho: str, codigo: str):

    quantidade = metricas_codigo.contar_funcoes(caminho, codigo)

    if quantidade is None:
        return "nao_faz_parse"
    if quantidade == 0:
        return "sem_funcoes"

    medidas = metricas_codigo.medir(caminho, codigo)
    return medidas if medidas is not None else "nao_faz_parse"


# =============================================================
# Relatar Fase 1
# -------------------------------------------------------------
# Imprime o resumo da leitura do parquet
# =============================================================
def relatar_fase1(contagem: dict, medidas: int) -> None:
    """Mostra quantas linhas entraram e por que as outras saíram."""
    print("\n\n  Fase 1 concluída.")
    print(f"    linhas lidas do parquet    : {contagem['lidas']}")
    print(f"    fora do escopo configurado : {contagem['fora_do_escopo']}")
    print(f"    caminho ignorado           : {contagem['caminho_ignorado']}")
    print(f"    sem conteúdo               : {contagem['sem_conteudo']}")
    print(f"    maior que "
          f"{config.TAMANHO_MAXIMO_BYTES // 1024} KB          "
          f": {contagem['grande_demais']}")
    print(f"    não faz parse              : {contagem['nao_faz_parse']}")
    print(f"    sem nenhuma função         : {contagem['sem_funcoes']}")
    print(f"    medidas                    : {medidas}")


# =============================================================
# Clonar
# ------------------------------------------------------------- 
# Baixa um repositório com o histórico completo
# =============================================================
def clonar(repositorio: str, destino: Path) -> bool:

    if (destino / ".git").exists():
        return True

    destino.parent.mkdir(parents=True, exist_ok=True)

    resultado = subprocess.run(
        ["git", "clone", "--quiet",
         f"https://github.com/{repositorio}.git", str(destino)],
        capture_output=True, text=True, timeout=7200,
    )

    if resultado.returncode != 0:
        print(f"falha: {resultado.stderr.strip()[:100]}")
        return False

    return True


# =============================================================
# Resolver Commits
# -------------------------------------------------------------
# Converte hashes abreviados em completos
# =============================================================
def resolver_commits(pasta: Path, hashes: list[str]) -> dict[str, str]:

    if not hashes:
        return {}

    resultado = subprocess.run(
        ["git", "-C", str(pasta), "cat-file", "--batch-check"],
        input="\n".join(hashes) + "\n",
        capture_output=True, text=True, timeout=600,
    )

    mapa = {}
    for informado, linha in zip(hashes, resultado.stdout.splitlines()):
        partes = linha.split()

        if len(partes) >= 2 and partes[1] == "commit":
            mapa[informado] = partes[0]

    return mapa


# =============================================================
# Medir Historico do Repositório
# -------------------------------------------------------------
# Fase 2 para um repositório
# =============================================================
def medir_historico_do_repo(repositorio: str,
                            tabela: pd.DataFrame) -> pd.DataFrame | None:

    pasta = config.PASTA_CLONES / repositorio.replace("/", "__")

    print(f"  {repositorio:<32} clonando... ", end="", flush=True)
    if not clonar(repositorio, pasta):
        return None

    informados = sorted(tabela["commit"].unique())
    mapa = resolver_commits(pasta, informados)

    if not mapa:
        print("nenhum commit encontrado no repositório")
        return None

    print(f"{len(mapa)}/{len(informados)} commits ", end="", flush=True)

    caminhos_por_commit: dict[str, set[str]] = {}
    for informado, arquivo in zip(tabela["commit"], tabela["arquivo"]):
        completo = mapa.get(informado)
        if completo:
            caminhos_por_commit.setdefault(completo, set()).add(arquivo)

    total = len(caminhos_por_commit)
    inicio = time.time()

    def progresso(feitas: int, pendentes: int) -> None:

        if total >= 10 and feitas % max(1, total // 10) == 0:
            print(".", end="", flush=True)

    fotografias = metricas_historico.medir_nos_commits(
        pasta, caminhos_por_commit, progresso)

    print(f" {time.time() - inicio:.0f}s ", end="", flush=True)

    linhas = []
    sem_historico = 0

    for linha in tabela.to_dict("records"):
        completo = mapa.get(linha["commit"])
        medidas = fotografias.get(completo, {}).get(linha["arquivo"])

        if medidas is None:
            sem_historico += 1
            continue

        linha["commit"] = completo
        linha.update(medidas)
        linhas.append(linha)

    if not linhas:
        print("nenhuma linha com histórico")
        return None

    print(f"{len(linhas)} linhas ({sem_historico} sem histórico)")

    if config.APAGAR_CLONES:
        shutil.rmtree(pasta, ignore_errors=True)

    return pd.DataFrame(linhas)


# =============================================================
# Montar
# -------------------------------------------------------------
# Executa as duas fases e grava o dataset
# =============================================================
def montar() -> pd.DataFrame:

    features.conferir_sem_vazamento()

    print("=" * 70)
    print("MONTAGEM DO DATASET")
    print("=" * 70)
    print(f"\n  origem  : {config.PASTA_DEFECTORS}/")
    print(f"  destino : {config.ARQUIVO_DATASET}")
    print(f"  escopo  : "
          f"{', '.join(config.REPOSITORIOS_INCLUIDOS) or 'todos'}")
    print(f"  divisão : {divisao.descrever_divisao()}")

    inicio = time.time()
    config.PASTA_PARCIAIS.mkdir(parents=True, exist_ok=True)

    print("\n" + "-" * 70)
    print("FASE 1 — métricas de código (a partir do parquet)")
    print("-" * 70 + "\n")
    codigo = medir_codigo()

    print("\n" + "-" * 70)
    print("FASE 2 — métricas de histórico (a partir dos clones)")
    print("-" * 70 + "\n")

    partes, falharam = [], []

    for repositorio, tabela in codigo.groupby("repositorio"):
        parcial = (config.PASTA_PARCIAIS
                   / f"{repositorio.replace('/', '__')}.csv")

        if parcial.exists() and not config.FORCAR_MONTAGEM:
            pronto = pd.read_csv(parcial)
            print(f"  {repositorio:<32} reaproveitado, "
                  f"{len(pronto)} linhas")
            partes.append(pronto)
            continue

        resultado = medir_historico_do_repo(repositorio, tabela)

        if resultado is None:
            falharam.append(repositorio)
        else:
            resultado.to_csv(parcial, index=False, encoding="utf-8")
            partes.append(resultado)

    if not partes:
        raise SystemExit("Nenhum repositório processado.")

    dataset = pd.concat(partes, ignore_index=True)

    # Remove linhas de parciais antigos que saíram do escopo atual.
    dentro = dataset["repositorio"].map(repositorio_incluido)
    if not dentro.all():
        fora = sorted(dataset.loc[~dentro, "repositorio"].unique())
        print(f"\n  {int((~dentro).sum())} linhas de parciais antigos "
              f"estão fora do escopo e foram removidas: "
              f"{', '.join(fora)}")
        dataset = dataset[dentro].reset_index(drop=True)

    dataset[features.COLUNA_PARTICAO] = divisao.dividir(dataset)

    features.conferir_contrato(dataset.columns)
    dataset = dataset[features.COLUNAS_CSV]

    config.PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(config.ARQUIVO_DATASET, index=False, encoding="utf-8")

    resumir(dataset, falharam, time.time() - inicio)
    return dataset


# =============================================================
# Resumir
# -------------------------------------------------------------
# Imprime o relatório final da montagem
# =============================================================
def resumir(dataset: pd.DataFrame, falharam: list[str],
            segundos: float) -> None:
    alvo = dataset[features.COLUNA_ALVO]

    print("\n" + "=" * 70)
    print(f"DATASET GRAVADO: {config.ARQUIVO_DATASET}")
    print("=" * 70)
    print(f"\n  {len(dataset)} linhas, {len(dataset.columns)} colunas")
    print(f"  {dataset.repositorio.nunique()} repositórios, "
          f"{dataset.commit.nunique()} commits")
    print(f"  {alvo.sum()} defeituosos ({100 * alvo.mean():.1f}%)")
    print(f"  {segundos:.0f} segundos, "
          f"{config.ARQUIVO_DATASET.stat().st_size / 1e6:.1f} MB")

    if falharam:
        print(f"\n  não processados: {', '.join(falharam)}")

    print(f"\n  Divisão ({divisao.descrever_divisao()}):")
    for particao, grupo in dataset.groupby(features.COLUNA_PARTICAO):
        a = grupo[features.COLUNA_ALVO]
        print(f"    {particao:<8} {len(grupo):>7} linhas, "
              f"{a.sum():>6} defeituosos ({100 * a.mean():.1f}%), "
              f"{grupo.repositorio.nunique()} repositórios")

    print("\n  Por repositório:")
    print(f"    {'repositório':<32} {'linhas':>7} {'%defeito':>9} "
          f"{'rev.méd':>8}  partições")
    for nome, grupo in dataset.groupby("repositorio"):
        a = grupo[features.COLUNA_ALVO]
        marcas = "/".join(sorted(grupo[features.COLUNA_PARTICAO].unique()))
        print(f"    {nome:<32} {len(grupo):>7} {100 * a.mean():>8.1f}% "
              f"{grupo.revisoes.mean():>8.1f}  {marcas}")
    print()


# =============================================================
# Main
# -------------------------------------------------------------
# lê os argumentos e executa o modo pedido
# =============================================================
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listar", action="store_true",
                        help="só mostra os repositórios do Defectors, "
                             "com os nomes exatos e a contagem de linhas")
    argumentos = parser.parse_args()

    config.conferir_local()

    if argumentos.listar:
        listar_repositorios()
    else:
        montar()


if __name__ == "__main__":
    main()
"""
Monta dados/dataset.csv a partir do Defectors.

CMD -> python frente1_treinamento/montar_dataset.py
       --listar             mostra os repositórios e os nomes exatos
       --repo NOME          processa só este repositório e grava o CSV dele
       --so-prontos         grava o dataset com os projetos já feitos
       --amostra N          monta só N linhas, sem gravar cópia
       --extrair-amostra N  grava em disco uma cópia reduzida
"""

import argparse
import gc
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import time
import warnings
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI))

import config
import divisao
import historico_retomavel
from extrator import features, metricas_codigo, metricas_historico


COLUNAS_DE_CHAVE = ["repo", "commit", "filepath"]

APELIDOS_DO_ROTULO = ("lines", "induce_bug", "bug_lines")

ROTULO_PADRAO = "linhas_com_defeito"

ESQUEMA_SEPARADO = pa.schema([
    ("repo",               pa.string()),
    ("commit",             pa.string()),
    ("filepath",           pa.string()),
    ("content",            pa.binary()),
    (ROTULO_PADRAO,        pa.list_(pa.int64())),
    ("particao_defectors", pa.string()),
])


# =============================================================
# Nome do Rotulo
# -------------------------------------------------------------
# Descobre como a coluna de rótulo se chama neste parquet
# =============================================================
def nome_do_rotulo(caminho: Path) -> str:
    colunas = pq.ParquetFile(caminho).schema_arrow.names

    for apelido in APELIDOS_DO_ROTULO:
        if apelido in colunas:
            return apelido

    raise SystemExit(
        f"Não achei a coluna de rótulo em {caminho.name}.\n"
        f"Procurei por: {', '.join(APELIDOS_DO_ROTULO)}\n"
        f"O arquivo tem: {', '.join(colunas)}\n"
        f"Acrescente o nome certo em APELIDOS_DO_ROTULO."
    )


# =============================================================
# Selecionar Parquets
# -------------------------------------------------------------
# Acha os arquivos da tarefa e do esquema configurados
# =============================================================
def selecionar_parquets(pasta: Path) -> list[Path]:
    encontrados = [c for c in sorted(pasta.rglob("*"))
                   if c.is_file() and ".parquet" in c.name]

    def no_caminho(caminho: Path, alvo: str) -> bool:
        return any(parte.lower() == alvo.lower() for parte in caminho.parts)

    return [c for c in encontrados
            if no_caminho(c, config.SUBPASTA_DEFECTORS)
            and no_caminho(c, config.ESQUEMA_DEFECTORS)]


# =============================================================
# Particao do Parquet
# -------------------------------------------------------------
# De qual divisão oficial do Defectors o arquivo veio
# =============================================================
def particao_do_parquet(caminho: Path) -> str:
    nome = caminho.name.lower()

    for marca in ("train", "test", "val"):
        if nome.startswith(marca):
            return marca

    return "?"


# =============================================================
# Exigir Parquets
# -------------------------------------------------------------
# Garante que o Defectors está no lugar
# =============================================================
def exigir_parquets() -> list[Path]:
    parquets = selecionar_parquets(config.PASTA_DEFECTORS)

    if not parquets:
        achados = [c.name for c in config.PASTA_DEFECTORS.rglob("*")
                   if c.is_file() and ".parquet" in c.name]

        mensagem = [
            f"Nenhum parquet em {config.PASTA_DEFECTORS}/ dentro de "
            f"{config.SUBPASTA_DEFECTORS}/{config.ESQUEMA_DEFECTORS}/.",
        ]

        if achados:
            mensagem.append(
                f"Existem {len(achados)} parquets na pasta, mas fora "
                f"desse caminho. Confira SUBPASTA_DEFECTORS e "
                f"ESQUEMA_DEFECTORS no config.py.")
        else:
            mensagem.append(
                "Baixe defectors.zip de "
                "https://zenodo.org/records/7708984 e descompacte "
                "nessa pasta.")

        raise SystemExit("\n".join(mensagem))

    return parquets


# =============================================================
# Repositorio Incluido
# -------------------------------------------------------------
# Decide se um repositório entra no escopo
# =============================================================
def repositorio_incluido(repositorio: str) -> bool:
    if not config.REPOSITORIOS_INCLUIDOS:
        return True

    alvos = {n.lower() for n in config.REPOSITORIOS_INCLUIDOS}
    alvos |= {n.lower() for n in config.REPOSITORIOS_TESTE}

    return repositorio.lower() in alvos


# =============================================================
# Arquivo Ignorado
# -------------------------------------------------------------
# Aplica os filtros de caminho
# =============================================================
def arquivo_ignorado(caminho: str) -> bool:
    normalizado = caminho.replace("\\", "/")

    if any(normalizado.startswith(p) for p in config.PASTAS_IGNORADAS):
        return True

    if Path(normalizado).name in config.ARQUIVOS_IGNORADOS:
        return True

    return False


# =============================================================
# Rotulo do Registro
# -------------------------------------------------------------
# Converte a lista de linhas com defeito em (quantidade, rótulo)
# =============================================================
def rotulo_do_registro(linhas_com_defeito) -> tuple[int, int]:
    if linhas_com_defeito is None:
        return 0, 0

    try:
        quantidade = len(linhas_com_defeito)
    except TypeError:
        return 0, 0

    return quantidade, int(quantidade > 0)


# =============================================================
# Listar Repositorios
# -------------------------------------------------------------
# Modo de consulta: nomes exatos e contagens, sem clonar
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
        rotulo = nome_do_rotulo(caminho)

        for lote in pq.ParquetFile(caminho).iter_batches(
                batch_size=20000, columns=["repo", rotulo]):
            tabela = lote.to_pandas()
            tabela["defeituoso"] = [
                rotulo_do_registro(v)[1] for v in tabela[rotulo]]
            partes.append(tabela[["repo", "defeituoso"]])
        print(f"    {caminho.name}  (rótulo em {rotulo!r})")

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
          f"{', '.join(config.REPOSITORIOS_TESTE)}\n")


# =============================================================
# Planejar Amostra
# -------------------------------------------------------------
# Escolhe quais linhas medir, antes de medir
# =============================================================
def planejar_amostra(parquets: list[Path],
                     quantidade: int) -> set[tuple[str, str, str]]:
    print(f"  planejando amostra de {quantidade} linhas "
          f"(passada barata, sem ler código)")

    partes = []
    for caminho in parquets:
        rotulo = nome_do_rotulo(caminho)

        for lote in pq.ParquetFile(caminho).iter_batches(
                batch_size=20000, columns=COLUNAS_DE_CHAVE + [rotulo]):
            tabela = lote.to_pandas()
            tabela["rotulo"] = [rotulo_do_registro(v)[1]
                                for v in tabela[rotulo]]
            partes.append(tabela[COLUNAS_DE_CHAVE + ["rotulo"]])

    populacao = pd.concat(partes, ignore_index=True)

    dentro = populacao["repo"].map(repositorio_incluido)
    fora_do_caminho = populacao["filepath"].map(arquivo_ignorado)
    populacao = populacao[dentro & ~fora_do_caminho]
    populacao = populacao.drop_duplicates(
        subset=["repo", "commit", "filepath"])

    if populacao.empty:
        return set()

    print(f"    {len(populacao)} linhas elegíveis em "
          f"{populacao['repo'].nunique()} repositórios")

    if quantidade >= len(populacao):
        print("    a amostra pedida é maior que a população: usando tudo")
        escolhidas = populacao
    else:
        fracao = quantidade / len(populacao)
        pedacos = []

        for _, grupo in populacao.groupby(["repo", "rotulo"]):
            quantas = max(1, round(len(grupo) * fracao))
            pedacos.append(grupo.sample(n=min(quantas, len(grupo)),
                                        random_state=config.SEMENTE))

        escolhidas = pd.concat(pedacos, ignore_index=True)

    print(f"    {len(escolhidas)} linhas sorteadas, "
          f"{int(escolhidas['rotulo'].sum())} defeituosas "
          f"({100 * escolhidas['rotulo'].mean():.1f}%)")

    return set(zip(escolhidas["repo"], escolhidas["commit"],
                   escolhidas["filepath"]))


# =============================================================
# Extrair Amostra
# -------------------------------------------------------------
# Grava em disco uma cópia reduzida do Defectors
# =============================================================
def extrair_amostra(quantidade: int, destino: Path) -> None:
    parquets = exigir_parquets()

    print("=" * 70)
    print("EXTRAÇÃO DE AMOSTRA")
    print("=" * 70)
    print(f"\n  origem  : {config.PASTA_DEFECTORS}/")
    print(f"  destino : {destino}/")
    print(f"  tarefa  : {config.SUBPASTA_DEFECTORS}")
    print(f"  esquema : {config.ESQUEMA_DEFECTORS}\n")

    desejadas = planejar_amostra(parquets, quantidade)
    if not desejadas:
        raise SystemExit("A amostra ficou vazia. Confira o config.py.")

    pasta_saida = (destino / config.SUBPASTA_DEFECTORS
                   / config.ESQUEMA_DEFECTORS)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    total = 0
    for caminho in parquets:
        origem = particao_do_parquet(caminho)
        print(f"  lendo {caminho.name} [{origem}]", end=" ", flush=True)

        pedacos = []
        for lote in pq.ParquetFile(caminho).iter_batches(
                batch_size=config.LINHAS_POR_LOTE):
            tabela = lote.to_pandas()
            chaves = list(zip(tabela["repo"], tabela["commit"],
                              tabela["filepath"]))
            tabela = tabela[[c in desejadas for c in chaves]]
            if len(tabela):
                pedacos.append(tabela)
            print(".", end="", flush=True)

        if not pedacos:
            print(" nenhuma linha sorteada deste arquivo")
            continue

        juntas = pd.concat(pedacos, ignore_index=True)
        arquivo_saida = pasta_saida / caminho.name
        juntas.to_parquet(arquivo_saida, index=False, compression="gzip")

        total += len(juntas)
        print(f" {len(juntas)} linhas, "
              f"{arquivo_saida.stat().st_size / 1e6:.1f} MB")

    print("\n" + "=" * 70)
    print(f"AMOSTRA GRAVADA: {pasta_saida}/")
    print("=" * 70)
    print(f"\n  {total} linhas no total")
    print("\n  Para usar esta amostra, troque no config.py:\n")
    print(f'      PASTA_DEFECTORS = Path("{destino}")')
    print("      TAMANHO_AMOSTRA = 0")
    print("\n  A estrutura é a mesma, então nada mais precisa mudar.\n")


# =============================================================
# Medir Um Arquivo
# -------------------------------------------------------------
# Mede, ou diz por que não mediu
# =============================================================
def medir_um_arquivo(caminho: str, codigo: str):
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message=".*invalid escape sequence.*")

        quantidade = metricas_codigo.contar_funcoes(caminho, codigo)

        if quantidade is None:
            return "nao_faz_parse"
        if quantidade == 0:
            return "sem_funcoes"

        medidas = metricas_codigo.medir(caminho, codigo)
        return medidas if medidas is not None else "nao_faz_parse"


# =============================================================
# Pasta Separado
# -------------------------------------------------------------
# Onde ficam os parquets de um repositório cada
# =============================================================
def pasta_separado() -> Path:
    return pasta_de_trabalho() / "separado"


# =============================================================
# Escrever Separados
# -------------------------------------------------------------
# Varre os parquets de origem gravando um parquet por projeto
# =============================================================
def escrever_separados(parquets: list[Path], chaves_desejadas,
                       apenas: set[str] | None) -> tuple[list[str], dict]:
    pasta = pasta_separado()
    pasta.mkdir(parents=True, exist_ok=True)

    escritores: dict[str, pq.ParquetWriter] = {}
    contagem = {"lidas": 0, "fora_do_escopo": 0, "caminho_ignorado": 0,
                "fora_da_amostra": 0, "separadas": 0}

    try:
        for caminho in parquets:
            origem = particao_do_parquet(caminho)
            rotulo = nome_do_rotulo(caminho)
            print(f"\n  lendo {caminho.name} [{origem}]",
                  end=" ", flush=True)

            for lote in pq.ParquetFile(caminho).iter_batches(
                    batch_size=config.LINHAS_POR_LOTE,
                    columns=COLUNAS_DE_CHAVE + ["content", rotulo]):

                tabela = lote.to_pandas()
                contagem["lidas"] += len(tabela)

                if apenas is not None:
                    tabela = tabela[tabela["repo"].isin(apenas)]

                if len(tabela) and chaves_desejadas is not None:
                    chaves = zip(tabela["repo"], tabela["commit"],
                                 tabela["filepath"])
                    manter = [c in chaves_desejadas for c in chaves]
                    contagem["fora_da_amostra"] += len(tabela) - sum(manter)
                    tabela = tabela[manter]

                if len(tabela):
                    dentro = tabela["repo"].map(repositorio_incluido)
                    contagem["fora_do_escopo"] += int((~dentro).sum())
                    tabela = tabela[dentro]

                if len(tabela):
                    ignorado = tabela["filepath"].map(arquivo_ignorado)
                    contagem["caminho_ignorado"] += int(ignorado.sum())
                    tabela = tabela[~ignorado]

                if not len(tabela):
                    print(".", end="", flush=True)
                    continue

                tabela = tabela.rename(columns={rotulo: ROTULO_PADRAO})
                tabela["particao_defectors"] = origem

                tabela["content"] = [
                    v.encode("utf-8", errors="ignore")
                    if isinstance(v, str) else v
                    for v in tabela["content"]]

                for nome, pedaco in tabela.groupby("repo", sort=False):
                    if nome not in escritores:
                        destino = pasta / f"{nome.replace('/', '__')}.parquet"
                        escritores[nome] = pq.ParquetWriter(
                            destino, ESQUEMA_SEPARADO, compression="gzip")

                    escritores[nome].write_table(pa.Table.from_pandas(
                        pedaco[ESQUEMA_SEPARADO.names],
                        schema=ESQUEMA_SEPARADO, preserve_index=False))

                    contagem["separadas"] += len(pedaco)

                print(".", end="", flush=True)
    finally:
        for escritor in escritores.values():
            escritor.close()

    return sorted(escritores), contagem


# =============================================================
# Separar Alguns
# -------------------------------------------------------------
# Regrava o parquet separado de projetos específicos
# =============================================================
def separar_alguns(apenas: set[str]) -> list[str]:
    pedidos = sorted(apenas)

    print(f"  Refazendo a separação de {len(pedidos)} "
          f"repositório(s): {', '.join(pedidos)}")

    chaves_desejadas = None
    parquets = exigir_parquets()
    if config.TAMANHO_AMOSTRA > 0:
        chaves_desejadas = planejar_amostra(parquets,
                                            config.TAMANHO_AMOSTRA)

    nomes, contagem = escrever_separados(parquets, chaves_desejadas, apenas)

    print(f"\n    {contagem['separadas']} linhas regravadas")

    nao_vieram = [n for n in pedidos if n not in nomes]
    if nao_vieram:
        print(f"    sem nenhuma linha elegível: {', '.join(nao_vieram)}")

    return nomes


# =============================================================
# Separar por Repositorio
# -------------------------------------------------------------
# Etapa 0: uma passada no Defectors, um parquet por projeto
# =============================================================
def separar_por_repositorio(apenas: set[str] | None = None) -> list[str]:
    if apenas:
        return separar_alguns(apenas)

    pasta = pasta_separado()
    marca = pasta_de_trabalho() / "separado.pronto"

    if marca.exists() and not config.FORCAR_MONTAGEM:
        registro = json.loads(marca.read_text(encoding="utf-8"))
        nomes = registro["repositorios"]
        print(f"  Separação reaproveitada: {len(nomes)} repositórios.")
        return nomes

    parquets = exigir_parquets()

    print(f"  {len(parquets)} parquets de origem:")
    for caminho in parquets:
        print(f"    {caminho.name}  "
              f"({caminho.stat().st_size / 1e6:.0f} MB)")

    chaves_desejadas = None
    if config.TAMANHO_AMOSTRA > 0:
        print()
        chaves_desejadas = planejar_amostra(parquets,
                                            config.TAMANHO_AMOSTRA)
        if not chaves_desejadas:
            raise SystemExit(
                "A amostra ficou vazia. Rode com --listar e confira "
                "REPOSITORIOS_INCLUIDOS no config.py."
            )

    apagar_pasta(pasta)

    nomes, contagem = escrever_separados(parquets, chaves_desejadas, None)

    print(f"\n\n  Separação concluída.")
    print(f"    linhas lidas               : {contagem['lidas']}")
    if contagem["fora_da_amostra"]:
        print(f"    fora da amostra planejada  : "
              f"{contagem['fora_da_amostra']}")
    print(f"    fora do escopo configurado : {contagem['fora_do_escopo']}")
    print(f"    caminho ignorado           : {contagem['caminho_ignorado']}")
    print(f"    separadas                  : {contagem['separadas']}")

    if not nomes:
        raise SystemExit(
            "Nenhum repositório separado. Rode --listar e confira "
            "REPOSITORIOS_INCLUIDOS no config.py contra os nomes "
            "que aparecem no dataset."
        )

    ocupado = sum(c.stat().st_size for c in pasta.glob("*.parquet"))
    print(f"\n  {len(nomes)} repositórios em {pasta}/ "
          f"({ocupado / 1e6:.0f} MB)")

    (pasta_de_trabalho() / "separado.pronto").write_text(
        json.dumps({"assinatura": assinatura_da_fase1(),
                    "repositorios": nomes}, indent=2),
        encoding="utf-8")

    return nomes


# =============================================================
# Medir Codigo do Repo
# -------------------------------------------------------------
# Fase 1 de um repositório só
# =============================================================
def medir_codigo_do_repo(nome: str, caminho: Path) -> pd.DataFrame:
    cache = {}
    contagem = {"lidas": 0, "sem_conteudo": 0, "grande_demais": 0,
                "nao_faz_parse": 0, "sem_funcoes": 0}
    linhas = []

    for lote in pq.ParquetFile(caminho).iter_batches(
            batch_size=config.LINHAS_POR_LOTE):

        for registro in lote.to_pandas().itertuples(index=False):
            contagem["lidas"] += 1

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

            quantidade, defeituoso = rotulo_do_registro(
                getattr(registro, ROTULO_PADRAO))

            linhas.append({
                "repositorio": registro.repo,
                "arquivo":     registro.filepath.replace("\\", "/"),
                "commit":      str(registro.commit),
                "particao_defectors": registro.particao_defectors,
                **medidas,
                "linhas_defeituosas": quantidade,
                features.COLUNA_ALVO: defeituoso,
            })

    descartadas = contagem["lidas"] - len(linhas)
    print(f"medidas {len(linhas)}/{contagem['lidas']} "
          f"(-{descartadas}: {contagem['sem_conteudo']} sem conteúdo, "
          f"{contagem['nao_faz_parse']} sem parse, "
          f"{contagem['sem_funcoes']} sem função, "
          f"{contagem['grande_demais']} grandes) ",
          end="", flush=True)

    if not linhas:
        return pd.DataFrame()

    tabela = pd.DataFrame(linhas)

    return tabela.drop_duplicates(
        subset=["repositorio", "arquivo", "commit"])


# =============================================================
# Assinatura da Fase 1
# -------------------------------------------------------------
# Identifica a configuração usada, para validar o que foi salvo
# =============================================================
def assinatura_da_fase1() -> dict:
    return {
        "subpasta":  config.SUBPASTA_DEFECTORS,
        "esquema":   config.ESQUEMA_DEFECTORS,
        "incluidos": list(config.REPOSITORIOS_INCLUIDOS),
        "teste":     list(config.REPOSITORIOS_TESTE),
        "amostra":   config.TAMANHO_AMOSTRA,
        "semente":   config.SEMENTE,
        "tamanho_maximo": config.TAMANHO_MAXIMO_BYTES,
        "pastas":    list(config.PASTAS_IGNORADAS),
        "arquivos":  list(config.ARQUIVOS_IGNORADOS),
        "medidos":   sorted(
            chave for chave, _ in features.GRUPOS_MEDIDOS
            if getattr(config, chave, False)),
        "janela":    config.JANELA_RECENTE_DIAS,
    }


# =============================================================
# Pasta de Trabalho
# -------------------------------------------------------------
# Subpasta dos parciais correspondente a esta configuração
# =============================================================
def pasta_de_trabalho() -> Path:
    texto = json.dumps(assinatura_da_fase1(), sort_keys=True)
    resumo = hashlib.sha1(texto.encode("utf-8")).hexdigest()[:10]
    return config.PASTA_PARCIAIS / resumo


# =============================================================
# Repositorios Pendentes
# -------------------------------------------------------------
# Projetos da separação que ainda não têm CSV gravado
# =============================================================
def repositorios_pendentes() -> list[str]:
    marca = pasta_de_trabalho() / "separado.pronto"

    if not marca.exists():
        return []

    try:
        registro = json.loads(marca.read_text(encoding="utf-8"))
    except Exception:
        return []

    pasta = pasta_de_trabalho()

    return [nome for nome in registro.get("repositorios", [])
            if nome not in config.REPOSITORIOS_PULADOS
            and not (pasta / f"{nome.replace('/', '__')}.csv").exists()]


SUFIXO_CODIGO = "__codigo.csv"


# =============================================================
# Csvs Completos
# -------------------------------------------------------------
# Os parciais de repositório prontos, sem os de código
# =============================================================
def csvs_completos(pasta: Path) -> list[Path]:
    return [c for c in sorted(pasta.glob("*.csv"))
            if not c.name.endswith(SUFIXO_CODIGO)]


# =============================================================
# Resumo do Erro
# -------------------------------------------------------------
# Uma linha do erro que sirva para entender a causa
# =============================================================
def resumo_do_erro(erro: Exception) -> str:
    linhas = [l.strip() for l in str(erro).splitlines() if l.strip()]

    if not linhas:
        return type(erro).__name__

    for linha in linhas:
        if linha.startswith(("error:", "fatal:", "warning:")):
            return linha[:100]

    return linhas[0][:100]


# =============================================================
# Apagar Pasta
# -------------------------------------------------------------
# Apaga uma pasta inteira e avisa quando não consegue
# =============================================================
def apagar_pasta(pasta: Path) -> bool:
    def liberar(funcao, caminho, _erro):
        try:
            Path(caminho).chmod(stat.S_IWRITE)
            funcao(caminho)
        except OSError:
            pass

    for espera in (0, 1, 2, 4):
        if not pasta.exists():
            return True

        time.sleep(espera)
        gc.collect()
        shutil.rmtree(pasta, onexc=liberar)

    if pasta.exists():
        print(f"\n      AVISO: não foi possível apagar {pasta}")
        return False

    return True


# =============================================================
# Clone Valido
# -------------------------------------------------------------
# Confere se a pasta é um repositório git próprio e com commits
# =============================================================
def clone_valido(pasta: Path) -> bool:
    if not (pasta / ".git").exists():
        return False

    resultado = subprocess.run(
        ["git", "-C", str(pasta), "rev-parse",
         "--absolute-git-dir", "--verify", "HEAD"],
        capture_output=True, text=True, timeout=60,
    )

    if resultado.returncode != 0:
        return False

    linhas = resultado.stdout.splitlines()
    return bool(linhas) and Path(linhas[0]) == (pasta / ".git").resolve()


# =============================================================
# Clonar
# -------------------------------------------------------------
# Baixa um repositório com o histórico completo
# =============================================================
def clonar(repositorio: str, destino: Path) -> bool:
    if clone_valido(destino):
        return True

    if destino.exists():
        print("clone inválido, apagando... ", end="", flush=True)
        if not apagar_pasta(destino):
            return False

    endereco = config.NOMES_NO_GITHUB.get(repositorio)
    if not endereco:
        print(f"nome fora de NOMES_NO_GITHUB, acrescente no config.py")
        return False

    destino.parent.mkdir(parents=True, exist_ok=True)

    sem_hooks = config.PASTA_CLONES / "_sem_hooks"
    sem_hooks.mkdir(parents=True, exist_ok=True)

    comando = [
        "git",
        "-c", f"core.hooksPath={sem_hooks}",
        "clone", "--quiet", f"--template={sem_hooks}",
        f"https://github.com/{endereco}.git", str(destino),
    ]

    for tentativa in (1, 2):
        resultado = subprocess.run(comando, capture_output=True,
                                   text=True, timeout=7200)

        if resultado.returncode == 0:
            return True

        if tentativa == 1:
            print("falhou, limpando e tentando de novo... ",
                  end="", flush=True)
            apagar_pasta(destino)

    print(f"falha do git: {resultado.stderr.strip()[-300:]}")
    return False


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

    if resultado.returncode != 0:
        raise RuntimeError(resultado.stderr.strip()[-300:])

    mapa = {}
    for informado, linha in zip(hashes, resultado.stdout.splitlines()):
        partes = linha.split()
        if len(partes) >= 2 and partes[1] == "commit":
            mapa[informado] = partes[0]

    return mapa


# =============================================================
# Arquivo do Ponto
# -------------------------------------------------------------
# Onde fica o ponto de retomada da travessia de um repositório
# =============================================================
def arquivo_do_ponto(repositorio: str) -> Path:
    base = repositorio.replace("/", "__")
    return pasta_de_trabalho() / f"{base}__ponto.pkl"


# =============================================================
# Gravar Csv Atomico
# -------------------------------------------------------------
# Grava de modo que o CSV nunca exista pela metade
# =============================================================
def gravar_csv_atomico(tabela: pd.DataFrame, destino: Path) -> None:
    temporario = destino.with_name(destino.name + ".tmp")
    tabela.to_csv(temporario, index=False, encoding="utf-8")
    os.replace(temporario, destino)


# =============================================================
# Medir Historico do Repo
# -------------------------------------------------------------
# Fase 2 para um repositório
# =============================================================
def medir_historico_do_repo(repositorio: str,
                            tabela: pd.DataFrame) -> pd.DataFrame | None:
    pasta = config.PASTA_CLONES / repositorio.replace("/", "__")

    for tentativa in (1, 2):
        print("clonando... " if tentativa == 1 else "clonando de novo... ",
              end="", flush=True)

        if not clonar(repositorio, pasta):
            apagar_pasta(pasta)
            return None

        try:
            resultado = medir_historico_do_clone(repositorio, pasta, tabela)

            if resultado is None:
                apagar_pasta(pasta)

            return resultado
        except Exception as erro:
            resumo = resumo_do_erro(erro)

            if tentativa == 1:
                print(f"\n      falhou: {resumo}")
                print("      apagando o clone danificado  ",
                      end="", flush=True)
                apagar_pasta(pasta)
            else:
                print(f"\n      falhou de novo: {resumo}")
                print("      repositório deixado de fora")
                apagar_pasta(pasta)

    return None


# =============================================================
# Medir Historico do Clone
# -------------------------------------------------------------
# Mede o histórico num clone que já está em disco
# =============================================================
def medir_historico_do_clone(repositorio: str, pasta: Path,
                             tabela: pd.DataFrame) -> pd.DataFrame | None:
    informados = sorted(tabela["commit"].unique())
    mapa = resolver_commits(pasta, informados)

    if not mapa:
        print(f"0 de {len(informados)} commits do dataset existem no "
              f"clone em {pasta}")
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

    if config.HISTORICO_RAPIDO:
        fotografias = historico_retomavel.medir_nos_commits(
            pasta, caminhos_por_commit,
            arquivo_do_ponto(repositorio), progresso)
    else:
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
        apagar_pasta(pasta)

    return pd.DataFrame(linhas)


# =============================================================
# Gravar Dataset
# -------------------------------------------------------------
# Junta os CSVs por repositório e grava o dataset final
# =============================================================
def gravar_dataset(partes: list[pd.DataFrame]) -> pd.DataFrame:
    dataset = pd.concat(partes, ignore_index=True)

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

    return dataset


# =============================================================
# Montar com os Prontos
# -------------------------------------------------------------
# Grava o dataset a partir dos CSVs que já existem
# =============================================================
def montar_com_os_prontos() -> pd.DataFrame:
    features.conferir_sem_vazamento()
    config.conferir_nomes()

    inicio = time.time()
    pasta = pasta_de_trabalho()

    print("=" * 70)
    print("MONTAGEM COM OS REPOSITÓRIOS JÁ PRONTOS")
    print("=" * 70)
    print(f"\n  parciais: {pasta}/")
    print(f"  destino : {config.ARQUIVO_DATASET}")
    print(f"  divisão : {divisao.descrever_divisao()}\n")

    prontos = csvs_completos(pasta)

    if not prontos:
        raise SystemExit(
            f"Nenhum CSV por repositório em {pasta}/.\n"
            f"Rode a montagem normal primeiro: "
            f"python frente1_treinamento/montar_dataset.py"
        )

    partes = []
    for caminho in prontos:
        tabela = pd.read_csv(caminho)
        print(f"    {caminho.stem:<24} {len(tabela):>7} linhas")
        partes.append(tabela)

    dataset = gravar_dataset(partes)

    pendentes = repositorios_pendentes()
    resumir(dataset, pendentes, time.time() - inicio)

    if pendentes:
        print(f"  Atenção: este dataset NÃO tem {len(pendentes)} "
              f"repositório(s) da separação.")
        print(f"  Para treinar com ele, desligue "
              f"EXIGIR_TODOS_OS_REPOSITORIOS no config.py.\n")

    return dataset


# =============================================================
# Resumir
# -------------------------------------------------------------
# Relatório final da montagem
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
        print(f"\n  não processados ({len(falharam)}): "
              f"{', '.join(falharam)}")
        print("  Eles não têm CSV, então basta rodar o mesmo comando de "
              "novo para tentar só eles.")

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
# Montar
# -------------------------------------------------------------
# Executa as duas fases e grava o dataset
# =============================================================
def montar(apenas: str | None = None) -> pd.DataFrame | None:
    features.conferir_sem_vazamento()
    config.conferir_nomes()

    print("=" * 70)
    print("MONTAGEM DO DATASET")
    print("=" * 70)
    print(f"\n  origem  : {config.PASTA_DEFECTORS}/")
    print(f"  destino : {config.ARQUIVO_DATASET}")
    print(f"  escopo  : "
          f"{', '.join(config.REPOSITORIOS_INCLUIDOS) or 'todos'}")
    print(f"  divisão : {divisao.descrever_divisao()}")
    if config.TAMANHO_AMOSTRA > 0:
        print(f"  amostra : piloto de {config.TAMANHO_AMOSTRA} linhas, "
              f"estratificada por repositório e rótulo")
    else:
        print("  amostra : dataset completo")

    inicio = time.time()
    pasta_parciais = pasta_de_trabalho()
    pasta_parciais.mkdir(parents=True, exist_ok=True)
    print(f"  parciais: {pasta_parciais}/")

    print("\n" + "-" * 70)
    print("ETAPA 1 — separar o Defectors em um parquet por repositório")
    print("-" * 70 + "\n")

    nomes = separar_por_repositorio()

    if apenas and apenas not in nomes:
        raise SystemExit(f"'{apenas}' não está entre os repositórios "
                         f"da separação: {', '.join(nomes)}")

    if not config.FORCAR_MONTAGEM:
        faltando = {
            nome for nome in nomes
            if nome not in config.REPOSITORIOS_PULADOS
            and (apenas is None or nome == apenas)
            and not (pasta_parciais /
                     f"{nome.replace('/', '__')}.csv").exists()
            and not (pasta_parciais /
                     f"{nome.replace('/', '__')}{SUFIXO_CODIGO}").exists()
            and not (pasta_separado() /
                     f"{nome.replace('/', '__')}.parquet").exists()
        }

        if faltando:
            print()
            separar_alguns(faltando)

    print("\n" + "-" * 70)
    print("ETAPA 2 — um repositório por vez: mede, clona, grava, apaga")
    print("-" * 70 + "\n")

    partes, falharam = [], []

    for ordem, repositorio in enumerate(nomes, start=1):
        if apenas and repositorio != apenas:
            continue

        base = repositorio.replace("/", "__")
        parcial = pasta_parciais / f"{base}.csv"
        parcial_codigo = pasta_parciais / f"{base}__codigo.csv"

        if parcial.exists() and not config.FORCAR_MONTAGEM:
            pronto = pd.read_csv(parcial)
            print(f"  [{ordem}/{len(nomes)}] {repositorio:<24} "
                  f"reaproveitado, {len(pronto)} linhas")
            partes.append(pronto)
            continue

        print(f"  [{ordem}/{len(nomes)}] {repositorio:<24} ",
              end="", flush=True)

        if repositorio in config.REPOSITORIOS_PULADOS:
            print("deixado de fora por REPOSITORIOS_PULADOS")
            apagar_pasta(config.PASTA_CLONES / base)
            continue

        separado = pasta_separado() / f"{base}.parquet"
        tem_codigo = parcial_codigo.exists() and not config.FORCAR_MONTAGEM

        if not separado.exists() and not tem_codigo:
            print("sem parquet separado e sem linha elegível na origem")
            falharam.append(repositorio)
            continue

        try:
            if tem_codigo:
                codigo = pd.read_csv(parcial_codigo)
                print(f"código reaproveitado ({len(codigo)}) ",
                      end="", flush=True)
            else:
                codigo = medir_codigo_do_repo(repositorio, separado)

                if codigo.empty:
                    print("nenhuma linha mensurável")
                    falharam.append(repositorio)
                    continue

                codigo.to_csv(parcial_codigo, index=False, encoding="utf-8")

                if config.APAGAR_SEPARADO:
                    separado.unlink(missing_ok=True)

            if codigo.empty:
                print("nenhuma linha mensurável")
                falharam.append(repositorio)
                continue

            resultado = medir_historico_do_repo(repositorio, codigo)
        except KeyboardInterrupt:
            raise SystemExit(
                f"\n\n  Interrompido durante o {repositorio}.\n"
                f"  Já estão gravados: {len(partes)} de {len(nomes)}. "
                f"Rode o mesmo comando para continuar daqui."
            )
        except Exception as erro:
            print(f"\n      erro inesperado: {resumo_do_erro(erro)}")
            falharam.append(repositorio)
            continue

        if resultado is None:
            falharam.append(repositorio)
            continue

        gravar_csv_atomico(resultado, parcial)
        arquivo_do_ponto(repositorio).unlink(missing_ok=True)
        partes.append(resultado)

    if apenas:
        if falharam:
            raise SystemExit(f"\n  {apenas} falhou: nenhum CSV gravado.")

        print(f"\n  {apenas} concluído em "
              f"{time.time() - inicio:.0f} segundos.\n")
        return None

    if not partes:
        raise SystemExit("Nenhum repositório processado.")

    dataset = gravar_dataset(partes)

    resumir(dataset, falharam, time.time() - inicio)
    return dataset


# =============================================================
# Main
# -------------------------------------------------------------
# Lê os argumentos e executa o modo pedido
# =============================================================
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listar", action="store_true",
                        help="mostra os repositórios do Defectors com os "
                             "nomes exatos e a contagem de linhas")
    parser.add_argument("--repo", default=None, metavar="NOME",
                        help="processa só este repositório e grava o "
                             "CSV dele, sem gravar o dataset")
    parser.add_argument("--amostra", type=int, default=None,
                        help="monta uma amostra piloto com esta "
                             "quantidade de linhas, sobrepondo "
                             "TAMANHO_AMOSTRA do config")
    parser.add_argument("--extrair-amostra", type=int, default=None,
                        metavar="N",
                        help="grava em disco uma cópia reduzida do "
                             "Defectors com N linhas, e sai")
    parser.add_argument("--destino", default="defectors_amostra",
                        help="pasta onde a cópia reduzida é gravada")
    parser.add_argument("--so-prontos", action="store_true",
                        help="grava o dataset juntando apenas os "
                             "repositórios que já têm CSV, sem ler "
                             "parquet nem clonar nada")
    argumentos = parser.parse_args()

    config.conferir_local()
    config.conferir_nomes()

    if argumentos.amostra is not None:
        config.TAMANHO_AMOSTRA = argumentos.amostra

    if argumentos.listar:
        listar_repositorios()
    elif argumentos.so_prontos:
        montar_com_os_prontos()
    elif argumentos.extrair_amostra is not None:
        extrair_amostra(argumentos.extrair_amostra,
                        Path(argumentos.destino))
    else:
        montar(argumentos.repo)


if __name__ == "__main__":
    main()

"""
Monta dados/dataset.csv a partir do Defectors.

O Defectors traz código e rótulo, e nenhuma métrica. Calcular as
9 features sobre isso é o trabalho deste arquivo.

Duas fases:

  Fase 1 -> lê os parquets e calcula as 6 métricas de código.
            Minutos, sem rede.

  Fase 2 -> clona cada repositório e mede o histórico de cada
            arquivo até o commit rotulado. Horas, dezenas de GB.

CMD -> python frente1_treinamento/montar_dataset.py
       --listar             mostra os repositórios e os nomes exatos
       --amostra N          monta só N linhas, sem gravar cópia
       --extrair-amostra N  grava em disco uma cópia reduzida
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import warnings
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI))

import config
import divisao
from extrator import features, metricas_codigo, metricas_historico


# As colunas que identificam a linha. 'content' fica fora desta
# lista porque é o código-fonte inteiro, e é por causa dele que a
# leitura é feita em lotes.
COLUNAS_DE_CHAVE = ["repo", "commit", "filepath"]

# O artigo do Defectors documenta a coluna de rótulo como
# 'induce_bug', mas os parquets publicados no Zenodo a chamam de
# 'lines'. A lista existe para o programa aceitar as duas e não
# travar por causa do nome.
APELIDOS_DO_ROTULO = ("lines", "induce_bug", "bug_lines")


# =============================================================
# Nome do Rotulo
# -------------------------------------------------------------
# Descobre como a coluna de rótulo se chama neste parquet
# =============================================================
def nome_do_rotulo(caminho: Path) -> str:
    # Lê só o cabeçalho do parquet, não os dados.
    #
    # schema_arrow e não schema: o segundo achata colunas de lista
    # e devolve 'element' no lugar do nome verdadeiro.
    colunas = pq.ParquetFile(caminho).schema_arrow.names

    for apelido in APELIDOS_DO_ROTULO:
        if apelido in colunas:
            return apelido

    # Para o programa em vez de seguir sem rótulo: sem ele não
    # existe nada para prever
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
    # A seleção é pelo CAMINHO, não pelas colunas. As duas tarefas
    # do Defectors têm exatamente as mesmas colunas: o que muda é
    # o significado de 'content', que numa é o arquivo e na outra
    # é o diff. Aceitar pelas colunas misturaria diffs no dataset
    # e o erro não apareceria.
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

    # Comparação exata, não por pedaço do nome: 'django' e
    # 'django-rest-framework' são dois projetos diferentes no
    # dataset, e um teste por substring confundiria os dois.
    #
    # Os de teste entram sempre: esquecer de listá-los nos dois
    # lugares deixaria o conjunto de teste vazio sem aviso.
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
    # Lista vazia -> arquivo limpo.
    # O campo chega como lista, array do numpy ou None conforme a
    # versão da biblioteca, e testar array com 'if' levanta
    # exceção. Por isso a conversão é pelo tamanho.
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
    # Passada barata: lê nome, commit, caminho e rótulo, nunca o
    # código. Conhece a população inteira em segundos.
    #
    # O sorteio é ESTRATIFICADO por (repositório, rótulo), então a
    # amostra tem a mesma composição do dataset completo.
    #
    # Fazer isso antes de medir é o que dá a economia: o programa
    # mede mil arquivos em vez de 213 mil.
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

    # Os mesmos filtros da medição, para sortear entre as linhas
    # que de fato poderiam entrar
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
            # Pelo menos uma linha por estrato, para nenhum
            # repositório e nenhuma classe sumir da amostra
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
    # Escreve parquets com a MESMA estrutura de pastas do
    # original, só com as linhas sorteadas, preservando a divisão
    # oficial. Depois disso basta apontar PASTA_DEFECTORS para a
    # pasta nova e o resto funciona sem mudança.
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

    # Segunda passada, agora lendo tudo mas guardando só o que foi
    # escolhido. É a única vez que o arquivo grande é aberto.
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
    # Silencia o aviso que o Python emite ao compilar o arquivo
    # MEDIDO. Projetos antigos escrevem expressões regulares como
    # "\d" em vez de r"\d". O código é válido, a métrica sai
    # correta, e são quatro linhas por arquivo — em mil arquivos o
    # aviso esconde a barra de progresso e qualquer mensagem que
    # importe.
    #
    # O filtro é pela MENSAGEM e não pela categoria, porque a
    # categoria mudou de versão para versão: DeprecationWarning
    # até o 3.13, SyntaxWarning no 3.14. A mensagem é a mesma.
    #
    # Escolher a mensagem em vez da categoria também evita engolir
    # aviso de depreciação do Radon ou do Lizard, que é coisa que
    # a gente quer ver.
    #
    # Vale só aqui dentro, então aviso vindo do código DESTE
    # projeto continua aparecendo.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message=".*invalid escape sequence.*")

        # Os dois motivos aparecem separados no relatório: não
        # fazer parse é código antigo ou quebrado, enquanto sem
        # função é tipicamente um __init__.py vazio
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
# Resumo da leitura do parquet
# =============================================================
def relatar_fase1(contagem: dict, medidas: int) -> None:
    print("\n\n  Fase 1 concluída.")
    print(f"    linhas lidas do parquet    : {contagem['lidas']}")
    if contagem["fora_da_amostra"]:
        print(f"    fora da amostra planejada  : "
              f"{contagem['fora_da_amostra']}")
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

    # None -> medir todas as que passarem pelos filtros
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

    cache = {}
    contagem = {"lidas": 0, "fora_do_escopo": 0, "caminho_ignorado": 0,
                "sem_conteudo": 0, "grande_demais": 0,
                "nao_faz_parse": 0, "sem_funcoes": 0,
                "fora_da_amostra": 0}
    linhas = []

    for caminho in parquets:
        origem = particao_do_parquet(caminho)
        rotulo = nome_do_rotulo(caminho)
        print(f"\n  lendo {caminho.name} [{origem}]", end=" ", flush=True)

        for lote in pq.ParquetFile(caminho).iter_batches(
                batch_size=config.LINHAS_POR_LOTE,
                columns=COLUNAS_DE_CHAVE + ["content", rotulo]):

            for registro in lote.to_pandas().itertuples(index=False):
                contagem["lidas"] += 1

                if chaves_desejadas is not None:
                    chave_linha = (registro.repo, registro.commit,
                                   registro.filepath)
                    if chave_linha not in chaves_desejadas:
                        contagem["fora_da_amostra"] += 1
                        continue

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

                # Cache pelo CONTEÚDO: o mesmo arquivo aparece em
                # muitos commits, quase sempre idêntico. Como a
                # chave é o texto, nunca devolve medida de outra
                # versão.
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
                    getattr(registro, rotulo))

                linhas.append({
                    "repositorio": registro.repo,
                    # Barra normal sempre, para combinar com o que
                    # o extrator de histórico devolve
                    "arquivo":     registro.filepath.replace("\\", "/"),
                    "commit":      str(registro.commit),
                    "particao_defectors": origem,
                    **medidas,
                    "linhas_defeituosas": quantidade,
                    features.COLUNA_ALVO: defeituoso,
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

    # O mesmo par pode aparecer em mais de um parquet, porque o
    # Defectors distribui divisões separadas
    return tabela.drop_duplicates(
        subset=["repositorio", "arquivo", "commit"])


# =============================================================
# Assinatura da Fase 1
# -------------------------------------------------------------
# Identifica a configuração usada, para validar o que foi salvo
# =============================================================
def assinatura_da_fase1() -> dict:
    # Mudar qualquer um destes muda quais arquivos entram e quais
    # métricas saem, então o resultado antigo deixa de valer
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
    }


# =============================================================
# Pasta de Trabalho
# -------------------------------------------------------------
# Subpasta dos parciais correspondente a esta configuração
# =============================================================
def pasta_de_trabalho() -> Path:
    # Configurações diferentes gravam em pastas diferentes, então
    # alternar entre a amostra piloto e o dataset completo não
    # mistura resultados nem descarta o trabalho de nenhum dos dois
    texto = json.dumps(assinatura_da_fase1(), sort_keys=True)
    resumo = hashlib.sha1(texto.encode("utf-8")).hexdigest()[:10]
    return config.PASTA_PARCIAIS / resumo


# =============================================================
# Ler Fase 1 do Disco
# -------------------------------------------------------------
# Reaproveita a Fase 1 já feita nesta configuração
# =============================================================
def ler_fase1_do_disco() -> pd.DataFrame | None:
    arquivo = pasta_de_trabalho() / "fase1.csv"
    marca = pasta_de_trabalho() / "fase1.pronta"

    # A marca só existe se a gravação terminou. Sem ela, o CSV
    # pode estar truncado por uma interrupção.
    if not (arquivo.exists() and marca.exists()):
        return None

    try:
        tabela = pd.read_csv(arquivo)
    except Exception:
        print("  A Fase 1 guardada está ilegível. Refazendo.")
        return None

    if tabela.empty:
        return None

    print(f"  Fase 1 reaproveitada do disco: {len(tabela)} linhas, "
          f"{tabela['repositorio'].nunique()} repositórios.")
    return tabela


# =============================================================
# Gravar Fase 1 no Disco
# -------------------------------------------------------------
# Salva assim que a Fase 1 termina
# =============================================================
def gravar_fase1_no_disco(tabela: pd.DataFrame) -> None:
    pasta = pasta_de_trabalho()
    pasta.mkdir(parents=True, exist_ok=True)

    tabela.to_csv(pasta / "fase1.csv", index=False, encoding="utf-8")

    # A marca vai por último, e é ela que torna o CSV válido. Se a
    # máquina morrer no meio, a marca não existe e a Fase 1 é
    # refeita em vez de ser lida truncada.
    (pasta / "fase1.pronta").write_text(
        json.dumps(assinatura_da_fase1(), indent=2), encoding="utf-8")

    print(f"  Fase 1 guardada em {pasta / 'fase1.csv'}")
    print("  Uma interrupção depois daqui não a refaz.")


# =============================================================
# Clonar
# -------------------------------------------------------------
# Baixa um repositório com o histórico completo
# =============================================================
def clonar(repositorio: str, destino: Path) -> bool:
    if (destino / ".git").exists():
        return True

    # O dataset guarda 'celery', e o GitHub precisa de
    # 'celery/celery'
    endereco = config.NOMES_NO_GITHUB.get(repositorio)
    if not endereco:
        print(f"nome fora de NOMES_NO_GITHUB, acrescente no config.py")
        return False

    destino.parent.mkdir(parents=True, exist_ok=True)

    # Pasta vazia de propósito, para apontar core.hooksPath para
    # ela
    sem_hooks = config.PASTA_CLONES / "_sem_hooks"
    sem_hooks.mkdir(parents=True, exist_ok=True)

    comando = [
        "git",

        # Nenhum hook é copiado para o clone, e nenhum é
        # executado. Se a máquina tiver um init.templateDir com um
        # post-checkout — coisa que Husky e pre-commit deixam
        # configurado —, o git copia esse hook para todo clone
        # novo e então recusa executá-lo, por segurança, abortando
        # o clone. Clonar sem hook nenhum resolve, e não custa
        # nada: aqui o repositório é só leitura.
        # --template vem depois porque, diferente de
        # init.templateDir, ele também vence a variável de
        # ambiente GIT_TEMPLATE_DIR
        "-c", f"core.hooksPath={sem_hooks}",

        "clone", "--quiet", f"--template={sem_hooks}",

        # Sem --depth de propósito: um clone raso traz só os
        # commits recentes e as 3 features de histórico ficariam
        # todas iguais a 1
        f"https://github.com/{endereco}.git", str(destino),
    ]

    # Duas tentativas. A primeira falha por queda de rede ou por
    # clone interrompido antes, e nos dois casos o que sobrou na
    # pasta impede a segunda, então ela é apagada no meio.
    for tentativa in (1, 2):
        resultado = subprocess.run(comando, capture_output=True,
                                   text=True, timeout=7200)

        if resultado.returncode == 0:
            return True

        if tentativa == 1:
            print("falhou, limpando e tentando de novo... ",
                  end="", flush=True)
            shutil.rmtree(destino, ignore_errors=True)

    print(f"falha: {resultado.stderr.strip()[:200]}")
    return False


# =============================================================
# Resolver Commits
# -------------------------------------------------------------
# Converte hashes abreviados em completos
# =============================================================
def resolver_commits(pasta: Path, hashes: list[str]) -> dict[str, str]:
    if not hashes:
        return {}

    # Todos de uma vez pela entrada padrão, em vez de uma chamada
    # por commit: alguns repositórios têm milhares deles
    resultado = subprocess.run(
        ["git", "-C", str(pasta), "cat-file", "--batch-check"],
        input="\n".join(hashes) + "\n",
        capture_output=True, text=True, timeout=600,
    )

    mapa = {}
    for informado, linha in zip(hashes, resultado.stdout.splitlines()):
        partes = linha.split()
        # Sucesso -> "<hash completo> commit <tamanho>"
        # Falha   -> "<consulta> missing"
        if len(partes) >= 2 and partes[1] == "commit":
            mapa[informado] = partes[0]

    return mapa


# =============================================================
# Medir Historico do Repo
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

    # Para cada commit, de quais arquivos precisamos. É isso que
    # permite fotografar só o necessário em vez do repositório inteiro.
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

        # Grava o hash completo, para a linha poder ser conferida
        # direto no repositório
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
# Montar
# -------------------------------------------------------------
# Executa as duas fases e grava o dataset
# =============================================================
def montar() -> pd.DataFrame:
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
    print("FASE 1 — métricas de código (a partir do parquet)")
    print("-" * 70 + "\n")

    # Reaproveitar a Fase 1 é o que impede que uma interrupção
    # durante a Fase 2 custe também a releitura do parquet
    codigo = None if config.FORCAR_MONTAGEM else ler_fase1_do_disco()

    if codigo is None:
        codigo = medir_codigo()
        gravar_fase1_no_disco(codigo)

    print("\n" + "-" * 70)
    print("FASE 2 — métricas de histórico (a partir dos clones)")
    print("-" * 70 + "\n")

    partes, falharam = [], []

    for repositorio, tabela in codigo.groupby("repositorio"):
        parcial = pasta_parciais / f"{repositorio.replace('/', '__')}.csv"

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

    # Remove linhas de parciais antigos que saíram do escopo
    dentro = dataset["repositorio"].map(repositorio_incluido)
    if not dentro.all():
        fora = sorted(dataset.loc[~dentro, "repositorio"].unique())
        print(f"\n  {int((~dentro).sum())} linhas de parciais antigos "
              f"estão fora do escopo e foram removidas: "
              f"{', '.join(fora)}")
        dataset = dataset[dentro].reset_index(drop=True)

    # A divisão é aplicada aqui, não guardada nos parciais. Medir é
    # caro e dividir é instantâneo, então trocar de estratégia não
    # exige remedir nada.
    dataset[features.COLUNA_PARTICAO] = divisao.dividir(dataset)

    features.conferir_contrato(dataset.columns)
    dataset = dataset[features.COLUNAS_CSV]

    config.PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(config.ARQUIVO_DATASET, index=False, encoding="utf-8")

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
    argumentos = parser.parse_args()

    config.conferir_local()
    config.conferir_nomes()

    # O argumento sobrepõe o config, para experimentar sem editar arquivo
    if argumentos.amostra is not None:
        config.TAMANHO_AMOSTRA = argumentos.amostra

    if argumentos.listar:
        listar_repositorios()
    elif argumentos.extrair_amostra is not None:
        extrair_amostra(argumentos.extrair_amostra,
                        Path(argumentos.destino))
    else:
        montar()


if __name__ == "__main__":
    main()
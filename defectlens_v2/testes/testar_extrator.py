"""
Confere o extrator e a Frente 2 num repositório Git pequeno, criado na
hora numa pasta temporária, sem usar a rede.

CMD -> python defectlens_v2/testes/testar_extrator.py
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import config
from extrator import extracao, features
from frente2_predicao import prever
from frente2_predicao import repositorio as acesso

DIA = 86400
INICIO = 1_700_000_000


# =============================================================
# Git
# -------------------------------------------------------------
# Roda o git na pasta de teste, com autor e data fixos
# =============================================================
def git(pasta: Path, *argumentos: str, autor: str = "ana",
        instante: int = INICIO) -> None:
    ambiente = {**os.environ,
                "GIT_AUTHOR_NAME": autor, "GIT_COMMITTER_NAME": autor,
                "GIT_AUTHOR_EMAIL": f"{autor}@teste",
                "GIT_COMMITTER_EMAIL": f"{autor}@teste",
                "GIT_AUTHOR_DATE": f"{instante} +0000",
                "GIT_COMMITTER_DATE": f"{instante} +0000"}
    subprocess.run(["git", "-C", str(pasta), "-c", "core.autocrlf=false",
                    "-c", "commit.gpgsign=false", *argumentos],
                   check=True, capture_output=True, env=ambiente)


# =============================================================
# Gravar
# -------------------------------------------------------------
# Escreve um arquivo com um número de linhas
# =============================================================
def gravar(pasta: Path, caminho: str, linhas: int, marca: str = "x") -> None:
    destino = pasta / caminho
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("".join(f"{marca} = {i}\n" for i in range(linhas)),
                       encoding="utf-8", newline="\n")


# =============================================================
# Criar Repositorio
# -------------------------------------------------------------
# Quatro commits: criação, mudança, renomeio e um commit enorme
# =============================================================
def criar_repositorio(pasta: Path) -> None:
    git(pasta, "init", "--quiet", "--initial-branch=main")

    gravar(pasta, "pacote/nucleo.py", 10)
    gravar(pasta, "tests/test_nucleo.py", 5)
    gravar(pasta, "LEIAME.md", 3)
    git(pasta, "add", "-A")
    git(pasta, "commit", "--quiet", "-m", "cria o projeto")

    gravar(pasta, "pacote/nucleo.py", 14)
    gravar(pasta, "pacote/util.py", 6)
    git(pasta, "add", "-A")
    git(pasta, "commit", "--quiet", "-m", "acrescenta util", autor="bia",
        instante=INICIO + 2 * DIA)

    git(pasta, "mv", "pacote/nucleo.py", "pacote/centro.py")
    git(pasta, "commit", "--quiet", "-m", "renomeia o nucleo",
        instante=INICIO + 3 * DIA)

    gravar(pasta, "pacote/centro.py", 1300, marca="y")
    git(pasta, "add", "-A")
    git(pasta, "commit", "--quiet", "-m", "reescreve tudo",
        instante=INICIO + 5 * DIA)


# =============================================================
# Testar Escopo
# -------------------------------------------------------------
# Só .py de código entra; testes, docs e setup ficam de fora
# =============================================================
def testar_escopo() -> None:
    assert features.arquivo_no_escopo("pacote/nucleo.py")
    assert not features.arquivo_no_escopo("tests/test_nucleo.py")
    assert not features.arquivo_no_escopo("pacote/test/apoio.py")
    assert not features.arquivo_no_escopo("pacote/nucleo_test.py")
    assert not features.arquivo_no_escopo("docs/conf.py")
    assert not features.arquivo_no_escopo("setup.py")
    assert not features.arquivo_no_escopo("LEIAME.md")


# =============================================================
# Testar Endereco
# -------------------------------------------------------------
# As formas aceitas de endereço e a recusa das demais
# =============================================================
def testar_endereco() -> None:
    assert acesso.interpretar_endereco("pallets/flask") == ("pallets/flask",
                                                            None)
    assert acesso.interpretar_endereco(
        "https://github.com/psf/black.git") == ("psf/black", None)
    assert acesso.interpretar_endereco(
        "github.com/a/b/tree/dev") == ("a/b", "dev")

    try:
        acesso.interpretar_endereco("não é endereço")
    except acesso.ErroDeAnalise:
        return

    raise AssertionError("endereço inválido foi aceito")


# =============================================================
# Testar Extracao
# -------------------------------------------------------------
# Medidas de commit, histórico por arquivo e renomeio
# =============================================================
def testar_extracao(pasta: Path) -> tuple:
    medidas, retratos, info = extracao.extrair(pasta, "teste")
    medidas = medidas.set_index("assunto")

    assert info["commits"] == 4
    assert info["referencia"] == INICIO + 5 * DIA

    criacao = medidas.loc["cria o projeto"]
    assert criacao["commit_arquivos"] == 3
    assert criacao["commit_adicionadas"] == 18
    assert criacao["commit_pastas"] == 3 and criacao["commit_topos"] == 3
    assert criacao["autor_commits"] == 0

    segundo = medidas.loc["acrescenta util"]
    assert segundo["commit_adicionadas"] == 10
    assert segundo["commit_removidas"] == 0

    do_segundo = retratos[retratos["commit"] == segundo["commit"]]
    assert sorted(do_segundo["arquivo"]) == ["pacote/nucleo.py",
                                             "pacote/util.py"]
    nucleo = do_segundo.set_index("arquivo").loc["pacote/nucleo.py"]
    assert nucleo["revisoes"] == 2 and nucleo["autores"] == 2
    assert nucleo["churn"] == 14 and nucleo["idade_dias"] == 2.0
    assert nucleo["dias_desde_anterior"] == 2.0
    assert nucleo["arquivo_adicionadas"] == 4

    reescrita = medidas.loc["reescreve tudo"]
    centro = retratos[retratos["commit"] == reescrita["commit"]].iloc[0]
    assert centro["arquivo"] == "pacote/centro.py"
    assert centro["revisoes"] == 4, "o renomeio deve carregar o histórico"
    assert "tests/test_nucleo.py" not in set(retratos["arquivo"])

    return medidas.reset_index(), retratos, info


# =============================================================
# Testar Dominio
# -------------------------------------------------------------
# O commit enorme fica fora do domínio, com o motivo
# =============================================================
def testar_dominio(medidas, retratos) -> None:
    tabela = features.montar_retratos(medidas, retratos)
    assert list(tabela[features.FEATURES_MODELO].columns) == (
        features.FEATURES_MODELO)

    grande = tabela[tabela["assunto"] == "reescreve tudo"]
    assert not features.no_dominio(grande).any()
    assert "linhas alteradas" in features.motivo_fora_do_dominio(
        grande.iloc[0].to_dict())

    pequeno = tabela[tabela["assunto"] == "acrescenta util"]
    assert features.no_dominio(pequeno).all()
    assert (pequeno["py_arquivos"] == 2).all()
    assert (pequeno["commit_churn"] == 10).all()


# =============================================================
# Testar Resultado
# -------------------------------------------------------------
# O resultado da Frente 2 com o modelo treinado, sem rede
# =============================================================
def testar_resultado(medidas, retratos, info) -> None:
    if not config.ARQUIVO_MODELO.exists():
        print("      (sem modelo treinado: teste do resultado pulado)")
        return

    pacote = prever.carregar_modelo()
    resultado = prever.montar_resultado(pacote, medidas, retratos,
                                        info["referencia"])

    assert resultado["resumo"]["avaliados"] == 2
    assert resultado["resumo"]["fora_do_dominio"] == 2
    assert resultado["janela"]["sem_py"] == 0
    assert len(resultado["fora_do_dominio"]) == 2

    for commit in resultado["commits"]:
        assert 0 <= commit["nota"] <= 1 and 0 <= commit["chance"] <= 1
        assert commit["faixa"] in ("alto", "médio", "baixo")
        assert commit["arquivos_alterados"]

    posicoes = sorted(c["posicao_risco"] for c in resultado["commits"])
    assert posicoes == [1, 2]
    assert resultado["curvas"]["risco"][-1] == [1.0, 1.0]
    assert abs(sum(f["repositorio"] for f in resultado["distribuicao"])
               - 1.0) < 1e-3


if __name__ == "__main__":
    testar_escopo()
    print("  ok  testar_escopo")
    testar_endereco()
    print("  ok  testar_endereco")

    with tempfile.TemporaryDirectory() as temporaria:
        raiz = Path(temporaria) / "repo"
        raiz.mkdir()
        criar_repositorio(raiz)

        extraido = testar_extracao(raiz)
        print("  ok  testar_extracao")
        testar_dominio(extraido[0], extraido[1])
        print("  ok  testar_dominio")
        testar_resultado(*extraido)
        print("  ok  testar_resultado")

        acesso.apagar_pasta(raiz)

    print("\n  5 testes passaram.")

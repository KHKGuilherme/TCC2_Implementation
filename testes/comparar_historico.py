"""
Confere que a travessia retomável dá o mesmo resultado do PyDriller.

A referência são os CSVs por repositório já gravados pelo PyDriller em
dados/parciais. O teste mede o mesmo repositório com
frente1_treinamento/historico_retomavel.py e compara as colunas de
histórico, linha a linha. Depois repete a medição interrompendo a
travessia no meio, e exige que a retomada chegue ao mesmo resultado.

Uso:
    python testes/comparar_historico.py NOME_DO_REPOSITORIO
"""

import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "frente1_treinamento"))

import config
import historico_retomavel
import montar_dataset
from frente2_predicao import historico_rapido


# =============================================================
# Pedir Fotografias
# -------------------------------------------------------------
# Monta o pedido a partir do CSV gravado pelo PyDriller
# =============================================================
def pedir_fotografias(referencia: pd.DataFrame) -> dict[str, set[str]]:
    pedido: dict[str, set[str]] = {}
    for commit, arquivo in zip(referencia["commit"], referencia["arquivo"]):
        pedido.setdefault(commit, set()).add(arquivo)
    return pedido


# =============================================================
# Comparar
# -------------------------------------------------------------
# Conta as células diferentes entre a referência e as fotografias
# =============================================================
def comparar(referencia: pd.DataFrame, fotografias: dict) -> int:
    diferencas = 0

    for linha in referencia.to_dict("records"):
        medidas = fotografias.get(linha["commit"], {}).get(linha["arquivo"])

        if medidas is None:
            diferencas += 1
            continue

        for coluna, valor in medidas.items():
            if abs(float(valor) - float(linha[coluna])) > 1e-9:
                diferencas += 1
                if diferencas <= 5:
                    print(f"    {linha['arquivo']} @ {linha['commit'][:8]} "
                          f"{coluna}: PyDriller {linha[coluna]}, "
                          f"rápido {valor}")

    return diferencas


# =============================================================
# Interromper no Meio
# -------------------------------------------------------------
# Força uma queda na metade da travessia, depois de gravar o ponto
# =============================================================
def interromper_no_meio(pasta: Path, pedido: dict, ponto: Path) -> None:
    class Queda(Exception):
        pass

    original = historico_retomavel.gravar_ponto

    # A metade do trecho percorrido, que acaba no último commit pedido
    hashes = historico_rapido.listar_commits(pasta)
    metade = max(i for i, c in enumerate(hashes) if c in pedido) // 2

    def gravar_e_cair(arquivo, dados):
        if dados["feitos"] >= metade:
            original(arquivo, dados)
            raise Queda

    historico_retomavel.gravar_ponto = gravar_e_cair
    config.SEGUNDOS_ENTRE_PONTOS = 0

    try:
        historico_retomavel.medir_nos_commits(pasta, pedido, ponto)
        raise SystemExit("a travessia terminou sem chegar a cair")
    except Queda:
        pass
    finally:
        historico_retomavel.gravar_ponto = original
        config.SEGUNDOS_ENTRE_PONTOS = 10 ** 9


# =============================================================
# Main
# =============================================================
def main() -> None:
    nome = sys.argv[1]
    referencia = pd.read_csv(
        montar_dataset.pasta_de_trabalho() / f"{nome}.csv")
    pedido = pedir_fotografias(referencia)
    pasta = config.PASTA_CLONES / nome
    ponto = montar_dataset.arquivo_do_ponto(f"_teste_{nome}")
    ponto.unlink(missing_ok=True)

    if not montar_dataset.clonar(nome, pasta):
        raise SystemExit("o clone falhou")

    print(f"{nome}: {len(referencia)} linhas, {len(pedido)} commits pedidos, "
          f"{len(historico_rapido.listar_commits(pasta))} commits no clone")

    # Direta, do início ao fim
    config.SEGUNDOS_ENTRE_PONTOS = 10 ** 9
    direta = historico_retomavel.medir_nos_commits(pasta, pedido, ponto)
    erros_direta = comparar(referencia, direta)
    print(f"  direta   : {erros_direta} diferenças")

    # Cai na metade e retoma do ponto
    interromper_no_meio(pasta, pedido, ponto)
    if not ponto.exists():
        raise SystemExit("a queda não deixou ponto de retomada")

    retomada = historico_retomavel.medir_nos_commits(pasta, pedido, ponto)
    print()
    ponto.unlink(missing_ok=True)
    erros_retomada = comparar(referencia, retomada)
    print(f"  retomada : {erros_retomada} diferenças")

    if erros_direta or erros_retomada or direta != retomada:
        raise SystemExit("RESULTADOS DIFERENTES")

    print("  IGUAIS")

    if config.APAGAR_CLONES:
        montar_dataset.apagar_pasta(pasta)


if __name__ == "__main__":
    main()

"""
Desenha o modelo treinado: o peso de cada feature e uma árvore.

Três figuras, e a diferença entre as duas primeiras é o ponto
principal deste arquivo:

  grafico_importancia.png  -> o peso que o próprio modelo declara
  grafico_permutacao.png   -> quanto o AUC cai se a feature for
                              embaralhada
  grafico_arvore.png       -> uma árvore de decisão, por dentro

A importância declarada é enganosa quando as features são
correlacionadas, e as nossas chegam a 0,91 entre si. Se 'linhas' e
'churn' carregam a mesma informação, a árvore escolhe uma das duas
quase por sorteio em cada nó, e o crédito se divide entre elas.
Duas features essenciais aparecem como duas medianas.

A permutação mede outra coisa: embaralha a coluna e vê quanto o
desempenho piora. É a pergunta honesta, e com features redundantes
ela responde baixo para as duas — porque a informação continua
disponível na outra. Ler as duas juntas é o que mostra a
redundância.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

import config
from extrator import features


# =============================================================
# Abrir Matplotlib
# -------------------------------------------------------------
# Importa sob demanda e avisa se faltar
# =============================================================
def abrir_matplotlib():
    # Importado aqui dentro para que a falta da biblioteca não
    # impeça o treino: as figuras são ilustração, o modelo é o
    # resultado
    try:
        import matplotlib
        matplotlib.use("Agg")  # sem janela: só grava arquivo
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        print("\n  Gráficos não gerados: falta o matplotlib.")
        print("    pip install matplotlib")
        return None


# =============================================================
# Pesos Declarados
# -------------------------------------------------------------
# O que o modelo diz sobre cada feature
# =============================================================
def pesos_declarados(modelo) -> tuple[np.ndarray, str] | None:
    interno = modelo.named_steps["modelo"]

    if hasattr(interno, "feature_importances_"):
        return interno.feature_importances_, "contribuição nas árvores"

    if hasattr(interno, "coef_"):
        bruto = np.abs(interno.coef_[0])
        total = bruto.sum()
        return (bruto / total if total else bruto), "coeficientes padronizados"

    return None


# =============================================================
# Desenhar Barras
# -------------------------------------------------------------
# Gráfico de barras horizontais de uma medida de peso
# =============================================================
def desenhar_barras(plt, valores: np.ndarray, nomes: list[str],
                    titulo: str, rodape: str, destino: Path,
                    erro: np.ndarray | None = None) -> None:
    ordem = np.argsort(valores)

    # Altura proporcional ao número de features: com 29 barras uma
    # figura de altura fixa sobrepõe os rótulos
    altura = max(4.5, 0.3 * len(nomes) + 1.5)
    figura, eixo = plt.subplots(figsize=(10, altura))

    posicoes = np.arange(len(nomes))
    eixo.barh(posicoes, valores[ordem],
              xerr=None if erro is None else erro[ordem],
              color="#4878a8", error_kw={"ecolor": "#303030",
                                         "elinewidth": 1})

    eixo.set_yticks(posicoes)
    eixo.set_yticklabels([nomes[i] for i in ordem], fontsize=9)
    eixo.set_xlabel(rodape, fontsize=10)
    eixo.set_title(titulo, fontsize=12, pad=12)
    eixo.grid(axis="x", alpha=0.3)

    figura.tight_layout()
    figura.savefig(destino, dpi=150)
    plt.close(figura)


# =============================================================
# Salvar Importancia
# -------------------------------------------------------------
# O peso que o modelo declara para cada feature
# =============================================================
def salvar_importancia(plt, modelo, nome_modelo: str) -> bool:
    declarado = pesos_declarados(modelo)

    if declarado is None:
        print(f"    importância: {nome_modelo} não expõe pesos")
        return False

    valores, origem = declarado

    desenhar_barras(
        plt, valores, list(features.FEATURES),
        f"Peso de cada feature — {nome_modelo}",
        origem, config.ARQUIVO_GRAFICO_IMPORTANCIA)

    return True


# =============================================================
# Salvar Permutacao
# -------------------------------------------------------------
# Quanto o AUC cai ao embaralhar cada feature
# =============================================================
def salvar_permutacao(plt, modelo, teste: pd.DataFrame,
                      nome_modelo: str) -> bool:
    from sklearn.inspection import permutation_importance

    # Embaralhar uma coluna e reavaliar custa uma previsão inteira,
    # e são 29 colunas vezes as repetições. Numa amostra o
    # resultado é o mesmo e o tempo é tratável.
    amostra = teste
    if len(teste) > config.AMOSTRA_PERMUTACAO:
        amostra = teste.sample(n=config.AMOSTRA_PERMUTACAO,
                               random_state=config.SEMENTE)

    X = amostra[features.FEATURES].to_numpy(dtype=float)
    y = amostra[features.COLUNA_ALVO].to_numpy()

    if len(np.unique(y)) < 2:
        print("    permutação: a amostra tem uma classe só")
        return False

    resultado = permutation_importance(
        modelo, X, y,
        scoring="roc_auc",
        n_repeats=config.REPETICOES_PERMUTACAO,
        random_state=config.SEMENTE,
        n_jobs=-1,
    )

    desenhar_barras(
        plt, resultado.importances_mean, list(features.FEATURES),
        f"Queda do AUC ao embaralhar a feature — {nome_modelo}\n"
        f"({len(amostra)} linhas do conjunto reservado, "
        f"{config.REPETICOES_PERMUTACAO} repetições)",
        "queda do AUC", config.ARQUIVO_GRAFICO_PERMUTACAO,
        erro=resultado.importances_std)

    return True


# =============================================================
# Primeira Arvore
# -------------------------------------------------------------
# Tira uma árvore de dentro do modelo, se houver
# =============================================================
def primeira_arvore(modelo):
    interno = modelo.named_steps["modelo"]

    arvores = getattr(interno, "estimators_", None)
    if arvores is None:
        return None

    # O Gradient Boosting guarda uma matriz de árvores, o Random
    # Forest uma lista
    arvores = np.asarray(arvores).ravel()
    return arvores[0] if len(arvores) else None


# =============================================================
# Desfazer Escala
# -------------------------------------------------------------
# Põe os limiares da árvore de volta na unidade original
# =============================================================
def desfazer_escala(modelo, arvore) -> None:
    escala = modelo.named_steps.get("escala")

    if escala is None or not hasattr(escala, "mean_"):
        return

    coluna = arvore.tree_.feature
    folha = coluna < 0  # nó folha não tem feature nem limiar

    # z = (x - media) / desvio  ->  x = z * desvio + media
    bruto = (arvore.tree_.threshold * escala.scale_[coluna]
             + escala.mean_[coluna])

    arvore.tree_.threshold[~folha] = bruto[~folha]


# =============================================================
# Salvar Arvore
# -------------------------------------------------------------
# Desenha uma árvore do modelo, cortada na profundidade
# =============================================================
def salvar_arvore(plt, modelo, nome_modelo: str) -> bool:
    from sklearn.tree import plot_tree

    arvore = primeira_arvore(modelo)

    if arvore is None:
        print(f"    árvore: {nome_modelo} não é feito de árvores")
        return False

    profundidade = arvore.get_depth()
    cortada = profundidade > config.PROFUNDIDADE_DO_GRAFICO

    figura, eixo = plt.subplots(figsize=(22, 11))

    # Os limiares da árvore estão em unidades PADRONIZADAS, porque
    # o StandardScaler vem antes dela no Pipeline. Desenhar assim
    # produz "churn <= -0.299", que não quer dizer nada para quem
    # lê: -0,299 é desvio padrão, não churn.
    #
    # Aqui os limiares voltam para a unidade original, só enquanto
    # a figura é desenhada, e são restaurados no finally. O modelo
    # já foi gravado em disco antes disto, então nem uma falha no
    # meio afetaria o que foi salvo.
    original = arvore.tree_.threshold.copy()

    try:
        desfazer_escala(modelo, arvore)

        # O corte de profundidade não é estética: uma árvore
        # treinada em 97 mil linhas chega a 44 níveis e sai como
        # uma mancha preta. Os primeiros níveis são os que mostram
        # por onde o modelo começa a decidir.
        plot_tree(
            arvore,
            max_depth=config.PROFUNDIDADE_DO_GRAFICO,
            feature_names=list(features.FEATURES),
            class_names=["limpo", "defeituoso"],
            filled=True, rounded=True, proportion=True,
            impurity=False, fontsize=8, ax=eixo,
        )
    finally:
        arvore.tree_.threshold[:] = original

    titulo = (f"Uma árvore do modelo {nome_modelo}"
              if not cortada else
              f"Uma árvore do modelo {nome_modelo}, "
              f"primeiros {config.PROFUNDIDADE_DO_GRAFICO} "
              f"de {profundidade} níveis")

    eixo.set_title(
        titulo + "\nLimiares na unidade original. A cor indica a classe "
                 "dominante; a proporção, a parcela do treino que "
                 "chega ao nó",
        fontsize=13, pad=16)

    figura.tight_layout()
    figura.savefig(config.ARQUIVO_GRAFICO_ARVORE, dpi=110)
    plt.close(figura)

    return True


# =============================================================
# Desenhar
# -------------------------------------------------------------
# Gera as três figuras do modelo escolhido
# =============================================================
def desenhar(modelo, nome_modelo: str, teste: pd.DataFrame) -> None:
    """Grava os gráficos do modelo em dados/."""
    plt = abrir_matplotlib()
    if plt is None:
        return

    print("\n" + "-" * 70)
    print("GRÁFICOS DO MODELO")
    print("-" * 70 + "\n")

    config.PASTA_DADOS.mkdir(parents=True, exist_ok=True)

    if salvar_importancia(plt, modelo, nome_modelo):
        print(f"    peso declarado : {config.ARQUIVO_GRAFICO_IMPORTANCIA}")

    if salvar_arvore(plt, modelo, nome_modelo):
        print(f"    árvore         : {config.ARQUIVO_GRAFICO_ARVORE}")

    if config.GERAR_PERMUTACAO and len(teste):
        print("    permutação     : calculando...", end=" ", flush=True)
        if salvar_permutacao(plt, modelo, teste, nome_modelo):
            print(f"\r    permutação     : "
                  f"{config.ARQUIVO_GRAFICO_PERMUTACAO}      ")
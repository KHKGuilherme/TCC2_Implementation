"""
Frente 1, etapa 6 — junta tabelas e gráficos num relatório HTML estático.

CMD -> python defectlens_v2/frente1_treinamento/relatorio.py
       grava resultados/relatorio.html (abre direto no navegador)
"""

import html
import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config

ESTILO = """
:root { --fundo:#f9f9f7; --papel:#fcfcfb; --tinta:#0b0b0b; --tinta2:#52514e;
        --borda:#e1e0d9; --azul:#2a78d6; }
@media (prefers-color-scheme: dark) {
  :root { --fundo:#0d0d0d; --papel:#1a1a19; --tinta:#f0efec;
          --tinta2:#c3c2b7; --borda:#2c2c2a; --azul:#3987e5; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--fundo); color:var(--tinta);
       font:15px/1.55 system-ui, sans-serif; }
main { max-width:1180px; margin:0 auto; padding:24px 16px 64px; }
h1 { font-size:28px; margin:8px 0 4px; }
h2 { font-size:19px; margin:44px 0 6px; padding-top:14px;
     border-top:1px solid var(--borda); }
p { color:var(--tinta2); max-width:86ch; }
figure { margin:14px 0 0; background:var(--papel);
         border:1px solid var(--borda); border-radius:10px; padding:8px; }
figure img { width:100%; height:auto; display:block; border-radius:6px; }
.rolagem { overflow-x:auto; background:var(--papel);
           border:1px solid var(--borda); border-radius:10px; }
table { border-collapse:collapse; width:100%; font-size:13.5px; }
th, td { padding:7px 10px; text-align:right; white-space:nowrap;
         border-bottom:1px solid var(--borda);
         font-variant-numeric:tabular-nums; }
th:first-child, td:first-child { text-align:left; }
th { color:var(--tinta2); font-weight:600; }
tr.destaque td { font-weight:700; color:var(--azul); }
.cartoes { display:grid; gap:12px;
           grid-template-columns:repeat(auto-fit, minmax(210px, 1fr)); }
.cartao { background:var(--papel); border:1px solid var(--borda);
          border-radius:10px; padding:14px; }
.cartao strong { display:block; font-size:26px; }
.cartao span { color:var(--tinta2); font-size:13px; }
"""

SECOES = [
    ("O dataset: partições e construção", "01_particoes_dataset.png",
     "A taxa de defeito de train não é natural: o Defectors reamostra os "
     "commits limpos. As partições test e val guardam a proporção original, "
     "e por isso viram o teste de sensibilidade, e não um defeito do rótulo."),
    ("Domínio do rótulo", "02_taxa_por_tamanho.png",
     "Commits acima do corte do Defectors são limpos por construção. Ficam "
     "fora do treino e da avaliação principal."),
    ("Efeito do filtro de domínio", "09_dominio_antes_depois.png",
     "Antes e depois de tirar da avaliação os commits fora do domínio."),
    ("Comparação por repositório", "03_auc_por_repositorio.png",
     "Cada repositório fica de fora do treino uma vez."),
    ("Todos os métodos", "04_comparacao_metodos.png",
     "Baselines triviais, modelos e o DefectLens original nos mesmos commits."),
    ("Antes e depois de cada mudança", "08_ablacao.png",
     "O que cada grupo de medidas acrescenta."),
    ("Significância", "14_significancia.png",
     "Wilcoxon pareado entre repositórios, correção de Holm e delta de Cliff."),
    ("Curvas ROC", "05_curvas_roc.png",
     "Com todos os commits juntos, nos dois cenários."),
    ("Curvas de esforço", "06_curvas_de_esforco.png",
     "Defeitos encontrados conforme as linhas revisadas."),
    ("Medidas que consideram o esforço", "07_medidas_de_esforco.png",
     "Recall@20%Effort e Popt."),
    ("Sensibilidade: proporção original", "10_sensibilidade_natural.png",
     "Os mesmos modelos avaliados em test e val."),
    ("Importância por permutação", "11_importancia_permutacao.png",
     "Medida no repositório deixado de fora."),
    ("Calibração", "12_calibracao.png",
     "A nota bruta não é uma chance; a calibrada se aproxima."),
    ("Faixas de risco do site", "13_faixas_de_risco.png",
     "A taxa de defeito observada em cada faixa."),
]

COLUNAS_DA_TABELA = [
    ("nome", "Método"), ("repositorios", "Repos"),
    ("auc", "AUC mediano"), ("auc_agregado", "AUC agregado"),
    ("topo_10", "Topo 10%"), ("revocacao_esforco_risco", "R@20% risco"),
    ("revocacao_esforco_densidade", "R@20% por linha"),
    ("popt_densidade", "Popt por linha"), ("ifa_densidade", "IFA"),
]


# =============================================================
# Formatar
# -------------------------------------------------------------
# Número com vírgula decimal, ou o texto como veio
# =============================================================
def formatar(valor) -> str:
    if isinstance(valor, float):
        return f"{valor:.3f}".replace(".", ",")

    return html.escape(str(valor))


# =============================================================
# Tabela de Metodos
# -------------------------------------------------------------
# A tabela principal de um cenário, em HTML
# =============================================================
def tabela_de_metodos(resumo: pd.DataFrame, cenario: str) -> str:
    recorte = resumo[resumo["cenario"] == cenario].sort_values(
        "auc", ascending=False)
    cabecalho = "".join(f"<th>{titulo}</th>" for _, titulo in COLUNAS_DA_TABELA)
    linhas = []

    for _, linha in recorte.iterrows():
        classe = (' class="destaque"'
                  if linha["metodo"] == config.METODO_PRINCIPAL else "")
        celulas = "".join(f"<td>{formatar(linha[coluna])}</td>"
                          for coluna, _ in COLUNAS_DA_TABELA)
        linhas.append(f"<tr{classe}>{celulas}</tr>")

    return (f'<div class="rolagem"><table><thead><tr>{cabecalho}</tr></thead>'
            f'<tbody>{"".join(linhas)}</tbody></table></div>')


# =============================================================
# Cartoes
# -------------------------------------------------------------
# Os números de abertura do relatório
# =============================================================
def cartoes(geral: dict) -> str:
    principal = geral["metodos"]["principal"]
    natural = geral["metodos"]["natural"]
    v2 = principal[config.METODO_PRINCIPAL]
    la = principal[config.METODO_REFERENCIA]

    itens = [
        (formatar(v2["auc"]), "AUC mediano do v2 em projeto nunca visto"),
        (formatar(la["auc"]), "AUC mediano ordenando só por linhas adicionadas"),
        (formatar(principal[config.METODO_ORIGINAL]["auc"]),
         "AUC mediano do modelo original, nos mesmos commits"),
        (formatar(natural[config.METODO_PRINCIPAL]["auc_agregado"]),
         "AUC do v2 na proporção original (test + val)"),
        (str(geral["fora_do_dominio"]),
         "commits fora do domínio do rótulo, nenhum defeituoso"),
    ]

    return ('<div class="cartoes">' + "".join(
        f'<div class="cartao"><strong>{valor}</strong><span>{rotulo}</span>'
        f'</div>' for valor, rotulo in itens) + "</div>")


# =============================================================
# Escrever
# -------------------------------------------------------------
# Monta e grava o relatório
# =============================================================
def escrever() -> Path:
    pasta = config.PASTA_RESULTADOS
    resumo = pd.read_csv(pasta / "resumo_metodos.csv")
    geral = json.loads((pasta / "resumo.json").read_text(encoding="utf-8"))

    partes = [
        "<h1>DefectLens v2 — relatório da avaliação</h1>",
        "<p>Priorização de commits para revisão em repositórios Python "
        "nunca vistos. Todos os números vêm dos scripts de "
        "<code>frente1_treinamento/</code> e estão em CSV nesta pasta.</p>",
        cartoes(geral),
    ]

    for cenario, descricao in geral["cenarios"].items():
        partes.append(f"<h2>Tabela: {html.escape(descricao)}</h2>")
        partes.append(tabela_de_metodos(resumo, cenario))

    for titulo, arquivo, texto in SECOES:
        if not (config.PASTA_GRAFICOS / arquivo).exists():
            continue

        partes.append(f"<h2>{html.escape(titulo)}</h2>"
                      f"<p>{html.escape(texto)}</p>"
                      f'<figure><img src="graficos/{arquivo}" '
                      f'alt="{html.escape(titulo)}"></figure>')

    pagina = (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
              f'<meta name="viewport" content="width=device-width, '
              f'initial-scale=1"><title>DefectLens v2 — avaliação</title>'
              f'<style>{ESTILO}</style></head><body><main>'
              f'{"".join(partes)}</main></body></html>')

    config.ARQUIVO_RELATORIO.write_text(pagina, encoding="utf-8")
    return config.ARQUIVO_RELATORIO


if __name__ == "__main__":
    print(f"  {escrever()}")

"""
Frente 1 — roda o pipeline inteiro, na ordem. Cada etapa grava em disco e a
validação pula o que já está pronto, então dá para rodar de novo depois de
um reinício.

CMD -> python defectlens_v2/frente1_treinamento/principal.py
       python defectlens_v2/frente1_treinamento/principal.py --refazer
"""

import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import analisar
import avaliar
import config
import graficos
import montar_commits
import relatorio
import treinar_final


# =============================================================
# Rodar
# -------------------------------------------------------------
# Monta, valida, analisa, desenha, treina e escreve o relatório
# =============================================================
def rodar(refazer: bool) -> None:
    inicio = time.time()

    if refazer or not config.ARQUIVO_RETRATOS.exists():
        print("\n  [1/6] montando as tabelas de retratos e de commits")
        montar_commits.resumir(*montar_commits.montar())
    else:
        print("\n  [1/6] tabelas já montadas")

    print("\n  [2/6] validação em projeto nunca visto")
    avaliar.avaliar(refazer)

    print("\n  [3/6] medidas, significância e calibração")
    analisar.mostrar(analisar.analisar())

    print("\n  [4/6] gráficos")
    for caminho in graficos.desenhar():
        print(f"  {caminho}")

    print("\n  [5/6] modelo final")
    final = treinar_final.treinar_final()
    print(f"  {final['nome']}: {len(final['features'])} features -> "
          f"{config.ARQUIVO_MODELO}")

    print("\n  [6/6] relatório")
    print(f"  {relatorio.escrever()}")
    print(f"\n  Pronto em {time.time() - inicio:.0f} s.")


if __name__ == "__main__":
    rodar(refazer="--refazer" in sys.argv)

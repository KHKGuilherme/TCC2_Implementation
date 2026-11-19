import importlib
import sys

PASSOS = {
    "extrair": "extrair_historicos",
    "montar": "montar_retratos",
    "validar": "validar",
    "avaliar": "avaliar",
    "treinar": "treinar",
    "graficos": "graficos",
    "exemplos": "exemplos",
}

SEQUENCIA = ["extrair", "montar", "validar", "avaliar", "treinar", "graficos"]


def executar(passo: str, argumentos: list[str]) -> None:
    modulo = importlib.import_module(f"treino.{PASSOS[passo]}")
    modulo.principal(argumentos)


def principal(argumentos: list[str]) -> None:
    opcoes = [*PASSOS, "tudo"]
    if not argumentos or argumentos[0] not in opcoes:
        print("uso: python -m treino {" + "|".join(opcoes) + "} [repositorios]")
        raise SystemExit(1)
    if argumentos[0] == "tudo":
        for passo in SEQUENCIA:
            executar(passo, [])
        return
    executar(argumentos[0], argumentos[1:])


if __name__ == "__main__":
    principal(sys.argv[1:])

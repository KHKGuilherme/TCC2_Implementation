import json
import sys

from predicao.analisar import analisar
from predicao.erros import ErroDeAnalise


def mostrar(resultado: dict, quantos: int = 20) -> None:
    resumo = resultado["resumo"]
    print(f"\n{resultado['repositorio']} @ {resultado['commit'][:10]} "
          f"({resultado['data_commit']}), {resultado['duracao_s']} s")
    print(f"  arquivos avaliados: {resumo['avaliados']}")
    print(f"  % estimada do repositório com defeito latente: {resumo['porcentagem_estimada']}% "
          f"(faixa {resumo['porcentagem_minima']}% a {resumo['porcentagem_maxima']}%)")
    print(f"  acima do limiar de {resumo['limiar']:.0%}: {resumo['risco_alto']} arquivos "
          f"({resumo['porcentagem_acima_do_limiar']}%)\n")
    for item in resultado["arquivos"][:quantos]:
        print(f"  {item['probabilidade']:6.1%}  {item['nivel']:<6} {item['caminho']}")


def principal(argumentos: list[str]) -> int:
    em_json = "--json" in argumentos
    posicionais = [a for a in argumentos if a != "--json"]
    if not posicionais:
        print("uso: python -m predicao ENDERECO [RAMO] [--json]")
        return 1
    try:
        resultado = analisar(posicionais[0], posicionais[1] if len(posicionais) > 1 else None)
    except ErroDeAnalise as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 2
    if em_json:
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(resultado, ensure_ascii=False))
    else:
        mostrar(resultado)
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))

import os

from django.http import HttpResponse

ORIGENS = [o.strip() for o in os.environ.get("DEFECTLENS_CORS", "").split(",") if o.strip()]


class Cors:
    def __init__(self, proximo):
        self.proximo = proximo

    def __call__(self, pedido):
        origem = pedido.headers.get("Origin")
        liberada = bool(origem) and ("*" in ORIGENS or origem in ORIGENS)

        if liberada and pedido.method == "OPTIONS":
            resposta = HttpResponse(status=204)
        else:
            resposta = self.proximo(pedido)

        if liberada:
            resposta["Access-Control-Allow-Origin"] = "*" if "*" in ORIGENS else origem
            resposta["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            resposta["Access-Control-Allow-Headers"] = "Content-Type"
            resposta["Access-Control-Max-Age"] = "86400"
            resposta["Vary"] = "Origin"
        return resposta

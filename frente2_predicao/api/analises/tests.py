import json
from pathlib import Path
from unittest import mock

from django.test import TestCase
from jsonschema import Draft202012Validator

from analises.models import Analise

CONTRATOS = Path(__file__).resolve().parents[3] / "contratos"
ESPECIFICACAO = json.loads((CONTRATOS / "api.openapi.json").read_text(encoding="utf-8"))
EXEMPLOS = CONTRATOS / "exemplos"


def exemplo(nome: str):
    return json.loads((EXEMPLOS / nome).read_text(encoding="utf-8"))


def erros_do_esquema(nome: str, dado) -> list[str]:
    esquema = {"$ref": f"#/components/schemas/{nome}", "components": ESPECIFICACAO["components"]}
    return [erro.message for erro in Draft202012Validator(esquema).iter_errors(dado)]


def criar_analise_pronta(commit: str = "abc123") -> Analise:
    base = exemplo("analise_flask.json")["resultado"]
    return Analise.objects.create(
        repositorio="pallets/flask", ramo="main", commit=commit, status=Analise.Status.CONCLUIDA,
        etapa="pronto", progresso=1.0, resultado=base, resumo=base["resumo"])


class TesteSaudeEModelo(TestCase):
    def test_saude(self):
        resposta = self.client.get("/api/saude/")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(erros_do_esquema("Saude", resposta.json()), [])

    def test_modelo_segue_o_contrato(self):
        resposta = self.client.get("/api/modelo/")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(erros_do_esquema("Modelo", resposta.json()), [])


class TesteAnalises(TestCase):
    def test_analise_concluida_segue_o_contrato(self):
        analise = criar_analise_pronta()
        resposta = self.client.get(f"/api/analises/{analise.id}/")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(erros_do_esquema("Analise", resposta.json()), [])

    def test_recentes_seguem_o_contrato(self):
        criar_analise_pronta()
        corpo = self.client.get("/api/analises/").json()
        self.assertEqual(len(corpo), 1)
        for item in corpo:
            self.assertEqual(erros_do_esquema("AnaliseResumo", item), [])

    def test_analise_inexistente(self):
        resposta = self.client.get("/api/analises/00000000-0000-0000-0000-000000000000/")
        self.assertEqual(resposta.status_code, 404)

    def test_endereco_invalido(self):
        resposta = self.client.post("/api/analises/", {"endereco": "isto nao e um endereco"},
                                    content_type="application/json")
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(erros_do_esquema("Erro", resposta.json()), [])

    def test_pedido_novo_entra_na_fila(self):
        with mock.patch("analises.views.repositorio.commit_remoto", return_value="abc123"), \
                mock.patch("analises.views.fila.enfileirar") as enfileirar:
            resposta = self.client.post("/api/analises/", {"endereco": "pallets/flask"},
                                        content_type="application/json")
        self.assertEqual(resposta.status_code, 202)
        self.assertEqual(erros_do_esquema("PedidoAceito", resposta.json()), [])
        self.assertFalse(resposta.json()["reaproveitada"])
        enfileirar.assert_called_once()

    def test_reaproveita_analise_pronta_do_mesmo_commit(self):
        criar_analise_pronta("abc123")
        with mock.patch("analises.views.repositorio.commit_remoto", return_value="abc123"), \
                mock.patch("analises.views.fila.enfileirar") as enfileirar:
            resposta = self.client.post("/api/analises/", {"endereco": "pallets/flask"},
                                        content_type="application/json")
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()["reaproveitada"])
        enfileirar.assert_not_called()

    def test_pedido_sem_endereco(self):
        resposta = self.client.post("/api/analises/", {}, content_type="application/json")
        self.assertEqual(resposta.status_code, 400)

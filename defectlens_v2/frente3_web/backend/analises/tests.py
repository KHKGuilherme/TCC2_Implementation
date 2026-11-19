"""
Testes da API: pedido, limite de tamanho, reaproveitamento e fila.

CMD -> cd defectlens_v2/frente3_web/backend
       python manage.py test
"""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from frente2_predicao import prever
from frente2_predicao import repositorio as acesso

from . import fila
from .models import Analise

COMMIT = "a" * 40

RESULTADO = {
    "repositorio": "dono/projeto", "ramo": "main", "commit": COMMIT,
    "modelo": {"versao": "2.0"},
    "resumo": {"avaliados": 12, "risco_alto": 2, "risco_maximo": 0.81},
    "commits": [], "duracao_s": 1.0,
}


# =============================================================
# Testes da API
# -------------------------------------------------------------
# Cada teste troca o acesso à rede e a fila por simulações
# =============================================================
class TestesDaApi(TestCase):
    # =============================================================
    # Set Up
    # -------------------------------------------------------------
    # Cliente novo e limite de pedidos zerado a cada teste
    # =============================================================
    def setUp(self):
        cache.clear()
        self.cliente = APIClient()

    # =============================================================
    # Pedir
    # -------------------------------------------------------------
    # Envia um pedido de análise com a rede simulada
    # =============================================================
    def pedir(self, endereco: str, tamanho_mb: float = 10.0):
        informacao = {"tamanho_mb": tamanho_mb, "ramo_padrao": "main",
                      "linguagem": "Python"}

        with mock.patch.object(acesso, "consultar_github",
                               return_value=informacao), \
                mock.patch.object(acesso, "commit_remoto",
                                  return_value=COMMIT), \
                mock.patch.object(fila, "enfileirar") as enfileirar:
            resposta = self.cliente.post("/api/analises/",
                                         {"endereco": endereco},
                                         format="json")

        return resposta, enfileirar

    # =============================================================
    # Test Modelo
    # -------------------------------------------------------------
    # O endpoint do modelo devolve as medidas de projeto nunca visto
    # =============================================================
    def test_modelo(self):
        resposta = self.cliente.get("/api/modelo/")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["versao"], "2.0")
        self.assertIn("principal", resposta.data["metricas"])
        self.assertIn("natural", resposta.data["metricas"])
        self.assertEqual(len(resposta.data["faixas"]), 3)
        self.assertNotIn("modelo", resposta.data)
        self.assertEqual(resposta.data["uso"]["analises"], 0)

    # =============================================================
    # Test Endereco Invalido
    # -------------------------------------------------------------
    # Um endereço que não é de repositório é recusado
    # =============================================================
    def test_endereco_invalido(self):
        resposta, enfileirar = self.pedir("isto não é um endereço")

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("erro", resposta.data)
        enfileirar.assert_not_called()

    # =============================================================
    # Test Pedido Novo
    # -------------------------------------------------------------
    # Um pedido válido cria a análise e a põe na fila
    # =============================================================
    def test_pedido_novo(self):
        resposta, enfileirar = self.pedir("https://github.com/dono/projeto")

        self.assertEqual(resposta.status_code, 202)
        self.assertFalse(resposta.data["reaproveitada"])
        enfileirar.assert_called_once()

        analise = Analise.objects.get(pk=resposta.data["id"])
        self.assertEqual(analise.repositorio, "dono/projeto")
        self.assertEqual(analise.commit, COMMIT)

    # =============================================================
    # Test Repositorio Grande
    # -------------------------------------------------------------
    # Acima do limite, o pedido é recusado antes de clonar
    # =============================================================
    def test_repositorio_grande(self):
        resposta, enfileirar = self.pedir("dono/gigante", tamanho_mb=99999)

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("limite", resposta.data["erro"])
        self.assertEqual(Analise.objects.count(), 0)
        enfileirar.assert_not_called()

    # =============================================================
    # Test Reaproveitamento
    # -------------------------------------------------------------
    # O mesmo commit já analisado não roda de novo
    # =============================================================
    def test_reaproveitamento(self):
        pronta = Analise.objects.create(
            repositorio="dono/projeto", commit=COMMIT,
            status=Analise.Status.CONCLUIDA, resultado=RESULTADO,
            resumo=RESULTADO["resumo"])

        resposta, enfileirar = self.pedir("dono/projeto")

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.data["reaproveitada"])
        self.assertEqual(str(resposta.data["id"]), str(pronta.id))
        enfileirar.assert_not_called()

    # =============================================================
    # Test Versao Antiga
    # -------------------------------------------------------------
    # Análise feita por outra versão do modelo não é reaproveitada
    # =============================================================
    def test_versao_antiga(self):
        Analise.objects.create(
            repositorio="dono/projeto", commit=COMMIT,
            status=Analise.Status.CONCLUIDA,
            resultado={**RESULTADO, "modelo": {"versao": "1.0"}})

        resposta, enfileirar = self.pedir("dono/projeto")

        self.assertEqual(resposta.status_code, 202)
        enfileirar.assert_called_once()

    # =============================================================
    # Test Analise Interrompida
    # -------------------------------------------------------------
    # Análise pendente fora da fila deste processo vira erro
    # =============================================================
    def test_analise_interrompida(self):
        analise = Analise.objects.create(repositorio="dono/projeto",
                                         status=Analise.Status.RODANDO)

        resposta = self.cliente.get(f"/api/analises/{analise.id}/")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["status"], "erro")
        self.assertIn("reiniciou", resposta.data["erro"])

    # =============================================================
    # Test Execucao
    # -------------------------------------------------------------
    # A fila grava o resultado da Frente 2 e a lista de recentes o mostra
    # =============================================================
    def test_execucao(self):
        analise = Analise.objects.create(repositorio="dono/projeto")

        with mock.patch.object(prever, "analisar", return_value=RESULTADO), \
                mock.patch.object(fila, "close_old_connections"), \
                mock.patch.object(fila.connection, "close"):
            fila.executar(str(analise.id))

        analise.refresh_from_db()
        self.assertEqual(analise.status, Analise.Status.CONCLUIDA)
        self.assertEqual(analise.resumo["avaliados"], 12)

        recentes = self.cliente.get("/api/analises/")
        self.assertEqual(len(recentes.data), 1)
        self.assertEqual(recentes.data[0]["risco_alto"], 2)

    # =============================================================
    # Test Falha da Frente 2
    # -------------------------------------------------------------
    # Um erro da análise chega ao usuário com a mensagem original
    # =============================================================
    def test_falha_da_frente_2(self):
        analise = Analise.objects.create(repositorio="dono/projeto")
        erro = prever.ErroDeAnalise("O clone passou do limite de 600 MB.")

        with mock.patch.object(prever, "analisar", side_effect=erro), \
                mock.patch.object(fila, "close_old_connections"), \
                mock.patch.object(fila.connection, "close"):
            fila.executar(str(analise.id))

        analise.refresh_from_db()
        self.assertEqual(analise.status, Analise.Status.ERRO)
        self.assertIn("limite", analise.erro)

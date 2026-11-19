import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from predicao import config, modelo, pontuar
from predicao.erros import ErroDeAnalise
from predicao.medidas import historico, metricas_historico

import construtor

CONTRATOS = Path(__file__).resolve().parents[2] / "contratos"


def carregar_exemplos() -> dict:
    return json.loads((CONTRATOS / "exemplos" / "golden_medidas.json").read_text(encoding="utf-8"))


def repositorio_de_exemplo(exemplos: dict) -> Path:
    pasta = Path(tempfile.mkdtemp(prefix="exemplo_"))
    construtor.construir(pasta, exemplos["especificacao"])
    return pasta


class TesteMedidas(unittest.TestCase):
    def test_medidas_conferem_com_o_arquivo_de_exemplos(self):
        exemplos = carregar_exemplos()
        pasta = repositorio_de_exemplo(exemplos)
        try:
            tabela = historico.ler_historico(pasta)
        finally:
            historico.apagar_pasta(pasta)
        medidas = metricas_historico.medir(metricas_historico.identificar(tabela),
                                           exemplos["instante"])
        self.assertEqual(metricas_historico.FEATURES, exemplos["features"])
        obtido = {linha["arquivo"]: linha for linha in medidas.to_dict("records")}
        self.assertEqual(set(obtido), set(exemplos["esperado"]))
        for arquivo, esperadas in exemplos["esperado"].items():
            for nome, valor in esperadas.items():
                atual = construtor.arredondar(obtido[arquivo][nome])
                if valor is None:
                    self.assertIsNone(atual, f"{arquivo}:{nome}")
                else:
                    self.assertAlmostEqual(atual, valor, places=5, msg=f"{arquivo}:{nome}")


class TesteModelo(unittest.TestCase):
    def test_manifesto_publicado_e_aceito(self):
        pacote = modelo.carregar()
        self.assertEqual(pacote["manifesto"]["contrato"], modelo.VERSAO_DO_CONTRATO)

    def test_rejeita_hash_diferente(self):
        manifesto = copy.deepcopy(modelo.carregar()["manifesto"])
        manifesto["modelo"]["sha256"] = "0" * 64
        with self.assertRaises(ErroDeAnalise):
            modelo.conferir_manifesto(manifesto, config.PASTA_MODELO / manifesto["modelo"]["arquivo"])

    def test_rejeita_medida_desconhecida(self):
        manifesto = copy.deepcopy(modelo.carregar()["manifesto"])
        manifesto["features"] = manifesto["features"] + ["medida_inexistente"]
        with self.assertRaises(ErroDeAnalise):
            modelo.conferir_manifesto(manifesto, config.PASTA_MODELO / manifesto["modelo"]["arquivo"])

    def test_rejeita_versao_de_contrato_desconhecida(self):
        manifesto = copy.deepcopy(modelo.carregar()["manifesto"])
        manifesto["contrato"] = 99
        with self.assertRaises(ErroDeAnalise):
            modelo.conferir_manifesto(manifesto, config.PASTA_MODELO / manifesto["modelo"]["arquivo"])

    def test_rejeita_scikit_learn_de_outra_versao(self):
        manifesto = copy.deepcopy(modelo.carregar()["manifesto"])
        manifesto["sklearn"] = "0.20.0"
        with self.assertRaises(ErroDeAnalise):
            modelo.conferir_manifesto(manifesto, config.PASTA_MODELO / manifesto["modelo"]["arquivo"])


class TesteAvaliacao(unittest.TestCase):
    def test_avalia_o_repositorio_de_exemplo(self):
        exemplos = carregar_exemplos()
        pasta = repositorio_de_exemplo(exemplos)
        try:
            tabela = historico.ler_historico(pasta)
        finally:
            historico.apagar_pasta(pasta)
        resumo, arquivos = pontuar.avaliar_historico(tabela, exemplos["instante"])
        self.assertEqual(resumo["avaliados"], 3)
        self.assertEqual(len(arquivos), 3)
        chances = [a["probabilidade"] for a in arquivos]
        self.assertTrue(all(0 <= c <= 1 for c in chances))
        self.assertEqual(chances, sorted(chances, reverse=True))
        self.assertAlmostEqual(resumo["porcentagem_estimada"], 100 * sum(chances) / 3, delta=0.05)
        self.assertEqual(sum(resumo["distribuicao"]), 3)

    def test_historico_vazio_e_recusado(self):
        tabela = pontuar.metricas_historico.identificar(
            historico.pd.DataFrame(columns=historico.COLUNAS))
        with self.assertRaises(ErroDeAnalise):
            with mock.patch.object(pontuar.metricas_historico, "identificar", return_value=tabela):
                pontuar.avaliar_historico(tabela, 0)


if __name__ == "__main__":
    unittest.main()

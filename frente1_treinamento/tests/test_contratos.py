import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from treino import config, exemplos, manifesto
from treino.medidas import historico, metricas_historico


class TesteManifesto(unittest.TestCase):
    def setUp(self):
        self.manifesto = json.loads(config.ARQUIVO_MANIFESTO.read_text(encoding="utf-8"))

    def test_segue_o_esquema_do_contrato(self):
        esquema = json.loads(
            (config.PASTA_CONTRATOS / "modelo.manifesto.schema.json").read_text(encoding="utf-8"))
        erros = list(Draft202012Validator(esquema).iter_errors(self.manifesto))
        self.assertEqual(erros, [])

    def test_hash_confere_com_o_arquivo_do_modelo(self):
        esperado = hashlib.sha256(config.ARQUIVO_MODELO.read_bytes()).hexdigest()
        self.assertEqual(self.manifesto["modelo"]["sha256"], esperado)

    def test_features_existem_nas_medidas(self):
        desconhecidas = set(self.manifesto["features"]) - set(metricas_historico.FEATURES)
        self.assertEqual(desconhecidas, set())

    def test_montar_acrescenta_contrato_e_hash(self):
        montado = manifesto.montar({"versao": "x"})
        self.assertEqual(montado["contrato"], manifesto.VERSAO_DO_CONTRATO)
        self.assertEqual(montado["modelo"]["arquivo"], config.ARQUIVO_MODELO.name)


class TesteExemplos(unittest.TestCase):
    def test_medidas_conferem_com_o_arquivo_de_exemplos(self):
        golden = json.loads(exemplos.ARQUIVO_SAIDA.read_text(encoding="utf-8"))
        pasta = Path(tempfile.mkdtemp(prefix="conferencia_"))
        try:
            exemplos.construir(pasta, golden["especificacao"])
            obtido = exemplos.calcular(pasta, golden["instante"])
        finally:
            historico.apagar_pasta(pasta)
        self.assertEqual(obtido["features"], golden["features"])
        self.assertEqual(set(obtido["esperado"]), set(golden["esperado"]))
        for arquivo, medidas in golden["esperado"].items():
            for nome, valor in medidas.items():
                atual = obtido["esperado"][arquivo][nome]
                if valor is None:
                    self.assertIsNone(atual, f"{arquivo}:{nome}")
                else:
                    self.assertAlmostEqual(atual, valor, places=5, msg=f"{arquivo}:{nome}")


if __name__ == "__main__":
    unittest.main()

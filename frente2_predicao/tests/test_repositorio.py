import unittest
from unittest import mock

from predicao import github, repositorio
from predicao.erros import ErroDeAnalise


class TesteEndereco(unittest.TestCase):
    def test_formas_aceitas(self):
        casos = {
            "pallets/flask": ("pallets/flask", None),
            "https://github.com/pallets/flask": ("pallets/flask", None),
            "https://github.com/pallets/flask.git": ("pallets/flask", None),
            "github.com/pallets/flask/": ("pallets/flask", None),
            "https://github.com/pallets/flask/tree/2.3.x": ("pallets/flask", "2.3.x"),
        }
        for texto, esperado in casos.items():
            self.assertEqual(repositorio.interpretar_endereco(texto), esperado, texto)

    def test_enderecos_invalidos(self):
        for texto in ["", "flask", "https://gitlab.com/a", "a b/c", "https://github.com/so-dono"]:
            with self.assertRaises(ErroDeAnalise, msg=texto):
                repositorio.interpretar_endereco(texto)


class TesteTamanho(unittest.TestCase):
    def test_recusa_repositorio_acima_do_limite(self):
        ficha = {"tamanho_kb": 5_000_000, "ramo": "main"}
        with mock.patch.object(github, "consultar_github", return_value=ficha):
            with self.assertRaises(ErroDeAnalise):
                github.conferir_tamanho("torvalds/linux")

    def test_aceita_repositorio_pequeno(self):
        ficha = {"tamanho_kb": 2_000, "ramo": "main"}
        with mock.patch.object(github, "consultar_github", return_value=ficha):
            self.assertEqual(github.conferir_tamanho("pallets/flask"), ficha)

    def test_segue_adiante_quando_a_api_nao_responde(self):
        with mock.patch.object(github, "consultar_github", return_value=None):
            self.assertIsNone(github.conferir_tamanho("pallets/flask"))


if __name__ == "__main__":
    unittest.main()

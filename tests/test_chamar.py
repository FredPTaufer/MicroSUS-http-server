"""Testes de POST /chamar (sem sockets).
       python -m unittest tests.test_chamar -v
"""
import unittest
from unittest import mock

import handlers
from repository import Repositorio
from tests.helpers import requisitar


class TesteChamar(unittest.TestCase):
    def setUp(self):
        self.repo = Repositorio()
        p = mock.patch.object(handlers, "repositorio", self.repo)
        p.start(); self.addCleanup(p.stop)

    def test_fila_vazia_404(self):
        status, _, d = requisitar("POST", "/chamar")
        self.assertEqual(status, 404)
        self.assertIn("Fila vazia", d["erro"])

    def test_chama_e_muda_estado(self):
        self.repo.cadastrar("Ana", "tosse", "verde")
        status, h, d = requisitar("POST", "/chamar")
        self.assertEqual(status, 200)
        self.assertIn("application/json", h["Content-Type"])
        self.assertEqual(d["id"], 1)
        self.assertEqual(d["estado"], "EM_ATENDIMENTO")
        self.assertIsNone(d["prognostico"])

    def test_estado_visivel_na_consulta_e_some_da_fila(self):
        self.repo.cadastrar("Ana", "tosse", "verde")
        requisitar("POST", "/chamar")
        _, _, d = requisitar("GET", "/pacientes/1")
        self.assertEqual(d["estado"], "EM_ATENDIMENTO")
        _, _, html = requisitar("GET", "/fila")
        self.assertIn("Nenhum paciente na fila", html)

    def test_ordem_prioridade_e_fifo(self):
        # ids: 1=verde 2=amarelo 3=vermelho 4=verde 5=vermelho 6=amarelo
        for pri in ["verde", "amarelo", "vermelho", "verde", "vermelho", "amarelo"]:
            self.repo.cadastrar("n", "s", pri)
        chamados = [requisitar("POST", "/chamar")[2]["id"] for _ in range(6)]
        self.assertEqual(chamados, [3, 5, 2, 6, 1, 4])
        status, _, _ = requisitar("POST", "/chamar")       # 7a chamada: vazia
        self.assertEqual(status, 404)

    def test_vermelho_que_chega_depois_passa_na_frente(self):
        self.repo.cadastrar("A", "s", "verde")
        self.repo.cadastrar("B", "s", "verde")
        self.assertEqual(requisitar("POST", "/chamar")[2]["id"], 1)
        self.repo.cadastrar("C", "s", "vermelho")
        self.assertEqual(requisitar("POST", "/chamar")[2]["id"], 3)
        self.assertEqual(requisitar("POST", "/chamar")[2]["id"], 2)

    def test_mesmo_paciente_nunca_e_chamado_duas_vezes(self):
        for _ in range(3):
            self.repo.cadastrar("n", "s", "amarelo")
        ids = [requisitar("POST", "/chamar")[2]["id"] for _ in range(3)]
        self.assertEqual(len(set(ids)), 3)

    def test_body_e_ignorado(self):
        self.repo.cadastrar("Ana", "tosse", "verde")
        status, _, d = requisitar("POST", "/chamar", '{"id": 99, "lixo": true}')
        self.assertEqual(status, 200)
        self.assertEqual(d["id"], 1)               # o servidor escolhe, nao o cliente

    def test_estatisticas_do_repositorio_apos_chamar(self):
        self.repo.cadastrar("A", "s", "verde"); self.repo.cadastrar("B", "s", "verde")
        requisitar("POST", "/chamar")
        est = self.repo.estatisticas()["porEstado"]
        self.assertEqual(est, {"EM_FILA": 1, "EM_ATENDIMENTO": 1, "ATENDIDO": 0})

    def test_metodo_errado_405(self):
        status, h, _ = requisitar("GET", "/chamar")
        self.assertEqual(status, 405)
        self.assertEqual(h["Allow"], "POST")


if __name__ == "__main__":
    unittest.main()

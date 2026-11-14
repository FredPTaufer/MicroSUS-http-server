"""Testes de GET /estatisticas (sem sockets).
       python -m unittest tests.test_estatisticas -v
"""
import unittest
from unittest import mock

import handlers
from repository import Repositorio
from tests.helpers import requisitar


def stats():
    status, h, d = requisitar("GET", "/estatisticas")
    assert status == 200 and "application/json" in h["Content-Type"]
    return d


class TesteEstatisticas(unittest.TestCase):
    def setUp(self):
        self.repo = Repositorio()
        p = mock.patch.object(handlers, "repositorio", self.repo)
        p.start(); self.addCleanup(p.stop)

    def test_sistema_vazio(self):
        self.assertEqual(stats(), {
            "total": 0,
            "porEstado": {"EM_FILA": 0, "EM_ATENDIMENTO": 0, "ATENDIDO": 0},
            "porPrioridade": {"vermelho": 0, "amarelo": 0, "verde": 0},
        })

    def test_acompanha_o_fluxo_completo(self):
        for pri in ["verde", "amarelo", "vermelho", "vermelho", "verde"]:
            requisitar("POST", "/pacientes",
                       '{"nome":"n","sintoma":"s","prioridade":"%s"}' % pri)
        d = stats()
        self.assertEqual(d["total"], 5)
        self.assertEqual(d["porEstado"], {"EM_FILA": 5, "EM_ATENDIMENTO": 0, "ATENDIDO": 0})
        self.assertEqual(d["porPrioridade"], {"vermelho": 2, "amarelo": 1, "verde": 2})

        requisitar("POST", "/chamar"); requisitar("POST", "/chamar")    # ids 3 e 4
        d = stats()
        self.assertEqual(d["porEstado"], {"EM_FILA": 3, "EM_ATENDIMENTO": 2, "ATENDIDO": 0})

        requisitar("POST", "/pacientes/3/finalizar", '{"prognostico": "alta"}')
        d = stats()
        self.assertEqual(d["porEstado"], {"EM_FILA": 3, "EM_ATENDIMENTO": 1, "ATENDIDO": 1})
        self.assertEqual(d["total"], 5)                                  # total nao muda
        self.assertEqual(d["porPrioridade"], {"vermelho": 2, "amarelo": 1, "verde": 2})

    def test_somas_sao_consistentes(self):
        for pri in ["verde", "amarelo", "vermelho"] * 3:
            self.repo.cadastrar("n", "s", pri)
        for _ in range(4):
            self.repo.chamar_proximo()           # chama os ids 3, 6, 2 e 5
        self.repo.finalizar(3, "ok")
        d = stats()
        self.assertEqual(sum(d["porEstado"].values()), d["total"])
        self.assertEqual(sum(d["porPrioridade"].values()), d["total"])

    def test_requisicoes_invalidas_nao_contam(self):
        requisitar("POST", "/pacientes", '{"nome":"n","sintoma":"s","prioridade":"azul"}')
        requisitar("POST", "/pacientes", "lixo")
        requisitar("POST", "/pacientes/99/finalizar", '{"prognostico":"x"}')
        self.assertEqual(stats()["total"], 0)

    def test_consulta_nao_altera_nada(self):
        self.repo.cadastrar("n", "s", "verde")
        self.assertEqual(stats(), stats())

    def test_metodo_errado_405(self):
        for metodo in ["POST", "PUT", "DELETE"]:
            status, h, _ = requisitar(metodo, "/estatisticas")
            self.assertEqual(status, 405, metodo)
            self.assertEqual(h["Allow"], "GET")


if __name__ == "__main__":
    unittest.main()

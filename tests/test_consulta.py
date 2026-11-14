"""Testes de GET /pacientes/{id}, sem sockets (chama o roteador direto).
       python -m unittest tests.test_consulta -v
"""
import json
import unittest
from unittest import mock

import handlers
from http_parser import Requisicao
from repository import Repositorio
from router import rotear
from tests.helpers import HEADERS_AUTH


def chamar(metodo, caminho, body=b""):
    """Executa uma requisicao no roteador e devolve (status, headers, dict_json)."""
    resp = rotear(Requisicao(metodo, caminho, "HTTP/1.1", dict(HEADERS_AUTH), body))
    cab, _, corpo = resp.partition(b"\r\n\r\n")
    linhas = cab.decode().split("\r\n")
    status = int(linhas[0].split(" ")[1])
    headers = dict(l.split(": ", 1) for l in linhas[1:])
    assert int(headers["Content-Length"]) == len(corpo)      # sempre confere
    return status, headers, json.loads(corpo.decode("utf-8"))


class TesteConsultaPaciente(unittest.TestCase):
    def setUp(self):
        self.repo = Repositorio()
        patcher = mock.patch.object(handlers, "repositorio", self.repo)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.repo.cadastrar("João", "dor no peito", "vermelho")     # id 1

    def test_existente_em_fila(self):
        status, h, d = chamar("GET", "/pacientes/1")
        self.assertEqual(status, 200)
        self.assertIn("application/json", h["Content-Type"])
        self.assertEqual(d["id"], 1)
        self.assertEqual(d["nome"], "João")
        self.assertEqual(d["estado"], "EM_FILA")
        self.assertIsNone(d["prognostico"])
        self.assertEqual(set(d), {"id", "nome", "sintoma", "prioridade",
                                  "estado", "horaChegada", "prognostico"})

    def test_em_atendimento(self):
        self.repo.chamar_proximo()
        _, _, d = chamar("GET", "/pacientes/1")
        self.assertEqual(d["estado"], "EM_ATENDIMENTO")
        self.assertIsNone(d["prognostico"])

    def test_atendido_inclui_prognostico(self):
        self.repo.chamar_proximo()
        self.repo.finalizar(1, "Alta com repouso")
        status, _, d = chamar("GET", "/pacientes/1")
        self.assertEqual(status, 200)
        self.assertEqual(d["estado"], "ATENDIDO")
        self.assertEqual(d["prognostico"], "Alta com repouso")

    def test_id_inexistente_404(self):
        status, _, d = chamar("GET", "/pacientes/99")
        self.assertEqual(status, 404)
        self.assertIn("erro", d)

    def test_ids_invalidos_404(self):
        for ruim in ["abc", "0", "-1", "1.5", "1e3", "%20", "99999999999999999999"]:
            status, _, _ = chamar("GET", f"/pacientes/{ruim}")
            self.assertEqual(status, 404, ruim)

    def test_consulta_nao_altera_nada(self):
        antes = self.repo.estatisticas()
        chamar("GET", "/pacientes/1"); chamar("GET", "/pacientes/99")
        self.assertEqual(self.repo.estatisticas(), antes)
        self.assertEqual(self.repo.buscar(1).estado, "EM_FILA")

    def test_metodo_errado_405(self):
        status, h, _ = chamar("POST", "/pacientes/1")
        self.assertEqual(status, 405)
        self.assertEqual(h["Allow"], "GET")
        status, _, _ = chamar("DELETE", "/pacientes/1")
        self.assertEqual(status, 405)


if __name__ == "__main__":
    unittest.main()

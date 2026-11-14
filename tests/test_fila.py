"""Testes de GET /fila (sem sockets).
       python -m unittest tests.test_fila -v
"""
import re
import unittest
from unittest import mock

import handlers
from http_parser import Requisicao
from repository import Repositorio
from router import rotear
from tests.helpers import HEADERS_AUTH


def get_fila():
    resp = rotear(Requisicao("GET", "/fila", "HTTP/1.1", {}, b""))
    cab, _, corpo = resp.partition(b"\r\n\r\n")
    linhas = cab.decode().split("\r\n")
    status = int(linhas[0].split(" ")[1])
    headers = dict(l.split(": ", 1) for l in linhas[1:])
    assert int(headers["Content-Length"]) == len(corpo)
    return status, headers, corpo.decode("utf-8")


def nomes_na_ordem(html):
    """Extrai a 3a coluna (nome) de cada linha da tabela, na ordem em que aparece."""
    return re.findall(r"<tr><td>\d+</td><td>\d+</td><td>(.*?)</td>", html)


class TesteFila(unittest.TestCase):
    def setUp(self):
        self.repo = Repositorio()
        p = mock.patch.object(handlers, "repositorio", self.repo)
        p.start(); self.addCleanup(p.stop)

    def test_content_type_html(self):
        status, h, _ = get_fila()
        self.assertEqual(status, 200)
        self.assertEqual(h["Content-Type"], "text/html; charset=utf-8")

    def test_fila_vazia(self):
        _, _, html = get_fila()
        self.assertIn("Nenhum paciente na fila", html)
        self.assertNotIn("<table>", html)

    def test_ordem_prioridade_e_fifo(self):
        for nome, pri in [("A-verde", "verde"), ("B-amarelo", "amarelo"),
                          ("C-vermelho", "vermelho"), ("D-verde", "verde"),
                          ("E-vermelho", "vermelho"), ("F-amarelo", "amarelo")]:
            self.repo.cadastrar(nome, "s", pri)
        _, _, html = get_fila()
        self.assertEqual(nomes_na_ordem(html),
                         ["C-vermelho", "E-vermelho", "B-amarelo",
                          "F-amarelo", "A-verde", "D-verde"])

    def test_somente_em_fila(self):
        self.repo.cadastrar("Chamado", "s", "vermelho")
        self.repo.cadastrar("Atendido", "s", "amarelo")
        self.repo.cadastrar("Esperando", "s", "verde")
        self.repo.chamar_proximo()                    # Chamado -> EM_ATENDIMENTO
        self.repo.chamar_proximo()                    # Atendido -> EM_ATENDIMENTO
        self.repo.finalizar(2, "alta")                # Atendido -> ATENDIDO
        _, _, html = get_fila()
        self.assertEqual(nomes_na_ordem(html), ["Esperando"])

    def test_acentos(self):
        self.repo.cadastrar("João Conceição", "dor de cabeça", "verde")
        _, _, html = get_fila()
        self.assertIn("João Conceição", html)
        self.assertIn("dor de cabeça", html)

    def test_html_e_escapado(self):
        self.repo.cadastrar("<script>alert(1)</script>", "a & b <b>negrito</b>", "verde")
        _, _, html = get_fila()
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("a &amp; b &lt;b&gt;negrito&lt;/b&gt;", html)

    def test_metodo_errado_405(self):
        resp = rotear(Requisicao("POST", "/fila", "HTTP/1.1", dict(HEADERS_AUTH), b""))
        self.assertTrue(resp.startswith(b"HTTP/1.1 405"))


if __name__ == "__main__":
    unittest.main()

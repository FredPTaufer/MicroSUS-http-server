"""Testes de POST /pacientes/{id}/finalizar e da maquina de estados (sem sockets).
       python -m unittest tests.test_finalizar -v
"""
import unittest
from unittest import mock

import handlers
from repository import Repositorio
from tests.helpers import requisitar

OK = '{"prognostico": "Alta com repouso"}'


class Base(unittest.TestCase):
    def setUp(self):
        self.repo = Repositorio()
        p = mock.patch.object(handlers, "repositorio", self.repo)
        p.start(); self.addCleanup(p.stop)

    def novo_em_atendimento(self, pri="vermelho"):
        p = self.repo.cadastrar("Maria", "dor", pri)
        self.repo.chamar_proximo()
        return p

    def fin(self, id, body=OK):
        return requisitar("POST", f"/pacientes/{id}/finalizar", body)


class TesteSucesso(Base):
    def test_finaliza(self):
        self.novo_em_atendimento()
        status, h, d = self.fin(1)
        self.assertEqual(status, 200)
        self.assertIn("application/json", h["Content-Type"])
        self.assertEqual(d["estado"], "ATENDIDO")
        self.assertEqual(d["prognostico"], "Alta com repouso")
        self.assertEqual(d["id"], 1)

    def test_acentos_no_prognostico(self):
        self.novo_em_atendimento()
        _, _, d = self.fin(1, '{"prognostico": "Recuperação em 3 dias, sem sequelas"}')
        self.assertEqual(d["prognostico"], "Recuperação em 3 dias, sem sequelas")

    def test_consulta_mostra_atendido_com_prognostico(self):
        self.novo_em_atendimento()
        self.fin(1)
        _, _, d = requisitar("GET", "/pacientes/1")
        self.assertEqual(d["estado"], "ATENDIDO")
        self.assertEqual(d["prognostico"], "Alta com repouso")

    def test_atendido_nao_aparece_na_fila_nem_e_chamado(self):
        self.novo_em_atendimento()
        self.fin(1)
        _, _, html = requisitar("GET", "/fila")
        self.assertIn("Nenhum paciente na fila", html)
        status, _, _ = requisitar("POST", "/chamar")
        self.assertEqual(status, 404)

    def test_estatisticas_do_repositorio(self):
        self.novo_em_atendimento()
        self.fin(1)
        self.assertEqual(self.repo.estatisticas()["porEstado"],
                         {"EM_FILA": 0, "EM_ATENDIMENTO": 0, "ATENDIDO": 1})

    def test_so_o_paciente_indicado_e_finalizado(self):
        for _ in range(2):
            self.repo.cadastrar("n", "s", "verde")
        self.repo.chamar_proximo(); self.repo.chamar_proximo()     # ids 1 e 2 em atendimento
        self.fin(2)
        self.assertEqual(self.repo.buscar(1).estado, "EM_ATENDIMENTO")
        self.assertEqual(self.repo.buscar(2).estado, "ATENDIDO")


class Teste404(Base):
    def test_id_inexistente(self):
        status, _, d = self.fin(99)
        self.assertEqual(status, 404)
        self.assertIn("erro", d)

    def test_id_invalido(self):
        for ruim in ["abc", "0", "-1", "1.5"]:
            self.assertEqual(self.fin(ruim)[0], 404, ruim)

    def test_404_vem_antes_de_validar_body(self):
        self.assertEqual(self.fin(99, "lixo")[0], 404)


class Teste409(Base):
    def test_finalizar_em_fila(self):
        p = self.repo.cadastrar("Ana", "tosse", "verde")
        status, _, d = self.fin(1)
        self.assertEqual(status, 409)
        self.assertIn("EM_FILA", d["erro"])
        self.assertIn("chamar", d["erro"])
        self.assertEqual(p.estado, "EM_FILA")
        self.assertIsNone(p.prognostico)

    def test_finalizar_atendido(self):
        p = self.novo_em_atendimento()
        self.fin(1)
        status, _, d = self.fin(1, '{"prognostico": "outro texto"}')
        self.assertEqual(status, 409)
        self.assertIn("ATENDIDO", d["erro"])
        self.assertEqual(p.estado, "ATENDIDO")
        self.assertEqual(p.prognostico, "Alta com repouso")        # nao sobrescreveu

    def test_atendido_e_terminal_repetidas_tentativas(self):
        self.novo_em_atendimento()
        self.fin(1)
        for _ in range(3):
            self.assertEqual(self.fin(1)[0], 409)
        self.assertEqual(self.repo.buscar(1).estado, "ATENDIDO")

    def test_409_vem_antes_de_validar_body(self):
        self.repo.cadastrar("Ana", "tosse", "verde")               # EM_FILA
        self.assertEqual(self.fin(1, "")[0], 409)                  # sem body
        self.assertEqual(self.fin(1, "lixo")[0], 409)              # body invalido

    def test_nenhum_estado_volta_para_tras(self):
        p = self.novo_em_atendimento()
        self.fin(1)
        for _ in range(2):
            requisitar("POST", "/chamar")
            self.fin(1)
        self.assertEqual(p.estado, "ATENDIDO")


class Teste400(Base):
    def setUp(self):
        super().setUp()
        self.p = self.novo_em_atendimento()

    def casos_ruins(self):
        return {
            "sem body": "",
            "json invalido": '{"prognostico": "x"',
            "campo ausente": '{"outro": "x"}',
            "tipo errado": '{"prognostico": 123}',
            "null": '{"prognostico": null}',
            "vazio": '{"prognostico": "   "}',
            "nao e objeto": '["x"]',
        }

    def test_400_e_nao_altera_o_estado(self):
        for nome, body in self.casos_ruins().items():
            status, _, d = self.fin(1, body)
            self.assertEqual(status, 400, nome)
            self.assertIn("erro", d)
            self.assertEqual(self.p.estado, "EM_ATENDIMENTO", nome)
            self.assertIsNone(self.p.prognostico, nome)

    def test_depois_de_400_ainda_da_para_finalizar(self):
        self.fin(1, "lixo")
        self.assertEqual(self.fin(1)[0], 200)


class TesteMetodo(Base):
    def test_405(self):
        for metodo in ["GET", "PUT", "DELETE"]:
            status, h, _ = requisitar(metodo, "/pacientes/1/finalizar")
            self.assertEqual(status, 405, metodo)
            self.assertEqual(h["Allow"], "POST")


class TesteCicloCompleto(Base):
    def test_ciclo_de_dois_pacientes(self):
        requisitar("POST", "/pacientes",
                   '{"nome":"Ana","sintoma":"tosse","prioridade":"verde"}')
        requisitar("POST", "/pacientes",
                   '{"nome":"Bia","sintoma":"dor","prioridade":"vermelho"}')
        self.assertEqual(self.fin(1)[0], 409)                      # Ana em fila
        self.assertEqual(requisitar("POST", "/chamar")[2]["id"], 2)  # Bia (vermelha)
        self.assertEqual(self.fin(1)[0], 409)                      # Ana ainda em fila
        self.assertEqual(self.fin(2)[0], 200)                      # Bia finalizada
        self.assertEqual(self.fin(2)[0], 409)                      # ja ATENDIDA
        self.assertEqual(requisitar("POST", "/chamar")[2]["id"], 1)  # agora Ana
        self.assertEqual(self.fin(1)[0], 200)
        self.assertEqual(requisitar("POST", "/chamar")[0], 404)    # fila vazia
        est = requisitar("GET", "/pacientes/1")[2], requisitar("GET", "/pacientes/2")[2]
        self.assertEqual([e["estado"] for e in est], ["ATENDIDO", "ATENDIDO"])


if __name__ == "__main__":
    unittest.main()

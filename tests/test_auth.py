"""Testes da autenticacao (Bonus 2), sem sockets.
       python -m unittest tests.test_auth -v
"""
import re
import unittest
from unittest import mock

import handlers
from repository import Repositorio
from tests.helpers import requisitar

LOGIN_OK = '{"usuario": "admin", "senha": "admin123"}'
PACIENTE = '{"nome": "Ana", "sintoma": "tosse", "prioridade": "verde"}'
SEM = {}     # nenhum header


def fazer_login():
    status, _, d = requisitar("POST", "/login", LOGIN_OK, headers=SEM)
    assert status == 200
    return d["chave"]


class Base(unittest.TestCase):
    def setUp(self):
        self.repo = Repositorio()
        p = mock.patch.object(handlers, "repositorio", self.repo)
        p.start(); self.addCleanup(p.stop)


class TesteLogin(Base):
    def test_sucesso(self):
        status, h, d = requisitar("POST", "/login", LOGIN_OK, headers=SEM)
        self.assertEqual(status, 200)
        self.assertIn("application/json", h["Content-Type"])
        self.assertEqual(list(d), ["chave"])
        self.assertRegex(d["chave"], r"^[0-9a-f]{32}$")

    def test_login_nao_exige_chave(self):
        self.assertEqual(requisitar("POST", "/login", LOGIN_OK, headers=SEM)[0], 200)
        # nem mesmo uma chave invalida atrapalha o login
        self.assertEqual(requisitar("POST", "/login", LOGIN_OK,
                                    headers={"authorization": "lixo"})[0], 200)

    def test_credenciais_invalidas_403(self):
        casos = {
            "senha errada": '{"usuario": "admin", "senha": "errada"}',
            "usuario errado": '{"usuario": "root", "senha": "admin123"}',
            "ambos errados": '{"usuario": "x", "senha": "y"}',
            "vazios": '{"usuario": "", "senha": ""}',
            "maiusculas": '{"usuario": "ADMIN", "senha": "admin123"}',
            "senha com espaco": '{"usuario": "admin", "senha": " admin123"}',
            "unicode": '{"usuario": "admin\\u00e9", "senha": "admin123"}',
        }
        for nome, corpo in casos.items():
            status, _, d = requisitar("POST", "/login", corpo, headers=SEM)
            self.assertEqual(status, 403, nome)
            self.assertIn("erro", d)
            self.assertNotIn("chave", d)

    def test_body_invalido_400(self):
        casos = {"sem body": "", "json invalido": '{"usuario": "admin"',
                 "sem senha": '{"usuario": "admin"}', "sem usuario": '{"senha": "x"}',
                 "tipo errado": '{"usuario": 1, "senha": 2}', "lista": '[1]'}
        for nome, corpo in casos.items():
            self.assertEqual(requisitar("POST", "/login", corpo, headers=SEM)[0], 400, nome)

    def test_cada_login_gera_chave_diferente_e_todas_valem(self):
        c1, c2 = fazer_login(), fazer_login()
        self.assertNotEqual(c1, c2)
        for c in (c1, c2):
            self.assertEqual(requisitar("POST", "/pacientes", PACIENTE,
                                        headers={"authorization": c})[0], 201)

    def test_barra_final_e_metodo_errado(self):
        self.assertEqual(requisitar("POST", "/login/", LOGIN_OK, headers=SEM)[0], 200)
        status, h, _ = requisitar("GET", "/login", headers=SEM)
        self.assertEqual((status, h["Allow"]), (405, "POST"))


class TesteProtecaoDosPost(Base):
    def test_post_sem_header_401(self):
        for caminho, corpo in [("/pacientes", PACIENTE), ("/chamar", ""),
                               ("/pacientes/1/finalizar", '{"prognostico": "x"}')]:
            status, h, d = requisitar("POST", caminho, corpo, headers=SEM)
            self.assertEqual(status, 401, caminho)
            self.assertEqual(h["WWW-Authenticate"], "Bearer")
            self.assertIn("Authorization ausente", d["erro"])

    def test_chave_incorreta_401(self):
        for valor in ["chave-errada", "0" * 32, "Bearer chave-errada", "Bearer", "   "]:
            status, _, d = requisitar("POST", "/pacientes", PACIENTE,
                                      headers={"authorization": valor})
            self.assertEqual(status, 401, valor)

    def test_mensagens_distinguem_ausente_de_invalida(self):
        _, _, d1 = requisitar("POST", "/chamar", headers=SEM)
        _, _, d2 = requisitar("POST", "/chamar", headers={"authorization": "xyz"})
        self.assertIn("ausente", d1["erro"])
        self.assertIn("invalida", d2["erro"])

    def test_chave_valida_pura_ou_bearer(self):
        chave = fazer_login()
        for valor in [chave, f"Bearer {chave}", f"bearer {chave}", f"  {chave}  "]:
            status, _, _ = requisitar("POST", "/pacientes", PACIENTE,
                                      headers={"authorization": valor})
            self.assertEqual(status, 201, valor)

    def test_401_nao_altera_nada(self):
        requisitar("POST", "/pacientes", PACIENTE, headers=SEM)
        requisitar("POST", "/pacientes", PACIENTE, headers={"authorization": "x"})
        self.assertEqual(self.repo.estatisticas()["total"], 0)
        self.repo.cadastrar("A", "s", "verde")
        requisitar("POST", "/chamar", headers=SEM)
        self.assertEqual(self.repo.buscar(1).estado, "EM_FILA")          # nao foi chamado
        requisitar("POST", "/pacientes/1/finalizar", '{"prognostico": "x"}', headers=SEM)
        self.assertIsNone(self.repo.buscar(1).prognostico)

    def test_auth_vem_antes_do_roteamento(self):
        self.assertEqual(requisitar("POST", "/xyz", headers=SEM)[0], 401)
        self.assertEqual(requisitar("POST", "/fila", headers=SEM)[0], 401)
        chave = {"authorization": fazer_login()}
        self.assertEqual(requisitar("POST", "/xyz", headers=chave)[0], 404)
        self.assertEqual(requisitar("POST", "/fila", headers=chave)[0], 405)

    def test_chave_valida_nao_dispensa_validacao_do_body(self):
        chave = {"authorization": fazer_login()}
        self.assertEqual(requisitar("POST", "/pacientes", "lixo", headers=chave)[0], 400)
        self.assertEqual(requisitar("POST", "/pacientes/99/finalizar",
                                    '{"prognostico": "x"}', headers=chave)[0], 404)

    def test_chave_valida_nao_dispensa_maquina_de_estados(self):
        chave = {"authorization": fazer_login()}
        self.repo.cadastrar("A", "s", "verde")
        self.assertEqual(requisitar("POST", "/pacientes/1/finalizar",
                                    '{"prognostico": "x"}', headers=chave)[0], 409)


class TesteGetContinuamLivres(Base):
    def test_gets_sem_chave(self):
        self.repo.cadastrar("A", "s", "verde")
        for caminho in ["/fila", "/estatisticas", "/pacientes/1"]:
            self.assertEqual(requisitar("GET", caminho, headers=SEM)[0], 200, caminho)
        self.assertEqual(requisitar("GET", "/pacientes/99", headers=SEM)[0], 404)
        self.assertEqual(requisitar("GET", "/xyz", headers=SEM)[0], 404)


if __name__ == "__main__":
    unittest.main()

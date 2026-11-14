"""Testes da Etapa 6 (sem HTTP). Executar na pasta do projeto:
       python -m unittest tests.test_repositorio -v
"""
import unittest

from models import (EM_FILA, EM_ATENDIMENTO, ATENDIDO, Paciente,
                    TransicaoInvalida, PacienteNaoEncontrado)
from repository import Repositorio


class TesteCadastro(unittest.TestCase):
    def test_id_sequencial_e_estado_inicial(self):
        r = Repositorio()
        a = r.cadastrar("Ana", "tosse", "verde")
        b = r.cadastrar("Bia", "febre", "amarelo")
        self.assertEqual((a.id, b.id), (1, 2))
        self.assertEqual(a.estado, EM_FILA)
        self.assertIsNone(a.prognostico)
        self.assertTrue(a.hora_chegada)

    def test_prioridade_invalida(self):
        with self.assertRaises(ValueError):
            Repositorio().cadastrar("X", "y", "azul")

    def test_to_dict_campos_do_enunciado(self):
        d = Repositorio().cadastrar("Ana", "tosse", "verde").to_dict()
        self.assertEqual(set(d), {"id", "nome", "sintoma", "prioridade",
                                  "estado", "horaChegada", "prognostico"})


class TesteFila(unittest.TestCase):
    def setUp(self):
        self.r = Repositorio()

    def test_ordem_por_prioridade_e_fifo(self):
        # ids: 1=verde 2=amarelo 3=vermelho 4=verde 5=vermelho 6=amarelo
        for nome, pri in [("A", "verde"), ("B", "amarelo"), ("C", "vermelho"),
                          ("D", "verde"), ("E", "vermelho"), ("F", "amarelo")]:
            self.r.cadastrar(nome, "s", pri)
        esperado = [3, 5, 2, 6, 1, 4]   # vermelhos, amarelos, verdes (FIFO em cada)
        self.assertEqual([p.id for p in self.r.listar_fila()], esperado)
        chamados = [self.r.chamar_proximo().id for _ in range(6)]
        self.assertEqual(chamados, esperado)

    def test_listar_fila_nao_altera_o_heap(self):
        self.r.cadastrar("A", "s", "verde")
        self.r.cadastrar("B", "s", "vermelho")
        antes = [p.id for p in self.r.listar_fila()]
        depois = [p.id for p in self.r.listar_fila()]
        self.assertEqual(antes, depois)
        self.assertEqual(self.r.chamar_proximo().id, 2)

    def test_fila_vazia(self):
        self.assertIsNone(self.r.chamar_proximo())
        self.assertEqual(self.r.listar_fila(), [])

    def test_chamado_sai_da_fila_e_vai_para_em_atendimento(self):
        a = self.r.cadastrar("A", "s", "verde")
        self.r.chamar_proximo()
        self.assertEqual(a.estado, EM_ATENDIMENTO)
        self.assertEqual(self.r.listar_fila(), [])
        self.assertIsNone(self.r.chamar_proximo())

    def test_vermelho_novo_fura_verde_antigo(self):
        self.r.cadastrar("A", "s", "verde")
        self.r.cadastrar("B", "s", "verde")
        self.assertEqual(self.r.chamar_proximo().id, 1)
        self.r.cadastrar("C", "s", "vermelho")        # chega depois, mas e vermelho
        self.assertEqual(self.r.chamar_proximo().id, 3)
        self.assertEqual(self.r.chamar_proximo().id, 2)


class TesteMaquinaDeEstados(unittest.TestCase):
    def setUp(self):
        self.r = Repositorio()
        self.p = self.r.cadastrar("A", "s", "amarelo")

    def test_fluxo_valido(self):
        self.r.chamar_proximo()
        p = self.r.finalizar(1, "alta")
        self.assertEqual(p.estado, ATENDIDO)
        self.assertEqual(p.prognostico, "alta")

    def test_finalizar_em_fila(self):
        with self.assertRaises(TransicaoInvalida) as e:
            self.r.finalizar(1, "x")
        self.assertIn("EM_FILA", str(e.exception))
        self.assertEqual(self.p.estado, EM_FILA)
        self.assertIsNone(self.p.prognostico)

    def test_finalizar_atendido_e_terminal(self):
        self.r.chamar_proximo()
        self.r.finalizar(1, "alta")
        with self.assertRaises(TransicaoInvalida) as e:
            self.r.finalizar(1, "outro prognostico")
        self.assertIn("ATENDIDO", str(e.exception))
        self.assertEqual(self.p.estado, ATENDIDO)
        self.assertEqual(self.p.prognostico, "alta")     # nao foi sobrescrito

    def test_chamar_paciente_atendido(self):
        self.r.chamar_proximo(); self.r.finalizar(1, "alta")
        with self.assertRaises(TransicaoInvalida):
            self.p.chamar()
        self.assertEqual(self.p.estado, ATENDIDO)

    def test_chamar_paciente_ja_em_atendimento(self):
        self.r.chamar_proximo()
        with self.assertRaises(TransicaoInvalida):
            self.p.chamar()
        self.assertEqual(self.p.estado, EM_ATENDIMENTO)

    def test_id_inexistente(self):
        with self.assertRaises(PacienteNaoEncontrado):
            self.r.finalizar(99, "x")
        self.assertIsNone(self.r.buscar(99))

    def test_nenhum_estado_volta_para_tras(self):
        # Todas as chamadas a partir de ATENDIDO falham e o estado nao muda.
        self.r.chamar_proximo(); self.r.finalizar(1, "alta")
        for acao in (lambda: self.p.chamar(), lambda: self.p.finalizar("x")):
            with self.assertRaises(TransicaoInvalida):
                acao()
        self.assertEqual(self.p.estado, ATENDIDO)


class TesteEstatisticas(unittest.TestCase):
    def test_contagens(self):
        r = Repositorio()
        for pri in ["vermelho", "vermelho", "amarelo", "verde", "verde"]:
            r.cadastrar("n", "s", pri)
        r.chamar_proximo()                 # id 1 -> EM_ATENDIMENTO
        r.chamar_proximo()                 # id 2 -> EM_ATENDIMENTO
        r.finalizar(1, "ok")               # id 1 -> ATENDIDO
        est = r.estatisticas()
        self.assertEqual(est["total"], 5)
        self.assertEqual(est["porEstado"],
                         {"EM_FILA": 3, "EM_ATENDIMENTO": 1, "ATENDIDO": 1})
        self.assertEqual(est["porPrioridade"],
                         {"vermelho": 2, "amarelo": 1, "verde": 2})

    def test_vazio_tem_todas_as_chaves_com_zero(self):
        est = Repositorio().estatisticas()
        self.assertEqual(est["total"], 0)
        self.assertEqual(est["porEstado"],
                         {"EM_FILA": 0, "EM_ATENDIMENTO": 0, "ATENDIDO": 0})


if __name__ == "__main__":
    unittest.main()

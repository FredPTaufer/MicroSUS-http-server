"""
models.py - Etapa 6: o Paciente e a MAQUINA DE ESTADOS.

Toda regra de transicao de estado esta AQUI, dentro da classe Paciente.
Como os outros modulos so mudam o estado chamando chamar() e finalizar(),
e impossivel violar a maquina de estados por esquecimento num handler.

    (novo) --> EM_FILA --chamar()--> EM_ATENDIMENTO --finalizar()--> ATENDIDO
"""
from datetime import datetime

# Estados
EM_FILA = "EM_FILA"
EM_ATENDIMENTO = "EM_ATENDIMENTO"
ATENDIDO = "ATENDIDO"
ESTADOS = (EM_FILA, EM_ATENDIMENTO, ATENDIDO)

# Prioridades -> peso na fila (MENOR peso = atendido primeiro)
PESO_PRIORIDADE = {"vermelho": 0, "amarelo": 1, "verde": 2}
PRIORIDADES = tuple(PESO_PRIORIDADE)


class TransicaoInvalida(Exception):
    """Tentativa de violar a maquina de estados. Vira 409 Conflict."""


class PacienteNaoEncontrado(Exception):
    """ID inexistente. Vira 404 Not Found."""


class Paciente:
    def __init__(self, id, nome, sintoma, prioridade):
        self.id = id
        self.nome = nome
        self.sintoma = sintoma
        self.prioridade = prioridade
        self.estado = EM_FILA                      # estado inicial
        self.hora_chegada = datetime.now().isoformat(timespec="seconds")
        self.prognostico = None                    # so preenchido ao finalizar

    # ---------- transicoes de estado ----------

    def chamar(self):
        """EM_FILA -> EM_ATENDIMENTO. Qualquer outro estado e invalido."""
        if self.estado == EM_ATENDIMENTO:
            raise TransicaoInvalida(
                "Paciente ja esta EM_ATENDIMENTO. Nao e possivel chama-lo novamente.")
        if self.estado == ATENDIDO:
            raise TransicaoInvalida(
                "Paciente ja esta ATENDIDO. Nao ha transicao possivel.")
        self.estado = EM_ATENDIMENTO

    def validar_finalizacao(self):
        """Levanta TransicaoInvalida se o paciente NAO esta EM_ATENDIMENTO.
        Separada de finalizar() para o handler poder checar o estado (409)
        antes de olhar o body (400)."""
        if self.estado == EM_FILA:
            raise TransicaoInvalida(
                "Paciente esta EM_FILA. Nao e possivel finalizar sem antes "
                "chamar para atendimento.")
        if self.estado == ATENDIDO:
            raise TransicaoInvalida(
                "Paciente ja esta ATENDIDO. Nao ha transicao possivel.")

    def finalizar(self, prognostico):
        """EM_ATENDIMENTO -> ATENDIDO. Qualquer outro estado e invalido."""
        self.validar_finalizacao()
        self.prognostico = prognostico
        self.estado = ATENDIDO

    # ---------- representacao ----------

    def to_dict(self):
        """Dicionario com os nomes de campo do enunciado (para virar JSON)."""
        return {
            "id": self.id,
            "nome": self.nome,
            "sintoma": self.sintoma,
            "prioridade": self.prioridade,
            "estado": self.estado,
            "horaChegada": self.hora_chegada,
            "prognostico": self.prognostico,
        }

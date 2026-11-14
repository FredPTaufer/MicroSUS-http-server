"""
repository.py - Etapa 6: armazenamento em memoria e fila de prioridade.

Estruturas de dados:
  _pacientes : dict {id: Paciente}   -> busca por id em O(1)
  _heap      : lista usada com heapq -> fila de prioridade (so EM_FILA)
  _proximo_id: contador para IDs sequenciais

Chave do heap: tupla (peso_prioridade, id)
  - peso: vermelho=0, amarelo=1, verde=2 (o heap devolve o MENOR primeiro)
  - id  : desempate. Como o id e sequencial, "menor id" = "chegou antes",
          o que garante o FIFO dentro da mesma prioridade.
"""
import heapq

from models import (
    Paciente, PacienteNaoEncontrado, PESO_PRIORIDADE, PRIORIDADES,
    ESTADOS, EM_FILA,
)


class Repositorio:
    def __init__(self):
        self._pacientes = {}
        self._heap = []
        self._proximo_id = 1

    def cadastrar(self, nome, sintoma, prioridade):
        """Cria o paciente (estado EM_FILA) e o coloca na fila."""
        if prioridade not in PESO_PRIORIDADE:
            raise ValueError(f"Prioridade invalida: {prioridade!r}")

        paciente = Paciente(self._proximo_id, nome, sintoma, prioridade)
        self._proximo_id += 1

        self._pacientes[paciente.id] = paciente
        heapq.heappush(self._heap, (PESO_PRIORIDADE[prioridade], paciente.id))
        return paciente

    def buscar(self, id):
        """Devolve o Paciente ou None se nao existir."""
        return self._pacientes.get(id)

    def listar_fila(self):
        """Pacientes EM_FILA na ordem de atendimento, SEM alterar o heap.
        sorted() cria uma copia ordenada; o heap original permanece intacto."""
        return [self._pacientes[id] for _, id in sorted(self._heap)]

    def chamar_proximo(self):
        """Tira o proximo da fila e o poe EM_ATENDIMENTO.
        Devolve o Paciente, ou None se a fila estiver vazia."""
        if not self._heap:
            return None
        _, id = self._heap[0]                 # espia o topo, sem remover
        paciente = self._pacientes[id]
        paciente.chamar()                     # muda o estado (valida a transicao)
        heapq.heappop(self._heap)             # so remove depois de dar certo
        return paciente

    def finalizar(self, id, prognostico):
        """Finaliza o atendimento. Levanta PacienteNaoEncontrado (404)
        ou TransicaoInvalida (409)."""
        paciente = self.buscar(id)
        if paciente is None:
            raise PacienteNaoEncontrado(f"Paciente {id} nao existe")
        paciente.finalizar(prognostico)
        return paciente

    def estatisticas(self):
        por_estado = {e: 0 for e in ESTADOS}
        por_prioridade = {p: 0 for p in PRIORIDADES}
        for p in self._pacientes.values():
            por_estado[p.estado] += 1
            por_prioridade[p.prioridade] += 1
        return {
            "total": len(self._pacientes),
            "porEstado": por_estado,
            "porPrioridade": por_prioridade,
        }


# Instancia unica, compartilhada por todos os handlers.
repositorio = Repositorio()

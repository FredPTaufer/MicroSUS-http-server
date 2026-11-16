"""
handlers.py - Funcoes que tratam cada rota.

Aqui ficam as 6 rotas obrigatorias, o login (bonus) e as funcoes de validacao que elas
compartilham. A regra de negocio (estados e fila) fica em models.py e
repository.py; o HTML da fila fica em views.py.

Assinatura de todo handler:  handler(req, params) -> bytes da resposta
  req    : objeto Requisicao (metodo, caminho, headers, body)
  params : dict com parametros da URL, ex.: {"id": "3"}
"""
import json

import auth
from http_response import resposta_json, resposta_html, resposta_erro
from models import PRIORIDADES, PacienteNaoEncontrado
from repository import repositorio
from views import html_fila


class ErroRequisicao(Exception):
    """Dados invalidos enviados pelo cliente. O roteador responde 400."""


# ---------- validacao (reaproveitada por varias rotas) ----------

def _ler_json_objeto(req):
    """Converte o body em dict. Levanta ErroRequisicao se nao for um JSON-objeto."""
    if not req.body:
        raise ErroRequisicao("Body vazio: envie um JSON")
    try:
        # utf-8-sig: aceita UTF-8 com ou sem BOM (o PowerShell 5 costuma pôr BOM).
        dados = json.loads(req.body.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ErroRequisicao("JSON invalido")
    if not isinstance(dados, dict):
        raise ErroRequisicao("O JSON deve ser um objeto, ex.: {\"campo\": \"valor\"}")
    return dados


def _buscar_paciente_ou_404(params):
    """Converte o {id} da URL em int e busca o paciente.
    Levanta PacienteNaoEncontrado (o roteador responde 404) se o id nao for
    um numero ou nao existir."""
    texto = params["id"]
    if not (texto.isascii() and texto.isdigit()):      # "abc", "-1", "1.5"...
        raise PacienteNaoEncontrado(f"Paciente {texto!r} nao existe")
    paciente = repositorio.buscar(int(texto))
    if paciente is None:
        raise PacienteNaoEncontrado(f"Paciente {texto} nao existe")
    return paciente


def _texto_obrigatorio(dados, campo):
    """Garante que o campo existe, e uma string e nao esta vazia."""
    if campo not in dados:
        raise ErroRequisicao(f"Campo obrigatorio ausente: {campo}")
    valor = dados[campo]
    if not isinstance(valor, str):
        raise ErroRequisicao(f"Campo '{campo}' deve ser texto (string)")
    valor = valor.strip()
    if not valor:
        raise ErroRequisicao(f"Campo '{campo}' nao pode ser vazio")
    return valor


def login(req, params):                   # POST /login   (Bonus 2)
    dados = _ler_json_objeto(req)
    for campo in ("usuario", "senha"):
        if campo not in dados:
            raise ErroRequisicao(f"Campo obrigatorio ausente: {campo}")
        if not isinstance(dados[campo], str):
            raise ErroRequisicao(f"Campo '{campo}' deve ser texto (string)")

    if not auth.credenciais_validas(dados["usuario"], dados["senha"]):
        return resposta_erro(403, "Credenciais invalidas")
    return resposta_json(200, {"chave": auth.criar_sessao()})


def cadastrar_paciente(req, params):      # POST /pacientes
    dados = _ler_json_objeto(req)
    nome = _texto_obrigatorio(dados, "nome")
    sintoma = _texto_obrigatorio(dados, "sintoma")
    prioridade = _texto_obrigatorio(dados, "prioridade")

    if prioridade not in PRIORIDADES:
        raise ErroRequisicao(
            f"Prioridade invalida: {prioridade!r}. Use vermelho, amarelo ou verde")

    paciente = repositorio.cadastrar(nome, sintoma, prioridade)
    return resposta_json(201, paciente.to_dict())


def visualizar_fila(req, params):         # GET /fila
    # listar_fila() ja devolve somente EM_FILA, na ordem de atendimento.
    return resposta_html(200, html_fila(repositorio.listar_fila()))


def consultar_paciente(req, params):      # GET /pacientes/{id}
    paciente = _buscar_paciente_ou_404(params)
    # to_dict() ja inclui estado e prognostico (null ate ser ATENDIDO).
    return resposta_json(200, paciente.to_dict())


def chamar_proximo(req, params):          # POST /chamar
    # Nao le o body: o proprio servidor escolhe o paciente (prioridade + FIFO).
    # O repositorio tira o paciente do heap e o move EM_FILA -> EM_ATENDIMENTO.
    paciente = repositorio.chamar_proximo()
    if paciente is None:
        return resposta_erro(404, "Fila vazia: nenhum paciente EM_FILA")
    return resposta_json(200, paciente.to_dict())


def finalizar_atendimento(req, params):   # POST /pacientes/{id}/finalizar
    # Ordem das verificacoes: 404 (existe?) -> 409 (estado permite?) -> 400 (body ok?)
    paciente = _buscar_paciente_ou_404(params)
    paciente.validar_finalizacao()

    dados = _ler_json_objeto(req)
    prognostico = _texto_obrigatorio(dados, "prognostico")

    # O repositorio valida a transicao de novo e aplica EM_ATENDIMENTO -> ATENDIDO.
    paciente = repositorio.finalizar(paciente.id, prognostico)
    return resposta_json(200, paciente.to_dict())


def estatisticas(req, params):            # GET /estatisticas
    # A contagem (por estado, por prioridade e total) e feita no repositorio.
    return resposta_json(200, repositorio.estatisticas())

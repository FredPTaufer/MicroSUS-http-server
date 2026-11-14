"""Auxiliar dos testes: executa uma requisicao no roteador, sem sockets."""
import json

import auth
from http_parser import Requisicao
from router import rotear

# Chave de sessao valida, usada por todos os testes que nao testam a
# autenticacao em si. Todo POST enviado pelos helpers leva este header.
HEADERS_AUTH = {"authorization": auth.criar_sessao()}


def requisitar(metodo, caminho, body=b"", headers=None):
    """Devolve (status, headers, corpo) ; corpo ja vem como dict se for JSON,
    ou como str se for HTML."""
    if isinstance(body, str):
        body = body.encode("utf-8")
    cabecalhos = HEADERS_AUTH if headers is None else headers
    resp = rotear(Requisicao(metodo, caminho, "HTTP/1.1", dict(cabecalhos), body))
    cab, _, corpo = resp.partition(b"\r\n\r\n")
    linhas = cab.decode().split("\r\n")
    status = int(linhas[0].split(" ")[1])
    headers = dict(l.split(": ", 1) for l in linhas[1:])
    assert int(headers["Content-Length"]) == len(corpo)
    texto = corpo.decode("utf-8")
    if headers["Content-Type"].startswith("application/json"):
        return status, headers, json.loads(texto)
    return status, headers, texto

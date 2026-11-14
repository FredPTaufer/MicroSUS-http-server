"""
http_response.py - Etapa 4: monta respostas HTTP/1.1 como bytes.

Formato de uma resposta HTTP/1.1:

    HTTP/1.1 201 Created\r\n                   <- status line
    Content-Type: application/json; charset=utf-8\r\n
    Content-Length: 142\r\n                     <- tamanho do body em BYTES
    Connection: close\r\n
    \r\n                                        <- linha vazia: fim dos headers
    {"id": 1, ...}                              <- body
"""
import json

# Codigo -> texto da status line (reason phrase).
MOTIVOS = {
    200: "OK",
    201: "Created",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    500: "Internal Server Error",
}

JSON = "application/json; charset=utf-8"
HTML = "text/html; charset=utf-8"


def montar_resposta(status, corpo, content_type, headers_extras=None):
    """Funcao base: recebe o status, o corpo (str ou bytes) e o Content-Type
    e devolve a resposta HTTP completa, em bytes, pronta para sendall()."""
    # O corpo vira bytes ANTES de medir: Content-Length conta BYTES.
    # (Ex.: "João" tem 4 caracteres, mas 5 bytes em UTF-8.)
    if isinstance(corpo, str):
        corpo = corpo.encode("utf-8")

    linhas = [
        f"HTTP/1.1 {status} {MOTIVOS.get(status, 'Unknown')}",
        f"Content-Type: {content_type}",
        f"Content-Length: {len(corpo)}",
        "Connection: close",   # fechamos a conexao apos cada resposta
    ]
    for nome, valor in (headers_extras or {}).items():
        linhas.append(f"{nome}: {valor}")

    # Linhas separadas por CRLF; o CRLF duplo no fim encerra os headers.
    cabecalho = "\r\n".join(linhas) + "\r\n\r\n"
    return cabecalho.encode("utf-8") + corpo


def resposta_json(status, dados, headers_extras=None):
    """Serializa 'dados' (dict/list) para JSON e monta a resposta."""
    # ensure_ascii=False mantem "João" legivel (UTF-8) em vez de "Jo\u00e3o".
    texto = json.dumps(dados, ensure_ascii=False)
    return montar_resposta(status, texto, JSON, headers_extras)


def resposta_html(status, html, headers_extras=None):
    """Monta uma resposta com uma pagina HTML."""
    return montar_resposta(status, html, HTML, headers_extras)


def resposta_erro(status, mensagem):
    """Atalho para erros: {"erro": "mensagem"} em JSON."""
    return resposta_json(status, {"erro": mensagem})

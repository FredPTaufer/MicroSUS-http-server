"""
http_parser.py - Etapa 3: transforma bytes do socket em uma Requisicao.

Formato de uma requisicao HTTP/1.1:

    POST /pacientes HTTP/1.1\r\n          <- request line
    Host: localhost\r\n                    <- headers (um por linha)
    Content-Length: 53\r\n
    \r\n                                   <- linha vazia: fim dos headers
    {"nome": ...}                          <- body (exatamente Content-Length bytes)
"""

FIM_HEADERS = b"\r\n\r\n"
MAX_HEADERS = 16 * 1024        # protecao: headers com mais de 16 KB sao recusados
MAX_BODY = 1024 * 1024         # protecao: body com mais de 1 MB e recusado
VERSOES_ACEITAS = ("HTTP/1.1", "HTTP/1.0")


class RequisicaoInvalida(Exception):
    """Requisicao malformada. Na Etapa 4/5 sera respondida com 400."""


class Requisicao:
    """Representa uma requisicao HTTP ja interpretada."""

    def __init__(self, metodo, caminho, versao, headers, body):
        self.metodo = metodo      # str, ex: "POST"
        self.caminho = caminho    # str, ex: "/pacientes/3" (sem query string)
        self.versao = versao      # str, ex: "HTTP/1.1"
        self.headers = headers    # dict com chaves em minusculo
        self.body = body          # bytes (exatamente Content-Length bytes)

    def __repr__(self):
        return (f"Requisicao(metodo={self.metodo!r}, caminho={self.caminho!r}, "
                f"versao={self.versao!r}, headers={self.headers!r}, body={self.body!r})")


def _ler_ate_fim_dos_headers(conexao):
    """Le do socket, em loop, ate aparecer \\r\\n\\r\\n.

    TCP e um STREAM de bytes: um unico recv() pode trazer so um pedaco
    da requisicao, ou ate mais do que uma requisicao. Por isso acumulamos
    em um buffer e procuramos o delimitador.

    Devolve (bytes_dos_headers, bytes_que_ja_vieram_do_body).
    """
    buffer = b""
    while FIM_HEADERS not in buffer:
        if len(buffer) > MAX_HEADERS:
            raise RequisicaoInvalida("Headers grandes demais")
        pedaco = conexao.recv(4096)
        if not pedaco:  # cliente fechou a conexao antes de terminar
            raise RequisicaoInvalida("Conexao encerrada antes do fim dos headers")
        buffer += pedaco

    cabecalho, _, resto = buffer.partition(FIM_HEADERS)
    return cabecalho, resto


def _parsear_request_line(linha):
    partes = linha.split(" ")
    if len(partes) != 3:
        raise RequisicaoInvalida(f"Request line invalida: {linha!r}")
    metodo, alvo, versao = partes

    if not metodo.isalpha() or not alvo.startswith("/"):
        raise RequisicaoInvalida(f"Request line invalida: {linha!r}")
    if versao not in VERSOES_ACEITAS:
        raise RequisicaoInvalida(f"Versao HTTP nao suportada: {versao!r}")

    # Descarta a query string (?a=1) e o fragmento: nao usamos neste trabalho.
    caminho = alvo.split("?", 1)[0]
    return metodo.upper(), caminho, versao


def _parsear_headers(linhas):
    headers = {}
    for linha in linhas:
        nome, separador, valor = linha.partition(":")
        if not separador or not nome.strip():
            raise RequisicaoInvalida(f"Header invalido: {linha!r}")
        # Nomes de header nao diferenciam maiusculas/minusculas (RFC 7230):
        # guardamos em minusculo para buscar sempre do mesmo jeito.
        headers[nome.strip().lower()] = valor.strip()
    return headers


def _ler_body(conexao, ja_lido, content_length):
    """Le EXATAMENTE content_length bytes de body."""
    body = ja_lido
    while len(body) < content_length:
        faltam = content_length - len(body)
        pedaco = conexao.recv(min(4096, faltam))
        if not pedaco:
            raise RequisicaoInvalida("Conexao encerrada antes do fim do body")
        body += pedaco
    # Se veio a mais (ex.: outra requisicao colada), ignoramos o excedente.
    return body[:content_length]


def ler_requisicao(conexao):
    """Le e interpreta uma requisicao completa do socket."""
    cabecalho_bytes, resto = _ler_ate_fim_dos_headers(conexao)

    # Headers HTTP sao ASCII/latin-1 por especificacao. Ja o BODY fica como
    # bytes: quem o usar decide a codificacao (JSON usa UTF-8).
    texto = cabecalho_bytes.decode("latin-1")
    linhas = texto.split("\r\n")

    metodo, caminho, versao = _parsear_request_line(linhas[0])
    headers = _parsear_headers(linhas[1:])

    content_length = 0
    if "content-length" in headers:
        valor = headers["content-length"]
        if not valor.isdigit():
            raise RequisicaoInvalida(f"Content-Length invalido: {valor!r}")
        content_length = int(valor)
        if content_length > MAX_BODY:
            raise RequisicaoInvalida("Body grande demais")

    body = _ler_body(conexao, resto, content_length)
    return Requisicao(metodo, caminho, versao, headers, body)

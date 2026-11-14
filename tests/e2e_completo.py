"""
Teste ponta a ponta do MicroSUS (Etapa 8).

Sobe o servidor sozinho numa porta de teste (memoria limpa) e faz requisicoes
HTTP de verdade por SOCKET, conferindo status, headers e corpo.

    python tests/e2e_completo.py

Termina com codigo 0 se tudo passou e 1 se algo falhou.
"""
import json
import os
import re
import socket
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTA = 8099
HOST_TESTE = "127.0.0.1"   # IP numerico: evita o atraso de ~2 s do "localhost" (::1) no Windows

CHAVE = None                  # chave de sessao, obtida no login (secao 0)
_AUTO = object()              # "use a chave global"

total = 0
falhas = []
respostas_vistas = 0          # quantas respostas tiveram Content-Length conferido


class Resposta:
    def __init__(self, bruto):
        cab, sep, corpo = bruto.partition(b"\r\n\r\n")
        self.bruto, self.corpo = bruto, corpo
        linhas = cab.decode("latin-1").split("\r\n")
        self.linha_status = linhas[0]
        self.status = int(linhas[0].split(" ")[1])
        self.headers = {k.lower(): v for k, v in (l.split(": ", 1) for l in linhas[1:])}
        self.texto = corpo.decode("utf-8")
        self.tem_separador = bool(sep)

    @property
    def json(self):
        return json.loads(self.texto)


def enviar_bruto(dados_em_pedacos, pausa=0.0):
    """Envia bytes (em um ou mais pedacos) e le a resposta ate o servidor fechar."""
    global respostas_vistas
    s = socket.create_connection((HOST_TESTE, PORTA), timeout=5)
    for pedaco in dados_em_pedacos:
        s.sendall(pedaco)
        if pausa:
            time.sleep(pausa)
    bruto = b""
    while True:
        p = s.recv(4096)
        if not p:
            break
        bruto += p
    s.close()
    r = Resposta(bruto)
    # Toda resposta do servidor deve ter Content-Length = bytes reais do corpo.
    respostas_vistas += 1
    verificar(f"Content-Length confere ({r.linha_status})",
              int(r.headers["content-length"]) == len(r.corpo))
    return r


def req(metodo, caminho, body=None, autorizacao=_AUTO):
    """autorizacao: _AUTO = usa a chave do login; None = nao envia o header;
    uma string = envia exatamente esse valor."""
    corpo = b"" if body is None else (body.encode("utf-8") if isinstance(body, str) else body)
    cab = f"{metodo} {caminho} HTTP/1.1\r\nHost: localhost\r\n"
    valor = CHAVE if autorizacao is _AUTO else autorizacao
    if metodo == "POST" and valor:
        cab += f"Authorization: {valor}\r\n"
    if body is not None:
        cab += f"Content-Length: {len(corpo)}\r\nContent-Type: application/json\r\n"
    return enviar_bruto([cab.encode() + b"\r\n" + corpo])


def verificar(nome, condicao, detalhe=""):
    """Registra um teste. So imprime os que falham (e os de 'visibilidade')."""
    global total
    total += 1
    if not condicao:
        falhas.append(nome)
        print(f"   [FALHOU] {nome}  {detalhe}")


def checar(nome, condicao, detalhe=""):
    """Como 'verificar', mas imprime tambem o que passou."""
    verificar(nome, condicao, detalhe)
    if condicao:
        print(f"   [ok] {nome}")


def secao(titulo):
    print(f"\n=== {titulo} ===")


def cadastrar(nome, sintoma, prioridade):
    return req("POST", "/pacientes",
               json.dumps({"nome": nome, "sintoma": sintoma, "prioridade": prioridade},
                          ensure_ascii=False))


def nomes_na_fila():
    r = req("GET", "/fila")
    return re.findall(r"<tr><td>\d+</td><td>\d+</td><td>(.*?)</td>", r.texto)


def rodar():
    global CHAVE
    # ------------------------------------------------------------------
    secao("0. Autenticacao (Bonus 2)")
    posts = [("/pacientes", '{"nome": "X", "sintoma": "y", "prioridade": "verde"}'),
             ("/chamar", None), ("/pacientes/1/finalizar", '{"prognostico": "x"}'),
             ("/xyz", None)]
    for caminho, corpo in posts:
        r = req("POST", caminho, corpo, autorizacao=None)
        verificar(f"POST {caminho} sem Authorization -> 401",
                  r.status == 401 and r.headers.get("www-authenticate") == "Bearer", r.linha_status)
    checar("POST sem header Authorization -> 401 (+ WWW-Authenticate), inclusive em rota inexistente", True)
    for valor in ["chave-errada", "0" * 32, "Bearer chave-errada"]:
        verificar(f"chave incorreta {valor!r} -> 401",
                  req("POST", "/chamar", autorizacao=valor).status == 401)
    checar("chave incorreta -> 401", True)
    checar("GETs continuam livres (sem chave)",
           all(req("GET", c).status == 200 for c in ["/fila", "/estatisticas"]))
    checar("login com senha errada -> 403",
           req("POST", "/login", '{"usuario": "admin", "senha": "errada"}', autorizacao=None).status == 403)
    checar("login com usuario errado -> 403",
           req("POST", "/login", '{"usuario": "root", "senha": "admin123"}', autorizacao=None).status == 403)
    checar("login sem campo senha -> 400",
           req("POST", "/login", '{"usuario": "admin"}', autorizacao=None).status == 400)
    checar("login com JSON invalido -> 400",
           req("POST", "/login", '{"usuario": ', autorizacao=None).status == 400)
    r = req("GET", "/login")
    checar("GET /login -> 405 com Allow: POST", r.status == 405 and r.headers.get("allow") == "POST")
    r = req("POST", "/login", '{"usuario": "admin", "senha": "admin123"}', autorizacao=None)
    checar("login correto -> 200 com chave de 32 caracteres hexadecimais",
           r.status == 200 and re.fullmatch(r"[0-9a-f]{32}", r.json["chave"]) is not None, r.texto)
    CHAVE = r.json["chave"]
    checar("chave valida aceita tambem no formato 'Bearer <chave>' (404 = passou da autenticacao)",
           req("POST", "/chamar", autorizacao=f"Bearer {CHAVE}").status == 404)
    checar("nenhuma requisicao recusada criou paciente", req("GET", "/estatisticas").json["total"] == 0)

    # ------------------------------------------------------------------
    secao("1. Sistema vazio")
    r = req("GET", "/estatisticas")
    checar("estatisticas zeradas", r.json == {
        "total": 0,
        "porEstado": {"EM_FILA": 0, "EM_ATENDIMENTO": 0, "ATENDIDO": 0},
        "porPrioridade": {"vermelho": 0, "amarelo": 0, "verde": 0}})
    r = req("POST", "/chamar")
    checar("chamar com fila vazia -> 404", r.status == 404)
    r = req("GET", "/fila")
    checar("fila vazia -> 200 com mensagem", r.status == 200 and "Nenhum paciente" in r.texto)

    # ------------------------------------------------------------------
    secao("2. Cadastro de pacientes de todas as prioridades")
    dados = [("Ana", "tosse leve", "verde"), ("João", "febre alta", "amarelo"),
             ("Maria", "dor no peito", "vermelho"), ("Pedro", "enjoo", "verde"),
             ("Carlos", "falta de ar", "vermelho"), ("Bia", "torção", "amarelo")]
    for i, (nome, sintoma, pri) in enumerate(dados, start=1):
        r = cadastrar(nome, sintoma, pri)
        d = r.json
        verificar(f"cadastro {nome}: 201", r.status == 201)
        verificar(f"cadastro {nome}: JSON", "application/json" in r.headers["content-type"])
        verificar(f"cadastro {nome}: id sequencial {i}", d["id"] == i)
        verificar(f"cadastro {nome}: estado EM_FILA", d["estado"] == "EM_FILA")
        verificar(f"cadastro {nome}: horaChegada", bool(d["horaChegada"]))
        verificar(f"cadastro {nome}: prognostico null", d["prognostico"] is None)
        verificar(f"cadastro {nome}: dados devolvidos",
                  (d["nome"], d["sintoma"], d["prioridade"]) == (nome, sintoma, pri))
    checar("6 pacientes cadastrados (ids 1 a 6, 201, EM_FILA, acentos preservados)", True)

    # ------------------------------------------------------------------
    secao("3. Cadastro invalido -> 400 (e nada e cadastrado)")
    ruins = {
        "JSON invalido": '{"nome": "X", "sintoma": "y"',
        "sem nome": '{"sintoma": "y", "prioridade": "verde"}',
        "sem sintoma": '{"nome": "X", "prioridade": "verde"}',
        "sem prioridade": '{"nome": "X", "sintoma": "y"}',
        "nome numerico": '{"nome": 123, "sintoma": "y", "prioridade": "verde"}',
        "prioridade numerica": '{"nome": "X", "sintoma": "y", "prioridade": 1}',
        "prioridade inexistente": '{"nome": "X", "sintoma": "y", "prioridade": "azul"}',
        "nome vazio": '{"nome": " ", "sintoma": "y", "prioridade": "verde"}',
        "JSON nao e objeto": '[1, 2]',
    }
    for nome, corpo in ruins.items():
        r = req("POST", "/pacientes", corpo)
        verificar(f"400 para: {nome}", r.status == 400 and "erro" in r.json)
    r = req("POST", "/pacientes")
    verificar("400 sem body", r.status == 400)
    checar("10 entradas invalidas -> 400 com mensagem de erro", True)
    checar("nenhum paciente a mais foi criado", req("GET", "/estatisticas").json["total"] == 6)

    # ------------------------------------------------------------------
    secao("4. Consulta de paciente")
    r = req("GET", "/pacientes/1")
    checar("existente -> 200 com todos os campos",
           r.status == 200 and r.json["nome"] == "Ana" and r.json["estado"] == "EM_FILA"
           and set(r.json) == {"id", "nome", "sintoma", "prioridade", "estado",
                               "horaChegada", "prognostico"})
    for caminho in ["/pacientes/999", "/pacientes/abc", "/pacientes/0", "/pacientes/-1"]:
        verificar(f"404 em GET {caminho}", req("GET", caminho).status == 404)
    checar("inexistente/invalido (999, abc, 0, -1) -> 404", True)

    # ------------------------------------------------------------------
    secao("5. GET /fila: HTML no navegador, ordem e FIFO")
    r = req("GET", "/fila")
    checar("Content-Type text/html", r.headers["content-type"].startswith("text/html"))
    checar("e um documento HTML com tabela",
           r.texto.startswith("<!DOCTYPE html>") and "<table>" in r.texto)
    esperado = ["Maria", "Carlos", "João", "Bia", "Ana", "Pedro"]
    checar(f"ordem: vermelhos, amarelos, verdes (FIFO em cada) = {esperado}",
           nomes_na_fila() == esperado, str(nomes_na_fila()))

    # ------------------------------------------------------------------
    secao("6. Maquina de estados: finalizar quem esta EM_FILA -> 409")
    r = req("POST", "/pacientes/1/finalizar", '{"prognostico": "Alta"}')
    checar("finalizar EM_FILA -> 409 com mensagem",
           r.status == 409 and "EM_FILA" in r.json["erro"], r.texto)
    r = req("POST", "/pacientes/1/finalizar")
    checar("finalizar EM_FILA sem body -> 409 (estado vem antes do body)", r.status == 409)
    checar("finalizar inexistente -> 404",
           req("POST", "/pacientes/999/finalizar", '{"prognostico": "x"}').status == 404)
    checar("paciente 1 continua EM_FILA", req("GET", "/pacientes/1").json["estado"] == "EM_FILA")

    # ------------------------------------------------------------------
    secao("7. POST /chamar: prioridade + FIFO")
    ids = []
    for _ in range(2):
        r = req("POST", "/chamar")
        verificar("chamar -> 200", r.status == 200)
        verificar("chamado fica EM_ATENDIMENTO", r.json["estado"] == "EM_ATENDIMENTO")
        ids.append(r.json["id"])
    checar("1a e 2a chamadas: os dois vermelhos, na ordem de chegada (ids 3, 5)", ids == [3, 5], str(ids))
    cadastrar("Zeca", "convulsão", "vermelho")                      # id 7, chega por ultimo
    r = req("POST", "/chamar")
    checar("vermelho que chegou DEPOIS passa na frente de amarelos e verdes (id 7)",
           r.json["id"] == 7, r.texto)
    resto = [req("POST", "/chamar").json["id"] for _ in range(4)]
    checar("depois: amarelos (2, 6) e verdes (1, 4) em FIFO", resto == [2, 6, 1, 4], str(resto))
    r = req("POST", "/chamar")
    checar("fila esvaziada -> 404", r.status == 404 and "erro" in r.json)
    checar("/fila vazia de novo", "Nenhum paciente" in req("GET", "/fila").texto)
    checar("paciente chamado aparece EM_ATENDIMENTO na consulta",
           req("GET", "/pacientes/3").json["estado"] == "EM_ATENDIMENTO")

    # ------------------------------------------------------------------
    secao("8. POST /pacientes/{id}/finalizar")
    ruins = {"sem body": None, "JSON invalido": '{"prognostico": "x"',
             "campo ausente": '{"texto": "x"}', "tipo errado": '{"prognostico": 7}',
             "vazio": '{"prognostico": " "}'}
    for nome, corpo in ruins.items():
        r = req("POST", "/pacientes/3/finalizar", corpo)
        verificar(f"400 para: {nome}", r.status == 400)
        verificar(f"estado intacto apos 400 ({nome})",
                  req("GET", "/pacientes/3").json["estado"] == "EM_ATENDIMENTO")
    checar("5 bodies invalidos -> 400, e o paciente continua EM_ATENDIMENTO", True)

    r = req("POST", "/pacientes/3/finalizar", '{"prognostico": "Alta com repouso"}')
    checar("finalizar EM_ATENDIMENTO -> 200, ATENDIDO + prognostico",
           r.status == 200 and r.json["estado"] == "ATENDIDO"
           and r.json["prognostico"] == "Alta com repouso", r.texto)
    d = req("GET", "/pacientes/3").json
    checar("consulta mostra ATENDIDO com prognostico",
           d["estado"] == "ATENDIDO" and d["prognostico"] == "Alta com repouso")

    secao("9. ATENDIDO e terminal")
    for i in range(3):
        r = req("POST", "/pacientes/3/finalizar", '{"prognostico": "Tentativa de sobrescrever"}')
        verificar(f"finalizar ATENDIDO de novo (#{i + 1}) -> 409",
                  r.status == 409 and "ATENDIDO" in r.json["erro"])
    checar("3 tentativas de finalizar de novo -> 409 com mensagem", True)
    checar("prognostico original preservado",
           req("GET", "/pacientes/3").json["prognostico"] == "Alta com repouso")
    checar("/chamar nao devolve ATENDIDO (fila vazia -> 404)", req("POST", "/chamar").status == 404)
    checar("ATENDIDO nao aparece na /fila", "Nenhum paciente" in req("GET", "/fila").texto)
    req("POST", "/pacientes/5/finalizar", '{"prognostico": "Internado"}')
    req("POST", "/pacientes/7/finalizar", '{"prognostico": "Observacao"}')

    # ------------------------------------------------------------------
    secao("10. Roteamento: 404 e 405")
    for caminho in ["/xyz", "/favicon.ico", "/pacientes/1/extra", "/pacientes/1/finalizar/x", "/"]:
        verificar(f"404 em GET {caminho}", req("GET", caminho).status == 404)
    checar("rotas inexistentes -> 404", True)
    nao_permitidos = [("GET", "/pacientes", "POST"), ("PUT", "/pacientes", "POST"),
                      ("POST", "/fila", "GET"), ("POST", "/estatisticas", "GET"),
                      ("DELETE", "/pacientes/1", "GET"), ("POST", "/pacientes/1", "GET"),
                      ("GET", "/chamar", "POST"), ("GET", "/pacientes/1/finalizar", "POST")]
    for metodo, caminho, permitido in nao_permitidos:
        r = req(metodo, caminho)
        verificar(f"405 em {metodo} {caminho} (Allow: {permitido})",
                  r.status == 405 and r.headers.get("allow") == permitido, r.linha_status)
    checar("metodos nao permitidos -> 405 com header Allow correto", True)
    checar("query string ignorada: /fila?x=1 -> 200", req("GET", "/fila?x=1").status == 200)
    checar("barra final tolerada: /fila/ -> 200", req("GET", "/fila/").status == 200)

    # ------------------------------------------------------------------
    secao("11. Protocolo HTTP sobre o socket")
    corpo = '{"nome": "Fragmentado", "sintoma": "teste de TCP", "prioridade": "verde"}'.encode()
    cab = (b"POST /pacientes HTTP/1.1\r\nHost: localhost\r\n"
           b"AUTHORIZATION: " + CHAVE.encode() + b"\r\n"
           b"CONTENT-length: %d\r\n\r\n" % len(corpo))
    r = enviar_bruto([cab[:25], cab[25:], corpo[:7], corpo[7:30], corpo[30:]], pausa=0.2)
    checar("headers e body chegando em 5 pedacos, nome de header em MAIUSCULAS -> 201",
           r.status == 201 and r.json["nome"] == "Fragmentado" and r.json["id"] == 8, r.texto)
    r = req("GET", "/pacientes/1")
    checar("resposta comeca com 'HTTP/1.1' e usa CRLF + linha em branco",
           r.bruto.startswith(b"HTTP/1.1 200 OK\r\n") and r.tem_separador)
    checar("resposta traz Connection: close", r.headers.get("connection") == "close")
    r = enviar_bruto([b"LIXO\r\n\r\n"])
    checar("request line invalida -> 400", r.status == 400)
    r = enviar_bruto([b"GET /fila HTTP/2.0\r\n\r\n"])
    checar("versao HTTP nao suportada -> 400", r.status == 400)
    r = enviar_bruto([b"POST /pacientes HTTP/1.1\r\nContent-Length: abc\r\n\r\n"])
    checar("Content-Length invalido -> 400", r.status == 400)
    nome_acento = "Conceição Ñandú"
    r = cadastrar(nome_acento, "dor de cabeça", "verde")
    n = len(r.corpo)
    checar("UTF-8: Content-Length conta bytes, nao caracteres",
           int(r.headers["content-length"]) == n and n > len(r.texto), f"{n} bytes, {len(r.texto)} chars")

    # ------------------------------------------------------------------
    secao("12. Estatisticas finais")
    d = req("GET", "/estatisticas").json
    checar("total 9, por estado e por prioridade",
           d == {"total": 9,
                 "porEstado": {"EM_FILA": 2, "EM_ATENDIMENTO": 4, "ATENDIDO": 3},
                 "porPrioridade": {"vermelho": 3, "amarelo": 2, "verde": 4}}, str(d))
    checar("soma dos estados e das prioridades = total",
           sum(d["porEstado"].values()) == d["total"] == sum(d["porPrioridade"].values()))
    checar("/fila mostra so os 2 EM_FILA", nomes_na_fila() == ["Fragmentado", "Conceição Ñandú"],
           str(nomes_na_fila()))


def subir_servidor():
    proc = subprocess.Popen([sys.executable, "main.py", str(PORTA)], cwd=RAIZ,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        try:
            socket.create_connection((HOST_TESTE, PORTA), timeout=0.3).close()
            time.sleep(0.2)
            return proc
        except OSError:
            time.sleep(0.15)
    proc.kill()
    raise SystemExit("Nao consegui subir o servidor de teste.")


if __name__ == "__main__":
    servidor = subir_servidor()
    try:
        rodar()
    finally:
        servidor.terminate()
        servidor.wait()
    print("\n" + "=" * 60)
    print(f"{total - len(falhas)} de {total} verificacoes passaram "
          f"({respostas_vistas} respostas HTTP conferidas)")
    if falhas:
        print("FALHARAM:", *falhas, sep="\n  - ")
        sys.exit(1)
    print("TUDO OK")

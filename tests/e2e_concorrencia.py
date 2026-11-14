"""
Teste de CONCORRENCIA do MicroSUS (Bonus 1 - multithread).

Sobe o servidor sozinho numa porta de teste (memoria limpa) e dispara
varios clientes AO MESMO TEMPO (threading.Barrier faz todos largarem juntos).

    python tests/e2e_concorrencia.py

Termina com codigo 0 se tudo passou e 1 se algo falhou.
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time

RAIZ = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTA = 8098
# IP numerico e nao "localhost": no Windows, "localhost" resolve para ::1 (IPv6)
# e 127.0.0.1; como o servidor escuta so em IPv4, a tentativa em ::1 e recusada
# e leva ~2 s para falhar, o que falsearia os testes que medem tempo.
HOST_TESTE = "127.0.0.1"

CHAVE = None          # chave de sessao (login no inicio de rodar)
total, falhas = 0, []


def checar(nome, condicao, detalhe=""):
    global total
    total += 1
    if not condicao:
        falhas.append(nome)
    print(f"   [{'ok' if condicao else 'FALHOU'}] {nome}  {'' if condicao else detalhe}")


def secao(titulo):
    print(f"\n=== {titulo} ===")


class Resp:
    def __init__(self, bruto):
        cab, _, corpo = bruto.partition(b"\r\n\r\n")
        self.status = int(cab.split(b" ", 2)[1])
        self.texto = corpo.decode("utf-8")
        try:
            self.json = json.loads(self.texto)
        except ValueError:
            self.json = None


def ler_resposta(s):
    bruto = b""
    while True:
        p = s.recv(4096)
        if not p:
            return Resp(bruto)
        bruto += p


def req(metodo, caminho, body=None, timeout=40):
    corpo = b"" if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    cab = f"{metodo} {caminho} HTTP/1.1\r\nHost: localhost\r\n"
    if metodo == "POST" and CHAVE:
        cab += f"Authorization: {CHAVE}\r\n"
    if body is not None:
        cab += f"Content-Length: {len(corpo)}\r\n"
    s = socket.create_connection((HOST_TESTE, PORTA), timeout=timeout)
    try:
        s.sendall(cab.encode() + b"\r\n" + corpo)
        return ler_resposta(s)
    finally:
        s.close()


def em_paralelo(tarefas):
    """Executa todas as funcoes ao mesmo tempo (largada sincronizada)
    e devolve os resultados na mesma ordem."""
    barreira = threading.Barrier(len(tarefas))
    resultados = [None] * len(tarefas)

    def rodar(i, f):
        barreira.wait()
        try:
            resultados[i] = f()
        except Exception as e:            # noqa
            resultados[i] = e

    threads = [threading.Thread(target=rodar, args=(i, f)) for i, f in enumerate(tarefas)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return resultados


def sem_erros(rs):
    return all(isinstance(r, Resp) for r in rs)


def rodar():
    global CHAVE
    CHAVE = req("POST", "/login", {"usuario": "admin", "senha": "admin123"}).json["chave"]

    # ------------------------------------------------------------------
    secao("A. Conexoes ociosas NAO bloqueiam os outros clientes")
    ociosas = [socket.create_connection((HOST_TESTE, PORTA)) for _ in range(5)]
    t0 = time.time()
    r = req("GET", "/estatisticas")
    dt = time.time() - t0
    checar(f"com 5 conexoes ociosas abertas, GET /estatisticas responde rapido ({dt:.2f}s)",
           r.status == 200 and dt < 1.0)
    for s in ociosas:
        s.close()

    # ------------------------------------------------------------------
    secao("B. 40 cadastros simultaneos: ids unicos e sequenciais")
    prioridades = ["vermelho", "amarelo", "verde"]
    dados = [{"nome": f"P{i}", "sintoma": "s", "prioridade": prioridades[i % 3]} for i in range(40)]
    rs = em_paralelo([lambda d=d: req("POST", "/pacientes", d) for d in dados])
    checar("todos responderam 201", sem_erros(rs) and all(r.status == 201 for r in rs),
           str([r if not isinstance(r, Resp) else r.status for r in rs if not isinstance(r, Resp) or r.status != 201][:3]))
    ids = sorted(r.json["id"] for r in rs if isinstance(r, Resp) and r.json)
    checar("ids = 1..40, sem repeticao e sem buraco", ids == list(range(1, 41)), str(ids))
    checar("total no servidor = 40", req("GET", "/estatisticas").json["total"] == 40)

    # ------------------------------------------------------------------
    secao("C. Cliente LENTO nao trava os outros")
    corpo = json.dumps({"nome": "Lento", "sintoma": "s", "prioridade": "verde"}).encode()
    s = socket.create_connection((HOST_TESTE, PORTA), timeout=20)
    s.sendall(b"POST /pacientes HTTP/1.1\r\nAuthorization: " + CHAVE.encode()
             + b"\r\nContent-Length: %d\r\n\r\n" % len(corpo) + corpo[:10])
    time.sleep(0.3)                      # o servidor fica esperando o resto do body
    t0 = time.time()
    r = req("GET", "/fila")
    dt = time.time() - t0
    checar(f"enquanto o cliente lento nao termina, GET /fila responde rapido ({dt:.2f}s)",
           r.status == 200 and dt < 1.0)
    s.sendall(corpo[10:])
    r = ler_resposta(s)
    s.close()
    checar("o cliente lento, ao terminar de enviar, e atendido normalmente (201, id 41)",
           r.status == 201 and r.json["id"] == 41, r.texto)

    # ------------------------------------------------------------------
    secao("D. 45 chamadas simultaneas para 41 pacientes: nenhum paciente chamado duas vezes")
    rs = em_paralelo([lambda: req("POST", "/chamar") for _ in range(45)])
    ok200 = [r for r in rs if isinstance(r, Resp) and r.status == 200]
    ok404 = [r for r in rs if isinstance(r, Resp) and r.status == 404]
    checar("41 respostas 200 e 4 respostas 404 (nenhum 500)",
           len(ok200) == 41 and len(ok404) == 4, f"200={len(ok200)} 404={len(ok404)}")
    chamados = [r.json["id"] for r in ok200]
    checar("os 41 pacientes chamados sao todos DIFERENTES", len(set(chamados)) == 41, str(sorted(chamados)))
    est = req("GET", "/estatisticas").json
    checar("estatisticas: EM_FILA 0, EM_ATENDIMENTO 41",
           est["porEstado"] == {"EM_FILA": 0, "EM_ATENDIMENTO": 41, "ATENDIDO": 0}, str(est))

    # ------------------------------------------------------------------
    secao("E. 30 tentativas simultaneas de finalizar o MESMO paciente")
    rs = em_paralelo([lambda i=i: req("POST", "/pacientes/7/finalizar", {"prognostico": f"p{i}"})
                      for i in range(30)])
    venc = [r for r in rs if isinstance(r, Resp) and r.status == 200]
    conf = [r for r in rs if isinstance(r, Resp) and r.status == 409]
    checar("exatamente 1 vence (200) e 29 recebem 409",
           len(venc) == 1 and len(conf) == 29, f"200={len(venc)} 409={len(conf)}")
    if len(venc) == 1:
        guardado = req("GET", "/pacientes/7").json
        checar("o prognostico guardado e o do vencedor (ninguem sobrescreveu)",
               guardado["estado"] == "ATENDIDO" and guardado["prognostico"] == venc[0].json["prognostico"],
               str(guardado))

    # ------------------------------------------------------------------
    secao("F. Finalizar os outros 40 pacientes ao mesmo tempo")
    outros = [i for i in range(1, 42) if i != 7]
    rs = em_paralelo([lambda i=i: req("POST", f"/pacientes/{i}/finalizar", {"prognostico": f"alta {i}"})
                      for i in outros])
    checar("todos 200", sem_erros(rs) and all(r.status == 200 for r in rs))
    est = req("GET", "/estatisticas").json
    checar("estatisticas: tudo ATENDIDO (41)",
           est["total"] == 41 and est["porEstado"] == {"EM_FILA": 0, "EM_ATENDIMENTO": 0, "ATENDIDO": 41},
           str(est))

    # ------------------------------------------------------------------
    secao("G. Escritas e leituras misturadas (30 cadastros + 30 /fila + 30 /estatisticas)")
    tarefas = ([lambda i=i: req("POST", "/pacientes",
                                {"nome": f"G{i}", "sintoma": "s", "prioridade": prioridades[i % 3]})
                for i in range(30)]
               + [lambda: req("GET", "/fila") for _ in range(30)]
               + [lambda: req("GET", "/estatisticas") for _ in range(30)])
    rs = em_paralelo(tarefas)
    checar("90 requisicoes, nenhum erro 500", sem_erros(rs) and all(r.status in (200, 201) for r in rs),
           str([r.status for r in rs if isinstance(r, Resp) and r.status not in (200, 201)][:5]))
    est = req("GET", "/estatisticas").json
    checar("totais consistentes: 71 pacientes, 30 EM_FILA, 41 ATENDIDO",
           est["total"] == 71 and est["porEstado"]["EM_FILA"] == 30
           and sum(est["porPrioridade"].values()) == 71, str(est))


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
    print(f"{total - len(falhas)} de {total} verificacoes passaram")
    if falhas:
        print("FALHARAM:", *falhas, sep="\n  - ")
        sys.exit(1)
    print("TUDO OK")

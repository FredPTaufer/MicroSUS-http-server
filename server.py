"""
server.py - Camada de rede do MicroSUS (multithread - Bonus 1).

Responsabilidade: criar o socket TCP, escutar uma porta, aceitar conexoes
e atender CADA conexao em sua propria thread.

  Thread principal : so faz accept() em loop e dispara uma thread por cliente.
  Thread do cliente: le a requisicao, processa, responde e fecha a conexao.

Dois locks (travas) evitam problemas de concorrencia:
  _trava_dados : garante que so UMA requisicao por vez mexe nos pacientes e na
                 fila (secao critica). Sem ela, duas threads poderiam, por
                 exemplo, chamar o MESMO paciente ou gerar o MESMO id.
  _trava_log   : impede que os prints de threads diferentes se misturem.
"""
import socket
import threading

from http_parser import ler_requisicao, RequisicaoInvalida
from http_response import resposta_erro
from router import rotear

HOST = "0.0.0.0"   # aceita conexoes de qualquer interface de rede
PORTA = 8080
TIMEOUT_CLIENTE = 5.0   # segundos que esperamos dados de um cliente

_trava_dados = threading.Lock()
_trava_log = threading.Lock()


def log(texto):
    with _trava_log:
        print(texto, flush=True)


def atender_cliente(conexao, endereco):
    """Executada em uma thread: trata UMA conexao do inicio ao fim."""
    nome = threading.current_thread().name
    origem = f"{endereco[0]}:{endereco[1]}"

    with conexao:   # garante o close() da conexao ao sair
        # Timeout: um cliente que conecta e nao envia nada (o navegador faz
        # isso) ocupa so a propria thread, nao trava os outros clientes.
        conexao.settimeout(TIMEOUT_CLIENTE)

        # 1) Le e interpreta a requisicao (ver http_parser.py). Esta parte e
        #    E/S de rede (pode demorar): fica FORA do lock, em paralelo.
        try:
            req = ler_requisicao(conexao)
        except socket.timeout:
            log(f"[{nome}] {origem} - cliente nao enviou nada (timeout). Descartando.")
            return
        except RequisicaoInvalida as erro:
            log(f"[{nome}] {origem} - requisicao invalida: {erro}")
            try:
                conexao.sendall(resposta_erro(400, f"Requisicao invalida: {erro}"))
            except OSError:
                pass
            return
        except OSError as erro:                  # ex.: conexao resetada pelo cliente
            log(f"[{nome}] {origem} - erro de conexao: {erro}")
            return

        # 2) SECAO CRITICA: processa a requisicao (roteador + handlers + dados).
        #    So uma thread por vez entra aqui, entao a fila, os ids e os
        #    estados dos pacientes nunca ficam inconsistentes.
        with _trava_dados:
            resposta = rotear(req)

        # 3) Envia a resposta (E/S de rede, de novo fora do lock).
        try:
            conexao.sendall(resposta)
        except OSError as erro:
            log(f"[{nome}] {origem} - falha ao enviar resposta: {erro}")
            return

        status = resposta.split(b"\r\n", 1)[0].decode("latin-1")
        # Nao despeja a chave de sessao inteira no log: mostra so o comeco.
        headers_log = dict(req.headers)
        if "authorization" in headers_log:
            headers_log["authorization"] = headers_log["authorization"][:12] + "***"
        log(f"[{nome}] {origem}\n"
            f"   {req.metodo} {req.caminho} {req.versao}\n"
            f"   headers: {headers_log}\n"
            f"   body: {req.body!r} ({len(req.body)} bytes)\n"
            f"   -> {status}")


def iniciar_servidor(host=HOST, porta=PORTA):
    # 1) socket(): cria o "telefone". AF_INET = IPv4, SOCK_STREAM = TCP.
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Permite reiniciar o servidor sem esperar o SO liberar a porta.
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # 2) bind(): associa o socket a um endereco (IP + porta).
    servidor.bind((host, porta))

    # 3) listen(): passa para o estado de escuta. O numero e o tamanho da fila
    #    de conexoes ainda nao aceitas; com varios clientes ao mesmo tempo, um
    #    valor pequeno (como 5) faria o SO recusar conexoes.
    servidor.listen(128)

    # Timeout no accept: no Windows, um accept() bloqueante nao deixa o
    # Ctrl+C funcionar. Acordando a cada 1s, o Ctrl+C passa a funcionar.
    servidor.settimeout(1.0)

    log(f"[MicroSUS] Escutando em http://localhost:{porta}  (Ctrl+C para parar)")

    try:
        while True:
            try:
                # 4) accept(): espera um cliente conectar. Devolve um NOVO
                #    socket (conexao) exclusivo desse cliente + o endereco dele.
                conexao, endereco = servidor.accept()
            except socket.timeout:
                continue

            # 5) Uma thread por cliente. daemon=True: se o programa for
            #    encerrado (Ctrl+C), as threads nao seguram o processo.
            threading.Thread(target=atender_cliente, args=(conexao, endereco),
                             daemon=True).start()
    except KeyboardInterrupt:
        log("\n[MicroSUS] Encerrando servidor.")
    finally:
        servidor.close()

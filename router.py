"""
router.py - Etapa 5: (metodo + caminho) -> handler.

Regras (em ordem):
  - POST (exceto /login) sem chave valida -> 401 Unauthorized   (bonus: autenticacao)
  - caminho existe e metodo permitido  -> executa o handler
  - caminho existe, metodo NAO permitido -> 405 Method Not Allowed (+ header Allow)
  - caminho nao existe                  -> 404 Not Found
  - handler levanta ErroRequisicao      -> 400 Bad Request
  - handler levanta PacienteNaoEncontrado -> 404 Not Found
  - handler levanta TransicaoInvalida   -> 409 Conflict
  - handler levanta excecao inesperada  -> 500 Internal Server Error
"""
import traceback

import auth
import handlers
from http_response import resposta_json, resposta_erro
from models import PacienteNaoEncontrado, TransicaoInvalida

# Tabela de rotas: (metodo, padrao do caminho, funcao).
# Trechos entre chaves, como {id}, sao parametros da URL.
ROTAS = [
    ("POST", "/login",                     handlers.login),          # bonus: autenticacao
    ("POST", "/pacientes",                 handlers.cadastrar_paciente),
    ("GET",  "/fila",                      handlers.visualizar_fila),
    ("GET",  "/pacientes/{id}",            handlers.consultar_paciente),
    ("POST", "/chamar",                    handlers.chamar_proximo),
    ("POST", "/pacientes/{id}/finalizar",  handlers.finalizar_atendimento),
    ("GET",  "/estatisticas",              handlers.estatisticas),
]


def _casar(padrao, caminho):
    """Compara o caminho com o padrao, trecho a trecho (separando por '/').
    Devolve um dict com os parametros ({"id": "3"}) se casar, ou None."""
    trechos_padrao = padrao.strip("/").split("/")
    trechos_caminho = caminho.strip("/").split("/")

    if len(trechos_padrao) != len(trechos_caminho):
        return None

    params = {}
    for esperado, recebido in zip(trechos_padrao, trechos_caminho):
        if esperado.startswith("{") and esperado.endswith("}"):
            if recebido == "":
                return None
            params[esperado[1:-1]] = recebido   # captura o parametro
        elif esperado != recebido:
            return None
    return params


def rotear(req):
    """Recebe a Requisicao e devolve os bytes da resposta HTTP."""
    # Autenticacao (Bonus 2): todo POST, exceto /login, exige uma chave valida
    # no header Authorization. Roda ANTES do roteamento.
    if req.metodo == "POST" and req.caminho.strip("/") != "login":
        chave = auth.extrair_chave(req.headers)
        if not auth.chave_valida(chave):
            motivo = ("Header Authorization ausente. Faca POST /login para obter a chave"
                      if not chave else "Chave de sessao invalida")
            return resposta_json(401, {"erro": motivo}, {"WWW-Authenticate": "Bearer"})

    metodos_permitidos = []

    for metodo, padrao, handler in ROTAS:
        params = _casar(padrao, req.caminho)
        if params is None:
            continue                       # caminho diferente: tenta a proxima
        if metodo == req.metodo:
            try:
                return handler(req, params)
            except handlers.ErroRequisicao as erro:
                return resposta_erro(400, str(erro))       # dados invalidos
            except PacienteNaoEncontrado as erro:
                return resposta_erro(404, str(erro))       # id inexistente
            except TransicaoInvalida as erro:
                return resposta_erro(409, str(erro))       # viola a maquina de estados
            except Exception:
                traceback.print_exc()      # detalhes so no terminal do servidor
                return resposta_erro(500, "Erro interno do servidor")
        metodos_permitidos.append(metodo)  # caminho existe, mas com outro metodo

    if metodos_permitidos:
        return resposta_json(
            405,
            {"erro": f"Metodo {req.metodo} nao permitido para {req.caminho}",
             "permitidos": sorted(set(metodos_permitidos))},
            {"Allow": ", ".join(sorted(set(metodos_permitidos)))},
        )

    return resposta_erro(404, f"Rota nao encontrada: {req.caminho}")

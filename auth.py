"""
auth.py - Bonus 2: autenticacao simples por chave de sessao.

Fluxo:
  1) POST /login com {"usuario": "...", "senha": "..."}
  2) Se as credenciais conferem, o servidor gera uma chave aleatoria, guarda
     em memoria e devolve {"chave": "..."}.
  3) O cliente envia essa chave no header  Authorization  de todo POST
     (exceto /login). Sem chave ou com chave desconhecida -> 401.

Concorrencia: este modulo so e usado dentro do roteador, que ja roda sob o
lock do servidor (server.py), entao o set de chaves nao precisa de lock proprio.
"""
import secrets

# Credenciais fixas no servidor (o enunciado permite).
USUARIO = "admin"
SENHA = "admin123"

_chaves_validas = set()     # chaves de sessao emitidas e ainda validas


def credenciais_validas(usuario, senha):
    """Confere usuario e senha. compare_digest compara em tempo constante
    (evita 'timing attack') e exige bytes quando ha caracteres nao-ASCII."""
    ok_usuario = secrets.compare_digest(usuario.encode("utf-8"), USUARIO.encode("utf-8"))
    ok_senha = secrets.compare_digest(senha.encode("utf-8"), SENHA.encode("utf-8"))
    return ok_usuario and ok_senha


def criar_sessao():
    """Gera uma chave aleatoria (32 caracteres hexadecimais) e a registra."""
    chave = secrets.token_hex(16)
    _chaves_validas.add(chave)
    return chave


def extrair_chave(headers):
    """Le a chave do header Authorization (nomes de header ja vem em minusculo).
    Aceita a chave pura ou no formato 'Bearer <chave>'. Devolve '' se ausente."""
    valor = headers.get("authorization", "").strip()
    partes = valor.split(None, 1)
    if len(partes) == 2 and partes[0].lower() == "bearer":
        return partes[1].strip()
    return valor


def chave_valida(chave):
    return bool(chave) and chave in _chaves_validas

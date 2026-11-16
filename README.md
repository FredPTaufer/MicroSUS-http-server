# MicroSUS – Servidor HTTP de Fila de Pronto-Socorro

Trabalho II de Sistemas Distribuídos I – IFSul, Câmpus Passo Fundo.

Servidor HTTP/1.1 construído **diretamente sobre sockets TCP** (sem frameworks HTTP),
em Python 3, usando apenas a biblioteca padrão. Dados em memória.

## Como executar

```
python main.py          # porta 8080
python main.py 9000     # outra porta
```

Requisitos: Python 3.9 ou superior. Nenhuma dependência externa.
Para parar: `Ctrl+C`.

## Como testar: `demo.http` (VS Code)

Abra o arquivo `demo.http` no VS Code com a extensão **REST Client** instalada e clique em
**Send Request** acima de cada bloco, na ordem. A resposta aparece ao lado, e o título de cada
bloco diz o que esperar. As rotas `GET` também podem ser abertas direto no navegador
(por exemplo, `http://localhost:8080/fila`).

Também funciona com Postman, Insomnia ou `curl`.

## ⚠ Autenticação (bônus): faça o login antes dos POST

Todo `POST`, exceto `/login`, exige o header `Authorization` com a chave devolvida pelo login.
Sem ele, o servidor responde `401 Unauthorized`.

```
POST /login   {"usuario": "admin", "senha": "admin123"}   ->   {"chave": "..."}
```

Depois, envie a chave em cada POST: `Authorization: <chave>` (ou `Authorization: Bearer <chave>`).
No `demo.http`, o bloco **C4** faz o login e guarda a chave automaticamente.
As chaves ficam em memória: se o servidor for reiniciado, faça o login de novo.
Os `GET` não exigem chave.

## Rotas

| Método | Rota | Descrição | Resposta | Autenticação |
|---|---|---|---|---|
| POST | `/login` | Obtém a chave de sessão (bônus) | JSON | não |
| POST | `/pacientes` | Cadastra paciente (→ `EM_FILA`) | JSON | sim |
| GET | `/fila` | Fila ordenada por prioridade e chegada | **HTML** | não |
| GET | `/pacientes/{id}` | Consulta um paciente | JSON | não |
| POST | `/chamar` | Chama o próximo (→ `EM_ATENDIMENTO`) | JSON | sim |
| POST | `/pacientes/{id}/finalizar` | Finaliza (→ `ATENDIDO`) | JSON | sim |
| GET | `/estatisticas` | Contagens por estado e prioridade | JSON | não |

Máquina de estados: `EM_FILA → EM_ATENDIMENTO → ATENDIDO` (terminal).
Ordem da fila: vermelho > amarelo > verde; FIFO dentro de cada prioridade.

## Estrutura

```
main.py            ponto de entrada
server.py          socket TCP, accept, uma thread por conexão (bônus multithread)
http_parser.py     bytes -> Requisicao (request line, headers, Content-Length, body)
http_response.py   monta respostas HTTP (status line, headers, body)
router.py          autenticação + (método, caminho) -> handler; 401/404/405/409/500
handlers.py        as rotas (validação e resposta)
models.py          Paciente e máquina de estados
repository.py      armazenamento em memória (dict) + fila de prioridade (heapq)
views.py           HTML da página /fila
auth.py            login e chaves de sessão (bônus)
demo.http          roteiro de demonstração (REST Client do VS Code)
```

> Dica (Windows): se a primeira requisição demorar ~2 s, use `127.0.0.1` em vez de `localhost`
> (o `localhost` tenta primeiro IPv6, e o servidor escuta em IPv4).

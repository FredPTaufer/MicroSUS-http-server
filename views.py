"""
views.py - Etapa 7: gera o HTML da pagina /fila.

Separado dos handlers para manter cada arquivo com uma responsabilidade:
handlers decidem O QUE responder, views.py decide COMO a pagina e escrita.
"""
from html import escape

ROTULO_PRIORIDADE = {"vermelho": "Vermelho", "amarelo": "Amarelo", "verde": "Verde"}

CSS = """
  body { font-family: Arial, Helvetica, sans-serif; margin: 2rem; background: #f4f6f8; color: #222; }
  h1 { margin-bottom: 0.2rem; }
  .sub { color: #555; margin-top: 0; }
  table { border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.15); }
  th, td { padding: 0.6rem 0.9rem; text-align: left; border-bottom: 1px solid #e3e6ea; }
  th { background: #1f3a5f; color: #fff; }
  .badge { display: inline-block; padding: 0.15rem 0.6rem; border-radius: 1rem; font-weight: bold; font-size: 0.85rem; }
  .vermelho { background: #d32f2f; color: #fff; }
  .amarelo  { background: #fbc02d; color: #222; }
  .verde    { background: #388e3c; color: #fff; }
  .vazio { padding: 2rem; background: #fff; text-align: center; color: #555; box-shadow: 0 1px 3px rgba(0,0,0,.15); }
"""


def _linha(posicao, p):
    # escape(): converte < > & " ' em entidades HTML. SEM isso, um paciente
    # cadastrado com nome "<script>...</script>" executaria codigo no navegador.
    return (
        "<tr>"
        f"<td>{posicao}</td>"
        f"<td>{p.id}</td>"
        f"<td>{escape(p.nome)}</td>"
        f"<td>{escape(p.sintoma)}</td>"
        f'<td><span class="badge {p.prioridade}">{ROTULO_PRIORIDADE[p.prioridade]}</span></td>'
        f"<td>{escape(p.hora_chegada)}</td>"
        "</tr>"
    )


def html_fila(pacientes):
    """Recebe a lista de Paciente (ja ordenada) e devolve a pagina HTML (str)."""
    if pacientes:
        linhas = "\n".join(_linha(i, p) for i, p in enumerate(pacientes, start=1))
        conteudo = (
            "<table>\n<thead><tr><th>Posição</th><th>ID</th><th>Nome</th>"
            "<th>Sintoma</th><th>Prioridade</th><th>Chegada</th></tr></thead>\n"
            f"<tbody>\n{linhas}\n</tbody>\n</table>"
        )
        total = f"{len(pacientes)} paciente(s) aguardando atendimento"
    else:
        conteudo = '<div class="vazio">Nenhum paciente na fila.</div>'
        total = "Fila vazia"

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>MicroSUS - Fila de Atendimento</title>
<link rel="icon" href="data:,">
<style>{CSS}</style>
</head>
<body>
<h1>MicroSUS - Fila de Atendimento</h1>
<p class="sub">{total} · ordem: vermelho &gt; amarelo &gt; verde, e por chegada dentro de cada prioridade</p>
{conteudo}
</body>
</html>
"""

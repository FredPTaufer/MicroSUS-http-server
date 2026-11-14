# Roteiro de testes do MicroSUS com curl.exe (PowerShell).
# 1) Reinicie o servidor (memoria limpa):   python main.py
# (o roteiro faz login sozinho e envia a chave em todos os POST)
# 2) Na pasta do projeto (microsus), em OUTRO terminal:
#       powershell -ExecutionPolicy Bypass -File tests\roteiro_curl.ps1
# Cada passo mostra o status e o corpo; confira com o "esperado" impresso.

$base = "http://localhost:8080"
$j = "tests\json"

Write-Host ""
Write-Host "[A1] POST /pacientes SEM Authorization" -ForegroundColor Cyan
Write-Host "     esperado: 401 + WWW-Authenticate" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/pacientes" -H "Content-Type: application/json" --data-binary "@$j\maria_vermelho.json"
Write-Host ""
Write-Host "[A2] POST /chamar com chave ERRADA" -ForegroundColor Cyan
Write-Host "     esperado: 401 (Chave de sessao invalida)" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/chamar" -H "Authorization: chave-errada"
Write-Host ""
Write-Host "[A3] LOGIN com senha errada" -ForegroundColor Cyan
Write-Host "     esperado: 403" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/login" -H "Content-Type: application/json" --data-binary "@$j\login_senha_errada.json"
Write-Host ""
Write-Host "[A4] LOGIN correto (a chave fica guardada em `$chave)" -ForegroundColor Cyan
Write-Host "     esperado: 200 com {chave: ...}" -ForegroundColor DarkGray
$resposta = curl.exe -s -X POST "$base/login" -H "Content-Type: application/json" --data-binary "@$j\login_ok.json"
Write-Host $resposta
$chave = ($resposta | ConvertFrom-Json).chave
Write-Host ""

Write-Host ""
Write-Host "[01] Estatisticas com o sistema vazio" -ForegroundColor Cyan
Write-Host "     esperado: 200, tudo zero" -ForegroundColor DarkGray
curl.exe -s -i "$base/estatisticas"
Write-Host ""
Write-Host ""
Write-Host "[02] Chamar com a fila vazia" -ForegroundColor Cyan
Write-Host "     esperado: 404" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/chamar" -H "Authorization: $chave"
Write-Host ""
Write-Host ""
Write-Host "[03] Cadastrar Maria (vermelho) -> id 1" -ForegroundColor Cyan
Write-Host "     esperado: 201" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/pacientes" -H "Content-Type: application/json" --data-binary "@$j\maria_vermelho.json" -H "Authorization: $chave"
Write-Host ""
Write-Host ""
Write-Host "[04] Cadastrar Joao (amarelo) -> id 2" -ForegroundColor Cyan
Write-Host "     esperado: 201" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/pacientes" -H "Content-Type: application/json" --data-binary "@$j\joao_amarelo.json" -H "Authorization: $chave"
Write-Host ""
Write-Host ""
Write-Host "[05] Cadastrar Ana (verde) -> id 3" -ForegroundColor Cyan
Write-Host "     esperado: 201" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/pacientes" -H "Content-Type: application/json" --data-binary "@$j\ana_verde.json" -H "Authorization: $chave"
Write-Host ""
Write-Host ""
Write-Host "[06] Cadastrar Pedro (verde) -> id 4" -ForegroundColor Cyan
Write-Host "     esperado: 201" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/pacientes" -H "Content-Type: application/json" --data-binary "@$j\pedro_verde.json" -H "Authorization: $chave"
Write-Host ""
Write-Host ""
Write-Host "[07] Cadastrar Carlos (vermelho) -> id 5" -ForegroundColor Cyan
Write-Host "     esperado: 201" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/pacientes" -H "Content-Type: application/json" --data-binary "@$j\carlos_vermelho.json" -H "Authorization: $chave"
Write-Host ""
Write-Host ""
Write-Host "[08] ERRO: JSON invalido" -ForegroundColor Cyan
Write-Host "     esperado: 400" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/pacientes" -H "Content-Type: application/json" --data-binary "@$j\invalido.json" -H "Authorization: $chave"
Write-Host ""
Write-Host ""
Write-Host "[09] ERRO: campo prioridade ausente" -ForegroundColor Cyan
Write-Host "     esperado: 400" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/pacientes" -H "Content-Type: application/json" --data-binary "@$j\sem_prioridade.json" -H "Authorization: $chave"
Write-Host ""
Write-Host ""
Write-Host "[10] ERRO: nome com tipo errado" -ForegroundColor Cyan
Write-Host "     esperado: 400" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/pacientes" -H "Content-Type: application/json" --data-binary "@$j\nome_numero.json" -H "Authorization: $chave"
Write-Host ""
Write-Host ""
Write-Host "[11] ERRO: prioridade inexistente" -ForegroundColor Cyan
Write-Host "     esperado: 400" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/pacientes" -H "Content-Type: application/json" --data-binary "@$j\prioridade_azul.json" -H "Authorization: $chave"
Write-Host ""
Write-Host ""
Write-Host "[12] Consultar paciente 1" -ForegroundColor Cyan
Write-Host "     esperado: 200, EM_FILA" -ForegroundColor DarkGray
curl.exe -s -i "$base/pacientes/1"
Write-Host ""
Write-Host ""
Write-Host "[13] Consultar paciente inexistente" -ForegroundColor Cyan
Write-Host "     esperado: 404" -ForegroundColor DarkGray
curl.exe -s -i "$base/pacientes/999"
Write-Host ""
Write-Host ""
Write-Host "[14] Fila em HTML (abra tambem no navegador)" -ForegroundColor Cyan
Write-Host "     esperado: 200, ordem: Maria, Carlos, Joao, Ana, Pedro" -ForegroundColor DarkGray
curl.exe -s -i "$base/fila"
Write-Host ""
Write-Host ""
Write-Host "[15] ERRO 409: finalizar paciente EM_FILA" -ForegroundColor Cyan
Write-Host "     esperado: 409" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/pacientes/1/finalizar" -H "Content-Type: application/json" --data-binary "@$j\prognostico.json" -H "Authorization: $chave"
Write-Host ""
Write-Host ""
Write-Host "[16] Chamar proximo (Maria)" -ForegroundColor Cyan
Write-Host "     esperado: 200, EM_ATENDIMENTO" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/chamar" -H "Authorization: $chave"
Write-Host ""
Write-Host ""
Write-Host "[17] Chamar proximo (Carlos)" -ForegroundColor Cyan
Write-Host "     esperado: 200, EM_ATENDIMENTO" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/chamar" -H "Authorization: $chave"
Write-Host ""
Write-Host ""
Write-Host "[18] ERRO 400: finalizar com prognostico de tipo errado" -ForegroundColor Cyan
Write-Host "     esperado: 400" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/pacientes/1/finalizar" -H "Content-Type: application/json" --data-binary "@$j\prognostico_invalido.json" -H "Authorization: $chave"
Write-Host ""
Write-Host ""
Write-Host "[19] Finalizar Maria" -ForegroundColor Cyan
Write-Host "     esperado: 200, ATENDIDO" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/pacientes/1/finalizar" -H "Content-Type: application/json" --data-binary "@$j\prognostico.json" -H "Authorization: $chave"
Write-Host ""
Write-Host ""
Write-Host "[20] ERRO 409: finalizar Maria de novo (ATENDIDO e terminal)" -ForegroundColor Cyan
Write-Host "     esperado: 409" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/pacientes/1/finalizar" -H "Content-Type: application/json" --data-binary "@$j\prognostico.json" -H "Authorization: $chave"
Write-Host ""
Write-Host ""
Write-Host "[21] Consultar Maria (ATENDIDO com prognostico)" -ForegroundColor Cyan
Write-Host "     esperado: 200, ATENDIDO" -ForegroundColor DarkGray
curl.exe -s -i "$base/pacientes/1"
Write-Host ""
Write-Host ""
Write-Host "[22] Estatisticas" -ForegroundColor Cyan
Write-Host "     esperado: total 5; EM_FILA 3, EM_ATENDIMENTO 1, ATENDIDO 1" -ForegroundColor DarkGray
curl.exe -s -i "$base/estatisticas"
Write-Host ""
Write-Host ""
Write-Host "[23] Rota inexistente" -ForegroundColor Cyan
Write-Host "     esperado: 404" -ForegroundColor DarkGray
curl.exe -s -i "$base/xyz"
Write-Host ""
Write-Host ""
Write-Host "[24] Metodo nao permitido (GET em /pacientes)" -ForegroundColor Cyan
Write-Host "     esperado: 405, Allow: POST" -ForegroundColor DarkGray
curl.exe -s -i "$base/pacientes"
Write-Host ""
Write-Host ""
Write-Host "[25] Metodo nao permitido (POST em /fila)" -ForegroundColor Cyan
Write-Host "     esperado: 405, Allow: GET" -ForegroundColor DarkGray
curl.exe -s -i -X POST "$base/fila" -H "Authorization: $chave"
Write-Host ""
Write-Host ""
Write-Host "[26] Metodo nao permitido (DELETE em /pacientes/1)" -ForegroundColor Cyan
Write-Host "     esperado: 405, Allow: GET" -ForegroundColor DarkGray
curl.exe -s -i -X DELETE "$base/pacientes/1"
Write-Host ""

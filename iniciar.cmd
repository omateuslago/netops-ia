@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Ambiente Python nao encontrado em .venv. Confira a instalacao do projeto.
    pause
    exit /b 1
)
rem Perfil do laboratorio v2 usado nas consultas atuais.
set "NETOPS_TOKEN_PIPELINE=pdf-token-v2"
set "NETOPS_DATA_DIR=data/token-v2-lab"
set "NETOPS_KNOWLEDGE_DIR=knowledge/token-v2-lab"
echo NetOps AI - laboratorio v2
echo Interface: http://127.0.0.1:8000/app
echo Para encerrar, pressione Ctrl+C. Mantenha apenas um servidor aberto.
echo Lembrete: depois, siga docs\extractive-answer.md para preparar o Ollama.
".venv\Scripts\python.exe" -m uvicorn netops_ai.main:app --host 127.0.0.1 --reload
if errorlevel 1 pause
endlocal

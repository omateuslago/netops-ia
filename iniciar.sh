#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ ! -x .venv/bin/python ]]; then
    echo 'Ambiente Python Linux não encontrado em .venv. Consulte docs/ubuntu-ollama.md.' >&2
    exit 1
fi

# Mesmo laboratório separado usado por iniciar.cmd; não migra a base padrão v1.
export NETOPS_TOKEN_PIPELINE=pdf-token-v2
export NETOPS_DATA_DIR=data/token-v2-lab
export NETOPS_KNOWLEDGE_DIR=knowledge/token-v2-lab

echo 'NetOps AI - laboratório v2'
echo 'Interface: http://127.0.0.1:8000/app'
echo 'Para encerrar, pressione Ctrl+C. Mantenha apenas um servidor por base.'
echo 'O modelo do Ollama pode ser configurado em .env. Consulte docs/ubuntu-ollama.md.'
exec .venv/bin/python -m uvicorn netops_ai.main:app --host 127.0.0.1 --reload

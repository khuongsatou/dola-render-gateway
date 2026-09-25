#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

if [ -f ".env.local" ]; then
    set -a
    source .env.local
    set +a
fi

exec uvicorn server:app --host "${DOLA_HOST:-127.0.0.1}" --port "${DOLA_PORT:-8000}"

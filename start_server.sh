#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

exec uvicorn server:app --host "${DOLA_HOST:-0.0.0.0}" --port "${DOLA_PORT:-8000}"

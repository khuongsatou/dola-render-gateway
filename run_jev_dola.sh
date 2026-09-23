#!/usr/bin/env bash
# Run Jev Ultrafast automation for dola.com
cd "$(dirname "$0")/jev-ultrafast" || exit 1
uv run python examples/dola.py "$@"

#!/usr/bin/env bash
# Run Jev Ultrafast Web Inspector (http://127.0.0.1:8766)
cd "$(dirname "$0")/jev-ultrafast" || exit 1
echo "Starting Jev Inspector at http://127.0.0.1:8766..."
uv run jev

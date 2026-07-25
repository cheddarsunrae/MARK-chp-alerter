#!/usr/bin/env bash
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
fi

PYTHON="$ROOT/.venv/bin/python"
"$PYTHON" -m pip install -r "$ROOT/requirements.txt"

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

exec "$PYTHON" "$ROOT/chp_gui.py"

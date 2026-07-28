#!/usr/bin/env bash
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Run the platform installer included with MARK."
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "Creating MARK's private Python environment..."
  python3 -m venv .venv
fi

PYTHON="$ROOT/.venv/bin/python"
"$PYTHON" -m pip install --disable-pip-version-check -r "$ROOT/requirements.txt"

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

exec "$PYTHON" "$ROOT/mark_region_column_entry.py"

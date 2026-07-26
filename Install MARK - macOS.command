#!/usr/bin/env bash
set -eu

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

show_error() {
  printf '\nMARK could not be installed.\n%s\n\n' "$1"
  read -r -p "Press Return to close..." _
  exit 1
}

printf '\nMARK installer for macOS\n========================\n\n'

if ! command -v python3 >/dev/null 2>&1; then
  show_error "Python 3 was not found. Install the current Python 3 package from python.org, then run this installer again."
fi

if ! python3 - <<'PY' >/dev/null 2>&1
import tkinter
PY
then
  show_error "Python's graphical Tk component is missing. Install the current macOS Python package from python.org, then run this installer again."
fi

printf 'Creating MARK\047s private program environment...\n'
python3 -m venv .venv || show_error "Python could not create the private environment."

PYTHON="$ROOT/.venv/bin/python"
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r requirements.txt || show_error "MARK could not install its required components. Check your internet connection and try again."

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

cat > "Start MARK.command" <<'LAUNCH'
#!/usr/bin/env bash
set -eu
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
exec "$ROOT/.venv/bin/python" "$ROOT/mark_gui_entry.py"
LAUNCH
chmod +x "Start MARK.command" start-chp-alerter.sh

printf '\nInstallation complete.\n\nDouble-click "Start MARK.command" to open MARK.\n'
read -r -p "Press Return to open MARK now..." _
exec "$PYTHON" "$ROOT/mark_gui_entry.py"

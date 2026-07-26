#!/usr/bin/env bash
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

printf '\nMARK installer for Linux\n========================\n\n'

install_packages() {
  if command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-tkinter
  elif command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-venv python3-tk
  elif command -v zypper >/dev/null 2>&1; then
    sudo zypper --non-interactive install python3 python3-tk
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -S --needed python tk
  else
    echo "MARK could not identify your Linux package manager."
    echo "Install Python 3, Python venv, and Tkinter, then run start-chp-alerter.sh."
    exit 1
  fi
}

if ! command -v python3 >/dev/null 2>&1 || ! python3 - <<'PY' >/dev/null 2>&1
import tkinter
PY
then
  echo "Installing the required Linux components. Your password may be requested."
  install_packages
fi

python3 -m venv .venv
PYTHON="$ROOT/.venv/bin/python"
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

chmod +x start-chp-alerter.sh install-mark-linux.sh

APPLICATIONS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPLICATIONS_DIR"
cat > "$APPLICATIONS_DIR/mark-chp-alerter.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=MARK CHP Alerter
Comment=Map-aware CHP incident monitoring and notifications
Exec=$ROOT/start-chp-alerter.sh
Path=$ROOT
Terminal=false
Categories=Utility;Network;
EOF
chmod +x "$APPLICATIONS_DIR/mark-chp-alerter.desktop"

printf '\nInstallation complete.\nOpen "MARK CHP Alerter" from your application menu, or double-click start-chp-alerter.sh.\n\n'
read -r -p "Press Enter to open MARK now..." _
exec "$PYTHON" "$ROOT/mark_gui_entry.py"

#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

need_command() { command -v "$1" >/dev/null 2>&1; }

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This setup script is for Linux/WSL. On Windows, run scripts/setup.ps1."
  exit 1
fi

missing=()
need_command python3 || missing+=(python3 python3-venv)
need_command curl || missing+=(curl)
need_command node || missing+=(nodejs npm)
if ((${#missing[@]})); then
  if ! need_command apt-get; then
    echo "Missing required commands and apt-get is unavailable: ${missing[*]}"
    exit 1
  fi
  sudo apt-get update
  sudo apt-get install -y "${missing[@]}"
fi

PNPM=(pnpm)
if ! need_command pnpm; then
  if need_command corepack; then
    PNPM=(corepack pnpm)
  elif need_command npm; then
    echo "Installing pnpm 11.21.0 for this user..."
    npm install --prefix "$HOME/.local" pnpm@11.21.0
    PNPM=("$HOME/.local/bin/pnpm")
  else
    echo "pnpm is required. Install pnpm 11.21.0 or newer, then rerun setup."
    exit 1
  fi
fi

python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required")
PY

node - <<'NODE'
const [major, minor] = process.versions.node.split('.').map(Number);
const supported = (major === 20 && minor >= 19) || (major === 22 && minor >= 12) || major >= 24;
if (!supported) {
  throw new Error('Node.js 20.19+, 22.12+, or 24+ is required');
}
NODE

if ! need_command llama-server && ! need_command llama && [[ ! -x "$HOME/.llama-app/llama" ]]; then
  echo "Installing the official llama.cpp runtime with hardware detection..."
  setup_temp="$(mktemp -d)"
  trap 'rm -rf "$setup_temp"' EXIT
  curl --proto '=https' --tlsv1.2 -fsSL https://llama.app/install.sh -o "$setup_temp/install-llama.sh"
  sh "$setup_temp/install-llama.sh"
fi

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r backend/requirements.txt

"${PNPM[@]}" install --frozen-lockfile
"${PNPM[@]}" build

PYTHONPATH="$PROJECT_DIR" .venv/bin/python - <<'PY'
from backend.app.database import initialize_database
from backend.app.services.model_scanner import scan_models
from backend.app.services.host_profile import apply_recommendations
initialize_database()
models = scan_models()
profile, settings, applied = apply_recommendations()
gpu = profile["gpus"][0] if profile["gpus"] else None
print(f"Database initialized. {len(models)} GGUF model(s) found.")
print(f"Detected: {profile['cpu']['name']} · {profile['memory']['total_bytes'] / 2**30:.1f} GB RAM · {gpu['name'] if gpu else 'CPU inference'}")
print(f"Recommended: {settings['context_size']} context · {settings['threads']} threads · {settings['gpu_layers']} GPU layers")
PY

echo
echo "Setup complete."
echo "1. Put a .gguf model in: $PROJECT_DIR/models"
echo "2. Run: $PROJECT_DIR/run.sh"
echo "3. Open: http://127.0.0.1:8181"

if [[ "$(ps -p 1 -o comm=)" == "systemd" ]] && systemctl --user show-environment >/dev/null 2>&1; then
  echo
  echo "Installing the per-user systemd service for automatic startup..."
  "$PROJECT_DIR/scripts/service.sh" install
else
  echo "systemd user services are unavailable; use $PROJECT_DIR/run.sh to start the app."
fi

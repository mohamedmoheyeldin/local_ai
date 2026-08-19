#!/usr/bin/env bash
set -euo pipefail

PAYLOAD_DIR=${PORTABLE_LOCAL_AI_PAYLOAD:?Installer payload is missing}
VERSION=$(<"$PAYLOAD_DIR/VERSION")
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.-]+)?$ ]]; then
  printf 'Installer version is invalid.\n' >&2
  exit 12
fi
BASE_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/portable-local-ai/app"
VERSION_DIR="$BASE_DIR/$VERSION"
CURRENT_LINK="$BASE_DIR/current"
BIN_DIR="$HOME/.local/bin"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/portable-local-ai"
MODELS_DIR="$HOME/PortableLocalAI/models"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNIT_NAME="portable-local-ai.service"

log() { printf '\n[%s] %s\n' "$1" "$2"; }

uninstall() {
  log "1/3" "Stopping the application"
  systemctl --user disable --now "$UNIT_NAME" >/dev/null 2>&1 || true
  if [[ -r "$DATA_DIR/runtime/application.pid" ]]; then
    pid=$(<"$DATA_DIR/runtime/application.pid")
    if [[ "$pid" =~ ^[0-9]+$ ]]; then kill "$pid" >/dev/null 2>&1 || true; fi
    rm -f "$DATA_DIR/runtime/application.pid"
  fi
  rm -f "$UNIT_DIR/$UNIT_NAME" "$BIN_DIR/portable-local-ai" "$BIN_DIR/portable-local-ai-start"
  systemctl --user daemon-reload >/dev/null 2>&1 || true
  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$(wslpath -w "$PAYLOAD_DIR/register-startup.ps1")" -Action Uninstall >/dev/null 2>&1 || true
  fi
  log "2/3" "Removing application files"
  if [[ -d "$BASE_DIR" ]]; then rm -rf -- "$BASE_DIR"; fi
  log "3/3" "Finished"
  printf 'Portable Local AI was removed. Models and private data were preserved in:\n  %s\n  %s\n' "$MODELS_DIR" "$DATA_DIR"
}

if [[ "${1:-}" == "--uninstall" ]]; then uninstall; exit 0; fi
if [[ "${PORTABLE_LOCAL_AI_TEST_MODE:-0}" != "1" ]] && { [[ "$(uname -s)" != "Linux" ]] || ! grep -qi microsoft /proc/sys/kernel/osrelease 2>/dev/null; }; then
  printf 'This installer is for Windows Subsystem for Linux. Use the Windows installer for native Windows.\n' >&2
  exit 2
fi

log "1/7" "Checking this WSL computer"
architecture=$(uname -m)
if [[ "$architecture" != "x86_64" ]]; then
  printf 'This release supports x86-64 WSL. Detected: %s\n' "$architecture" >&2
  exit 2
fi
available_kb=$(df -Pk "$HOME" | awk 'NR==2 {print $4}')
required_kb=$(du -sk "$PAYLOAD_DIR/app" | awk '{print $1}')
if (( available_kb < required_kb * 2 )); then
  printf 'Not enough free disk space to install safely.\n' >&2
  exit 3
fi

log "2/7" "Installing the self-contained application"
mkdir -p "$BASE_DIR" "$BIN_DIR" "$DATA_DIR/runtime/logs" "$MODELS_DIR"
chmod 700 "$DATA_DIR" "$DATA_DIR/runtime" "$DATA_DIR/runtime/logs" "$MODELS_DIR"
temporary="$BASE_DIR/.install-$VERSION-$$"
trap 'rm -rf -- "$temporary"' EXIT
rm -rf -- "$temporary"
mkdir -p "$temporary"
cp -a "$PAYLOAD_DIR/app/." "$temporary/"
chmod +x "$temporary/portable-local-ai"
rm -rf -- "$VERSION_DIR"
mv "$temporary" "$VERSION_DIR"
ln -sfn "$VERSION_DIR" "$CURRENT_LINK"
ln -sfn "$CURRENT_LINK/portable-local-ai" "$BIN_DIR/portable-local-ai"

log "3/7" "Selecting the local model runtime"
runtime=""
if command -v llama-server >/dev/null 2>&1; then runtime=$(command -v llama-server); fi
if [[ -z "$runtime" ]] && command -v llama >/dev/null 2>&1; then runtime=$(command -v llama); fi
if [[ -z "$runtime" ]]; then
  runtime=$(find "$CURRENT_LINK/_internal/runtime" -type f -name llama-server -print -quit)
fi
if [[ -z "$runtime" || ! -x "$runtime" ]]; then
  printf 'The bundled llama.cpp runtime is missing. Installation cannot continue.\n' >&2
  exit 4
fi
"$CURRENT_LINK/portable-local-ai" --configure-runtime "$runtime" >"$DATA_DIR/install-result.json"
chmod 600 "$DATA_DIR/install-result.json"

log "4/7" "Creating the operating-system service"
systemd_available=false
if [[ "${PORTABLE_LOCAL_AI_TEST_MODE:-0}" != "1" ]] && command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; then
  systemd_available=true
  mkdir -p "$UNIT_DIR"
  sed "s|__EXECUTABLE__|$CURRENT_LINK/portable-local-ai|g" "$PAYLOAD_DIR/portable-local-ai.service.in" >"$UNIT_DIR/$UNIT_NAME"
  chmod 600 "$UNIT_DIR/$UNIT_NAME"
  systemctl --user daemon-reload
  systemctl --user enable --now "$UNIT_NAME"
else
  cat >"$BIN_DIR/portable-local-ai-start" <<EOF
#!/usr/bin/env bash
if "$CURRENT_LINK/portable-local-ai" --health-check >/dev/null 2>&1; then exit 0; fi
nohup "$CURRENT_LINK/portable-local-ai" --no-browser >>"$DATA_DIR/runtime/logs/application.log" 2>&1 </dev/null &
echo \$! >"$DATA_DIR/runtime/application.pid"
EOF
  chmod 700 "$BIN_DIR/portable-local-ai-start"
  "$BIN_DIR/portable-local-ai-start"
fi

log "5/7" "Connecting startup to Windows sign-in"
if [[ "${PORTABLE_LOCAL_AI_TEST_MODE:-0}" != "1" ]] && command -v powershell.exe >/dev/null 2>&1; then
  distro=${WSL_DISTRO_NAME:-}
  script_windows=$(wslpath -w "$PAYLOAD_DIR/register-startup.ps1")
  if $systemd_available; then
    powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$script_windows" -Action Install -Distro "$distro" -Mode Systemd >/dev/null
  else
    powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$script_windows" -Action Install -Distro "$distro" -Mode Direct -LinuxCommand "$BIN_DIR/portable-local-ai-start" >/dev/null
  fi
fi

log "6/7" "Verifying the installation"
healthy=false
for _ in {1..30}; do
  if "$CURRENT_LINK/portable-local-ai" --health-check >/dev/null 2>&1; then healthy=true; break; fi
  sleep 1
done
if ! $healthy; then
  printf 'The application was installed but did not become healthy. Review %s/runtime/logs.\n' "$DATA_DIR" >&2
  exit 5
fi

log "7/7" "Installation complete"
printf 'Application: http://127.0.0.1:8181\nModels:      %s\nData:        %s\n\nOnly a GGUF model is still required. Add it in Settings or copy it into the model folder above.\n' "$MODELS_DIR" "$DATA_DIR"
if [[ "${PORTABLE_LOCAL_AI_TEST_MODE:-0}" != "1" ]] && command -v powershell.exe >/dev/null 2>&1; then
  powershell.exe -NoLogo -NoProfile -NonInteractive -Command "Start-Process 'http://127.0.0.1:8181'" >/dev/null 2>&1 || true
fi

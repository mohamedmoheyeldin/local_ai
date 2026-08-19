#!/usr/bin/env bash
set -euo pipefail

PAYLOAD_DIR=${LOCAL_AI_PAYLOAD:?Installer payload is missing}
VERSION=$(<"$PAYLOAD_DIR/VERSION")
TEST_MODE=${LOCAL_AI_INSTALLER_TEST_MODE:-0}
TEST_ROOT=${LOCAL_AI_INSTALLER_TEST_ROOT:-}
APP_PORT=${LOCAL_AI_PORT:-8181}

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.-]+)?$ ]]; then
  printf 'Installer version is invalid.\n' >&2
  exit 12
fi

if [[ "$TEST_MODE" != "1" && $EUID -ne 0 ]]; then
  export LOCAL_AI_INSTALL_USER=${LOCAL_AI_INSTALL_USER:-$(id -un)}
  exec sudo --preserve-env=LOCAL_AI_PAYLOAD,LOCAL_AI_INSTALL_USER bash "$0" "$@"
fi

if [[ "$TEST_MODE" == "1" ]]; then
  [[ -n "$TEST_ROOT" ]] || { printf 'Test root is required in installer test mode.\n' >&2; exit 13; }
  APP_ROOT="$TEST_ROOT/opt/local-ai"
  BIN_PATH="$TEST_ROOT/usr/local/bin/local-ai"
  DATA_DIR="$TEST_ROOT/var/lib/local-ai"
  UNIT_PATH="$TEST_ROOT/etc/systemd/system/local-ai.service"
  SERVICE_USER=$(id -un)
  SERVICE_GROUP=$(id -gn)
else
  APP_ROOT=/opt/local-ai
  BIN_PATH=/usr/local/bin/local-ai
  DATA_DIR=/var/lib/local-ai
  UNIT_PATH=/etc/systemd/system/local-ai.service
  SERVICE_USER=${LOCAL_AI_INSTALL_USER:-${SUDO_USER:-}}
  [[ -n "$SERVICE_USER" && "$SERVICE_USER" != "root" ]] || {
    printf 'Run this installer from your normal WSL account; it will request sudo for the system installation.\n' >&2
    exit 14
  }
  SERVICE_GROUP=$(id -gn "$SERVICE_USER")
fi

VERSION_DIR="$APP_ROOT/versions/$VERSION"
CURRENT_LINK="$APP_ROOT/current"
MODELS_DIR="$DATA_DIR/models"
UNIT_NAME=local-ai.service

log() { printf '\n[%s] %s\n' "$1" "$2"; }

uninstall() {
  log "1/3" "Stopping the Local AI system service"
  if [[ "$TEST_MODE" == "1" ]]; then
    if [[ -r "$DATA_DIR/runtime/application.pid" ]]; then
      pid=$(<"$DATA_DIR/runtime/application.pid")
      [[ "$pid" =~ ^[0-9]+$ ]] && kill "$pid" >/dev/null 2>&1 || true
      rm -f "$DATA_DIR/runtime/application.pid"
    fi
  else
    systemctl disable --now "$UNIT_NAME" >/dev/null 2>&1 || true
  fi
  rm -f "$UNIT_PATH" "$BIN_PATH"
  [[ "$TEST_MODE" == "1" ]] || systemctl daemon-reload >/dev/null 2>&1 || true
  if [[ "$TEST_MODE" != "1" ]] && command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$(wslpath -w "$PAYLOAD_DIR/register-startup.ps1")" -Action Uninstall >/dev/null 2>&1 || true
  fi
  log "2/3" "Removing installed application files"
  [[ -d "$APP_ROOT" ]] && rm -rf -- "$APP_ROOT"
  log "3/3" "Uninstall complete"
  printf 'Local AI was removed. Models and private data were preserved in %s.\n' "$DATA_DIR"
}

if [[ "${1:-}" == "--uninstall" ]]; then uninstall; exit 0; fi
if [[ "$TEST_MODE" != "1" ]] && { [[ "$(uname -s)" != "Linux" ]] || ! grep -qi microsoft /proc/sys/kernel/osrelease 2>/dev/null; }; then
  printf 'This installer is for Windows Subsystem for Linux. Use the Windows installer for native Windows.\n' >&2
  exit 2
fi

log "1/7" "Checking the WSL system"
architecture=$(uname -m)
[[ "$architecture" == "x86_64" ]] || { printf 'This release supports x86-64 WSL. Detected: %s\n' "$architecture" >&2; exit 2; }
if [[ "$TEST_MODE" != "1" ]]; then
  command -v systemctl >/dev/null 2>&1 || { printf 'systemd is required for the Local AI system service. Enable systemd in WSL and retry.\n' >&2; exit 3; }
  [[ "$(ps -p 1 -o comm=)" == "systemd" ]] || { printf 'WSL systemd is not active. Enable it in /etc/wsl.conf, restart WSL, and retry.\n' >&2; exit 3; }
fi
available_kb=$(df -Pk "${TEST_ROOT:-/opt}" | awk 'NR==2 {print $4}')
required_kb=$(du -sk "$PAYLOAD_DIR/app" | awk '{print $1}')
(( available_kb >= required_kb * 2 )) || { printf 'Not enough free disk space to install safely.\n' >&2; exit 4; }

log "2/7" "Installing application files under $APP_ROOT"
install -d -m 755 "$APP_ROOT/versions" "$(dirname "$BIN_PATH")" "$(dirname "$UNIT_PATH")"
install -d -m 700 -o "$SERVICE_USER" -g "$SERVICE_GROUP" "$DATA_DIR" "$DATA_DIR/runtime" "$DATA_DIR/runtime/logs" "$MODELS_DIR"
temporary="$APP_ROOT/versions/.install-$VERSION-$$"
trap 'rm -rf -- "$temporary"' EXIT
rm -rf -- "$temporary"
mkdir -p "$temporary"
cp -a "$PAYLOAD_DIR/app/." "$temporary/"
chmod +x "$temporary/local-ai"
if [[ "$TEST_MODE" != "1" ]]; then chown -R root:root "$temporary"; fi
rm -rf -- "$VERSION_DIR"
mv "$temporary" "$VERSION_DIR"
ln -sfn "$VERSION_DIR" "$CURRENT_LINK"
ln -sfn "$CURRENT_LINK/local-ai" "$BIN_PATH"

log "3/7" "Selecting the local model runtime"
runtime=""
command -v llama-server >/dev/null 2>&1 && runtime=$(command -v llama-server)
[[ -n "$runtime" ]] || runtime=$(find "$CURRENT_LINK/_internal/runtime" -type f -name llama-server -print -quit)
[[ -n "$runtime" && -x "$runtime" ]] || { printf 'The bundled llama.cpp runtime is missing.\n' >&2; exit 5; }
run_as_user() {
  if [[ "$TEST_MODE" == "1" ]]; then "$@"; else runuser -u "$SERVICE_USER" -- "$@"; fi
}
run_as_user env LOCAL_AI_DATA_DIR="$DATA_DIR" LOCAL_AI_MODELS_DIR="$MODELS_DIR" "$CURRENT_LINK/local-ai" --configure-runtime "$runtime" >"$DATA_DIR/install-result.json"
chmod 600 "$DATA_DIR/install-result.json"
chown "$SERVICE_USER:$SERVICE_GROUP" "$DATA_DIR/install-result.json"

log "4/7" "Installing the operating-system service"
if [[ "$TEST_MODE" == "1" ]]; then
  sed -e "s|__EXECUTABLE__|$CURRENT_LINK/local-ai|g" -e "s|__USER__|$SERVICE_USER|g" -e "s|__GROUP__|$SERVICE_GROUP|g" -e "s|__DATA_DIR__|$DATA_DIR|g" -e "s|__MODELS_DIR__|$MODELS_DIR|g" "$PAYLOAD_DIR/local-ai.service.in" >"$UNIT_PATH"
  nohup env LOCAL_AI_DATA_DIR="$DATA_DIR" LOCAL_AI_MODELS_DIR="$MODELS_DIR" "$CURRENT_LINK/local-ai" --no-browser >>"$DATA_DIR/runtime/logs/application.log" 2>&1 </dev/null &
  echo $! >"$DATA_DIR/runtime/application.pid"
else
  sed -e "s|__EXECUTABLE__|$CURRENT_LINK/local-ai|g" -e "s|__USER__|$SERVICE_USER|g" -e "s|__GROUP__|$SERVICE_GROUP|g" -e "s|__DATA_DIR__|$DATA_DIR|g" -e "s|__MODELS_DIR__|$MODELS_DIR|g" "$PAYLOAD_DIR/local-ai.service.in" >"$UNIT_PATH"
  chmod 644 "$UNIT_PATH"
  systemctl daemon-reload
  systemctl enable --now "$UNIT_NAME"
fi

log "5/7" "Connecting WSL startup to Windows sign-in"
if [[ "$TEST_MODE" != "1" ]] && command -v powershell.exe >/dev/null 2>&1; then
  script_windows=$(wslpath -w "$PAYLOAD_DIR/register-startup.ps1")
  powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$script_windows" -Action Install -Distro "${WSL_DISTRO_NAME:-}" >/dev/null
fi

log "6/7" "Verifying the installed service"
healthy=false
for _ in {1..30}; do
  if env LOCAL_AI_DATA_DIR="$DATA_DIR" LOCAL_AI_MODELS_DIR="$MODELS_DIR" "$CURRENT_LINK/local-ai" --health-check >/dev/null 2>&1; then healthy=true; break; fi
  sleep 1
done
$healthy || { printf 'Local AI was installed but did not become healthy. Review %s/runtime/logs.\n' "$DATA_DIR" >&2; exit 6; }

log "7/7" "Installation complete"
printf 'Application: %s\nService:     %s\nModels:      %s\nData:        %s\nURL:         http://127.0.0.1:%s\n\nOnly a licensed GGUF model is still required.\n' "$APP_ROOT" "$UNIT_PATH" "$MODELS_DIR" "$DATA_DIR" "$APP_PORT"
if [[ "$TEST_MODE" != "1" ]] && command -v powershell.exe >/dev/null 2>&1; then
  powershell.exe -NoLogo -NoProfile -NonInteractive -Command "Start-Process 'http://127.0.0.1:$APP_PORT'" >/dev/null 2>&1 || true
fi

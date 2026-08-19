#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
APP_UNIT="portable-local-ai.service"
STACK_TARGET="local-ai-stack.target"
OPTIONAL_UNITS=(llama-server.service embedding-server.service project-indexer.service semantic-index.timer)

installed_optional_units() {
  local unit
  for unit in "${OPTIONAL_UNITS[@]}"; do
    if systemctl --user list-unit-files "$unit" --no-legend 2>/dev/null | grep -q "^$unit"; then
      printf '%s\n' "$unit"
    fi
  done
}

resolved_app_url() {
  if [[ -n "${LOCAL_AI_PORT:-}" ]]; then
    printf 'http://127.0.0.1:%s' "$LOCAL_AI_PORT"
  elif [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
    PYTHONPATH="$PROJECT_DIR" "$PROJECT_DIR/.venv/bin/python" -c 'from backend.app.database import get_settings; print("http://127.0.0.1:{}".format(get_settings()["app_port"]))'
  else
    printf 'http://127.0.0.1:8181'
  fi
}

require_systemd() {
  if [[ "$(ps -p 1 -o comm=)" != "systemd" ]] || ! command -v systemctl >/dev/null 2>&1; then
    echo "systemd is not active. In WSL, add systemd=true under [boot] in /etc/wsl.conf, then restart WSL."
    exit 1
  fi
}

install_units() {
  if [[ ! -x "$PROJECT_DIR/.venv/bin/python" || ! -r "$PROJECT_DIR/frontend/dist/index.html" ]]; then
    echo "Project setup is incomplete. Run $PROJECT_DIR/scripts/setup.sh first."
    exit 1
  fi
  mkdir -p "$USER_UNIT_DIR"
  escaped_project=${PROJECT_DIR//&/\\&}
  sed "s&__PROJECT_DIR__&$escaped_project&g" \
    "$PROJECT_DIR/deploy/systemd/portable-local-ai.service.in" >"$USER_UNIT_DIR/$APP_UNIT"
  sed "s&__PROJECT_DIR__&$escaped_project&g" \
    "$PROJECT_DIR/deploy/systemd/local-ai-stack.target.in" >"$USER_UNIT_DIR/$STACK_TARGET"
  dropin_dir="$USER_UNIT_DIR/$STACK_TARGET.d"
  mkdir -p "$dropin_dir"
  mapfile -t optional_units < <(installed_optional_units)
  if ((${#optional_units[@]})); then
    {
      echo '[Unit]'
      printf 'Wants=%s\n' "${optional_units[*]}"
      printf 'After=%s\n' "${optional_units[*]}"
    } >"$dropin_dir/10-detected-services.conf"
    chmod 600 "$dropin_dir/10-detected-services.conf"
    echo "Detected optional local services: ${optional_units[*]}"
  else
    rm -f "$dropin_dir/10-detected-services.conf"
    echo "No separate model or indexing services detected; the application will manage its own runtime."
  fi
  chmod 600 "$USER_UNIT_DIR/$APP_UNIT" "$USER_UNIT_DIR/$STACK_TARGET"
  systemctl --user daemon-reload
  systemctl --user enable "$APP_UNIT" "$STACK_TARGET"
  echo "Installed and enabled $APP_UNIT and $STACK_TARGET."
}

show_status() {
  mapfile -t optional_units < <(installed_optional_units)
  systemctl --user --no-pager --full status "$STACK_TARGET" "$APP_UNIT" "${optional_units[@]}" 2>&1 || true
  echo
  app_url="$(resolved_app_url)"
  if health="$(curl --max-time 3 --silent --show-error --fail "$app_url/api/health")"; then
    printf 'Application health: '
    printf '%s' "$health"
    echo
  else
    echo "Application health: unavailable at $app_url"
  fi
}

require_systemd
action="${1:-status}"
case "$action" in
  install)
    install_units
    systemctl --user start "$STACK_TARGET"
    ;;
  start)
    systemctl --user start "$STACK_TARGET"
    ;;
  restart)
    systemctl --user restart "$APP_UNIT"
    systemctl --user start "$STACK_TARGET"
    ;;
  stop)
    systemctl --user stop "$APP_UNIT"
    ;;
  stop-all)
    mapfile -t optional_units < <(installed_optional_units)
    systemctl --user stop "$APP_UNIT" "${optional_units[@]}"
    ;;
  status)
    show_status
    ;;
  logs)
    mapfile -t optional_units < <(installed_optional_units)
    journal_args=(-u "$APP_UNIT")
    for unit in "${optional_units[@]}"; do journal_args+=(-u "$unit"); done
    exec journalctl --user "${journal_args[@]}" --no-pager -n "${2:-200}"
    ;;
  uninstall)
    systemctl --user disable --now "$APP_UNIT" "$STACK_TARGET" 2>/dev/null || true
    rm -f "$USER_UNIT_DIR/$APP_UNIT" "$USER_UNIT_DIR/$STACK_TARGET"
    rm -rf "$USER_UNIT_DIR/$STACK_TARGET.d"
    systemctl --user daemon-reload
    echo "Removed Portable Local AI service units. Existing model and indexing services were preserved."
    ;;
  *)
    echo "Usage: $0 {install|start|restart|stop|stop-all|status|logs [lines]|uninstall}"
    exit 2
    ;;
esac

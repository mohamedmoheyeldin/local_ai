#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [[ ! -x .venv/bin/python || ! -f frontend/dist/index.html ]]; then
  echo "Setup is incomplete. Run: $PROJECT_DIR/scripts/setup.sh"
  exit 1
fi

export PYTHONPATH="$PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}"
exec .venv/bin/python -m backend.app.run

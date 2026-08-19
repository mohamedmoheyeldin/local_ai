from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SOURCE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(os.environ.get("LOCAL_AI_INSTALL_ROOT", SOURCE_ROOT)).resolve()
CONFIG_PATH = PROJECT_ROOT / "config" / "default.json"
DATA_DIR = Path(os.environ.get("LOCAL_AI_DATA_DIR", PROJECT_ROOT / "data")).resolve()
CONTEXT_DIR = DATA_DIR / "context"
MODELS_DIR = Path(os.environ.get("LOCAL_AI_MODELS_DIR", PROJECT_ROOT / "models")).resolve()
FRONTEND_DIR = PROJECT_ROOT / "frontend" / "dist"
DATABASE_PATH = Path(os.environ.get("LOCAL_AI_DATABASE", DATA_DIR / "local-ai.db")).resolve()
WORKSPACES_ROOT = Path(os.environ.get("LOCAL_AI_WORKSPACES_ROOT", Path.home())).resolve()
ENV_SETTING_MAP = {
    "app_host": "LOCAL_AI_HOST",
    "app_port": "LOCAL_AI_PORT",
    "model_host": "LOCAL_AI_MODEL_HOST",
    "model_port": "LOCAL_AI_MODEL_PORT",
    "llama_executable": "LOCAL_AI_LLAMA_EXECUTABLE",
}


def environment_setting_overrides() -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, env_name in ENV_SETTING_MAP.items():
        value = os.environ.get(env_name)
        if value is not None and value.strip():
            values[key] = int(value) if key.endswith("_port") else value.strip()
    return values


def load_defaults() -> dict[str, Any]:
    values = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    values.update(environment_setting_overrides())
    return values


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "runtime" / "logs").mkdir(parents=True, exist_ok=True)
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    for path in (DATA_DIR, CONTEXT_DIR):
        try:
            path.chmod(0o700)
        except OSError:
            pass

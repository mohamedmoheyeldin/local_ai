from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ..config import MODELS_DIR, ensure_directories
from ..database import replace_models


def safe_model_path(relative_path: str) -> Path:
    candidate = (MODELS_DIR / relative_path).resolve()
    try:
        candidate.relative_to(MODELS_DIR)
    except ValueError as exc:
        raise ValueError("Model must be inside the models directory") from exc
    if candidate.suffix.casefold() != ".gguf" or not candidate.is_file():
        raise ValueError("Selected GGUF model does not exist")
    return candidate


def scan_models() -> list[dict[str, Any]]:
    ensure_directories()
    models: list[dict[str, Any]] = []
    for path in sorted(MODELS_DIR.rglob("*.gguf"), key=lambda item: item.name.casefold()):
        if path.is_symlink() or not path.is_file():
            continue
        relative_path = path.relative_to(MODELS_DIR).as_posix()
        stat = path.stat()
        models.append(
            {
                "id": hashlib.sha256(relative_path.encode()).hexdigest()[:20],
                "relative_path": relative_path,
                "name": path.stem,
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
            }
        )
    replace_models(models)
    return models

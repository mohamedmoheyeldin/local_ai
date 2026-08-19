from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


def _configure_installed_paths() -> None:
    install_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2])).resolve()
    os.environ.setdefault("LOCAL_AI_INSTALL_ROOT", str(install_root))
    if not getattr(sys, "frozen", False) and os.environ.get("LOCAL_AI_PACKAGED") != "1":
        return
    if platform.system() == "Windows":
        data_root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "PortableLocalAI"
        models_root = Path.home() / "Documents" / "Portable Local AI" / "Models"
    else:
        data_root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "portable-local-ai"
        models_root = Path.home() / "PortableLocalAI" / "models"
    os.environ.setdefault("LOCAL_AI_DATA_DIR", str(data_root))
    os.environ.setdefault("LOCAL_AI_MODELS_DIR", str(models_root))


def _open_when_ready(url: str) -> None:
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=1) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.5)


def _healthy(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/api/health", timeout=2) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def _initialize(runtime: str = "") -> dict:
    from backend.app.config import DATA_DIR, MODELS_DIR
    from backend.app.database import get_settings, initialize_database, update_settings
    from backend.app.services.host_profile import apply_recommendations
    from backend.app.services.model_scanner import scan_models

    initialize_database()
    if runtime:
        executable = Path(runtime).expanduser().resolve()
        if not executable.is_file():
            raise SystemExit(f"llama.cpp runtime was not found: {executable}")
        update_settings({"llama_executable": str(executable)})
    models = scan_models()
    profile, settings, _ = apply_recommendations()
    return {
        "initialized": True,
        "models_found": len(models),
        "data_directory": str(DATA_DIR),
        "models_directory": str(MODELS_DIR),
        "runtime": get_settings().get("llama_executable") or "auto-detect",
        "host": profile["platform"],
        "recommended": {key: settings[key] for key in ("context_size", "threads", "gpu_layers", "parallel")},
    }


def main() -> None:
    _configure_installed_paths()
    parser = argparse.ArgumentParser(prog="portable-local-ai")
    parser.add_argument("--initialize", action="store_true", help="Initialize local data and host recommendations, then exit")
    parser.add_argument("--configure-runtime", default="", metavar="PATH", help="Save a llama.cpp executable and initialize, then exit")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the web UI automatically")
    parser.add_argument("--health-check", action="store_true", help="Exit successfully only when the local application is healthy")
    args = parser.parse_args()
    if args.initialize or args.configure_runtime:
        print(json.dumps(_initialize(args.configure_runtime), ensure_ascii=False))
        return

    from backend.app.database import get_settings, initialize_database
    from backend.app.run import main as run

    initialize_database()
    settings = get_settings()
    url = f"http://127.0.0.1:{int(settings['app_port'])}"
    if args.health_check:
        raise SystemExit(0 if _healthy(url) else 1)
    if _healthy(url):
        if not args.no_browser:
            webbrowser.open(url)
        return
    if not args.no_browser:
        threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()
    run()


if __name__ == "__main__":
    main()

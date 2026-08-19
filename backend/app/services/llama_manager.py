from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ..config import DATA_DIR, PROJECT_ROOT
from .model_scanner import safe_model_path


class LlamaManager:
    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._log_handle = None
        self._lock = threading.Lock()
        self._status_lock = threading.Lock()
        self._started_at: float | None = None
        self._command: list[str] = []
        self._status_cache_key: tuple[Any, ...] | None = None
        self._status_cache_until = 0.0
        self._status_cache: dict[str, Any] | None = None

    @staticmethod
    def find_executable(configured: str = "") -> tuple[Path, bool]:
        candidates: list[Path] = []
        if configured:
            candidates.append(Path(configured).expanduser())
        for name in ("llama-server", "llama-server.exe", "llama", "llama.exe"):
            found = shutil.which(name)
            if found:
                candidates.append(Path(found))
        home = Path.home()
        candidates.extend(
            [
                home / ".llama-app" / "llama",
                home / ".llama-app" / "llama.exe",
                home / "ai" / "src" / "llama.cpp" / "build" / "bin" / "llama-server",
                home / "llama.cpp" / "build" / "bin" / "llama-server",
                DATA_DIR / "runtime" / "llama-server",
                DATA_DIR / "runtime" / "llama-server.exe",
                PROJECT_ROOT / "runtime" / "llama-server",
                PROJECT_ROOT / "runtime" / "llama-server.exe",
                PROJECT_ROOT / "runtime" / "cpu" / "llama-server",
                PROJECT_ROOT / "runtime" / "cpu" / "llama-server.exe",
            ]
        )
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved.is_file() and os.access(resolved, os.X_OK):
                return resolved, resolved.stem.casefold() == "llama"
        raise FileNotFoundError("llama.cpp is not installed. Run the setup script first.")

    @staticmethod
    def discover_local_ports() -> list[int]:
        """Find ports from local llama.cpp process command lines without scanning the network."""
        command_lines: list[str] = []
        if Path("/proc").is_dir():
            for command_path in Path("/proc").glob("[0-9]*/cmdline"):
                try:
                    text = command_path.read_bytes().replace(b"\0", b" ").decode(errors="ignore")
                except (OSError, PermissionError):
                    continue
                lowered = text.casefold()
                embedding_only = bool(re.search(r"(?:^|\s)--?embeddings?(?:\s|$)", lowered))
                reranking_only = bool(re.search(r"(?:^|\s)--?rerank(?:ing)?(?:\s|$)", lowered))
                if not embedding_only and not reranking_only and ("llama-server" in lowered or re.search(r"\bllama(?:\.exe)?\s+serve\b", text, re.I)):
                    command_lines.append(text)
        elif os.name == "nt":
            try:
                result = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^llama'} | Select-Object -ExpandProperty CommandLine"],
                    capture_output=True, text=True, timeout=4, check=False,
                )
                command_lines.extend(result.stdout.splitlines())
            except (OSError, subprocess.TimeoutExpired):
                pass
        ports: list[int] = []
        for command in command_lines:
            match = re.search(r"(?:--port|-p)\s+(\d{2,5})\b", command)
            if match and 1_024 <= int(match.group(1)) <= 65_535:
                ports.append(int(match.group(1)))
        return list(dict.fromkeys(ports))

    @staticmethod
    def health_url(settings: dict[str, Any]) -> str:
        host = settings["model_host"]
        if host == "localhost":
            host = "127.0.0.1"
        return f"http://{host}:{settings['model_port']}/health"

    @staticmethod
    def server_healthy(settings: dict[str, Any]) -> bool:
        try:
            with urllib.request.urlopen(LlamaManager.health_url(settings), timeout=0.35) as response:
                return response.status == 200
        except (OSError, urllib.error.URLError):
            return False

    @staticmethod
    def active_settings(settings: dict[str, Any]) -> tuple[dict[str, Any], bool, bool]:
        """Prefer configured settings, then local llama.cpp processes and safe conventions."""
        if LlamaManager.server_healthy(settings):
            return settings, False, True
        if os.environ.get("LOCAL_AI_MODEL_PORT"):
            return settings, False, False
        ports = [*LlamaManager.discover_local_ports(), 8180, 8080]
        for port in dict.fromkeys(ports):
            if int(port) == int(settings.get("model_port", 8180)):
                continue
            detected = {**settings, "model_host": "127.0.0.1", "model_port": port}
            if LlamaManager.server_healthy(detected):
                return detected, True, True
        return settings, False, False

    @staticmethod
    def model_info(settings: dict[str, Any]) -> dict[str, Any] | None:
        """Describe the model reported by the configured llama.cpp server."""
        base_url = LlamaManager.health_url(settings).removesuffix("/health")
        payload: dict[str, Any] | None = None
        for endpoint in ("/props", "/v1/models"):
            try:
                with urllib.request.urlopen(f"{base_url}{endpoint}", timeout=0.5) as response:
                    payload = json.load(response)
                if payload:
                    break
            except (OSError, ValueError, urllib.error.URLError):
                continue
        if not payload:
            return None

        first_model = (payload.get("data") or [{}])[0]
        alias = str(
            payload.get("model_alias")
            or first_model.get("id")
            or first_model.get("name")
            or ""
        ).strip()
        model_path = str(payload.get("model_path") or "").strip()
        quantization = str(
            payload.get("model_ftype")
            or payload.get("meta", {}).get("ftype")
            or ""
        ).strip()
        context_size = (
            payload.get("default_generation_settings", {}).get("n_ctx")
            or payload.get("meta", {}).get("n_ctx")
        )
        source_name = Path(model_path).stem if model_path else alias.rsplit("/", 1)[-1].split(":", 1)[0]
        source_name = re.sub(r"-?GGUF$", "", source_name, flags=re.IGNORECASE)
        source_name = re.sub(r"^([A-Za-z0-9]+)_\1", r"\1", source_name, flags=re.IGNORECASE)
        if quantization:
            source_name = re.sub(
                rf"[-_ ]?{re.escape(quantization)}$", "", source_name, flags=re.IGNORECASE
            )
        display_name = source_name.replace("_", " ").strip(" -") or alias or "Local model"
        if quantization:
            display_name = f"{display_name} · {quantization}"
        return {
            "id": alias or source_name,
            "display_name": display_name,
            "quantization": quantization or None,
            "context_size": context_size,
            "file_name": Path(model_path).name if model_path else None,
        }

    def command_for(self, settings: dict[str, Any]) -> list[str]:
        model = safe_model_path(settings.get("selected_model", ""))
        executable, unified = self.find_executable(settings.get("llama_executable", ""))
        command = [str(executable)]
        if unified:
            command.append("serve")
        command.extend(
            [
                "-m", str(model),
                "--host", str(settings["model_host"]),
                "--port", str(settings["model_port"]),
                "-c", str(settings["context_size"]),
                "-np", str(settings["parallel"]),
                "-ngl", str(settings["gpu_layers"]),
                "--no-webui",
            ]
        )
        if int(settings.get("threads", 0)) > 0:
            command.extend(["-t", str(settings["threads"])])
        if int(settings.get("cache_ram_mb", 0)) > 0:
            command.extend(["--cache-ram", str(settings["cache_ram_mb"])])
        if settings.get("flash_attention", True):
            command.extend(["--flash-attn", "on"])
        return command

    def start(self, settings: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if self._process and self._process.poll() is None:
                return self.status(settings)
            if self.server_healthy(settings):
                raise RuntimeError("The configured model port is already in use by another llama.cpp server")
            command = self.command_for(settings)
            log_path = DATA_DIR / "runtime" / "logs" / "llama-server.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_handle = log_path.open("a", encoding="utf-8")
            self._log_handle.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting llama.cpp\n")
            self._log_handle.flush()
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
            self._process = subprocess.Popen(
                command,
                cwd=PROJECT_ROOT,
                stdin=subprocess.DEVNULL,
                stdout=self._log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                shell=False,
                creationflags=creationflags,
            )
            if os.name != "nt" and hasattr(os, "setpriority"):
                try:
                    os.setpriority(os.PRIO_PROCESS, self._process.pid, 5)
                except OSError:
                    pass
            self._started_at = time.time()
            self._command = command
            self._invalidate_status()
        return self.status(settings)

    def stop(self, settings: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            process = self._process
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            self._process = None
            self._started_at = None
            self._command = []
            if self._log_handle:
                self._log_handle.close()
                self._log_handle = None
            self._invalidate_status()
        return self.status(settings)

    def _invalidate_status(self) -> None:
        self._status_cache_until = 0.0
        self._status_cache = None

    def cached_status(self, settings: dict[str, Any]) -> dict[str, Any]:
        """Return liveness-safe runtime state without starting network discovery."""
        with self._status_lock:
            if self._status_cache:
                return dict(self._status_cache)
        process_pid = self._process.pid if self._process and self._process.poll() is None else None
        return {
            "state": "starting" if process_pid else "checking",
            "healthy": False,
            "managed": process_pid is not None,
            "pid": process_pid,
            "uptime_seconds": round(time.time() - self._started_at) if self._started_at else None,
            "endpoint": self.health_url(settings).removesuffix("/health"),
            "detected": False,
            "model": None,
            "command": [Path(part).name if index == 0 else part for index, part in enumerate(self._command)],
        }

    def status(self, settings: dict[str, Any]) -> dict[str, Any]:
        process_pid = self._process.pid if self._process and self._process.poll() is None else None
        cache_key = (
            settings.get("model_host"), settings.get("model_port"), settings.get("selected_model"),
            settings.get("llama_executable"), process_pid,
        )
        now = time.monotonic()
        with self._status_lock:
            if self._status_cache_key == cache_key and self._status_cache and now < self._status_cache_until:
                return dict(self._status_cache)
            process_running = process_pid is not None
            active, detected, healthy = self.active_settings(settings)
            status = {
                "state": "ready" if healthy else "starting" if process_running else "stopped",
                "healthy": healthy,
                "managed": process_running,
                "pid": process_pid,
                "uptime_seconds": round(time.time() - self._started_at) if self._started_at else None,
                "endpoint": self.health_url(active).removesuffix("/health"),
                "detected": detected,
                "model": self.model_info(active) if healthy else None,
                "command": [Path(part).name if index == 0 else part for index, part in enumerate(self._command)],
            }
            self._status_cache_key = cache_key
            self._status_cache_until = time.monotonic() + 1.0
            self._status_cache = status
            return dict(status)


manager = LlamaManager()

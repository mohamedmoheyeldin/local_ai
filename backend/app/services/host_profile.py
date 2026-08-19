from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..config import DATA_DIR, MODELS_DIR, PROJECT_ROOT

TUNING_VERSION = 1


def _run(command: list[str], timeout: float = 3) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _linux_cpu() -> tuple[str, int | None]:
    try:
        text = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return platform.processor() or "Unknown CPU", None
    name_match = re.search(r"^(?:model name|Hardware)\s*:\s*(.+)$", text, re.MULTILINE)
    pairs = set()
    physical_id = core_id = None
    for line in text.splitlines() + [""]:
        if line.startswith("physical id"):
            physical_id = line.split(":", 1)[1].strip()
        elif line.startswith("core id"):
            core_id = line.split(":", 1)[1].strip()
        elif not line.strip():
            if core_id is not None:
                pairs.add((physical_id or "0", core_id))
            physical_id = core_id = None
    return (name_match.group(1).strip() if name_match else platform.processor() or "Unknown CPU", len(pairs) or None)


def _memory_bytes() -> tuple[int, int]:
    if platform.system() == "Windows":
        try:
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                    ("total", ctypes.c_ulonglong), ("available", ctypes.c_ulonglong),
                    ("total_page", ctypes.c_ulonglong), ("available_page", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong), ("available_virtual", ctypes.c_ulonglong),
                    ("available_extended", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return int(status.total), int(status.available)
        except (AttributeError, OSError):
            pass
    if Path("/proc/meminfo").is_file():
        values = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            values[key] = int(value.strip().split()[0]) * 1024
        return values.get("MemTotal", 0), values.get("MemAvailable", values.get("MemFree", 0))
    total = int(_run(["sysctl", "-n", "hw.memsize"]) or 0)
    return total, total


def _nvidia_gpus() -> list[dict[str, Any]]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        for candidate in (Path("/usr/lib/wsl/lib/nvidia-smi"), Path("/usr/bin/nvidia-smi"), Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "NVIDIA Corporation" / "NVSMI" / "nvidia-smi.exe"):
            if candidate.is_file():
                executable = str(candidate)
                break
    if not executable:
        return []
    output = _run([
        executable, "--query-gpu=name,memory.total,driver_version",
        "--format=csv,noheader,nounits",
    ])
    gpus = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 2:
            try:
                memory = int(float(parts[1]))
            except ValueError:
                memory = 0
            gpus.append({"name": parts[0], "vendor": "NVIDIA", "memory_total_mb": memory, "backend": "CUDA", "driver": parts[2] if len(parts) > 2 else None})
    return gpus


def _other_gpus() -> list[dict[str, Any]]:
    system = platform.system()
    if system == "Windows":
        script = "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json -Compress"
        raw = _run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], timeout=6)
        try:
            rows = json.loads(raw) if raw else []
            if isinstance(rows, dict):
                rows = [rows]
            return [{
                "name": str(row.get("Name") or "Graphics adapter"),
                "vendor": "AMD" if "AMD" in str(row.get("Name", "")).upper() or "RADEON" in str(row.get("Name", "")).upper() else "Intel" if "INTEL" in str(row.get("Name", "")).upper() else "Other",
                "memory_total_mb": int(row.get("AdapterRAM") or 0) // 1_048_576,
                "backend": "Vulkan",
                "driver": row.get("DriverVersion"),
            } for row in rows]
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    if system == "Darwin":
        raw = _run(["system_profiler", "SPDisplaysDataType", "-json"], timeout=8)
        try:
            rows = json.loads(raw).get("SPDisplaysDataType", [])
            return [{"name": row.get("sppci_model", "Apple GPU"), "vendor": "Apple", "memory_total_mb": 0, "backend": "Metal", "driver": None} for row in rows]
        except (ValueError, json.JSONDecodeError):
            return []
    output = _run(["lspci"], timeout=3)
    rows = [line.split(": ", 1)[-1] for line in output.splitlines() if re.search(r"VGA|3D controller|Display controller", line, re.I)]
    return [{
        "name": name,
        "vendor": "AMD" if re.search(r"AMD|ATI|Radeon", name, re.I) else "Intel" if re.search(r"Intel", name, re.I) else "Other",
        "memory_total_mb": 0,
        "backend": "Vulkan",
        "driver": None,
    } for name in rows]


def _dependencies() -> dict[str, dict[str, Any]]:
    checks = {
        "python": [sys.executable, "--version"], "node": ["node", "--version"],
        "pnpm": ["pnpm", "--version"], "git": ["git", "--version"],
        "llama.cpp": ["llama-server", "--version"],
    }
    values = {}
    for name, command in checks.items():
        executable = shutil.which(command[0])
        if name == "llama.cpp" and not executable:
            try:
                from .llama_manager import LlamaManager
                executable = str(LlamaManager.find_executable()[0])
            except FileNotFoundError:
                pass
        output = _run([executable, *command[1:]], timeout=2) if executable else ""
        version = output.splitlines()[0] if output.splitlines() else ""
        values[name] = {"available": bool(executable), "required_at_runtime": name in {"python", "llama.cpp"}, "path": executable, "version": version[:200] or None}
    return values


def _model_size() -> int:
    try:
        return max((path.stat().st_size for path in MODELS_DIR.rglob("*.gguf") if path.is_file()), default=0)
    except OSError:
        return 0


def recommendations(profile: dict[str, Any]) -> dict[str, Any]:
    total_gb = profile["memory"]["total_bytes"] / 2**30
    physical = profile["cpu"]["physical_cores"] or profile["cpu"]["logical_cores"] or 2
    gpus = profile["gpus"]
    accelerator = any(gpu["backend"] in {"CUDA", "Metal", "Vulkan"} for gpu in gpus)
    max_vram = max((int(gpu.get("memory_total_mb") or 0) for gpu in gpus), default=0)
    if total_gb < 7.5:
        context, cache = 4_096, 128
    elif total_gb < 15:
        context, cache = 8_192, 256
    elif total_gb < 31:
        context, cache = 16_384, 512
    elif total_gb < 64:
        context, cache = 32_768, 512
    else:
        context, cache = 32_768, 1_024
    if not accelerator and total_gb < 24:
        context = min(context, 8_192)
    model_gb = profile["models"]["largest_size_bytes"] / 2**30
    if model_gb and model_gb + 4 > total_gb:
        context, cache = min(context, 4_096), 128
    threads = max(1, min(int(physical), 32))
    if accelerator:
        threads = max(2, min(threads, 8))
    reasons = [
        f"{total_gb:.1f} GB system memory supports a {context:,}-token starting context.",
        f"{physical} physical CPU core(s) detected; {threads} inference thread(s) are recommended.",
    ]
    if accelerator:
        reasons.append(f"{gpus[0]['backend']} graphics acceleration was detected; offload all supported model layers.")
    else:
        reasons.append("No supported graphics accelerator was confirmed; use CPU inference without GPU offload.")
    if max_vram:
        reasons.append(f"Largest detected GPU reports {max_vram:,} MB of video memory.")
    return {
        "context_size": context,
        "gpu_layers": 9_999 if accelerator else 0,
        "threads": threads,
        "parallel": 1,
        "cache_ram_mb": cache,
        "flash_attention": True,
        "reasons": reasons,
    }


def detect_host() -> dict[str, Any]:
    system = platform.system()
    release = platform.release()
    wsl = system == "Linux" and ("microsoft" in release.casefold() or bool(os.environ.get("WSL_DISTRO_NAME")))
    cpu_name, physical_cores = _linux_cpu() if system == "Linux" else (platform.processor() or platform.machine() or "Unknown CPU", None)
    logical_cores = os.cpu_count() or 1
    if physical_cores is None and system == "Darwin":
        physical_cores = int(_run(["sysctl", "-n", "hw.physicalcpu"]) or 0) or None
    if physical_cores is None and system == "Windows":
        physical_cores = int(_run(["powershell.exe", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor | Measure-Object NumberOfCores -Sum).Sum"]) or 0) or None
    total, available = _memory_bytes()
    gpus = _nvidia_gpus() or _other_gpus()
    disk = shutil.disk_usage(DATA_DIR.parent if DATA_DIR.parent.exists() else PROJECT_ROOT)
    stable = {
        "system": system, "release": release, "machine": platform.machine(), "wsl": wsl,
        "cpu": cpu_name, "physical": physical_cores, "logical": logical_cores,
        "memory": total, "gpus": [(gpu["name"], gpu["memory_total_mb"], gpu["backend"]) for gpu in gpus],
    }
    wsl_distribution = os.environ.get("WSL_DISTRO_NAME")
    if wsl and not wsl_distribution:
        try:
            os_release = dict(
                line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines()
                if "=" in line
            )
            wsl_distribution = f"{os_release.get('NAME', 'Linux').strip(chr(34))} {os_release.get('VERSION_ID', '').strip(chr(34))}".strip()
        except OSError:
            pass
    profile = {
        "fingerprint": hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()[:20],
        "tuning_version": TUNING_VERSION,
        "platform": {"system": system, "release": release, "version": platform.version(), "machine": platform.machine(), "wsl": wsl, "wsl_distribution": wsl_distribution},
        "cpu": {"name": cpu_name, "physical_cores": physical_cores, "logical_cores": logical_cores},
        "memory": {"total_bytes": total, "available_bytes": available},
        "gpus": gpus,
        "storage": {"data_free_bytes": disk.free, "data_total_bytes": disk.total},
        "models": {"directory": str(MODELS_DIR), "largest_size_bytes": _model_size()},
        "paths": {"project": str(PROJECT_ROOT), "data": str(DATA_DIR), "models": str(MODELS_DIR), "home": str(Path.home())},
        "dependencies": _dependencies(),
    }
    profile["recommended"] = recommendations(profile)
    return profile


def apply_recommendations(force: bool = False) -> tuple[dict[str, Any], dict[str, Any], bool]:
    """Apply safe host defaults initially or after a hardware change; preserve opt-out."""
    from ..database import get_settings, update_settings

    profile = detect_host()
    settings = get_settings()
    should_apply = force or (
        settings.get("auto_tune", True)
        and (
            settings.get("hardware_fingerprint") != profile["fingerprint"]
            or int(settings.get("tuning_version", 0)) < TUNING_VERSION
        )
    )
    if should_apply:
        values = {key: value for key, value in profile["recommended"].items() if key != "reasons"}
        settings = update_settings({
            **values,
            "auto_tune": True,
            "hardware_fingerprint": profile["fingerprint"],
            "tuning_version": TUNING_VERSION,
        })
    return profile, settings, should_apply

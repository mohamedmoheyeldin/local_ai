from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

API = "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"


def _request(url: str):
    return urllib.request.urlopen(urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Local-AI-Packager"},
    ), timeout=120)


def _asset_pattern(system: str, architecture: str, backend: str) -> tuple[str, str]:
    arch = "arm64" if architecture.lower() in {"arm64", "aarch64"} else "x64"
    if system == "windows":
        suffix = {"cpu": f"bin-win-cpu-{arch}.zip", "vulkan": f"bin-win-vulkan-{arch}.zip", "cuda12": f"bin-win-cuda-12.4-{arch}.zip"}[backend]
        return suffix, ".zip"
    suffix = {"cpu": f"bin-ubuntu-{arch}.tar.gz", "vulkan": f"bin-ubuntu-vulkan-{arch}.tar.gz"}[backend]
    return suffix, ".tar.gz"


def _safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as opened:
            members = opened.infolist()
            if any(Path(member.filename).is_absolute() or ".." in Path(member.filename).parts for member in members):
                raise RuntimeError("Unsafe path in llama.cpp archive")
            opened.extractall(destination)
    else:
        with tarfile.open(archive, "r:gz") as opened:
            members = opened.getmembers()
            if any(Path(member.name).is_absolute() or ".." in Path(member.name).parts for member in members):
                raise RuntimeError("Unsafe path in llama.cpp archive")
            opened.extractall(destination, filter="data")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", choices=("windows", "linux"), required=True)
    parser.add_argument("--architecture", default=platform.machine())
    parser.add_argument("--backend", choices=("cpu", "vulkan", "cuda12"), default="cpu")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.system == "linux" and args.backend == "cuda12":
        raise SystemExit("Official Linux release assets do not currently provide a self-contained CUDA archive")

    with _request(API) as response:
        release = json.load(response)
    suffix, extension = _asset_pattern(args.system, args.architecture, args.backend)
    asset = next((item for item in release.get("assets", []) if item["name"].endswith(suffix)), None)
    if not asset:
        raise SystemExit(f"No official llama.cpp release asset matched {suffix}")
    expected = str(asset.get("digest") or "")
    if not expected.startswith("sha256:"):
        raise SystemExit("The official llama.cpp release asset did not provide a SHA-256 digest")

    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="local-ai-llama-") as temporary:
        archive = Path(temporary) / f"runtime{extension}"
        digest = hashlib.sha256()
        with _request(asset["browser_download_url"]) as response, archive.open("wb") as target:
            while chunk := response.read(1024 * 1024):
                target.write(chunk)
                digest.update(chunk)
        if digest.hexdigest().lower() != expected.split(":", 1)[1].lower():
            raise SystemExit("llama.cpp archive checksum did not match the GitHub release digest")
        extracted = Path(temporary) / "extracted"
        _safe_extract(archive, extracted)
        executable_name = "llama-server.exe" if args.system == "windows" else "llama-server"
        executable = next(extracted.rglob(executable_name), None)
        if not executable:
            raise SystemExit(f"{executable_name} was not found in the official archive")
        for item in executable.parent.rglob("*"):
            if item.is_file():
                relative = item.relative_to(executable.parent)
                destination = args.output / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, destination)
        if args.system == "linux":
            (args.output / executable_name).chmod(0o755)
    (args.output / "LLAMA_CPP_RELEASE.json").write_text(json.dumps({
        "tag": release["tag_name"], "asset": asset["name"], "sha256": expected.split(":", 1)[1], "backend": args.backend,
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"tag": release["tag_name"], "asset": asset["name"], "output": str(args.output)}))


if __name__ == "__main__":
    main()

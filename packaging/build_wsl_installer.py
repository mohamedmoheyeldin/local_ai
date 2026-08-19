from __future__ import annotations

import argparse
import hashlib
import io
import os
import re
import tarfile
from pathlib import Path


def add_tree(archive: tarfile.TarFile, source: Path, destination: str) -> None:
    for item in sorted(source.rglob("*")):
        archive.add(item, arcname=str(Path(destination) / item.relative_to(source)), recursive=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[.-][A-Za-z0-9.-]+)?", args.version):
        raise SystemExit("Version must be a safe semantic version such as 1.2.0")
    root = Path(__file__).resolve().parents[1]
    wsl = root / "packaging" / "wsl"
    if not (args.bundle / "portable-local-ai").is_file():
        raise SystemExit("Compiled WSL application bundle is missing")

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.PAX_FORMAT) as archive:
        add_tree(archive, args.bundle, "app")
        for name in ("install.sh", "register-startup.ps1", "portable-local-ai.service.in"):
            archive.add(wsl / name, arcname=name)
        payload = args.version.encode()
        info = tarfile.TarInfo("VERSION")
        info.size = len(payload)
        info.mode = 0o600
        archive.addfile(info, io.BytesIO(payload))
    payload = buffer.getvalue()
    digest = hashlib.sha256(payload).hexdigest()
    header = (wsl / "self-extract.sh.in").read_text(encoding="utf-8").replace("__PAYLOAD_SHA256__", digest).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(header + payload)
    args.output.chmod(0o755)
    (args.output.parent / f"{args.output.name}.sha256").write_text(f"{hashlib.sha256(header + payload).hexdigest()}  {args.output.name}\n", encoding="ascii")
    print(f"Created {args.output} ({args.output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()

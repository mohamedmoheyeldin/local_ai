from __future__ import annotations

import argparse
import re
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Stamp a validated release version into the frozen application.")
    parser.add_argument("version")
    args = parser.parse_args()
    version = args.version.removeprefix("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[.-][A-Za-z0-9.-]+)?", version):
        raise SystemExit(f"Invalid release version: {version}")
    target = Path(__file__).resolve().parents[1] / "backend" / "app" / "_build_version.py"
    target.write_text(
        '"""Build-time application version. Updated by the release packaging workflow."""\n\n'
        f'__version__ = "{version}"\n',
        encoding="utf-8",
    )
    print(version)


if __name__ == "__main__":
    main()

from pathlib import Path
import platform

from PyInstaller.utils.hooks import collect_all, collect_submodules

root = Path(SPEC).resolve().parents[1]
datas = [
    (str(root / "config"), "config"),
    (str(root / "frontend" / "dist"), "frontend/dist"),
    (str(root / "README.md"), "."),
    (str(root / "models" / "README.md"), "models"),
]
binaries = []
runtime = root / "packaging" / "runtime"
if runtime.is_dir():
    datas.append((str(runtime), "runtime"))

hiddenimports = collect_submodules("mcp", filter=lambda name: not name.startswith("mcp.cli")) + collect_submodules("keyring.backends")
for package in ("cryptography", "pypdf"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

a = Analysis(
    [str(root / "backend" / "app" / "launcher.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="local-ai",
    console=platform.system() != "Windows",
    disable_windowed_traceback=False,
    upx=False,
)
executables = [exe]
if platform.system() == "Windows":
    cli = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="local-ai-cli",
        console=True,
        disable_windowed_traceback=False,
        upx=False,
    )
    executables.append(cli)
coll = COLLECT(
    *executables,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="local-ai",
)

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_installer_is_machine_level() -> None:
    script = (ROOT / "packaging/windows/installer.iss").read_text(encoding="utf-8")
    assert "DefaultDirName={autopf}\\Local AI" in script
    assert "PrivilegesRequired=admin" in script
    assert "OutputBaseFilename=Local-AI-Windows-Setup-" in script
    assert "local-ai.exe" in script
    assert "{localappdata}\\Local AI" in script


def test_wsl_installer_uses_standard_system_paths_and_service() -> None:
    script = (ROOT / "packaging/wsl/install.sh").read_text(encoding="utf-8")
    unit = (ROOT / "packaging/wsl/local-ai.service.in").read_text(encoding="utf-8")
    assert "APP_ROOT=/opt/local-ai" in script
    assert "DATA_DIR=/var/lib/local-ai" in script
    assert "BIN_PATH=/usr/local/bin/local-ai" in script
    assert "UNIT_PATH=/etc/systemd/system/local-ai.service" in script
    assert "systemctl enable --now" in script
    assert "WantedBy=multi-user.target" in unit
    assert "User=__USER__" in unit

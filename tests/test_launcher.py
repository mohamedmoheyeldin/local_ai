from __future__ import annotations

import io
import os
import sys
from pathlib import Path

from backend.app.launcher import _configure_installed_paths, _emit_result


def test_emit_result_writes_json_when_console_is_available(monkeypatch) -> None:
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)

    _emit_result({"initialized": True})

    assert output.getvalue() == '{"initialized": true}\n'


def test_emit_result_is_safe_for_windowed_windows_executable(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdout", None)

    _emit_result({"initialized": True})


def test_crash_report_is_written_without_a_console(monkeypatch, tmp_path: Path) -> None:
    from backend.app.launcher import _write_crash_report

    monkeypatch.setenv("LOCAL_AI_DATA_DIR", str(tmp_path))
    try:
        raise RuntimeError("packaged failure")
    except RuntimeError:
        _write_crash_report()

    report = tmp_path / "runtime" / "logs" / "launcher-error.log"
    assert "RuntimeError: packaged failure" in report.read_text(encoding="utf-8")


def test_installed_windows_uses_private_profile_data(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr("backend.app.launcher.platform.system", lambda: "Windows")
    monkeypatch.setenv("LOCALAPPDATA", "C:/Users/test/AppData/Local")
    monkeypatch.delenv("LOCAL_AI_DATA_DIR", raising=False)
    monkeypatch.delenv("LOCAL_AI_MODELS_DIR", raising=False)

    _configure_installed_paths()

    assert Path(os.environ["LOCAL_AI_DATA_DIR"]) == Path("C:/Users/test/AppData/Local/Local AI")
    assert Path(os.environ["LOCAL_AI_MODELS_DIR"]) == Path("C:/Users/test/AppData/Local/Local AI/Models")


def test_installed_linux_uses_system_data_paths(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr("backend.app.launcher.platform.system", lambda: "Linux")
    monkeypatch.delenv("LOCAL_AI_DATA_DIR", raising=False)
    monkeypatch.delenv("LOCAL_AI_MODELS_DIR", raising=False)

    _configure_installed_paths()

    assert os.environ["LOCAL_AI_DATA_DIR"] == "/var/lib/local-ai"
    assert os.environ["LOCAL_AI_MODELS_DIR"] == "/var/lib/local-ai/models"

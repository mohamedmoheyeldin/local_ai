from __future__ import annotations

import io
import sys
from pathlib import Path

from backend.app.launcher import _emit_result


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

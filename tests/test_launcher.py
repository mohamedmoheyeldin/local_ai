from __future__ import annotations

import io
import sys

from backend.app.launcher import _emit_result


def test_emit_result_writes_json_when_console_is_available(monkeypatch) -> None:
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)

    _emit_result({"initialized": True})

    assert output.getvalue() == '{"initialized": true}\n'


def test_emit_result_is_safe_for_windowed_windows_executable(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdout", None)

    _emit_result({"initialized": True})

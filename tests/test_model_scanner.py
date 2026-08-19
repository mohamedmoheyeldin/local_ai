from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.app.services import model_scanner
from backend.app.services.llama_manager import LlamaManager


def test_scanner_finds_only_regular_gguf_files(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "model.gguf").write_bytes(b"GGUF-test")
    (tmp_path / "notes.txt").write_text("not a model", encoding="utf-8")
    with patch.object(model_scanner, "MODELS_DIR", tmp_path), patch.object(model_scanner, "replace_models") as replace:
        models = model_scanner.scan_models()
    assert [model["relative_path"] for model in models] == ["nested/model.gguf"]
    replace.assert_called_once_with(models)


def test_safe_model_path_rejects_escape(tmp_path: Path) -> None:
    with patch.object(model_scanner, "MODELS_DIR", tmp_path):
        try:
            model_scanner.safe_model_path("../outside.gguf")
        except ValueError as exc:
            assert "inside" in str(exc)
        else:
            raise AssertionError("Path escape was accepted")


def test_llama_command_uses_selected_local_model_without_shell(tmp_path: Path) -> None:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"GGUF-test")
    settings = {
        "selected_model": "model.gguf", "llama_executable": "", "model_host": "127.0.0.1",
        "model_port": 8180, "context_size": 4096, "parallel": 1, "gpu_layers": 99,
        "threads": 4, "cache_ram_mb": 256, "flash_attention": True,
    }
    manager = LlamaManager()
    with patch.object(model_scanner, "MODELS_DIR", tmp_path), patch.object(manager, "find_executable", return_value=(Path("/bin/true"), False)):
        command = manager.command_for(settings)
    assert command[0] == str(Path("/bin/true"))
    assert command[command.index("-m") + 1] == str(model)
    assert ["--host", "127.0.0.1"] == command[command.index("--host"):command.index("--host") + 2]
    assert "--flash-attn" in command
    assert "--no-webui" in command


def test_llama_status_reports_the_model_loaded_by_the_server() -> None:
    props = MagicMock()
    props.__enter__.return_value = props
    props.status = 200
    props.read.return_value = (
        b'{"model_alias":"bartowski/Qwen_Qwen3-8B-GGUF:Q6_K",'
        b'"model_path":"/models/Qwen_Qwen3-8B-Q6_K.gguf",'
        b'"model_ftype":"Q6_K","default_generation_settings":{"n_ctx":16384}}'
    )
    settings = {"model_host": "127.0.0.1", "model_port": 8180}

    with patch("backend.app.services.llama_manager.urllib.request.urlopen", return_value=props):
        status = LlamaManager().status(settings)

    assert status["state"] == "ready"
    assert status["model"]["display_name"] == "Qwen3-8B · Q6_K"
    assert status["model"]["context_size"] == 16384


def test_runtime_discovery_excludes_embedding_only_servers(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    (proc / "101").mkdir(parents=True)
    (proc / "102").mkdir(parents=True)
    (proc / "101" / "cmdline").write_bytes(b"llama-server\0--embedding\0--port\08082\0")
    (proc / "102" / "cmdline").write_bytes(b"llama-server\0--port\08080\0")
    original_glob = Path.glob

    proc_root = Path("/proc")

    def fake_glob(path, pattern):
        if path == proc_root:
            return original_glob(proc, "[0-9]*/cmdline")
        return original_glob(path, pattern)

    with patch.object(Path, "is_dir", lambda path: True if path == proc_root else path.exists()), patch.object(Path, "glob", fake_glob):
        assert LlamaManager.discover_local_ports() == [8080]

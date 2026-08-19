from unittest.mock import patch

from backend.app.services.host_profile import recommendations


def profile(memory_gb: int, physical: int, gpus: list[dict] | None = None, model_gb: int = 0) -> dict:
    return {
        "memory": {"total_bytes": memory_gb * 2**30},
        "cpu": {"physical_cores": physical, "logical_cores": physical * 2},
        "gpus": gpus or [],
        "models": {"largest_size_bytes": model_gb * 2**30},
    }


def test_cpu_only_low_memory_host_gets_safe_settings() -> None:
    result = recommendations(profile(6, 4))
    assert result["context_size"] == 4096
    assert result["gpu_layers"] == 0
    assert result["threads"] == 4
    assert result["cache_ram_mb"] == 128


def test_cuda_host_gets_gpu_offload_without_excessive_threads() -> None:
    result = recommendations(profile(32, 16, [{"name": "GPU", "backend": "CUDA", "memory_total_mb": 16_384}]))
    assert result["context_size"] == 32768
    assert result["gpu_layers"] == 9999
    assert result["threads"] == 8
    assert result["parallel"] == 1


def test_model_larger_than_host_memory_forces_conservative_context() -> None:
    result = recommendations(profile(16, 8, model_gb=14))
    assert result["context_size"] == 4096
    assert result["cache_ram_mb"] == 128

from __future__ import annotations


def test_gpu_info_is_cached_and_copied(monkeypatch):
    from bionodulo.api import system_stats as stats

    calls = 0

    def fake_detect_gpu_info():
        nonlocal calls
        calls += 1
        return [{"index": 0, "name": "GPU", "vram_total": 1}]

    now = 1000.0
    monkeypatch.setattr(stats, "_GPU_INFO_CACHE", None)
    monkeypatch.setattr(stats, "_detect_gpu_info", fake_detect_gpu_info)
    monkeypatch.setattr(stats.time, "monotonic", lambda: now)
    monkeypatch.setenv("BIONODULO_GPU_STATS_TTL_SECONDS", "30")
    monkeypatch.delenv("BIONODULO_ENABLE_GPU_STATS", raising=False)

    first = stats._get_gpu_info()
    first[0]["name"] = "mutated"
    second = stats._get_gpu_info()

    assert calls == 1
    assert second == [{"index": 0, "name": "GPU", "vram_total": 1}]


def test_gpu_info_cache_expires(monkeypatch):
    from bionodulo.api import system_stats as stats

    calls = 0
    now = 1000.0

    def fake_detect_gpu_info():
        nonlocal calls
        calls += 1
        return [{"index": 0, "name": f"GPU {calls}"}]

    monkeypatch.setattr(stats, "_GPU_INFO_CACHE", None)
    monkeypatch.setattr(stats, "_detect_gpu_info", fake_detect_gpu_info)
    monkeypatch.setattr(stats.time, "monotonic", lambda: now)
    monkeypatch.setenv("BIONODULO_GPU_STATS_TTL_SECONDS", "30")
    monkeypatch.delenv("BIONODULO_ENABLE_GPU_STATS", raising=False)

    assert stats._get_gpu_info()[0]["name"] == "GPU 1"
    now = 1031.0
    assert stats._get_gpu_info()[0]["name"] == "GPU 2"
    assert calls == 2


def test_gpu_info_can_be_disabled(monkeypatch):
    from bionodulo.api import system_stats as stats

    def fail_detect_gpu_info():
        raise AssertionError("GPU detection should not run when disabled")

    monkeypatch.setattr(stats, "_GPU_INFO_CACHE", None)
    monkeypatch.setattr(stats, "_detect_gpu_info", fail_detect_gpu_info)
    monkeypatch.setenv("BIONODULO_ENABLE_GPU_STATS", "0")

    assert stats._get_gpu_info() == []

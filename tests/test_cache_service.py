"""Tests for cache service startup behavior."""

from app import cache_service
from app import globals as G


def test_startup_always_rebuilds_photo_index(tmp_path, monkeypatch):
    G.CACHE_DIR = str(tmp_path / "cache")
    calls = []
    monkeypatch.setattr(
        cache_service,
        "build_cache",
        lambda root, progress_callback=None: calls.append(root),
    )
    monkeypatch.setattr(cache_service, "prune_cache", lambda: None)

    cache_service.build_initial_cache()

    assert calls == [G.PHOTO_ROOT]

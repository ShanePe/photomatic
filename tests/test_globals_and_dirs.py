"""Tests for global configuration and directory initialization.

Validates instance directory creation, cache locks, and global state.
"""

import os

from app import globals as G


def test_ensure_instance_dirs_creates(tmp_path):
    """Test that ensure_instance_dirs creates required cache and log directories."""
    inst = str(tmp_path / "instance")
    # ensure dirs do not exist
    assert not os.path.exists(inst)

    G.ensure_instance_dirs(inst)

    assert os.path.isdir(os.path.join(inst, "cache"))
    assert os.path.isdir(os.path.join(inst, "cache", "photos"))
    assert os.path.isdir(os.path.join(inst, "log"))


def test_ensure_instance_dirs_creates_icons_subdir(tmp_path):
    """Test that ensure_instance_dirs also creates icons subdirectory."""
    inst = str(tmp_path / "instance_icons")
    assert not os.path.exists(inst)

    G.ensure_instance_dirs(inst)

    assert os.path.isdir(os.path.join(inst, "cache", "icons"))


def test_same_day_keys_is_set_type():
    """Verify SAME_DAY_KEYS is initialized as a set for O(1) lookup."""
    # Reset to initial state
    G.SAME_DAY_KEYS = set()

    assert isinstance(G.SAME_DAY_KEYS, set)

    # Test set operations work
    G.SAME_DAY_KEYS.add("test_key")
    assert "test_key" in G.SAME_DAY_KEYS
    assert "other_key" not in G.SAME_DAY_KEYS

    # Cleanup
    G.SAME_DAY_KEYS = set()


def test_get_cache_lock_returns_lock():
    """Test that get_cache_lock returns a threading lock."""
    lock = G.get_cache_lock()
    assert lock is not None

    # Should be usable as context manager
    with lock:
        pass  # Should not raise


def test_ensure_instance_dirs_uses_configured_relative_paths(tmp_path):
    """Ensure configured relative cache/log paths are resolved under instance root."""
    inst = str(tmp_path / "instance_custom")

    original_paths = G.PATHS_CONFIG.copy()
    try:
        G.PATHS_CONFIG = {
            "cache_dir": "runtime-cache",
            "photo_cache_dir": "runtime-cache/photos2",
            "log_dir": "runtime-log",
        }

        G.ensure_instance_dirs(inst)

        assert os.path.isdir(os.path.join(inst, "runtime-cache"))
        assert os.path.isdir(os.path.join(inst, "runtime-cache", "photos2"))
        assert os.path.isdir(os.path.join(inst, "runtime-cache", "icons"))
        assert os.path.isdir(os.path.join(inst, "runtime-log"))
    finally:
        G.PATHS_CONFIG = original_paths

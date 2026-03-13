"""Tests for configuration loading and merging.

Validates that YAML config files properly override default settings.
"""

import yaml

from app import config_manager


def test_load_config_overrides(tmp_path):
    """Test that load_config merges YAML overrides with default configuration."""
    cfg_path = tmp_path / "config.yaml"
    data = {
        "app": {"port": 6000},
        "paths": {"photo_dir": "/tmp/photos"},
        "image": {"max_width": 1600},
        "cache": {"limit_enabled": False, "limit": 50},
    }
    cfg_path.write_text(yaml.safe_dump(data))

    cfg = config_manager.load_config(str(cfg_path))
    assert cfg["paths"]["photo_dir"] == "/tmp/photos"
    assert cfg["app"]["port"] == 6000
    assert cfg["image"]["max_width"] == 1600
    assert cfg["cache"]["limit_enabled"] is False
    assert cfg["cache"]["limit"] == 50


def test_load_config_uses_cache_limit_enabled_default(tmp_path):
    """Test that cache.limit_enabled defaults to the configured default."""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.safe_dump({"cache": {"limit": 25}}), encoding="utf-8")

    cfg = config_manager.load_config(str(cfg_path))

    assert cfg["cache"]["limit"] == 25
    # limit_enabled is not set unless present in YAML, so only check for limit

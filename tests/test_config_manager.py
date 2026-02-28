"""Tests for configuration loading and merging.

Validates that YAML config files properly override default settings.
"""

import yaml

from app import config_manager


def test_load_config_overrides(tmp_path):
    """Test that load_config merges YAML overrides with default configuration."""
    cfg_path = tmp_path / "config.yaml"
    data = {
        "app": {"photo_dir": "/tmp/photos", "port": 6000},
        "image": {"max_width": 1600},
        "cache": {"limit": 50},
    }
    cfg_path.write_text(yaml.safe_dump(data))

    cfg = config_manager.load_config(str(cfg_path))
    assert cfg["app"]["photo_dir"] == "/tmp/photos"
    assert cfg["app"]["port"] == 6000
    assert cfg["image"]["max_width"] == 1600
    assert cfg["cache"]["limit"] == 50
    # defaults remain for unspecified keys
    assert (
        cfg["image"]["max_height"]
        == config_manager.DEFAULT_CONFIG["image"]["max_height"]
    )

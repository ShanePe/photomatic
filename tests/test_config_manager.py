import os
import tempfile
import yaml

from app import config_manager


def test_load_config_overrides(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    data = {"image": {"max_width": 1600}, "cache": {"limit": 50}}
    cfg_path.write_text(yaml.safe_dump(data))

    cfg = config_manager.load_config(str(cfg_path))
    assert cfg["image"]["max_width"] == 1600
    assert cfg["cache"]["limit"] == 50
    # defaults remain for unspecified keys
    assert (
        cfg["image"]["max_height"]
        == config_manager.DEFAULT_CONFIG["image"]["max_height"]
    )

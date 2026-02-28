"""Configuration loader for Photomatic.

Provides `DEFAULT_CONFIG` and a safe `load_config()` helper that merges
`config.yaml` values into defaults while ignoring unknown keys. Other
modules import this at startup to obtain runtime settings.
"""

import os

import yaml

DEFAULT_CONFIG = {
    "app": {
        "photo_dir": "/app/photo-storage",
        "port": 5050,
    },
    "paths": {
        "cache_dir": "cache",
        "photo_cache_dir": "cache/photos",
        "log_dir": "log",
    },
    "image": {
        "max_width": 2080,
        "max_height": 768,
    },
    "cache": {
        "limit": 2000,
        "same_day_cycle": 100,
    },
}


def load_config(path="config.yaml"):
    """
    Load nested YAML configuration with safe defaults.

    - Missing sections fall back to DEFAULT_CONFIG.
    - Unknown keys are ignored.
    - Only keys defined in DEFAULT_CONFIG are accepted.

    Returns:
        dict: merged configuration dictionary.
    """
    config = DEFAULT_CONFIG.copy()

    # Deep copy nested dicts
    config = {section: values.copy() for section, values in DEFAULT_CONFIG.items()}

    config_path = path
    if path == "config.yaml" and not os.path.exists(config_path):
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            file_cfg = yaml.safe_load(f) or {}

            for section, values in file_cfg.items():
                if section in config and isinstance(values, dict):
                    for key, val in values.items():
                        if key in config[section]:
                            config[section][key] = val

    return config

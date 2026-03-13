"""Configuration loader for Photomatic.

Provides `DEFAULT_CONFIG` and a safe `load_config()` helper that merges
`config.yaml` values into defaults while ignoring unknown keys. Other
modules import this at startup to obtain runtime settings.
"""

import os

import yaml


def deep_merge(base, override):
    """
    Recursively merge two dictionaries, with override taking precedence.
    All keys from both dicts are included.
    """
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(path="config.yaml"):
    """
    Load YAML configuration, merging config.yaml and config.local.yaml if present.
    All keys from both files are included. Local config overrides main config.
    Returns:
        dict: merged configuration dictionary.
    """
    # Load main config
    config_path = path
    if path == "config.yaml" and not os.path.exists(config_path):
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    main_cfg = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            main_cfg = yaml.safe_load(f) or {}

    # Load local config if present
    local_path = os.path.join(os.path.dirname(__file__), "config.local.yaml")
    local_cfg = {}
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            local_cfg = yaml.safe_load(f) or {}

    merged = main_cfg
    if local_cfg:
        merged = deep_merge(merged, local_cfg)
    return merged

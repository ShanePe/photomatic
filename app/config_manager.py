"""Configuration loader for Photomatic.

Loads YAML config (config.yaml + config.local.yaml) for all app settings.
Client config section now supports a `ken_burns` flag to enable the Ken Burns effect (zoom+pan) on slideshow images.
Other modules import this at startup to obtain runtime settings.
"""

import os

import yaml


def _resolve_config_path(path: str) -> str:
    """Resolve a configuration file path.

    If ``path`` is a directory, look for ``config.yaml`` inside it.
    Returns the resolved candidate path.
    """
    if os.path.isdir(path):
        return os.path.join(path, "config.yaml")
    return path


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

    Respects CONFIG_FILE environment variable to override the default config path.

    Returns:
        dict: merged configuration dictionary.
    """
    # Check for CONFIG_FILE environment variable
    env_config_path = os.environ.get("CONFIG_FILE")
    if env_config_path:
        path = env_config_path

    # Load main config
    config_path = _resolve_config_path(path)
    default_config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    if not os.path.isfile(config_path):
        config_path = _resolve_config_path(default_config_path)
    main_cfg = {}
    if os.path.isfile(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            main_cfg = yaml.safe_load(f) or {}

    # Only merge local config if loading the default config.yaml
    merged = main_cfg
    if path == "config.yaml":
        local_path = os.path.join(os.path.dirname(__file__), "config.local.yaml")
        local_cfg = {}
        if os.path.exists(local_path):
            with open(local_path, "r", encoding="utf-8") as f:
                local_cfg = yaml.safe_load(f) or {}
        if local_cfg:
            merged = deep_merge(merged, local_cfg)
    return merged

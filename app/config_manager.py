import yaml
import os

DEFAULT_CONFIG = {
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

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            file_cfg = yaml.safe_load(f) or {}

            for section, values in file_cfg.items():
                if section in config and isinstance(values, dict):
                    for key, val in values.items():
                        if key in config[section]:
                            config[section][key] = val

    return config

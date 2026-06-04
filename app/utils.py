"""Utility functions for application startup."""

import json
import os

from . import globals as G
from .cache_manager import prune_cache


def redact_sensitive_values(value):
    """Recursively redact obvious sensitive keys in nested config values."""
    sensitive_markers = ("key", "token", "secret", "password", "passwd")

    if isinstance(value, dict):
        redacted = {}
        for k, v in value.items():
            key_name = str(k).lower()
            if any(marker in key_name for marker in sensitive_markers):
                redacted[k] = "***REDACTED***"
            else:
                redacted[k] = redact_sensitive_values(v)
        return redacted

    if isinstance(value, list):
        return [redact_sensitive_values(item) for item in value]

    return value


def _resolve_port(config_port):
    """Resolve effective port using PORT env var first, then config value."""
    env_port = os.environ.get("PORT")
    if not env_port:
        return config_port

    try:
        return int(env_port)
    except ValueError:
        G.logger.warning(
            "Invalid PORT environment variable '%s'; using config port %s",
            env_port,
            config_port,
        )
        return config_port


def initialize_app_state():
    """Initialize runtime globals and perform startup housekeeping."""
    paths_cfg = G.CONFIG["paths"]
    G.PHOTO_ROOT = paths_cfg["photo_dir"]

    redacted_config = redact_sensitive_values(G.CONFIG)
    G.logger.info(
        "Effective startup config:\n%s", json.dumps(redacted_config, indent=2)
    )

    if G.CACHE_LIMIT_ENABLED and G.CACHE_COUNT > G.CACHE_LIMIT:
        G.logger.info(
            "Initial cache count: %s, pruning to limit %s", G.CACHE_COUNT, G.CACHE_LIMIT
        )
        prune_cache()


def run_app():
    """Configure globals and run the Flask application.

    Uses values from `config.yaml` (`paths.photo_dir`, `app.port`), prunes the
    cache if the on-disk cache exceeds the configured limit, and launches
    the Flask app.
    """
    app_cfg = G.CONFIG["app"]
    effective_port = _resolve_port(app_cfg["port"])

    initialize_app_state()
    G.logger.info("Effective port: %s", effective_port)

    G.app.run(debug=True, host="0.0.0.0", port=effective_port)

"""Utility functions for application startup."""

import argparse
import json
import os
import sys
from typing import Any

from . import globals as G
from .cache_manager import prune_cache
from .version import __version__


def redact_sensitive_values(value: Any) -> Any:
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


def _resolve_port(config_port, cli_port=None):
    """Resolve the effective port with CLI > env > config precedence."""
    if cli_port is not None:
        return cli_port

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


def parse_runtime_args(argv=None):
    """Parse process-level startup overrides for the Flask app."""
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--photos", default=None)
    parser.add_argument("--debug", action="store_true")
    args, _ = parser.parse_known_args(argv)
    return {"port": args.port, "photos": args.photos, "debug": args.debug}


def _is_debugger_attached():
    """Return True when running under a debugger (e.g., debugpy)."""
    gettrace = getattr(sys, "gettrace", None)
    if callable(gettrace) and gettrace() is not None:
        return True
    return "debugpy" in sys.modules


def _resolve_debug_mode(default=False):
    """Resolve debug mode from APP_DEBUG/FLASK_DEBUG env vars."""
    raw = os.environ.get("APP_DEBUG", os.environ.get("FLASK_DEBUG"))
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


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


def run_app(argv=None):
    """Configure globals and run the Flask application.

    Uses values from `config.yaml` (`paths.photo_dir`, `app.port`), prunes the
    cache if the on-disk cache exceeds the configured limit, and launches
    the Flask app.
    """
    cli_args = parse_runtime_args(argv)
    app_cfg = G.CONFIG["app"]
    if cli_args["photos"]:
        G.CONFIG.setdefault("paths", {})["photo_dir"] = cli_args["photos"]
    if cli_args["port"] is not None:
        app_cfg["port"] = cli_args["port"]

    effective_port = _resolve_port(app_cfg["port"], cli_port=cli_args["port"])
    debug_mode = _resolve_debug_mode(default=False)
    use_reloader = debug_mode and not _is_debugger_attached()

    initialize_app_state()
    G.logger.info(
        "Effective version: %s | Port: %s | Debug: %s | Reloader: %s",
        __version__,
        effective_port,
        debug_mode,
        use_reloader,
    )

    G.app.run(
        debug=debug_mode,
        use_reloader=use_reloader,
        host="0.0.0.0",
        port=effective_port,
    )

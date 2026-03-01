"""Utility functions for application startup."""

from . import globals as G
from .cache_manager import prune_cache


def run_app():
    """Configure globals and run the Flask application.

    Uses values from `config.yaml` (`paths.photo_dir`, `app.port`), prunes the
    cache if the on-disk cache exceeds the configured limit, and launches
    the Flask app.
    """
    app_cfg = G.CONFIG["app"]
    paths_cfg = G.CONFIG["paths"]
    G.PHOTO_ROOT = paths_cfg["photo_dir"]

    if G.CACHE_LIMIT_ENABLED and G.CACHE_COUNT > G.CACHE_LIMIT:
        G.logger.info(
            "Initial cache count: %s, pruning to limit %s", G.CACHE_COUNT, G.CACHE_LIMIT
        )
        prune_cache()

    G.app.run(debug=True, host="0.0.0.0", port=app_cfg["port"])

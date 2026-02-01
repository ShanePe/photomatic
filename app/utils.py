"""Utility functions for CLI parsing and application startup."""

import argparse

from . import globals as G
from .cache_manager import prune_cache


def parse_args():
    """Parse CLI args.

    Returns an `argparse.Namespace` with `photos` (required) and `port`.
    """
    parser = argparse.ArgumentParser(description="Photo slideshow")
    parser.add_argument("--photos", required=True, help="Base folder containing images")
    parser.add_argument("--port", type=int, default=5000, help="Port to run the server")
    return parser.parse_args()


def run_app(arguments):
    """Configure globals and run the Flask application.

    Sets `G.PHOTO_ROOT` from the parsed `arguments`, prunes the cache if the
    on-disk cache exceeds the configured limit, and launches the Flask app.
    """
    G.PHOTO_ROOT = arguments.photos

    if G.CACHE_COUNT > G.CACHE_LIMIT:
        G.logger.info(
            "Initial cache count: %s, pruning to limit %s", G.CACHE_COUNT, G.CACHE_LIMIT
        )
        prune_cache()

    G.app.run(debug=True, host="0.0.0.0", port=arguments.port)

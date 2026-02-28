"""
Global configuration and state for Photomatic application.

This module centralizes all module-level constants, Flask app instance,
and configuration loaded from config.yaml.
"""

import os
import logging
import threading
import atexit
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask
from pillow_heif import register_heif_opener
from .config_manager import load_config
from .image_utils import cleanup_requests_session

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "..", "templates")
STATIC_DIR = os.path.join(BASE_DIR, "..", "templates", "static")

# Initialize Flask app
app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.secret_key = os.urandom(24)

# Register HEIF opener so Pillow can read HEIC files
register_heif_opener()

# Load configuration from config.yaml
CONFIG = load_config()


def _resolve_configured_dir(
    config_path: str | None, instance_root: str, fallback: str
) -> str:
    """Resolve configured directory path.

    - Absolute config paths are used as-is.
    - Relative config paths are resolved under `instance_root`.
    - Empty/None config values fall back to `fallback` under `instance_root`.
    """
    base = Path(instance_root)
    path_value = config_path or fallback
    configured = Path(path_value)
    return str(configured if configured.is_absolute() else (base / configured))


# Image processing settings
MAX_WIDTH = CONFIG["image"]["max_width"]
MAX_HEIGHT = CONFIG["image"]["max_height"]

# Cache settings
CACHE_LIMIT = CONFIG["cache"]["limit"]
SAME_DAY_CYCLE = CONFIG["cache"]["same_day_cycle"]

PATHS_CONFIG = CONFIG["paths"]

# Cache directory is inside the app's instance_path (writable area for the app)
CACHE_DIR = _resolve_configured_dir(
    PATHS_CONFIG.get("cache_dir"), app.instance_path, "cache"
)
CACHE_DIR_PHOTO = _resolve_configured_dir(
    PATHS_CONFIG.get("photo_cache_dir"),
    app.instance_path,
    os.path.join("cache", "photos"),
)
CACHE_DIR_ICON = os.path.join(CACHE_DIR, "icons")
CACHE_DIR_LOG = _resolve_configured_dir(
    PATHS_CONFIG.get("log_dir"), app.instance_path, "log"
)

# Cache layout and filenames (must match expectations in app code)
CACHE_DIR_NAME = "cache"
CACHE_ALL_FILENAME = "cache_all.txt"
CACHE_SAME_DAY_FILENAME = "cache_same_day.txt"
CACHE_PHOTOS_SUBDIR = "photos"
CACHE_ICONS_SUBDIR = "icons"

# Logging
LOG_DIR_NAME = "log"
LOG_FILENAME = "photomatic.log"

# Keys used by prune_cache() and populated at runtime with MD5 keys for
# same-day images that must be preserved. Using set for O(1) lookup.
SAME_DAY_KEYS: set[str] = set()

# Flask session keys used by the slideshow
SESSION_INITIALIZED = "initialized"
SESSION_PHOTO_INDEX = "photo_index"
SESSION_PHOTO_SERVED = "photo_served"


def _normalize_instance_path(instance_root) -> Path:
    """
    Normalize and return a Path for the Flask instance root.
    Accepts either a Path or string.
    """
    return Path(instance_root) if not isinstance(instance_root, Path) else instance_root


def ensure_instance_dirs(instance_root):
    """
    Ensure required instance directories exist:
      - instance/cache
      - instance/cache/photos
      - instance/log

    Raises OSError on failure.
    """
    root = str(_normalize_instance_path(instance_root))
    cache_dir = _resolve_configured_dir(PATHS_CONFIG.get("cache_dir"), root, "cache")
    photo_cache_dir = _resolve_configured_dir(
        PATHS_CONFIG.get("photo_cache_dir"), root, os.path.join("cache", "photos")
    )
    log_dir = _resolve_configured_dir(PATHS_CONFIG.get("log_dir"), root, "log")

    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    Path(photo_cache_dir).mkdir(parents=True, exist_ok=True)
    Path(os.path.join(cache_dir, CACHE_ICONS_SUBDIR)).mkdir(parents=True, exist_ok=True)
    Path(log_dir).mkdir(parents=True, exist_ok=True)


# Create cache directories
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(CACHE_DIR_PHOTO, exist_ok=True)
os.makedirs(CACHE_DIR_ICON, exist_ok=True)
os.makedirs(CACHE_DIR_LOG, exist_ok=True)

# Configure logging
log_handler = RotatingFileHandler(
    os.path.join(CACHE_DIR_LOG, "photomatic.log"),
    maxBytes=5 * 1024 * 1024,
    backupCount=7,
    encoding="utf-8",
)

formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
log_handler.setFormatter(formatter)

logger = logging.getLogger("slideshow")
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

# ============ Mutable State (shared across modules) ============
PHOTO_ROOT = None
CACHE_DATE = None
BUILDING_CACHE = False
CACHE_COUNT = 0
_cache_lock = threading.RLock()  # Thread-safe cache operations


def _cleanup_resources():
    """Clean up resources on application shutdown."""
    logger.info("Cleaning up application resources...")

    # Close logging handlers to release file handles
    for handler in logger.handlers[:]:
        try:
            handler.close()
            logger.removeHandler(handler)
        except (OSError, ValueError) as e:
            print(f"Error closing handler: {e}")

    # Close requests session if it was created
    try:
        cleanup_requests_session()
        logger.info("Closed requests session")
    except (ImportError, AttributeError) as e:
        logger.warning("Error closing requests session: %s", e)


# Register cleanup on application shutdown
atexit.register(_cleanup_resources)


def get_cache_lock():
    """Return the cache lock for thread-safe operations."""
    return _cache_lock

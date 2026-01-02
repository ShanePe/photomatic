"""
Global configuration and state for Photomatic application.

This module centralizes all module-level constants, Flask app instance,
and configuration loaded from config.yaml.
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask
from pillow_heif import register_heif_opener
from .config_manager import load_config

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "..", "templates")

# Initialize Flask app
app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.secret_key = os.urandom(24)

# Register HEIF opener so Pillow can read HEIC files
register_heif_opener()

# Load configuration from config.yaml
CONFIG = load_config()

# Image processing settings
MAX_WIDTH = CONFIG["image"]["max_width"]
MAX_HEIGHT = CONFIG["image"]["max_height"]

# Cache settings
CACHE_LIMIT = CONFIG["cache"]["limit"]
SAME_DAY_CYCLE = CONFIG["cache"]["same_day_cycle"]

# Cache directory is inside the app's instance_path (writable area for the app)
CACHE_DIR = os.path.join(app.instance_path, "cache")
CACHE_DIR_PHOTO = os.path.join(CACHE_DIR, "photos")
CACHE_DIR_LOG = os.path.join(app.instance_path, "log")

# Cache layout and filenames (must match expectations in app code)
CACHE_DIR_NAME = "cache"
CACHE_ALL_FILENAME = "cache_all.txt"
CACHE_SAME_DAY_FILENAME = "cache_same_day.txt"
CACHE_PHOTOS_SUBDIR = "photos"

# Logging
LOG_DIR_NAME = "log"
LOG_FILENAME = "photomatic.log"

# Keys used by prune_cache() and populated at runtime with MD5 keys for
# same-day images that must be preserved. Must be a mutable list.
SAME_DAY_KEYS = []

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
    root = _normalize_instance_path(instance_root)
    (root / CACHE_DIR_NAME).mkdir(parents=True, exist_ok=True)
    (root / CACHE_DIR_NAME / CACHE_PHOTOS_SUBDIR).mkdir(parents=True, exist_ok=True)
    (root / LOG_DIR_NAME).mkdir(parents=True, exist_ok=True)


# Create cache directories
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(CACHE_DIR_PHOTO, exist_ok=True)
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

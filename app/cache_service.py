"""Build and refresh photo indexes outside slideshow requests."""

import argparse
import datetime
import sqlite3
import time

from . import globals as G
from .cache_manager import build_cache, clear_directory, prune_cache
from .cache_database import (
    cache_built_today,
    get_cache_service_health,
    set_cache_service_health,
)
from .client_photo_tracker import clear_client_photo_tracking, remove_expired_clients
from .utils import initialize_app_state


def build_initial_cache():
    """Rebuild the SQLite photo index whenever the service starts."""
    set_cache_service_health("building", "Photo index rebuild is in progress")
    try:
        build_cache(
            G.PHOTO_ROOT,
            progress_callback=lambda: set_cache_service_health("building"),
        )
        prune_cache()
    except (OSError, sqlite3.Error, TypeError, ValueError, RuntimeError) as exc:
        set_cache_service_health("unhealthy", str(exc))
        raise
    set_cache_service_health("healthy", succeeded=True)


def rebuild_daily_cache():
    """Clear generated images and atomically rebuild the SQLite photo index."""
    set_cache_service_health("building", "Photo index rebuild is in progress")
    G.BUILDING_CACHE = True
    try:
        for cache_dir in (G.CACHE_DIR_PHOTO, G.CACHE_DIR_ICON):
            clear_directory(cache_dir)
        clear_client_photo_tracking()
        build_cache(
            G.PHOTO_ROOT,
            progress_callback=lambda: set_cache_service_health("building"),
        )
        G.BUILDING_CACHE = True
        prune_cache()
        clear_client_photo_tracking()
    finally:
        G.BUILDING_CACHE = False


def run_schedule():
    """Refresh at midnight and recover if the indexes are manually removed."""
    last_build_date = datetime.date.today()
    set_cache_service_health("healthy")
    while True:
        time.sleep(30)
        today = datetime.date.today()
        rebuilt = False
        try:
            if (
                today != last_build_date
                or not cache_built_today()
                or not get_cache_service_health()["ok"]
            ):
                rebuild_daily_cache()
                last_build_date = today
                rebuilt = True
                G.logger.info("[CacheService] Photo cache rebuilt for %s", today)
            removed = remove_expired_clients()
            if removed:
                G.logger.info("[CacheService] Removed %d expired client records", removed)
            set_cache_service_health("healthy", succeeded=rebuilt)
        except (OSError, sqlite3.Error, TypeError, ValueError, RuntimeError) as exc:
            set_cache_service_health("unhealthy", str(exc))
            G.logger.exception("[CacheService] Maintenance failed: %s", exc)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build-once", action="store_true")
    mode.add_argument("--schedule", action="store_true")
    args = parser.parse_args(argv)

    initialize_app_state()
    if args.build_once:
        build_initial_cache()
    else:
        run_schedule()


if __name__ == "__main__":
    main()

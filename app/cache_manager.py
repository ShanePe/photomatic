"""SQLite photo-index construction, photo-date utilities, and image-cache pruning."""

import datetime
import hashlib
import heapq
import os
import random
import re
import shutil
import sqlite3
import tempfile
import time
from contextlib import contextmanager

try:
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover - not available on Windows
    fcntl = None

from flask import g
from PIL import ExifTags, Image, UnidentifiedImageError

from . import globals as G
from .cache_database import connect, open_database
from .session import get_photo_state


def _coerce_non_negative_int(value: object, default: int = 0) -> int:
    """Normalize a session value into a non-negative integer."""
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return max(0, int(value))
    if isinstance(value, str):
        try:
            return max(0, int(value))
        except ValueError:
            return default
    return default


@contextmanager
def _cache_process_lock(lock_name="cache_manager.lock"):
    """Cross-process lock for cache index operations.

    Uses `fcntl.flock` when available (Linux containers). On platforms without
    fcntl (e.g., Windows), this becomes a no-op context manager.
    """
    os.makedirs(G.CACHE_DIR, exist_ok=True)
    lock_path = os.path.join(G.CACHE_DIR, lock_name)
    lock_file = open(lock_path, "w", encoding="utf-8")
    try:
        if fcntl is not None:
            # `fcntl` is available only on Unix-like systems; typing tools may not
            # expose flock/LOCK_* on Windows, so guard the runtime access below.
            flock = getattr(fcntl, "flock", None)
            lock_ex = getattr(fcntl, "LOCK_EX", None)
            lock_un = getattr(fcntl, "LOCK_UN", None)
            if flock is not None and lock_ex is not None:
                flock(lock_file.fileno(), lock_ex)
        yield
    finally:
        if fcntl is not None:
            flock = getattr(fcntl, "flock", None)
            lock_un = getattr(fcntl, "LOCK_UN", None)
            if flock is not None and lock_un is not None:
                flock(lock_file.fileno(), lock_un)
        lock_file.close()


def _count_cached_images_on_disk():
    """Return the count of cached image files currently on disk."""
    if not os.path.isdir(G.CACHE_DIR_PHOTO):
        return 0

    count = 0
    for fn in os.listdir(G.CACHE_DIR_PHOTO):
        if fn.startswith(".") or fn.endswith(".json"):
            continue
        path = os.path.join(G.CACHE_DIR_PHOTO, fn)
        if os.path.isfile(path):
            count += 1
    return count


def _load_same_day_keys_from_database():
    """Load protected same-day image keys from the SQLite photo index."""
    with open_database() as connection:
        paths = connection.execute(
            "SELECT path FROM photos WHERE same_day = 1"
        ).fetchall()
    return {hashlib.md5(path.encode()).hexdigest() for (path,) in paths}


# --- Metadata utilities ---


def write_image_metadata(
    cache_file, width, height, mime_type="image/jpeg", photo_date=None
):
    """
    Store converted-image metadata in the SQLite cache.

    Args:
        cache_file: Path to the cached image file.
        width: Image width in pixels.
        height: Image height in pixels.
        mime_type: MIME type of the image (default: image/jpeg).
        photo_date: Original photo date, if known.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        if hasattr(photo_date, "isoformat"):
            photo_date = photo_date.isoformat()
        with open_database() as connection:
            connection.execute(
                """
                INSERT INTO image_metadata
                    (cache_path, width, height, mime_type, photo_date)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(cache_path) DO UPDATE SET
                    width = excluded.width,
                    height = excluded.height,
                    mime_type = excluded.mime_type,
                    photo_date = COALESCE(
                        excluded.photo_date, image_metadata.photo_date
                    )
                """,
                (cache_file, width, height, mime_type, photo_date),
            )
        return True
    except (OSError, IOError, sqlite3.Error) as e:
        G.logger.warning(
            "[Metadata] Failed to store image metadata for %s: %s", cache_file, e
        )
        return False


def get_image_metadata(cache_file, photo_date=None):
    """
    Return (width, height, mime_type) for a cached JPEG file.

    Read metadata from SQLite, inspecting the image once when no database
    record exists.
    """
    try:
        with open_database() as connection:
            row = connection.execute(
                """
                SELECT width, height, mime_type, photo_date
                FROM image_metadata WHERE cache_path = ?
                """,
                (cache_file,),
            ).fetchone()
        if row:
            if photo_date is not None and row[3] is None:
                write_image_metadata(cache_file, row[0], row[1], row[2], photo_date)
            return row[0], row[1], row[2]
    except sqlite3.Error as e:
        G.logger.warning(
            "[Metadata] Failed to read cached image metadata for %s: %s",
            cache_file,
            e,
        )

    # Read the cached image once when no database record exists.
    try:
        with Image.open(cache_file) as img:
            width, height = img.size
            mime_type = (
                getattr(img, "get_format_mimetype", lambda: None)() or "image/jpeg"
            )
        write_image_metadata(cache_file, width, height, mime_type, photo_date)
        return width, height, mime_type
    except (OSError, UnidentifiedImageError) as e:
        G.logger.error(
            "[Metadata] Failed to open image for metadata %s: %s", cache_file, e
        )
        return None, None, "image/jpeg"


# --- Date utilities ---


def parse_date_from_filename(filename):
    """Extract a date from `filename` using common filename patterns.

    Recognizes `YYYYMMDD` and `YYYY-MM-DD` patterns and returns a
    `datetime.date` instance or `None` if no valid date is found. Date
    tokens must be separated from adjacent letters and digits so IDs and
    hashes are not mistaken for dates.
    """
    patterns = (
        r"(?<![A-Za-z0-9])(\d{4})(\d{2})(\d{2})(?![A-Za-z0-9])",
        r"(?<![A-Za-z0-9])(\d{4})-(\d{2})-(\d{2})(?![A-Za-z0-9])",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, filename):
            try:
                return datetime.date(*(int(part) for part in match.groups()))
            except ValueError:
                continue

    return None


def get_photo_date(path):
    """Return the best-effort `date` for `path`.

    Priority:
      1. Date parsed from filename.
      2. EXIF fields: `DateTimeOriginal`, `DateTimeDigitized`, `DateTime`.
      3. File modification time (mtime).

    Returns a `datetime.date` or `None` if the date cannot be determined.
    """
    filename_date = parse_date_from_filename(os.path.basename(path))
    if filename_date:
        return filename_date

    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if exif:
                for tag, value in exif.items():
                    tag_name = ExifTags.TAGS.get(tag, tag)
                    if tag_name in (
                        "DateTimeOriginal",
                        "DateTimeDigitized",
                        "DateTime",
                    ):
                        try:
                            dt = datetime.datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                            return dt.date()
                        except ValueError as e:
                            G.logger.error(
                                "[DateParser] Bad EXIF date in %s: %s", path, e
                            )
    except UnidentifiedImageError as e:
        G.logger.error("[DateParser] Cannot identify image %s: %s", path, e)
    except OSError as e:
        G.logger.error("[DateParser] I/O error reading %s: %s", path, e)

    try:
        ts = os.path.getmtime(path)
        return datetime.date.fromtimestamp(ts)
    except OSError as e:
        G.logger.error("[DateParser] File timestamp read failed for %s: %s", path, e)

    return None


def get_cached_photo_date(path):
    """Return a photo date from the index, parsing and caching legacy rows once."""
    with open_database() as connection:
        row = connection.execute(
            "SELECT photo_date FROM photos WHERE path = ?", (path,)
        ).fetchone()

    if row is None:
        return get_photo_date(path)
    if row[0] is not None:
        try:
            return datetime.date.fromisoformat(row[0]) if row[0] else None
        except ValueError:
            G.logger.warning("[DateParser] Invalid cached photo date for %s", path)

    photo_date = get_photo_date(path)
    with open_database() as connection:
        connection.execute(
            "UPDATE photos SET photo_date = ? WHERE path = ?",
            (photo_date.isoformat() if photo_date else "", path),
        )
    return photo_date


def format_date_with_suffix(dt):
    """Return date formatted with ordinal suffix, e.g. `1st Jan 2020`."""
    day = dt.day
    if 11 <= day <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix} {dt.strftime('%b %Y')}"


# --- Cache management ---


def prune_cache():
    """
    Prune the photo cache directory so total cached files <= G.CACHE_LIMIT.

    Preserves keys found in `G.SAME_DAY_KEYS`.
    Also removes any orphaned metadata files.
    Thread-safe operation using lock.
    """
    if not G.CACHE_LIMIT_ENABLED:
        return

    with _cache_process_lock("cache_prune.lock"):
        with G.get_cache_lock():
            current_count = _count_cached_images_on_disk()
            G.CACHE_COUNT = current_count

            if current_count <= G.CACHE_LIMIT:
                return

            protected_keys = _load_same_day_keys_from_database()
            if not protected_keys and G.SAME_DAY_KEYS:
                protected_keys = set(G.SAME_DAY_KEYS)

            heap = []
            for fn in os.listdir(G.CACHE_DIR_PHOTO):
                if fn.startswith(".") or fn.endswith(".json"):
                    continue
                f = os.path.join(G.CACHE_DIR_PHOTO, fn)
                if not os.path.isfile(f):
                    continue
                mtime = os.path.getmtime(f)
                heapq.heappush(heap, (mtime, f))

            while current_count > G.CACHE_LIMIT and heap:
                _, f = heapq.heappop(heap)
                key = os.path.basename(f).replace(".jpg", "")
                if key in protected_keys:
                    G.logger.info("[CacheManager] Cache retained (same-day): %s", f)
                    continue
                try:
                    os.remove(f)
                    # Also remove the sidecar metadata file if it exists
                    meta_file = f + ".json"
                    if os.path.exists(meta_file):
                        os.remove(meta_file)
                    with open_database() as connection:
                        connection.execute(
                            "DELETE FROM image_metadata WHERE cache_path = ?", (f,)
                        )
                    current_count -= 1
                    G.CACHE_COUNT = current_count
                    G.logger.info("[CacheManager] Cache pruned: removed %s", f)
                except OSError:
                    G.logger.warning("[CacheManager] Failed to remove cache file %s", f)

    # Clean up any orphaned metadata files (runs outside the lock for perf)
    prune_orphaned_metadata()


def prune_orphaned_metadata():
    """
    Remove orphaned .json metadata files in the photo cache directory.

    A metadata file is considered orphaned if its corresponding image
    file (.jpg) no longer exists. This prevents accumulation of stale
    metadata files over time.

    Thread-safe operation using lock.
    """
    with G.get_cache_lock():
        removed_count = 0
        for fn in os.listdir(G.CACHE_DIR_PHOTO):
            if not fn.endswith(".json"):
                continue
            meta_path = os.path.join(G.CACHE_DIR_PHOTO, fn)
            # Corresponding image file: e.g., abc123.jpg.json -> abc123.jpg
            image_path = meta_path[:-5]  # Remove .json suffix
            if not os.path.exists(image_path):
                try:
                    os.remove(meta_path)
                    removed_count += 1
                except OSError:
                    G.logger.warning(
                        "[CacheManager] Failed to remove orphaned metadata: %s",
                        meta_path,
                    )

        if removed_count > 0:
            G.logger.info(
                "[CacheManager] Pruned %d orphaned metadata files", removed_count
            )


def clear_directory(path):
    """
    Delete all files and folders inside the given directory,
    but leave the directory itself intact.
    """
    if not os.path.isdir(path):
        raise ValueError(f"Not a directory: {path}")

    for entry in os.listdir(path):
        full_path = os.path.join(path, entry)

        if os.path.isfile(full_path) or os.path.islink(full_path):
            os.remove(full_path)
        elif os.path.isdir(full_path):
            shutil.rmtree(full_path)


def clear_entire_cache():
    """
    Completely clear all cached JPEGs and indexed client/photo state.

    Removes:
      - All files under G.CACHE_DIR_PHOTO and G.CACHE_DIR_ICON
      - Indexed photo paths, build metadata, and client tracking state

    Resets:
      - G.CACHE_COUNT
      - G.SAME_DAY_KEYS
      - G.CACHE_DATE

    Returns:
        bool: True if successful, False if errors occurred.
    """
    with G.get_cache_lock():
        errors = False

        G.logger.info(
            "[CacheManager] Full cache clear requested — removing all cached files and indexes."
        )

        # 1. Remove cached JPEGs
        for cache_subdir in (G.CACHE_DIR_PHOTO, G.CACHE_DIR_ICON):
            try:
                clear_directory(cache_subdir)
                G.logger.info(
                    "[CacheManager] Cleared cache directory: %s", cache_subdir
                )
            except OSError as e:
                G.logger.warning(
                    "[CacheManager] Failed to clear cache directory %s: %s",
                    cache_subdir,
                    e,
                )
                errors = True

        try:
            from .cache_database import clear_database

            clear_database()
        except sqlite3.Error as e:
            G.logger.warning(
                "[CacheManager] Failed to clear SQLite cache: %s", e
            )
            errors = True

        # 3. Reset globals
        G.CACHE_COUNT = 0
        G.SAME_DAY_KEYS = set()
        G.CACHE_DATE = None

        G.logger.info(
            "[CacheManager] Cache fully cleared. CACHE_COUNT reset to 0, SAME_DAY_KEYS emptied."
        )

        return not errors


def build_cache(base_dir, progress_callback=None):
    """Scan `base_dir` and transactionally rebuild the SQLite photo index."""
    with _cache_process_lock("cache_build.lock"):
        G.CACHE_DATE = None
        G.BUILDING_CACHE = True
        G.SAME_DAY_KEYS = set()
        staging_path = None

        try:
            staging_file = tempfile.NamedTemporaryFile(
                prefix="photomatic-cache-build-",
                suffix=".sqlite3",
                dir=G.CACHE_DIR,
                delete=False,
            )
            staging_path = staging_file.name
            staging_file.close()
            today = datetime.date.today()
            extensions = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic")
            ignore_dirs = {"thumbnails", "cache", ".git", "__pycache__", "@__thumb"}
            staging_connection = sqlite3.connect(staging_path, timeout=30)
            try:
                staging_connection.execute(
                    """
                    CREATE TABLE photos (
                        path TEXT PRIMARY KEY,
                        same_day INTEGER NOT NULL,
                        photo_date TEXT
                    )
                    """
                )
                with staging_connection:
                    staging_connection.execute("BEGIN")
                    last_progress = time.monotonic()
                    for root, _, files in os.walk(base_dir):
                        if any(ign in root.lower() for ign in ignore_dirs):
                            continue

                        for fn in files:
                            if fn.lower().endswith(extensions):
                                path = os.path.join(root, fn)
                                photo_date = get_photo_date(path)
                                same_day = bool(
                                    photo_date
                                    and photo_date.month == today.month
                                    and photo_date.day == today.day
                                )
                                staging_connection.execute(
                                    """
                                    INSERT OR REPLACE INTO photos
                                        (path, same_day, photo_date)
                                    VALUES (?, ?, ?)
                                    """,
                                    (
                                        path,
                                        int(same_day),
                                        photo_date.isoformat() if photo_date else "",
                                    ),
                                )
                                if same_day:
                                    G.SAME_DAY_KEYS.add(
                                        hashlib.md5(path.encode()).hexdigest()
                                    )
                                if (
                                    progress_callback
                                    and time.monotonic() - last_progress >= 30
                                ):
                                    progress_callback()
                                    last_progress = time.monotonic()
            finally:
                staging_connection.close()

            connection = connect()
            staging_attached = False
            try:
                connection.execute("ATTACH DATABASE ? AS staging", (staging_path,))
                staging_attached = True
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("DELETE FROM photos")
                connection.execute(
                    """
                    INSERT INTO photos (path, same_day, photo_date)
                    SELECT path, same_day, photo_date FROM staging.photos
                    """
                )
                connection.execute(
                    """
                    INSERT INTO cache_metadata (key, value)
                    VALUES ('built_date', ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (today.isoformat(),),
                )
                connection.commit()
            finally:
                if connection.in_transaction:
                    connection.rollback()
                try:
                    if staging_attached:
                        connection.execute("DETACH DATABASE staging")
                finally:
                    connection.close()
            G.CACHE_DATE = today
        finally:
            try:
                if staging_path and os.path.exists(staging_path):
                    os.remove(staging_path)
            finally:
                G.BUILDING_CACHE = False


def pick_file(base_dir, state=None):
    """Select the next photo path for the current browser.

    Behavior:
      - Uses the indexes prepared by the cache service; it never rebuilds them.
      - Serve same-day photos sequentially for the current browser first.
      - Interleave non-same-day photos so same-day entries do not starve the
        general pool. `G.SAME_DAY_CYCLE` controls how many same-day photos appear
        before a random general photo is injected.
      - When the same-day list is exhausted, select from the general photo pool.

    Returns a filesystem path string or `None` if no photos are available.
    """
    if state is None:
        state = getattr(g, "photo_state", None)
        if state is None:
            state = get_photo_state()
            g.photo_state = state

    today = datetime.date.today()
    with open_database() as connection:
        built = connection.execute(
            "SELECT 1 FROM cache_metadata WHERE key = 'built_date'"
        ).fetchone()
        if not built:
            return None

        if state.get("photo_date") != str(today):
            state["photo_date"] = str(today)
            state["photo_index"] = 0
            state["photo_served"] = 0
            state.pop("same_day_exhausted_date", None)

        same_day_exhausted = state.get("same_day_exhausted_date") == str(today)
        all_count = connection.execute(
            "SELECT COUNT(*) FROM photos WHERE same_day = 0"
        ).fetchone()[0]
        same_day_count = connection.execute(
            "SELECT COUNT(*) FROM photos WHERE same_day = 1"
        ).fetchone()[0]
        path = None
        idx = _coerce_non_negative_int(state.get("photo_index", 0))

        if not same_day_exhausted:
            row = connection.execute(
                """
                SELECT path FROM photos WHERE same_day = 1
                ORDER BY path LIMIT 1 OFFSET ?
                """,
                (idx,),
            ).fetchone()
            path = row[0] if row else None
            if not path:
                state["same_day_exhausted_date"] = str(today)

        same_day_streak = _coerce_non_negative_int(state.get("photo_served", 0))
        max_same_day_streak = max(0, int(G.SAME_DAY_CYCLE))

        should_serve_same_day = bool(path) and (
            all_count == 0
            or max_same_day_streak <= 0
            or same_day_streak < max_same_day_streak
        )

        if should_serve_same_day:
            state["photo_index"] = idx + 1
            state["photo_served"] = same_day_streak + 1
            return path

        if all_count > 0:
            state["photo_served"] = 0
            row = connection.execute(
                """
                SELECT path FROM photos WHERE same_day = 0
                ORDER BY path LIMIT 1 OFFSET ?
                """,
                (random.randrange(all_count),),
            ).fetchone()
            return row[0] if row else None

        if same_day_count:
            return connection.execute(
                "SELECT path FROM photos WHERE same_day = 1 ORDER BY path LIMIT 1"
            ).fetchone()[0]
        return None

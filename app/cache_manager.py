"""Cache and photo date utilities.

Responsible for building the line-oriented cache files used by the
slideshow (`cache_all.txt` and `cache_same_day.txt`), determining
photo dates (filename → EXIF → mtime), and pruning the cached JPEGs
under `instance/cache/photos/` while preserving same-day entries.
"""

import datetime
import hashlib
import heapq
import json
import os
import random
import re
import shutil

from flask import session
from PIL import ExifTags, Image, UnidentifiedImageError

from . import globals as G


# --- Metadata utilities ---


def write_image_metadata(cache_file, width, height, mime_type="image/jpeg"):
    """
    Write image metadata to a .json sidecar file.

    Args:
        cache_file: Path to the cached image file.
        width: Image width in pixels.
        height: Image height in pixels.
        mime_type: MIME type of the image (default: image/jpeg).

    Returns:
        bool: True if successful, False otherwise.
    """
    meta_file = cache_file + ".json"
    try:
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump({"width": width, "height": height, "mime_type": mime_type}, f)
        return True
    except (OSError, IOError) as e:
        G.logger.warning(
            "[Metadata] Failed to write metadata file %s: %s", meta_file, e
        )
        return False


def get_image_metadata(cache_file):
    """
    Return (width, height, mime_type) for a cached JPEG file.

    If a metadata .json file exists, use it. Otherwise, open the image,
    extract metadata, write the .json via write_image_metadata, and return.
    """
    meta_file = cache_file + ".json"

    # Try reading existing metadata file
    if os.path.exists(meta_file):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            return meta["width"], meta["height"], meta["mime_type"]
        except (OSError, IOError, json.JSONDecodeError, KeyError) as e:
            G.logger.warning(
                "[Metadata] Failed to read metadata file %s: %s", meta_file, e
            )

    # Fallback: open image, extract metadata, and write it
    try:
        with Image.open(cache_file) as img:
            width, height = img.size
            mime_type = (
                getattr(img, "get_format_mimetype", lambda: None)() or "image/jpeg"
            )
        write_image_metadata(cache_file, width, height, mime_type)
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
    `datetime.date` instance or `None` if no valid date is found.
    """
    m1 = re.search(r"(\d{4})(\d{2})(\d{2})", filename)
    if m1:
        try:
            return datetime.date(int(m1.group(1)), int(m1.group(2)), int(m1.group(3)))
        except ValueError as e:
            G.logger.error(
                "[DateParser] Invalid YYYYMMDD in filename %s: %s", filename, e
            )

    m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", filename)
    if m2:
        try:
            return datetime.date(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
        except ValueError as e:
            G.logger.error(
                "[DateParser] Invalid YYYY-MM-DD in filename %s: %s", filename, e
            )

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
    with G.get_cache_lock():
        if G.CACHE_COUNT <= G.CACHE_LIMIT:
            return

        heap = []
        for fn in os.listdir(G.CACHE_DIR_PHOTO):
            if fn.startswith(".") or fn.endswith(".json"):
                continue
            f = os.path.join(G.CACHE_DIR_PHOTO, fn)
            if not os.path.isfile(f):
                continue
            mtime = os.path.getmtime(f)
            heapq.heappush(heap, (mtime, f))

        while G.CACHE_COUNT > G.CACHE_LIMIT and heap:
            mtime, f = heapq.heappop(heap)
            key = os.path.basename(f).replace(".jpg", "")
            if key in G.SAME_DAY_KEYS:
                G.logger.info("[CacheManager] Cache retained (same-day): %s", f)
                continue
            try:
                os.remove(f)
                # Also remove the sidecar metadata file if it exists
                meta_file = f + ".json"
                if os.path.exists(meta_file):
                    os.remove(meta_file)
                G.CACHE_COUNT -= 1
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
    Completely clear all cached JPEGs and cache text files.

    Removes:
      - All files under G.CACHE_DIR_PHOTO and G.CACHE_DIR_ICON
      - cache_all.txt
      - cache_same_day.txt

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

        # 2. Remove cache text files
        for txt in ("cache_all.txt", "cache_same_day.txt"):
            txt_path = os.path.join(G.CACHE_DIR, txt)
            try:
                os.remove(txt_path)
                G.logger.info("[CacheManager] Removed cache index file: %s", txt_path)
            except FileNotFoundError:
                G.logger.info(
                    "[CacheManager] Cache index file not found (already cleared): %s",
                    txt_path,
                )
            except OSError as e:
                G.logger.warning(
                    "[CacheManager] Failed to remove cache index file %s: %s",
                    txt_path,
                    e,
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


# --- Cache file utilities ---


def get_line(filepath, file_line_idx):
    """Return the 0-based `file_line_idx` line from `filepath` or `None`.

    This reads the file sequentially and does not load the whole file into memory.
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i == file_line_idx:
                    return line.strip()
    except FileNotFoundError:
        return None
    return None


def count_lines(filepath):
    """Return number of lines in `filepath` or 0 if it doesn't exist."""
    try:
        with open(filepath, encoding="utf-8") as f:
            return sum(1 for _ in f)
    except FileNotFoundError:
        return 0


def build_cache(base_dir):
    """Scan `base_dir` and atomically rebuild cache files.

    Writes two line-oriented files into `G.CACHE_DIR`:
      - `cache_all.txt`: all photo paths not matching today's month/day
      - `cache_same_day.txt`: paths matching today's month/day across years

    Also populates `G.SAME_DAY_KEYS` with MD5(path) keys to prevent
    `prune_cache()` from deleting those JPEGs.
    """
    G.CACHE_DATE = None
    G.BUILDING_CACHE = True
    G.SAME_DAY_KEYS = set()

    try:
        today = datetime.date.today()
        extensions = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic")
        ignore_dirs = {"thumbnails", "cache", ".git", "__pycache__", "@__thumb"}
        all_path = os.path.join(G.CACHE_DIR, "cache_all.txt")
        same_day_path = os.path.join(G.CACHE_DIR, "cache_same_day.txt")

        with open(all_path, "w", encoding="utf-8") as f_all, open(
            same_day_path, "w", encoding="utf-8"
        ) as f_same:
            for root, _, files in os.walk(base_dir):
                if any(ign in root.lower() for ign in ignore_dirs):
                    continue

                for fn in files:
                    if fn.lower().endswith(extensions):
                        path = os.path.join(root, fn)
                        photo_date = get_photo_date(path)
                        if (
                            photo_date
                            and photo_date.month == today.month
                            and photo_date.day == today.day
                        ):
                            f_same.write(path + "\n")
                            key_hash = hashlib.md5(path.encode()).hexdigest()
                            G.SAME_DAY_KEYS.add(key_hash)
                        else:
                            f_all.write(path + "\n")

        G.CACHE_DATE = today
    finally:
        G.BUILDING_CACHE = False


def pick_file(base_dir):
    """Select the next photo path for the current session.

    Behavior:
      - If the cache is stale or missing, rebuild via `build_cache()`.
      - Serve same-day photos sequentially per-session using `session['photo_index']`.
      - When same-day list is exhausted, pick a random line from `cache_all.txt`.

    Returns a filesystem path string or `None` if no photos are available.
    """
    today = datetime.date.today()
    all_file = os.path.join(G.CACHE_DIR, "cache_all.txt")
    same_day_file = os.path.join(G.CACHE_DIR, "cache_same_day.txt")

    if G.CACHE_DATE != today or not os.path.exists(all_file):
        build_cache(base_dir)

    # Serve next same-day photo for this session
    if "photo_date" not in session or session["photo_date"] != str(today):
        session["photo_date"] = str(today)
        session["photo_index"] = 0

    idx = session.get("photo_index", 0)
    path = get_line(same_day_file, idx)
    if path:
        session["photo_index"] = idx + 1
        return path

    total = count_lines(all_file)
    if total > 0:
        rand_idx = random.randrange(total)
        return get_line(all_file, rand_idx)

    return None

"""Cache and photo date utilities.

Responsible for building the line-oriented cache files used by the
slideshow (`cache_all.txt` and `cache_same_day.txt`), determining
photo dates (filename → EXIF → mtime), and pruning the cached JPEGs
under `instance/cache/photos/` while preserving same-day entries.
"""

import datetime
import hashlib
import heapq
import os
import random
import re

from flask import session
from PIL import ExifTags, Image, UnidentifiedImageError

from . import globals as G


def prune_cache():
    """
    Prune the photo cache directory so total cached files <= G.CACHE_LIMIT.
    Preserves keys found in `G.SAME_DAY_KEYS`.
    """
    if G.CACHE_COUNT <= G.CACHE_LIMIT:
        return

    heap = []
    for fn in os.listdir(G.CACHE_DIR_PHOTO):
        if fn.startswith("."):
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
            G.logger.info("Cache retained (same-day): %s", f)
            continue
        try:
            os.remove(f)
            G.CACHE_COUNT -= 1
            G.logger.info("Cache pruned: removed %s", f)
        except OSError:
            G.logger.warning("Failed to remove cache file %s", f)


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
            G.logger.error("Invalid YYYYMMDD in filename %s: %s", filename, e)

    m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", filename)
    if m2:
        try:
            return datetime.date(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
        except ValueError as e:
            G.logger.error("Invalid YYYY-MM-DD in filename %s: %s", filename, e)

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
        img = Image.open(path)
        exif = img.getexif()
        if exif:
            for tag, value in exif.items():
                tag_name = ExifTags.TAGS.get(tag, tag)
                if tag_name in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
                    try:
                        dt = datetime.datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                        return dt.date()
                    except ValueError as e:
                        G.logger.error("Bad EXIF date in %s: %s", path, e)
    except UnidentifiedImageError as e:
        G.logger.error("Cannot identify image %s: %s", path, e)
    except OSError as e:
        G.logger.error("I/O error reading %s: %s", path, e)

    try:
        ts = os.path.getmtime(path)
        return datetime.date.fromtimestamp(ts)
    except OSError as e:
        G.logger.error("File timestamp read failed for %s: %s", path, e)

    return None


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
    # Coerce SAME_DAY_KEYS to a fresh mutable list to avoid issues if an
    # earlier import created an immutable object under a different module name.
    G.SAME_DAY_KEYS = []

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
                            G.SAME_DAY_KEYS.append(key_hash)
                        else:
                            f_all.write(path + "\n")

        G.CACHE_DATE = today
    finally:
        G.BUILDING_CACHE = False


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


def format_date_with_suffix(dt):
    """Return date formatted with ordinal suffix, e.g. `1st Jan 2020`."""
    day = dt.day
    if 11 <= day <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix} {dt.strftime('%b %Y')}"


def clear_entire_cache():
    """
    Completely clear all cached JPEGs and cache text files.

    Removes:
      - All files under G.CACHE_DIR_PHOTO
      - cache_all.txt
      - cache_same_day.txt

    Resets:
      - G.CACHE_COUNT
      - G.SAME_DAY_KEYS
      - G.CACHE_DATE

    Returns:
        bool: True if successful, False if errors occurred.
    """
    errors = False

    G.logger.info("Full cache clear requested — removing all cached files and indexes.")

    # 1. Remove cached JPEGs
    try:
        for fn in os.listdir(G.CACHE_DIR_PHOTO):
            if fn.startswith("."):
                continue
            f = os.path.join(G.CACHE_DIR_PHOTO, fn)
            if os.path.isfile(f):
                try:
                    os.remove(f)
                    G.logger.info("Removed cached photo: %s", f)
                except OSError as e:
                    G.logger.warning("Failed to remove cached photo %s: %s", f, e)
                    errors = True
    except FileNotFoundError:
        G.logger.warning("Cache photo directory missing: %s", G.CACHE_DIR_PHOTO)

    # 2. Remove cache text files
    for txt in ("cache_all.txt", "cache_same_day.txt"):
        path = os.path.join(G.CACHE_DIR, txt)
        try:
            os.remove(path)
            G.logger.info("Removed cache index file: %s", path)
        except FileNotFoundError:
            G.logger.info("Cache index file not found (already cleared): %s", path)
        except OSError as e:
            G.logger.warning("Failed to remove cache index file %s: %s", path, e)
            errors = True

    # 3. Reset globals
    G.CACHE_COUNT = 0
    G.SAME_DAY_KEYS = []
    G.CACHE_DATE = None

    G.logger.info("Cache fully cleared. CACHE_COUNT reset to 0, SAME_DAY_KEYS emptied.")

    return not errors

"""
Photomatic Flask Application
============================

This Flask application serves a photo slideshow from a local directory. It supports
multiple image formats, including HEIC (converted to JPEG on the fly). The slideshow
prefers photos taken on the same calendar day across different years. Each browser
session gets its own sequence: all same-day photos are served in order before falling
back to random from the entire collection.

Caching:
--------
- Photo lists are cached as line-oriented text files (one path per line).
- Cache files are stored in a writable directory under the Flask app's instance_path
  (e.g. <project>/instance/photo_cache).
- This design avoids keeping large lists in memory; only the current line is read
  per request.
- Cache is rebuilt once per day or when missing.

Session Behavior:
-----------------
- Each browser session tracks its own index through today's photos.
- On the first request of the day, the session index resets to 0.
- The session then receives each same-day photo sequentially.
- Once all same-day photos are exhausted, the session falls back to random selection
  from the entire photo collection.

Date Resolution Priority:
-------------------------
1. Filename patterns (YYYYMMDD or YYYY-MM-DD).
2. EXIF metadata (DateTimeOriginal, DateTimeDigitized, DateTime).
3. File modified time.

Error Handling:
---------------
- Narrow exception handling (ValueError, OSError, UnidentifiedImageError).
- Error logging uses lazy % formatting for efficiency.

Usage:
------
    python app.py --photos /path/to/photos --port 5000

Arguments:
----------
--photos   Base folder containing images (required).
--port     Port to run the server (default: 5000).

Endpoints:
----------
/          Serves the main slideshow page.
/random    Serves an image:
             - Sequential same-day photo (per session).
             - Falls back to random photo if none available.
"""

# pylint: disable=global-statement
# pylint: disable=broad-except

import argparse
import io
import os
import random
import logging
import hashlib
from logging.handlers import RotatingFileHandler
import re
import datetime

from flask import Flask, render_template, send_file, session, request
from PIL import Image, ExifTags, UnidentifiedImageError, ImageDraw, ImageFont, ImageOps
from pillow_heif import register_heif_opener

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "..", "templates")

# Initialize Flask app
app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.secret_key = "replace_with_a_secure_random_key"  # required for session handling

# Register HEIF opener so Pillow can read HEIC files
register_heif_opener()

# Global configuration
PHOTO_ROOT = None
CACHE_DATE = None

# Cache directory is inside the app's instance_path (writable area for the app)
CACHE_DIR = os.path.join(app.instance_path, "cache")
CACHE_DIR_PHOTO = os.path.join(CACHE_DIR, "photos")
CACHE_DIR_LOG = os.path.join(app.instance_path, "log")

BUILDING_CACHE = False
MAX_WIDTH = 2080
MAX_HEIGHT = 768
CACHE_LIMIT = 2000  # max number of cached files
CACHE_COUNT = 0
SAME_DAY_KEYS = []

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(CACHE_DIR_PHOTO, exist_ok=True)
os.makedirs(CACHE_DIR_LOG, exist_ok=True)

CACHE_COUNT = sum(
    1
    for entry in os.listdir(CACHE_DIR_PHOTO)
    if os.path.isfile(os.path.join(CACHE_DIR_PHOTO, entry))
)

# Configure logging: one file per day
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


@app.before_request
def reset_on_first_visit():
    # If this is a brand new session (no cookie yet)
    if "initialized" not in session:
        # Reset your slideshow index
        session.clear()
        session["photo_index"] = 0
        session["initialized"] = True


def resize_and_compress(
    path: str, overlay_text: str = "", quality: int = 75
) -> io.BytesIO:
    """
    Resize/compress image with optional overlay text, using local cache.
    Logs original vs compressed file size.
    """
    global CACHE_COUNT

    key_hash = hashlib.md5(path.encode()).hexdigest()
    cache_file = os.path.join(CACHE_DIR_PHOTO, f"{key_hash}.jpg")

    # --- Check cache ---
    if os.path.exists(cache_file):
        with open(cache_file, "rb") as f:
            buf = io.BytesIO(f.read())
            buf.seek(0)
        logger.info(
            "Cache hit for %s (size %.1f KB)", path, os.path.getsize(cache_file) / 1024
        )
        return buf

    # --- Process image ---
    original_size = os.path.getsize(path)
    with Image.open(path) as img:
        # Normalize orientation based on EXIF metadata, then drop EXIF
        img = ImageOps.exif_transpose(img)

        width, height = img.size
        if width > MAX_WIDTH or height > MAX_HEIGHT:
            img.thumbnail((MAX_WIDTH, MAX_HEIGHT), Image.Resampling.LANCZOS)

        if overlay_text:
            draw = ImageDraw.Draw(img)
            font = ImageFont.load_default(30)
            x, y = 20, 20
            draw.text((x + 2, y + 2), overlay_text, font=font, fill="black")
            draw.text((x, y), overlay_text, font=font, fill="white")

        buf = io.BytesIO()
        # Save without EXIF metadata
        img.convert("RGB").save(
            buf, format="JPEG", quality=quality, optimize=True, progressive=True
        )
        buf.seek(0)

        # Save to cache
        with open(cache_file, "wb") as f:
            f.write(buf.getvalue())

        CACHE_COUNT = CACHE_COUNT + 1

    compressed_size = os.path.getsize(cache_file)

    # --- Log sizes ---
    logger.info(
        "Processed %s | Original: %.1f KB | Compressed: %.1f KB | Overlay: %s",
        os.path.basename(path),
        original_size / 1024,
        compressed_size / 1024,
        overlay_text or "None",
    )

    # --- Enforce cache limit ---
    prune_cache()

    return buf


def prune_cache():
    global CACHE_COUNT
    # --- Enforce cache limit ---
    if CACHE_COUNT > CACHE_LIMIT:
        cached_files = sorted(
            (
                (os.path.getmtime(f), f)
                for f in [
                    os.path.join(CACHE_DIR_PHOTO, fn)
                    for fn in os.listdir(CACHE_DIR_PHOTO)
                ]
            ),
            key=lambda x: x[0],
        )

        for _, f in cached_files:
            try:
                if CACHE_COUNT <= CACHE_LIMIT:
                    break

                # Skip removal if this cache file corresponds to a same-day photo
                # We check by hash: the cache filename is md5(path|overlay|quality).jpg
                if os.path.basename(f).replace(".jpg", "") in SAME_DAY_KEYS:
                    logger.info("Cache retained (same-day): %s", f)
                    continue

                os.remove(f)
                CACHE_COUNT -= 1
                logger.info("Cache pruned: removed %s", f)
            except OSError:
                logger.warning("Failed to remove cache file %s", f)


def convert_heic_to_jpg(heic_path):
    """
    Convert an Apple HEIC image file to JPEG format.
    """
    try:
        img = Image.open(heic_path)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        return buf
    except UnidentifiedImageError as e:
        logger.error("Cannot identify HEIC image %s: %s", heic_path, e)
        raise
    except OSError as e:
        logger.error("I/O error converting HEIC %s: %s", heic_path, e)
        raise


def parse_date_from_filename(filename):
    """
    Extract a date from filename patterns (YYYYMMDD or YYYY-MM-DD).
    """
    m1 = re.search(r"(\d{4})(\d{2})(\d{2})", filename)
    if m1:
        try:
            return datetime.date(int(m1.group(1)), int(m1.group(2)), int(m1.group(3)))
        except ValueError as e:
            logger.error("Invalid YYYYMMDD in filename %s: %s", filename, e)

    m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", filename)
    if m2:
        try:
            return datetime.date(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
        except ValueError as e:
            logger.error("Invalid YYYY-MM-DD in filename %s: %s", filename, e)

    return None


def get_photo_date(path):
    """
    Determine the date associated with a photo.
    Priority: filename → EXIF → file modified time.
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
                        logger.error("Bad EXIF date in %s: %s", path, e)
    except UnidentifiedImageError as e:
        logger.error("Cannot identify image %s: %s", path, e)
    except OSError as e:
        logger.error("I/O error reading %s: %s", path, e)

    try:
        ts = os.path.getmtime(path)
        return datetime.date.fromtimestamp(ts)
    except OSError as e:
        logger.error("File timestamp read failed for %s: %s", path, e)

    return None


def build_cache(base_dir):
    """
    Scan the photo directory and build cache lists for today's date.

    Creates two line-oriented text files in the cache directory:
        - cache_all.txt: All photo paths (excluding same-day photos).
        - cache_same_day.txt: Photos matching today's month/day across years.

    Args:
        base_dir (str): Base directory containing photos.

    Side effects:
        Writes cache files and updates the global CACHE_DATE marker.
    """
    global CACHE_DATE
    global BUILDING_CACHE
    global SAME_DAY_KEYS

    CACHE_DATE = None
    BUILDING_CACHE = True
    SAME_DAY_KEYS.clear()

    try:
        today = datetime.date.today()
        extensions = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic")
        ignore_dirs = {"thumbnails", "cache", ".git", "__pycache__", "@__thumb"}
        all_path = os.path.join(CACHE_DIR, "cache_all.txt")
        same_day_path = os.path.join(CACHE_DIR, "cache_same_day.txt")

        with open(all_path, "w", encoding="utf-8") as f_all, open(
            same_day_path, "w", encoding="utf-8"
        ) as f_same:
            for root, _, files in os.walk(base_dir):
                if any(ign in root.lower() for ign in ignore_dirs):
                    continue

                for f in files:
                    if f.lower().endswith(extensions):
                        path = os.path.join(root, f)
                        photo_date = get_photo_date(path)
                        if (
                            photo_date
                            and photo_date.month == today.month
                            and photo_date.day == today.day
                        ):
                            f_same.write(path + "\n")
                            key_hash = hashlib.md5(path.encode()).hexdigest()
                            SAME_DAY_KEYS.append(key_hash)
                        else:
                            f_all.write(path + "\n")

        CACHE_DATE = today
    finally:
        BUILDING_CACHE = False


def get_line(filepath, file_line_idx):
    """
    Return the line at a given index from a text file.

    Args:
        filepath (str): Path to the text file.
        file_line_idx (int): 0-based line index.

    Returns:
        str | None: Line content (stripped), or None if out of range or file missing.
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
    """
    Count the number of lines in a text file.

    Args:
        filepath (str): Path to the text file.

    Returns:
        int: Number of lines, or 0 if file not found.
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            return sum(1 for _ in f)
    except FileNotFoundError:
        return 0


def pick_file(base_dir):
    """
    Select a photo for the current session.

    Logic:
        - Serve sequential same-day photos per session using a session index.
        - Once exhausted, fall back to random from all photos.

    Args:
        base_dir (str): Base directory containing photos.

    Returns:
        str | None: Path to the selected photo, or None if none available.
    """
    today = datetime.date.today()
    all_file = os.path.join(CACHE_DIR, "cache_all.txt")
    same_day_file = os.path.join(CACHE_DIR, "cache_same_day.txt")

    # Rebuild cache if date changed or cache missing
    if CACHE_DATE != today or not os.path.exists(all_file):
        build_cache(base_dir)
        session["photo_date"] = str(today)
        session["photo_index"] = 0

    # Initialize or reset session state when day changes
    if "photo_date" not in session or session["photo_date"] != str(today):
        session["photo_date"] = str(today)
        session["photo_index"] = 0

    # Serve next same-day photo for this session
    idx = session.get("photo_index", 0)
    path = get_line(same_day_file, idx)
    if path:
        session["photo_index"] = idx + 1
        return path

    # Fallback: random from all photos (without loading entire file)
    total = count_lines(all_file)
    if total > 0:
        rand_idx = random.randrange(total)
        return get_line(all_file, rand_idx)

    return None


def format_date_with_suffix(dt):
    day = dt.day
    # Determine suffix
    if 11 <= day <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    # Format with abbreviated month
    return f"{day}{suffix} {dt.strftime('%b %Y')}"


@app.route("/")
def index():
    """
    Serve the main slideshow page.

    Returns:
        Response: Rendered index.html template.
    """
    return render_template("index.html")


@app.route("/random")
def random_image():
    """
    Serve an image from the photo directory.

    Behavior:
        - Sequential same-day photo per session.
        - Falls back to random from the entire collection.

    Returns:
        Response: The image file or converted HEIC JPEG as a Flask response.

    Status codes:
        200: Image served successfully.
        404: No images found.
        500: Error while serving image.
    """
    try:
        if BUILDING_CACHE:
            return "Cache is being built, please try again shortly.", 503

        path = pick_file(PHOTO_ROOT)
        if not path:
            return "No images found", 404

        client_ip = request.remote_addr
        user_agent = request.headers.get("User-Agent")

        photo_date = get_photo_date(path)

        # --- Process into buffer ---
        buf = resize_and_compress(
            path, format_date_with_suffix(photo_date) if photo_date else "", 50
        )

        # --- Gather metadata about buf ---
        compressed_size = len(buf.getvalue())  # size in bytes
        width, height = None, None
        try:
            with Image.open(buf) as img:
                width, height = img.size
                mime_type = img.get_format_mimetype() or "image/jpeg"
            buf.seek(0)
        except Exception:
            mime_type = "image/jpeg"

        # --- Log details about returned buffer ---
        logger.info(
            "Served buffer from %s | Compressed size: %.1f KB | Dimensions: %sx%s | MIME: %s | "
            "Client IP: %s | UA: %s | Photo index: %s",
            os.path.basename(path),
            compressed_size / 1024,
            width,
            height,
            mime_type,
            client_ip,
            user_agent,
            session.get("photo_index"),
        )

        return send_file(buf, mimetype="image/jpeg")

    except (OSError, UnidentifiedImageError, ValueError) as e:
        logger.error("Error serving image: %s", e)
        return f"Error: {e}", 500


def parse_args():
    """
    Parse command-line arguments for the application.

    Returns:
        argparse.Namespace: Parsed arguments containing:
            - photos (str): Base folder containing images.
            - port (int): Port to run the server.
    """
    parser = argparse.ArgumentParser(description="Photo slideshow")
    parser.add_argument("--photos", required=True, help="Base folder containing images")
    parser.add_argument("--port", type=int, default=5000, help="Port to run the server")
    return parser.parse_args()


def run_app(arguments):
    """
    Configure global settings and run the Flask application.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.
    """
    global PHOTO_ROOT
    PHOTO_ROOT = arguments.photos

    if CACHE_COUNT > CACHE_LIMIT:
        logger.info(
            "Initial cache count: %s, pruning to limit %s", CACHE_COUNT, CACHE_LIMIT
        )
        prune_cache()  # initial prune at default quality

    app.run(debug=True, host="0.0.0.0", port=arguments.port)


if __name__ == "__main__":
    args = parse_args()
    run_app(args)

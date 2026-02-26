"""Image utilities: resizing, compression, and HEIC conversion.

This module handles reading images via Pillow, normalizing orientation,
resizing to configured limits, drawing optional overlay text, and
writing/reading cached JPEGs under the Flask instance cache directory.
"""

import hashlib
import os
import atexit

from PIL import Image, ImageDraw, ImageFont, ImageOps
import requests

from . import globals as G
from .cache_manager import prune_cache, write_image_metadata

# HTTP session for connection pooling and reuse
_SESSION_CONTAINER: dict[str, requests.Session | None] = {"session": None}


def get_requests_session():
    """Get or create a persistent requests session for connection pooling."""
    if _SESSION_CONTAINER["session"] is None:
        _SESSION_CONTAINER["session"] = requests.Session()
        # Register cleanup on app shutdown
        atexit.register(cleanup_requests_session)
    return _SESSION_CONTAINER["session"]


def cleanup_requests_session():
    """Clean up the requests session on shutdown."""
    if _SESSION_CONTAINER["session"] is not None:
        _SESSION_CONTAINER["session"].close()
        _SESSION_CONTAINER["session"] = None


FONT_PATH = os.path.join(
    os.path.dirname(__file__), "assets", "fonts", "NotoSans-Regular.ttf"
)


def draw_text(draw, font, text, x, y):
    """Draw text with a drop shadow, matching original behaviour."""
    draw.text((x + 2, y + 2), text, font=font, fill="black")  # shadow
    draw.text((x, y), text, font=font, fill="white")  # foreground


def load_scaled_font(height, scale=0.01):
    """Load a truetype font scaled to image height."""
    font_size = max(12, int(height * scale))

    try:
        return ImageFont.truetype(FONT_PATH, font_size)
    except OSError:
        return ImageFont.load_default()


def apply_overlays(img, overlays: dict[str, str]):
    """Apply overlay text to the four corners of the image."""
    draw = ImageDraw.Draw(img)
    width, height = img.size

    font = load_scaled_font(height, scale=0.01)

    for position, text in overlays.items():
        if not text:
            continue

        # Measure text
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        padding = int(height * 0.02)  # scale padding too

        if position == "top_left":
            x, y = padding, padding

        elif position == "top_right":
            x = width - tw - padding
            y = padding

        elif position == "bottom_left":
            x = padding
            y = height - th - padding

        elif position == "bottom_right":
            x = width - tw - padding
            y = height - th - padding

        else:
            continue

        draw_text(draw, font, text, x, y)


def resize_and_compress(
    path: str,
    overlays: dict[str, str] | None = None,
    quality: int = 75,
) -> str:
    """
    Resize/compress image with optional overlay text, using local cache.
    Returns the path to the cached JPEG file.
    Ensures proper resource cleanup even on exceptions.
    """

    overlays = overlays or {}

    key_hash = hashlib.md5(path.encode()).hexdigest()
    cache_file = os.path.join(G.CACHE_DIR_PHOTO, f"{key_hash}.jpg")

    # --- Cache check ---
    if os.path.exists(cache_file):
        G.logger.info(
            "Cache hit for %s (size %.1f KB)", path, os.path.getsize(cache_file) / 1024
        )
        return cache_file

    original_size = os.path.getsize(path)
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)

            width, height = img.size
            if width > G.MAX_WIDTH or height > G.MAX_HEIGHT:
                img.thumbnail((G.MAX_WIDTH, G.MAX_HEIGHT), Image.Resampling.LANCZOS)

            # Apply overlay text
            if overlays:
                apply_overlays(img, overlays)

            # Save to cache
            rgb_img = img.convert("RGB")
            rgb_img.save(
                cache_file,
                format="JPEG",
                quality=quality,
                optimize=True,
                progressive=True,
            )

            # Write metadata file (use final dimensions after thumbnail)
            final_width, final_height = rgb_img.size
            write_image_metadata(cache_file, final_width, final_height, "image/jpeg")

            with G.get_cache_lock():
                G.CACHE_COUNT += 1

        compressed_size = os.path.getsize(cache_file)

        G.logger.info(
            "Processed %s | Original: %.1f KB | Compressed: %.1f KB | Overlays: %s",
            os.path.basename(path),
            original_size / 1024,
            compressed_size / 1024,
            overlays,
        )

        # Optionally force garbage collection after large image ops
        import gc

        gc.collect()

        prune_cache()

        return cache_file
    except Exception as e:
        G.logger.error("Error processing image %s: %s", path, e)
        raise e

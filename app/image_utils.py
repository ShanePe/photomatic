"""Image utilities: resizing, compression, and HEIC conversion.

This module handles reading images via Pillow, normalizing orientation,
resizing to configured limits, drawing optional overlay text, and
writing/reading cached JPEGs under the Flask instance cache directory.
"""

import io
import os
import hashlib

from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import globals as G
from .cache_manager import prune_cache

import io
import os
import hashlib
from PIL import Image, ImageOps, ImageDraw, ImageFont


def draw_text(draw, font, text, x, y):
    """Draw text with a drop shadow, matching original behaviour."""
    draw.text((x + 2, y + 2), text, font=font, fill="black")  # shadow
    draw.text((x, y), text, font=font, fill="white")  # foreground


def apply_overlays(img, overlays: dict[str, str]):
    """Apply overlay text to the four corners of the image."""
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    width, height = img.size

    for position, text in overlays.items():
        if not text:
            continue

        # Measure text once
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        if position == "top_left":
            x, y = 20, 20

        elif position == "top_right":
            x = width - tw - 20
            y = 20

        elif position == "bottom_left":
            x = 20
            y = height - th - 20

        elif position == "bottom_right":
            x = width - tw - 20
            y = height - th - 20

        else:
            continue  # ignore unknown keys

        draw_text(draw, font, text, x, y)


def resize_and_compress(
    path: str,
    overlays: dict[str, str] | None = None,
    quality: int = 75,
) -> io.BytesIO:
    """
    Resize/compress image with optional overlay text, using local cache.
    Returns an in-memory `BytesIO` containing a JPEG.
    """

    overlays = overlays or {}

    key_hash = hashlib.md5(path.encode()).hexdigest()
    cache_file = os.path.join(G.CACHE_DIR_PHOTO, f"{key_hash}.jpg")

    # --- Cache check ---
    if os.path.exists(cache_file):
        with open(cache_file, "rb") as f:
            buf = io.BytesIO(f.read())
            buf.seek(0)
        G.logger.info(
            "Cache hit for %s (size %.1f KB)", path, os.path.getsize(cache_file) / 1024
        )
        return buf

    original_size = os.path.getsize(path)

    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)

        width, height = img.size
        if width > G.MAX_WIDTH or height > G.MAX_HEIGHT:
            img.thumbnail((G.MAX_WIDTH, G.MAX_HEIGHT), Image.Resampling.LANCZOS)

        # Apply overlay text
        if overlays:
            apply_overlays(img, overlays)

        # Save to buffer
        buf = io.BytesIO()
        img.convert("RGB").save(
            buf, format="JPEG", quality=quality, optimize=True, progressive=True
        )
        buf.seek(0)

        # Save to cache
        with open(cache_file, "wb") as f:
            f.write(buf.getvalue())

        G.CACHE_COUNT += 1

    compressed_size = os.path.getsize(cache_file)

    G.logger.info(
        "Processed %s | Original: %.1f KB | Compressed: %.1f KB | Overlays: %s",
        os.path.basename(path),
        original_size / 1024,
        compressed_size / 1024,
        overlays,
    )

    prune_cache()

    return buf

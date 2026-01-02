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


def resize_and_compress(
    path: str,
    overlay_text: str = "",
    quality: int = 75,
    bottom_right_text: str = "",
) -> io.BytesIO:
    """
    Resize/compress image with optional overlay text, using local cache.
    Returns an in-memory `BytesIO` containing a JPEG.
    """
    key_hash = hashlib.md5(path.encode()).hexdigest()
    cache_file = os.path.join(G.CACHE_DIR_PHOTO, f"{key_hash}.jpg")

    # --- Check cache ---
    if os.path.exists(cache_file):
        with open(cache_file, "rb") as f:
            buf = io.BytesIO(f.read())
            buf.seek(0)
        G.logger.info(
            "Cache hit for %s (size %.1f KB)", path, os.path.getsize(cache_file) / 1024
        )
        return buf

    original_size = os.path.getsize(path)

    # Default bottom-right text to the file's base name when not provided
    if not bottom_right_text:
        bottom_right_text = os.path.basename(path)
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)

        width, height = img.size
        if width > G.MAX_WIDTH or height > G.MAX_HEIGHT:
            img.thumbnail((G.MAX_WIDTH, G.MAX_HEIGHT), Image.Resampling.LANCZOS)

        # Re-read actual size after any resizing
        width, height = img.size

        draw = None
        font = None
        if overlay_text or bottom_right_text:
            draw = ImageDraw.Draw(img)
            font = ImageFont.load_default()

        if overlay_text and draw:
            x, y = 20, 20
            # drop shadow then white text
            draw.text((x + 2, y + 2), overlay_text, font=font, fill="black")
            draw.text((x, y), overlay_text, font=font, fill="white")

        if bottom_right_text and draw:
            # measure text size using textbbox
            bbox = draw.textbbox((0, 0), bottom_right_text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]

            br_x = max(10, width - tw - 20)
            br_y = max(10, height - th - 20)
            draw.text((br_x + 2, br_y + 2), bottom_right_text, font=font, fill="black")
            draw.text((br_x, br_y), bottom_right_text, font=font, fill="white")

        buf = io.BytesIO()
        img.convert("RGB").save(
            buf, format="JPEG", quality=quality, optimize=True, progressive=True
        )
        buf.seek(0)

        # Save to cache
        with open(cache_file, "wb") as f:
            f.write(buf.getvalue())

        # update global cache count
        G.CACHE_COUNT = G.CACHE_COUNT + 1

    compressed_size = os.path.getsize(cache_file)

    G.logger.info(
        "Processed %s | Original: %.1f KB | Compressed: %.1f KB | Overlay: %s",
        os.path.basename(path),
        original_size / 1024,
        compressed_size / 1024,
        overlay_text or "None",
    )

    prune_cache()

    return buf

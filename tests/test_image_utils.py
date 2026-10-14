"""Tests for image processing utilities.

Covers image resizing, compression, font caching, and overlay functionality.
"""

import json
import os
from PIL import Image

from app import image_utils
from app import globals as G


def make_image(path, size=(300, 200), color=(200, 100, 50)):
    """Create a test JPEG image at the specified path.

    Args:
        path: File path where the image will be saved.
        size: Tuple of (width, height) in pixels.
        color: RGB tuple for the image fill color.
    """
    img = Image.new("RGB", size, color)
    img.save(path, format="JPEG")


def setup_cache_dirs(tmp_path):
    """Helper to set up cache directories for tests."""
    inst = tmp_path / "instance"
    inst.mkdir(exist_ok=True)
    G.app.instance_path = str(inst)
    G.CACHE_DIR = os.path.join(G.app.instance_path, "cache")
    G.CACHE_DIR_PHOTO = os.path.join(G.CACHE_DIR, "photos")
    os.makedirs(G.CACHE_DIR_PHOTO, exist_ok=True)
    return G.CACHE_DIR, G.CACHE_DIR_PHOTO


def test_resize_and_compress_creates_cache(tmp_path):
    """Test that resize_and_compress creates a cached PNG file."""
    photos = tmp_path / "photos"
    photos.mkdir()
    img_path = photos / "test.jpg"
    make_image(str(img_path))

    inst = tmp_path / "instance"
    inst.mkdir()
    G.app.instance_path = str(inst)
    G.CACHE_DIR = os.path.join(G.app.instance_path, "cache")
    G.CACHE_DIR_PHOTO = os.path.join(G.CACHE_DIR, "photos")
    os.makedirs(G.CACHE_DIR_PHOTO, exist_ok=True)

    cache_file_path = image_utils.resize_and_compress(
        str(img_path), {"top_left": "Test Overlay"}, 80
    )

    # Read the cached file and verify it's a valid PNG
    with open(cache_file_path, "rb") as f:
        data = f.read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"

    # cache file should exist
    # pylint: disable=protected-access
    key_hash = image_utils._build_cache_key(
        str(img_path), {"top_left": "Test Overlay"}, 80
    )
    # pylint: enable=protected-access
    cache_file = os.path.join(G.CACHE_DIR_PHOTO, f"{key_hash}.png")
    assert os.path.exists(cache_file)
    assert cache_file_path == cache_file


def test_font_caching():
    """Test that fonts are cached and reused."""
    # Clear font cache first
    image_utils._FONT_CACHE.clear()  # pylint: disable=protected-access

    # Load a font - min size is 12, so 1200 * 0.01 = 12
    font1 = image_utils.load_scaled_font(1200, scale=0.01)  # size = 12
    assert 12 in image_utils._FONT_CACHE  # pylint: disable=protected-access

    # Load the same size - should return cached font
    font2 = image_utils.load_scaled_font(1200, scale=0.01)
    assert font1 is font2  # Same object reference

    # Load a different size - 2000 * 0.01 = 20
    font3 = image_utils.load_scaled_font(2000, scale=0.01)  # size = 20
    assert 20 in image_utils._FONT_CACHE  # pylint: disable=protected-access
    assert font3 is not font1

    # Verify cache has both sizes
    assert len(image_utils._FONT_CACHE) == 2  # pylint: disable=protected-access


def test_font_cache_limit():
    """Test that font cache respects max size limit."""
    # Clear font cache first
    image_utils._FONT_CACHE.clear()  # pylint: disable=protected-access

    # Load more fonts than the max limit
    max_cache = image_utils._MAX_FONT_CACHE  # pylint: disable=protected-access
    for i in range(max_cache + 5):
        # Create different sizes: 12, 22, 32, etc. (ensuring min 12)
        height = (i + 1) * 1000  # 1000, 2000, 3000...
        image_utils.load_scaled_font(height, scale=0.01)

    # Cache should not exceed max limit
    # pylint: disable=protected-access
    assert len(image_utils._FONT_CACHE) <= max_cache


def test_resize_and_compress_creates_metadata(tmp_path):
    """Test that resize_and_compress creates a metadata sidecar file."""
    photos = tmp_path / "photos_meta"
    photos.mkdir()
    img_path = photos / "meta_test.jpg"
    make_image(str(img_path))

    setup_cache_dirs(tmp_path)

    cache_file_path = image_utils.resize_and_compress(
        str(img_path), {"bottom_right": "Metadata Test"}, 75
    )

    # Metadata file should exist
    meta_file = cache_file_path + ".json"
    assert os.path.exists(meta_file)

    # Verify metadata content
    with open(meta_file, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert "width" in meta
    assert "height" in meta
    assert meta["mime_type"] == "image/png"


def test_resize_and_compress_cache_hit(tmp_path):
    """Test that subsequent calls use cached file."""
    photos = tmp_path / "photos_hit"
    photos.mkdir()
    img_path = photos / "cache_hit.jpg"
    make_image(str(img_path))

    setup_cache_dirs(tmp_path)

    # First call - creates cache
    cache_file1 = image_utils.resize_and_compress(str(img_path), {}, 80)
    mtime1 = os.path.getmtime(cache_file1)

    # Second call - should use cached file (same mtime)
    cache_file2 = image_utils.resize_and_compress(str(img_path), {}, 80)
    mtime2 = os.path.getmtime(cache_file2)

    assert cache_file1 == cache_file2
    assert mtime1 == mtime2  # File wasn't recreated


def test_resize_and_compress_uses_processing_specific_cache_key(tmp_path):
    """Changing processing inputs should not reuse stale cache files."""
    photos = tmp_path / "photos_cache_key"
    photos.mkdir()
    img_path = photos / "cache_key_test.jpg"
    make_image(str(img_path), size=(400, 300))

    setup_cache_dirs(tmp_path)

    cache_file1 = image_utils.resize_and_compress(str(img_path), {"top_left": "v1"}, 80)
    cache_file2 = image_utils.resize_and_compress(str(img_path), {"top_left": "v2"}, 80)

    assert cache_file1 != cache_file2
    assert os.path.exists(cache_file1)
    assert os.path.exists(cache_file2)


def test_resize_and_compress_uses_png_for_rounded_corners(tmp_path):
    """Rounded-corner output should preserve alpha in a PNG cache."""
    photos = tmp_path / "photos_png"
    photos.mkdir()
    img_path = photos / "rounded_test.jpg"
    make_image(str(img_path), size=(400, 300))

    setup_cache_dirs(tmp_path)

    cache_file = image_utils.resize_and_compress(
        str(img_path), {"top_left": "Rounded PNG"}, 80
    )

    assert cache_file.endswith(".png")
    assert os.path.exists(cache_file)

    with Image.open(cache_file) as img:
        assert img.mode in {"RGBA", "LA", "P"}

    with open(cache_file + ".json", "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["mime_type"] == "image/png"


def test_apply_round_corners_creates_rounded_edges():
    """Test that round-corner mask is applied without changing image size."""
    img = Image.new("RGBA", (200, 120), (255, 0, 0, 255))

    rounded = image_utils.apply_round_corners(img, radius=20)

    assert rounded.size == img.size
    assert rounded.mode == "RGBA"

    # Check a corner pixel is transparent to confirm the corner was clipped.
    corner_pixel = rounded.getpixel((0, 0))
    center_pixel = rounded.getpixel((100, 60))
    assert isinstance(corner_pixel, tuple)
    assert isinstance(center_pixel, tuple)
    assert corner_pixel[3] == 0
    assert center_pixel[3] == 255


def test_apply_overlays_all_corners():
    """Test that overlays can be applied to all four corners."""
    img = Image.new("RGB", (800, 600), (100, 100, 100))

    overlays = {
        "top_left": "TL",
        "top_right": "TR",
        "bottom_left": "BL",
        "bottom_right": "BR",
    }

    # This should not raise any exceptions
    image_utils.apply_overlays(img, overlays)

    # Basic validation - image should still be valid
    assert img.size == (800, 600)

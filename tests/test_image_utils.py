"""Tests for image processing utilities.

Covers image resizing, compression, font caching, and overlay functionality.
"""

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
    """Test that resize_and_compress creates a cached JPEG file."""
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

    # Read the cached file and verify it's a valid JPEG
    with open(cache_file_path, "rb") as f:
        data = f.read()
    # JPEG files start with 0xFF 0xD8
    assert data[:2] == b"\xff\xd8"

    # cache file should exist
    key_hash = __import__("hashlib").md5(str(img_path).encode()).hexdigest()
    cache_file = os.path.join(G.CACHE_DIR_PHOTO, f"{key_hash}.jpg")
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
    import json

    with open(meta_file, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert "width" in meta
    assert "height" in meta
    assert meta["mime_type"] == "image/jpeg"


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

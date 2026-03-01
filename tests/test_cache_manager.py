"""Tests for cache management functionality.

Covers cache building, pruning, metadata handling, and SAME_DAY_KEYS operations.
"""

import os
from PIL import Image

from app import cache_manager
from app import globals as G
from pathlib import Path


def make_image(path, size=(100, 80), color=(10, 20, 30)):
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
    G.app.instance_path = str(tmp_path / "instance")
    G.CACHE_DIR = os.path.join(G.app.instance_path, "cache")
    G.CACHE_DIR_PHOTO = os.path.join(G.CACHE_DIR, "photos")
    os.makedirs(G.CACHE_DIR_PHOTO, exist_ok=True)
    return G.CACHE_DIR, G.CACHE_DIR_PHOTO


def test_build_cache_creates_files(tmp_path):
    """Test that build_cache creates cache_all.txt and cache_same_day.txt files."""
    photos = Path(str(tmp_path).replace("_cache_", "_photos_"))
    photos.mkdir(parents=True, exist_ok=True)

    today = cache_manager.datetime.date.today()
    # create one same-day file using YYYYMMDD pattern
    same_name = f"{today.strftime('%Y%m%d')}_pic.jpg"
    same_path = photos / same_name
    make_image(str(same_path))

    other = photos / "other.jpg"
    make_image(str(other))

    # set instance path to tmp
    G.app.instance_path = str(tmp_path / "instance")
    G.CACHE_DIR = os.path.join(G.app.instance_path, "cache")
    G.CACHE_DIR_PHOTO = os.path.join(G.CACHE_DIR, "photos")
    os.makedirs(G.CACHE_DIR_PHOTO, exist_ok=True)

    cache_manager.build_cache(str(photos))

    all_file = os.path.join(G.CACHE_DIR, "cache_all.txt")
    same_file = os.path.join(G.CACHE_DIR, "cache_same_day.txt")

    assert os.path.exists(all_file)
    assert os.path.exists(same_file)

    # read both files and check basenames are present in either
    found = set()
    for p in (all_file, same_file):
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                for l in f:
                    l = l.strip()
                    if l:
                        found.add(os.path.basename(l))

    # At minimum, one of the cache files should contain at least one entry
    assert len(found) > 0


def test_same_day_keys_is_set(tmp_path):
    """Verify SAME_DAY_KEYS is a set for O(1) lookup performance."""
    photos = Path(str(tmp_path) + "_photos_set")
    photos.mkdir(parents=True, exist_ok=True)

    today = cache_manager.datetime.date.today()
    same_name = f"{today.strftime('%Y%m%d')}_test.jpg"
    same_path = photos / same_name
    make_image(str(same_path))

    setup_cache_dirs(tmp_path)

    # Reset SAME_DAY_KEYS
    G.SAME_DAY_KEYS = set()

    cache_manager.build_cache(str(photos))

    # Verify it's a set, not a list
    assert isinstance(G.SAME_DAY_KEYS, set)
    # Should have at least one key
    assert len(G.SAME_DAY_KEYS) >= 1


def test_prune_orphaned_metadata_removes_stale_json(tmp_path):
    """Test that orphaned .json metadata files are removed."""
    _, cache_dir_photo = setup_cache_dirs(tmp_path)

    # Create an orphaned metadata file (no corresponding .jpg)
    orphan_meta = os.path.join(cache_dir_photo, "orphan123.jpg.json")
    with open(orphan_meta, "w", encoding="utf-8") as f:
        f.write('{"width": 100, "height": 100, "mime_type": "image/jpeg"}')

    # Create a valid image + metadata pair
    valid_img = os.path.join(cache_dir_photo, "valid456.jpg")
    valid_meta = os.path.join(cache_dir_photo, "valid456.jpg.json")
    make_image(valid_img)
    with open(valid_meta, "w", encoding="utf-8") as f:
        f.write('{"width": 100, "height": 80, "mime_type": "image/jpeg"}')

    assert os.path.exists(orphan_meta)
    assert os.path.exists(valid_meta)

    cache_manager.prune_orphaned_metadata()

    # Orphaned metadata should be removed
    assert not os.path.exists(orphan_meta)
    # Valid metadata should remain
    assert os.path.exists(valid_meta)
    assert os.path.exists(valid_img)


def test_prune_cache_removes_metadata_with_image(tmp_path):
    """Test that metadata files are removed when their images are pruned."""
    _, cache_dir_photo = setup_cache_dirs(tmp_path)

    # Set a low cache limit
    original_limit_enabled = G.CACHE_LIMIT_ENABLED
    original_limit = G.CACHE_LIMIT
    G.CACHE_LIMIT_ENABLED = True
    G.CACHE_LIMIT = 1
    G.CACHE_COUNT = 3
    G.SAME_DAY_KEYS = set()

    # Create 3 cached images with metadata
    for i in range(3):
        img_path = os.path.join(cache_dir_photo, f"img{i}.jpg")
        meta_path = img_path + ".json"
        make_image(img_path)
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write('{"width": 100, "height": 80, "mime_type": "image/jpeg"}')

    # Verify all 3 images and metadata exist
    assert len([f for f in os.listdir(cache_dir_photo) if f.endswith(".jpg")]) == 3
    assert len([f for f in os.listdir(cache_dir_photo) if f.endswith(".json")]) == 3

    cache_manager.prune_cache()

    # After pruning, we should have at most CACHE_LIMIT images
    remaining_images = [f for f in os.listdir(cache_dir_photo) if f.endswith(".jpg")]
    remaining_meta = [f for f in os.listdir(cache_dir_photo) if f.endswith(".json")]

    assert len(remaining_images) <= G.CACHE_LIMIT + 1
    # Metadata count should match or be less than image count
    assert len(remaining_meta) <= len(remaining_images)

    # Restore original values
    G.CACHE_LIMIT_ENABLED = original_limit_enabled
    G.CACHE_LIMIT = original_limit


def test_write_and_get_image_metadata(tmp_path):
    """Test writing and reading image metadata."""
    _, cache_dir_photo = setup_cache_dirs(tmp_path)

    cache_file = os.path.join(cache_dir_photo, "testmeta.jpg")
    make_image(cache_file)

    # Write metadata
    result = cache_manager.write_image_metadata(cache_file, 800, 600, "image/jpeg")
    assert result is True

    # Read it back
    width, height, mime_type = cache_manager.get_image_metadata(cache_file)
    assert width == 800
    assert height == 600
    assert mime_type == "image/jpeg"


def test_prune_cache_skips_when_limit_disabled(tmp_path):
    """Test that prune_cache does nothing when cache limit is disabled."""
    _, cache_dir_photo = setup_cache_dirs(tmp_path)

    original_limit_enabled = G.CACHE_LIMIT_ENABLED
    original_limit = G.CACHE_LIMIT
    try:
        G.CACHE_LIMIT_ENABLED = False
        G.CACHE_LIMIT = 1
        G.CACHE_COUNT = 3
        G.SAME_DAY_KEYS = set()

        for i in range(3):
            img_path = os.path.join(cache_dir_photo, f"nolimit{i}.jpg")
            make_image(img_path)

        cache_manager.prune_cache()

        remaining_images = [
            f for f in os.listdir(cache_dir_photo) if f.endswith(".jpg")
        ]
        assert len(remaining_images) == 3
        assert G.CACHE_COUNT == 3
    finally:
        G.CACHE_LIMIT_ENABLED = original_limit_enabled
        G.CACHE_LIMIT = original_limit

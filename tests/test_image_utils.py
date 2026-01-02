import os
from PIL import Image

from app import image_utils
from app import globals as G


def make_image(path, size=(300, 200), color=(200, 100, 50)):
    img = Image.new("RGB", size, color)
    img.save(path, format="JPEG")


def test_resize_and_compress_creates_cache(tmp_path):
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

    buf = image_utils.resize_and_compress(
        str(img_path), overlay_text="Top", bottom_right_text="BR"
    )
    data = buf.getvalue()
    # JPEG files start with 0xFF 0xD8
    assert data[:2] == b"\xff\xd8"

    # cache file should exist
    key_hash = __import__("hashlib").md5(str(img_path).encode()).hexdigest()
    cache_file = os.path.join(G.CACHE_DIR_PHOTO, f"{key_hash}.jpg")
    assert os.path.exists(cache_file)

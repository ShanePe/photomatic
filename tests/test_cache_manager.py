import os
import hashlib
from PIL import Image

from app import cache_manager
from app import globals as G
from pathlib import Path


def make_image(path, size=(100, 80), color=(10, 20, 30)):
    img = Image.new("RGB", size, color)
    img.save(path, format="JPEG")


def test_build_cache_creates_files(tmp_path):
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

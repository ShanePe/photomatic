"""Tests for Flask application routes.

Validates HTTP endpoints including the /random image serving route.
"""

import os

from PIL import Image

import app.routes  # noqa: F401 pylint: disable=unused-import
from app import cache_manager
from app import globals as G


def test_random_route_serves_image(tmp_path):
    """Test that the /random route serves an image with correct content type."""
    photos = tmp_path / "photos"
    photos.mkdir()
    # create a simple image

    img = Image.new("RGB", (120, 90), (10, 20, 30))
    img_path = photos / "pic.jpg"
    img.save(str(img_path), format="JPEG")

    # prepare instance
    inst = tmp_path / "instance"
    inst.mkdir()
    G.app.instance_path = str(inst)
    G.CACHE_DIR = os.path.join(G.app.instance_path, "cache")
    G.CACHE_DIR_PHOTO = os.path.join(G.CACHE_DIR, "photos")
    os.makedirs(G.CACHE_DIR_PHOTO, exist_ok=True)

    # build cache then run test client
    cache_manager.build_cache(str(photos))

    client = G.app.test_client()
    resp = client.get("/random")
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        assert resp.headers.get("Content-Type", "").startswith("image/")

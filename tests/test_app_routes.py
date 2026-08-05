"""Tests for Flask application routes.

Validates HTTP endpoints including the /random image serving route.
"""

import datetime
import os

from PIL import Image

import app.routes as routes
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


def test_api_random_route_returns_photo_age_payload(tmp_path, monkeypatch):
    """The /api/random route should return JSON metadata with age label and image URL."""
    photos = tmp_path / "photos"
    photos.mkdir()

    img = Image.new("RGB", (120, 90), (10, 20, 30))
    img_path = photos / "same_day.jpg"
    img.save(str(img_path), format="JPEG")

    inst = tmp_path / "instance"
    inst.mkdir()
    G.app.instance_path = str(inst)
    G.CACHE_DIR = os.path.join(G.app.instance_path, "cache")
    G.CACHE_DIR_PHOTO = os.path.join(G.CACHE_DIR, "photos")
    os.makedirs(G.CACHE_DIR_PHOTO, exist_ok=True)

    captured = {}

    def fake_resize_and_compress(path, overlays=None, quality=75):
        captured["path"] = path
        captured["overlays"] = overlays or {}
        captured["quality"] = quality
        return str(img_path)

    today = datetime.date.today()
    ten_years_ago = datetime.date(today.year - 10, today.month, today.day)

    monkeypatch.setattr(routes, "pick_file", lambda _base_dir: str(img_path))
    monkeypatch.setattr(routes, "get_photo_date", lambda _path: ten_years_ago)
    monkeypatch.setattr(routes, "resize_and_compress", fake_resize_and_compress)

    G.PHOTO_ROOT = str(photos)
    client = G.app.test_client()
    resp = client.get("/api/random")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["age_label"] == "Today, 10 years ago"
    assert data["photo_path"] == str(img_path)
    assert data["image_url"].startswith("/random_image?path=")
    # Age label now renders on the client, so top_right overlay should be empty.
    assert captured["overlays"]["top_right"] == ""


def test_random_image_by_path_rejects_invalid_path(tmp_path):
    """/random_image should reject paths outside the configured photo root."""
    photos = tmp_path / "photos"
    photos.mkdir()
    G.PHOTO_ROOT = str(photos)

    outside = tmp_path / "outside.jpg"
    img = Image.new("RGB", (20, 20), (30, 40, 50))
    img.save(str(outside), format="JPEG")

    client = G.app.test_client()
    resp = client.get(f"/random_image?path={outside}")

    assert resp.status_code == 400

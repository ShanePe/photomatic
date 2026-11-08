"""Tests for Flask application routes.

Validates HTTP endpoints including the /random image serving route.
"""

import datetime
import os

from PIL import Image

import app.routes as routes
from app import cache_manager
from app import globals as G
from app.session import PHOTO_STATE_SESSION_KEY, configure_server_sessions


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


def test_api_random_advances_after_single_same_day_photo(tmp_path):
    """A client's second request should leave a one-photo same-day pool."""
    photos = tmp_path / "photos"
    photos.mkdir()

    today = datetime.date.today()
    daily_photo = photos / f"{today.strftime('%Y%m%d')}_daily.jpg"
    older_photo = photos / "20180101_older.jpg"
    Image.new("RGB", (120, 90), (10, 20, 30)).save(daily_photo, format="JPEG")
    Image.new("RGB", (120, 90), (30, 20, 10)).save(older_photo, format="JPEG")

    instance_dir = tmp_path / "instance"
    instance_dir.mkdir()
    G.app.instance_path = str(instance_dir)
    configure_server_sessions()
    G.CACHE_DIR = os.path.join(G.app.instance_path, "cache")
    G.CACHE_DIR_PHOTO = os.path.join(G.CACHE_DIR, "photos")
    os.makedirs(G.CACHE_DIR_PHOTO, exist_ok=True)
    G.PHOTO_ROOT = str(photos)
    cache_manager.build_cache(str(photos))

    first_client = G.app.test_client()
    second_client = G.app.test_client()
    first = first_client.get("/api/random")
    other_client_first = second_client.get("/api/random")
    second = first_client.get("/api/random")

    assert first.status_code == 200
    assert other_client_first.status_code == 200
    assert second.status_code == 200
    assert first.get_json()["photo_path"] == str(daily_photo)
    assert other_client_first.get_json()["photo_path"] == str(daily_photo)
    assert second.get_json()["photo_path"] == str(older_photo)

    session_cookie = first.headers.get("Set-Cookie", "")
    assert "photomatic_session=" in session_cookie
    assert "photomatic_photo_state" not in session_cookie
    first_session_cookie = first_client.get_cookie("photomatic_session")
    other_session_cookie = second_client.get_cookie("photomatic_session")
    assert first_session_cookie is not None
    assert other_session_cookie is not None
    assert first_session_cookie.value != other_session_cookie.value
    assert "photo_index" not in first_session_cookie.value


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


def test_clear_cache_logs_request(monkeypatch):
    """Every incoming request should log the HTTP method and path for visibility."""
    messages = []

    def fake_info(message, *args):
        if args:
            messages.append(message % args)
        else:
            messages.append(message)

    monkeypatch.setattr(G.logger, "info", fake_info)

    client = G.app.test_client()
    resp = client.get("/clear_cache")

    assert resp.status_code in (200, 503)
    assert any("GET /clear_cache" in message for message in messages)


def test_clear_cache_removes_client_photo_state():
    """Clearing the cache also resets only the requesting client's photo state."""
    client = G.app.test_client()
    with client.session_transaction() as server_session:
        server_session[PHOTO_STATE_SESSION_KEY] = {"photo_index": 4}

    response = client.get("/clear_cache")

    assert response.status_code == 200
    with client.session_transaction() as server_session:
        assert PHOTO_STATE_SESSION_KEY not in server_session


def test_random_image_routes_fail_during_cache_build(tmp_path):
    """Any random-image fetch should fail fast while the cache is being rebuilt."""
    photos = tmp_path / "photos"
    photos.mkdir()
    valid_photo = photos / "photo.jpg"
    Image.new("RGB", (20, 20), (30, 40, 50)).save(valid_photo, format="JPEG")

    G.PHOTO_ROOT = str(photos)
    G.BUILDING_CACHE = True

    client = G.app.test_client()

    random_resp = client.get("/random")
    image_resp = client.get(f"/random_image?path={valid_photo}")
    api_resp = client.get("/api/random")

    assert random_resp.status_code == 500
    assert image_resp.status_code == 500
    assert api_resp.status_code == 500

    G.BUILDING_CACHE = False

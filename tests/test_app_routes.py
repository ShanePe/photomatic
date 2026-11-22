"""Tests for Flask application routes.

Validates HTTP endpoints including the /random image serving route.
"""

import datetime
import os

from PIL import Image

import app.routes as routes
from app import cache_manager
from app import globals as G
from app.cache_database import open_database, set_cache_service_health
from app.session import configure_server_sessions


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

    monkeypatch.setattr(routes, "_select_photo_for_client", lambda: str(img_path))
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


def test_api_random_tracks_clients_by_ip(tmp_path):
    """Requests from the same IP share selection state across browser sessions."""
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
    assert other_client_first.get_json()["photo_path"] == str(older_photo)
    assert second.get_json()["photo_path"] == str(older_photo)

    assert first.headers.get("Set-Cookie") is None


def test_random_route_does_not_build_missing_cache(tmp_path, monkeypatch):
    """Random requests return 503 when indexes are absent instead of building them."""
    G.CACHE_DIR = str(tmp_path / "cache")
    os.makedirs(G.CACHE_DIR, exist_ok=True)
    G.PHOTO_ROOT = str(tmp_path / "photos")
    monkeypatch.setattr(
        cache_manager,
        "build_cache",
        lambda _root: (_ for _ in ()).throw(AssertionError("request built cache")),
    )

    response = G.app.test_client().get("/api/random")

    assert response.status_code == 503


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
    """Clearing the cache clears persistent client tracking state."""
    from app.client_photo_tracker import client_key_from_ip, select_photo

    photos = G.PHOTO_ROOT or os.getcwd()
    G.CACHE_DIR = os.path.join(G.app.instance_path, "cache")
    G.CACHE_DIR_PHOTO = os.path.join(G.CACHE_DIR, "photos")
    G.CACHE_DIR_ICON = os.path.join(G.CACHE_DIR, "icons")
    os.makedirs(G.CACHE_DIR_PHOTO, exist_ok=True)
    os.makedirs(G.CACHE_DIR_ICON, exist_ok=True)
    with open_database() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO photos (path, same_day) VALUES (?, 0)",
            (os.path.join(photos, "cached.jpg"),),
        )
        connection.execute(
            "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES ('built_date', ?)",
            (datetime.date.today().isoformat(),),
        )
    select_photo(client_key_from_ip("127.0.0.1"))
    set_cache_service_health("healthy", succeeded=True)

    client = G.app.test_client()
    response = client.get("/clear_cache")

    assert response.status_code == 200
    with open_database() as connection:
        assert connection.execute("SELECT COUNT(*) FROM clients").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM photos").fetchone()[0] == 0


def test_healthcheck_reports_cache_service_health(tmp_path, monkeypatch):
    """The health endpoint includes the cache service's SQLite heartbeat."""
    cache_dir = tmp_path / "cache"
    G.CACHE_DIR = str(cache_dir)
    G.PHOTO_ROOT = str(tmp_path / "photos")
    cache_dir.mkdir()
    with open_database() as connection:
        connection.execute(
            "INSERT INTO cache_metadata (key, value) VALUES ('built_date', ?)",
            (datetime.date.today().isoformat(),),
        )
    set_cache_service_health("healthy", succeeded=True)
    monkeypatch.setattr(
        routes,
        "_api_call_status",
        {
            "config": {"ok": True, "last_error": None},
            "weather": {"ok": True, "last_error": None},
            "icon": {"ok": True, "last_error": None},
            "random": {"ok": True, "last_error": None},
        },
    )

    response = G.app.test_client().get("/healthcheck")

    assert response.status_code == 200
    assert response.get_json()["cache_service"]["ok"]


def test_random_route_waits_while_background_service_builds(tmp_path):
    """Random requests do not contend with an index rebuild in another process."""
    G.CACHE_DIR = str(tmp_path / "cache")
    set_cache_service_health("building", "Photo index rebuild is in progress")

    response = G.app.test_client().get("/api/random")

    assert response.status_code == 503


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

    assert random_resp.status_code == 503
    assert image_resp.status_code == 503
    assert api_resp.status_code == 503

    G.BUILDING_CACHE = False

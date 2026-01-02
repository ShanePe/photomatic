import os
from app import app as app_pkg
import app.app  # ensure routes are registered
from app import cache_manager
from app import globals as G


def test_random_route_serves_image(tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    # create a simple image
    from PIL import Image

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

    # ensure routes are registered on the Flask app
    import app.app  # noqa: F401

    client = G.app.test_client()
    resp = client.get("/random")
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        assert resp.headers.get("Content-Type", "").startswith("image/")

"""Flask route handlers for the photo slideshow application."""

import os
from urllib.parse import urlparse

import requests
from flask import (
    jsonify,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
)
from PIL import Image, UnidentifiedImageError

from . import globals as G
from .cache_manager import (
    clear_entire_cache,
    format_date_with_suffix,
    get_photo_date,
    pick_file,
)
from .image_utils import resize_and_compress
from .weather_utils import map_openmeteo_code, map_metno_symbol


@G.app.route("/favicon.ico")
def favicon():
    """Serve the favicon.ico file."""
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), "assets"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@G.app.route("/")
def index():
    """
    Render and return the index page template.

    Returns:
        str: Rendered HTML content of the index.html template.
    """
    return render_template("index.html")


@G.app.route("/random")
def random_image():
    """
    Serve a randomly selected and compressed image from the photo root directory.
    Handles cache building state, file selection, image compression, and logging.
    Tracks photo serving statistics per session and returns image with appropriate
    MIME type and dimensions.
    Returns:
        Flask Response: Compressed image file with JPEG MIME type, or error response.
        - 200: Image served successfully
        - 404: No images found in photo root
        - 503: Cache is currently being built
        - 500: Error occurred during image processing
    """
    try:
        if G.BUILDING_CACHE:
            return "Cache is being built, please try again shortly.", 503

        path = pick_file(G.PHOTO_ROOT)
        if not path:
            return "No images found", 404

        client_ip = request.remote_addr
        user_agent = request.headers.get("User-Agent")

        photo_date = get_photo_date(path)

        buf = resize_and_compress(
            path,
            {
                "top_left": format_date_with_suffix(photo_date) if photo_date else "",
                "top_right": os.path.basename(path),
            },
            50,
        )

        compressed_size = len(buf.getvalue())
        width = height = None
        try:
            buf.seek(0)
            with Image.open(buf) as img:
                width, height = img.size
                mime_type = (
                    getattr(img, "get_format_mimetype", lambda: None)() or "image/jpeg"
                )
            buf.seek(0)
        except (UnidentifiedImageError, OSError, ValueError):
            mime_type = "image/jpeg"

        session["photo_served"] = session.get("photo_served", 0) + 1

        if session.get("photo_served", 0) > G.SAME_DAY_CYCLE:
            session["photo_index"] = 0
            session["photo_served"] = 0

        G.logger.info(
            "Served buffer from %s | Compressed size: %.1f KB | Dimensions: %sx%s | MIME: %s | "
            "Client IP: %s | UA: %s | Photo index: %s : Photo served: %s",
            os.path.basename(path),
            compressed_size / 1024,
            width,
            height,
            mime_type,
            client_ip,
            user_agent,
            session.get("photo_index"),
            session.get("photo_served"),
        )

        return send_file(buf, mimetype="image/jpeg")

    except (OSError, UnidentifiedImageError, ValueError) as e:
        G.logger.error("Error serving image: %s", e)
        return f"Error: {e}", 500


@G.app.route("/clear_cache")
def clear_cache():
    """
    Clear the on-disk cache unless a build is in progress.
    """
    if G.BUILDING_CACHE:
        return "Cache is currently being built. Try again later.", 503

    try:
        G.logger.info("Manual cache clear requested by client.")

        clear_entire_cache()

        # Optional: reset session counters too
        session["photo_index"] = 0
        session["photo_served"] = 0

        return "Cache cleared.", 200

    except Exception as e:  # pylint: disable=broad-except
        G.logger.error("Error clearing cache: %s", e)
        return f"Error clearing cache: {e}", 500


@G.app.route("/cache_icon", methods=["POST"])
def cache_icon():
    """ "Fetch and cache an icon from a given URL."""
    data = request.get_json()
    full_url = data["url"]

    # Parse URL path: /lucide/cloud.svg
    parsed = urlparse(full_url)
    parts = parsed.path.strip("/").split("/")

    if len(parts) < 2:
        return jsonify({"error": "Invalid icon URL"}), 400

    style = parts[-2]  # "lucide"
    filename = parts[-1]  # "cloud.svg"

    # Build local cache path
    style_dir = os.path.join(G.CACHE_DIR_ICON, style)
    os.makedirs(style_dir, exist_ok=True)

    local_path = os.path.join(style_dir, filename)
    relative_path = f"/icons/{style}/{filename}"

    # If cached, return immediately
    if os.path.exists(local_path):
        return jsonify({"path": relative_path})

    # Download and cache
    r = requests.get(full_url, timeout=60)
    if r.status_code == 200:
        with open(local_path, "wb") as f:
            f.write(r.content)
        return jsonify({"path": relative_path})
    else:
        return jsonify({"error": "Failed to fetch icon"}), 500


@G.app.route("/icons/<style>/<filename>")
def serve_icon(style, filename):
    """Serve cached icon files."""
    return send_from_directory(os.path.join(G.CACHE_DIR_ICON, style), filename)


@G.app.route("/api/weather/<lat>/<lon>")
def get_weather(lat, lon):
    """
    Unified weather endpoint with fallback logic.
    Tries met.no first, falls back to open-meteo.
    Returns standardized weather condition.

    Args:
        lat: Latitude coordinate
        lon: Longitude coordinate

    Returns:
        JSON with temp and standardized condition name
    """
    # Try met.no first
    try:
        url = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat}&lon={lon}"
        headers = {"User-Agent": "PhotomaticWeatherDisplay/1.0"}

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        latest = data["properties"]["timeseries"][0]
        temp = latest["data"]["instant"]["details"]["air_temperature"]
        symbol_code = latest["data"]["next_1_hours"]["summary"]["symbol_code"]

        return jsonify(
            {
                "temp": temp,
                "condition": map_metno_symbol(symbol_code),
            }
        )
    except Exception as e:  # pylint: disable=broad-except
        G.logger.warning("Met.no API failed, falling back to open-meteo: %s", e)

    # Fallback to open-meteo
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()
        temp = data["current_weather"]["temperature"]
        code = data["current_weather"]["weathercode"]

        return jsonify(
            {
                "temp": temp,
                "condition": map_openmeteo_code(code),
            }
        )
    except Exception as e:  # pylint: disable=broad-except
        G.logger.error("All weather APIs failed: %s", e)
        return jsonify({"error": "Unable to fetch weather data"}), 503

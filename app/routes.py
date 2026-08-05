"""
Flask route handlers for the photo slideshow application.
"""

# Standard library imports
import datetime
import os
from pathlib import Path
from urllib.parse import quote, urlparse

# Third-party imports
from flask import (
    jsonify,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
)
from PIL import UnidentifiedImageError

# Local imports
from . import globals as G

# Healthcheck API call status cache
_api_call_status = {
    "config": {"ok": True, "last_error": None},
    "weather": {"ok": True, "last_error": None},
    "icon": {"ok": True, "last_error": None},
    "random": {"ok": True, "last_error": None},
}


def _set_api_status(api_name, ok, error=None):
    _api_call_status[api_name]["ok"] = ok
    _api_call_status[api_name]["last_error"] = error
    if not ok and error:
        G.logger.error("[Healthcheck] %s API failed: %s", api_name, error)


def _pluralize(value: int, unit: str) -> str:
    return f"{value} {unit}" if value == 1 else f"{value} {unit}s"


def _format_photo_age_label(photo_date: datetime.date | None) -> str:
    """Format a human-friendly age label for overlay text."""
    if not photo_date:
        return ""

    today = datetime.date.today()
    if photo_date > today:
        return "Future photo"

    is_same_month_day = photo_date.month == today.month and photo_date.day == today.day

    if is_same_month_day:
        years = today.year - photo_date.year
        if years <= 0:
            return "Today"
        return f"Today, {_pluralize(years, 'year')} ago"

    total_months = (today.year - photo_date.year) * 12 + (
        today.month - photo_date.month
    )
    if today.day < photo_date.day:
        total_months -= 1
    total_months = max(total_months, 0)

    years, months = divmod(total_months, 12)

    if years == 0 and months == 0:
        return "Less than 1 month ago"

    if years == 0:
        return f"{_pluralize(months, 'month')} ago"

    if months == 0:
        return f"{_pluralize(years, 'year')} ago"

    # Keep month-first wording to match requested style.
    return f"{_pluralize(months, 'month')} and {_pluralize(years, 'year')} ago"


def _is_path_under_root(path: str, root: str | None) -> bool:
    """Return True when `path` is inside `root` after resolution."""
    if not path or not root:
        return False

    try:
        resolved_path = Path(path).resolve()
        resolved_root = Path(root).resolve()
    except OSError:
        return False

    return resolved_root == resolved_path or resolved_root in resolved_path.parents


def _prepare_random_photo_payload(path: str) -> dict[str, str]:
    """Prepare random photo metadata and ensure cached image exists."""
    photo_date = get_photo_date(path)
    age_label = _format_photo_age_label(photo_date)

    cache_file = resize_and_compress(
        path,
        {
            "top_left": format_date_with_suffix(photo_date) if photo_date else "",
            "top_right": "",
        },
        50,
    )

    return {
        "cache_file": cache_file,
        "photo_path": path,
        "age_label": age_label,
        "photo_date": format_date_with_suffix(photo_date) if photo_date else "",
    }


@G.app.route("/healthcheck")
def healthcheck():
    failed = [name for name, status in _api_call_status.items() if not status["ok"]]
    if failed:
        return (
            jsonify(
                {
                    "status": "fail",
                    "failed": failed,
                    "details": {
                        k: v for k, v in _api_call_status.items() if not v["ok"]
                    },
                }
            ),
            500,
        )
    return jsonify({"status": "ok", "cache": _api_call_status})


from .cache_manager import (
    clear_entire_cache,
    format_date_with_suffix,
    get_image_metadata,
    get_photo_date,
    pick_file,
)
from .image_utils import resize_and_compress, get_requests_session
from .weather_utils import (
    map_openmeteo_code,
    map_metno_symbol,
    get_cached_weather,
    set_cached_weather,
)
from .config_manager import load_config


@G.app.route("/api/config")
def api_config():
    """API endpoint to return client configuration settings."""
    try:
        cfg = load_config()
        _set_api_status("config", True)
        return jsonify(cfg.get("client", {}))
    except (OSError, ValueError, TypeError) as e:
        _set_api_status("config", False, str(e))
        return jsonify({"error": "Config load failed"}), 500


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
            _set_api_status("random", False, "Cache is being built")
            return "Cache is being built, please try again shortly.", 503

        path = pick_file(G.PHOTO_ROOT)
        if not path:
            _set_api_status("random", False, "No images found")
            return "No images found", 404

        client_ip = request.remote_addr
        user_agent = request.headers.get("User-Agent")

        payload = _prepare_random_photo_payload(path)
        cache_file = payload["cache_file"]

        compressed_size = os.path.getsize(cache_file)
        width, height, mime_type = get_image_metadata(cache_file)

        session["photo_served"] = session.get("photo_served", 0) + 1

        if session.get("photo_served", 0) > G.SAME_DAY_CYCLE:
            session["photo_index"] = 0
            session["photo_served"] = 0

        G.logger.info(
            "[Routes] Served buffer from %s | Compressed size: %.1f KB | Dimensions: %sx%s | MIME: %s | "
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

        _set_api_status("random", True)
        return send_file(cache_file, mimetype="image/jpeg")

    except (OSError, UnidentifiedImageError, ValueError) as e:
        G.logger.error("[Routes] Error serving image: %s", e)
        _set_api_status("random", False, str(e))
        return f"Error: {e}", 500


@G.app.route("/api/random")
def api_random_image():
    """Return JSON metadata for a random photo and where to fetch its image."""
    try:
        if G.BUILDING_CACHE:
            _set_api_status("random", False, "Cache is being built")
            return jsonify({"error": "Cache is being built"}), 503

        path = pick_file(G.PHOTO_ROOT)
        if not path:
            _set_api_status("random", False, "No images found")
            return jsonify({"error": "No images found"}), 404

        payload = _prepare_random_photo_payload(path)
        _set_api_status("random", True)

        return jsonify(
            {
                "photo_path": payload["photo_path"],
                "photo_date": payload["photo_date"],
                "age_label": payload["age_label"],
                "image_url": f"/random_image?path={quote(path, safe='')}",
            }
        )
    except (OSError, UnidentifiedImageError, ValueError) as e:
        G.logger.error("[Routes] Error preparing random image metadata: %s", e)
        _set_api_status("random", False, str(e))
        return jsonify({"error": "Failed to prepare random image"}), 500


@G.app.route("/random_image")
def random_image_by_path():
    """Serve a compressed image for a client-supplied photo path."""
    path = request.args.get("path", "")
    if not path:
        return jsonify({"error": "Missing path"}), 400

    if not _is_path_under_root(path, G.PHOTO_ROOT):
        return jsonify({"error": "Invalid path"}), 400

    if not os.path.exists(path):
        return jsonify({"error": "Photo not found"}), 404

    try:
        payload = _prepare_random_photo_payload(path)
        _set_api_status("random", True)
        return send_file(payload["cache_file"], mimetype="image/jpeg")
    except (OSError, UnidentifiedImageError, ValueError) as e:
        G.logger.error("[Routes] Error serving image for path %s: %s", path, e)
        _set_api_status("random", False, str(e))
        return jsonify({"error": "Failed to process photo"}), 500


@G.app.route("/clear_cache")
def clear_cache():
    """
    Clear the on-disk cache unless a build is in progress.
    """
    if G.BUILDING_CACHE:
        return "Cache is currently being built. Try again later.", 503

    try:
        G.logger.info("[Routes] Manual cache clear requested by client.")

        clear_entire_cache()

        # Optional: reset session counters too
        session["photo_index"] = 0
        session["photo_served"] = 0

        return "Cache cleared.", 200

    except Exception as e:  # pylint: disable=broad-except
        G.logger.error("[Routes] Error clearing cache: %s", e)
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
        _set_api_status("icon", True)
        return jsonify({"path": relative_path})

    # Download and cache
    try:
        session_obj = get_requests_session()
        r = session_obj.get(full_url, timeout=60)
        if r.status_code == 200:
            with open(local_path, "wb") as f:
                f.write(r.content)
            _set_api_status("icon", True)
            return jsonify({"path": relative_path})
        else:
            _set_api_status("icon", False, f"Status code {r.status_code}")
            return jsonify({"error": "Failed to fetch icon"}), 500
    except (OSError, IOError, ValueError) as e:
        G.logger.error("[Icons] Error caching icon from %s: %s", full_url, e)
        _set_api_status("icon", False, str(e))
        return jsonify({"error": "Failed to fetch icon"}), 500


@G.app.route("/icons/<style>/<filename>")
def serve_icon(style, filename):
    """Serve cached icon files."""
    return send_from_directory(os.path.join(G.CACHE_DIR_ICON, style), filename)


@G.app.route("/api/weather/<lat>/<lon>")
def get_weather(lat: str, lon: str):
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
    # Check cache first
    cached = get_cached_weather(lat, lon)
    if cached:
        G.logger.info("[Weather] Returning cached weather for %s,%s", lat, lon)
        _set_api_status("weather", True)
        return jsonify(cached)

    # Try met.no first
    session_obj = get_requests_session()
    try:
        url = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat}&lon={lon}"
        headers = {"User-Agent": "PhotomaticWeatherDisplay/1.0"}

        response = session_obj.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        latest = data["properties"]["timeseries"][0]
        temp = latest["data"]["instant"]["details"]["air_temperature"]
        symbol_code = latest["data"]["next_1_hours"]["summary"]["symbol_code"]

        weather_data = {
            "temp": temp,
            "condition": map_metno_symbol(symbol_code),
        }
        set_cached_weather(lat, lon, weather_data)
        _set_api_status("weather", True)
        return jsonify(weather_data)
    except Exception as e:  # pylint: disable=broad-except
        G.logger.warning(
            "[Weather] Met.no API failed, falling back to open-meteo: %s", e
        )

    # Fallback to open-meteo
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"

        response = session_obj.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()
        temp = data["current_weather"]["temperature"]
        code = data["current_weather"]["weathercode"]

        weather_data = {
            "temp": temp,
            "condition": map_openmeteo_code(code),
        }
        set_cached_weather(lat, lon, weather_data)
        _set_api_status("weather", True)
        return jsonify(weather_data)
    except Exception as e:  # pylint: disable=broad-except
        G.logger.info("[Weather] All weather APIs failed: %s", e)
        _set_api_status("weather", False, str(e))
        return jsonify({"error": "Unable to fetch weather data"}), 503

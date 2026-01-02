"""Application entrypoint that wires routes to split modules."""

import argparse
import os
from flask import render_template, send_file, session, request
from PIL import Image, UnidentifiedImageError

from . import globals as G
from .image_utils import resize_and_compress
from .cache_manager import (
    get_photo_date,
    pick_file,
    format_date_with_suffix,
    prune_cache,
)


@G.app.before_request
def reset_on_first_visit():
    """
    Reset session state on first visit.

    Clears the session and initializes default values for photo tracking
    if this is the user's first visit to the application.
    """
    if "initialized" not in session:
        session.clear()
        session["photo_index"] = 0
        session["photo_served"] = 0
        session["initialized"] = True


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
            path, format_date_with_suffix(photo_date) if photo_date else "", 50
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


def parse_args():
    """Parse CLI args.

    Returns an `argparse.Namespace` with `photos` (required) and `port`.
    """
    parser = argparse.ArgumentParser(description="Photo slideshow")
    parser.add_argument("--photos", required=True, help="Base folder containing images")
    parser.add_argument("--port", type=int, default=5000, help="Port to run the server")
    return parser.parse_args()


def run_app(arguments):
    """Configure globals and run the Flask application.

    Sets `G.PHOTO_ROOT` from the parsed `arguments`, prunes the cache if the
    on-disk cache exceeds the configured limit, and launches the Flask app.
    """
    G.PHOTO_ROOT = arguments.photos

    if G.CACHE_COUNT > G.CACHE_LIMIT:
        G.logger.info(
            "Initial cache count: %s, pruning to limit %s", G.CACHE_COUNT, G.CACHE_LIMIT
        )
        prune_cache()

    G.app.run(debug=True, host="0.0.0.0", port=arguments.port)


if __name__ == "__main__":
    args = parse_args()
    run_app(args)

"""
Photomatic Flask Application

A web application for displaying a random photo slideshow from a local directory.
Supports various image formats including HEIC conversion to JPEG.
"""

import argparse
import io
import os
import random

from flask import Flask, render_template, send_file
from PIL import Image
from pillow_heif import register_heif_opener

app = Flask(__name__)
register_heif_opener()  # Register HEIF opener for Image.open to handle HEIC files
PHOTO_ROOT = None


def convert_heic_to_jpg(heic_path):
    """
    Convert an Apple HEIC image file to JPEG format.

    Args:
        heic_path (str): Path to the HEIC file.

    Returns:
        io.BytesIO: A BytesIO buffer containing the JPEG image data.
    """
    img = Image.open(heic_path)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


def pick_random_file(base_dir):
    """
    Select a random image file from the given base directory using reservoir sampling.

    This method efficiently picks one random file without loading all files into memory,
    making it suitable for large directories.

    Args:
        base_dir (str): The root directory to search for images.

    Returns:
        str or None: The path to a randomly selected image file, or None if no images found.

    Supported formats: .jpg, .jpeg, .png, .gif, .webp, .heic
    """
    extensions = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic")
    chosen = None
    count = 0
    for root, _, files in os.walk(base_dir):
        for f in files:
            if f.lower().endswith(extensions):
                count += 1
                if random.randint(1, count) == 1:
                    chosen = os.path.join(root, f)
    return chosen


@app.route("/")
def index():
    """
    Serve the main slideshow page.

    Returns:
        Response: Rendered HTML template for the slideshow interface.
    """
    return render_template("index.html")


@app.route("/random")
def random_image():
    """
    Serve a random image from the configured photo directory.

    Selects a random image, converts HEIC files to JPEG if necessary,
    and returns the image data.

    Returns:
        Response: Image file response, or 404 error if no images found.
    """
    path = pick_random_file(PHOTO_ROOT)
    if not path:
        return "No images found", 404

    # Convert HEIC to JPEG on the fly
    if path.lower().endswith(".heic"):
        buf = convert_heic_to_jpg(path)
        return send_file(buf, mimetype="image/jpeg")

    return send_file(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Random photo slideshow")
    parser.add_argument("--photos", required=True, help="Base folder containing images")
    parser.add_argument("--port", type=int, default=5000, help="Port to run the server")
    args = parser.parse_args()

    PHOTO_ROOT = args.photos
    app.run(debug=True, host="0.0.0.0", port=args.port)

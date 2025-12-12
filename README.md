# Photomatic

A simple Flask-based random photo slideshow web application.

## Features

- Serves random photos from a specified directory
- Web-based slideshow with automatic image transitions every 30 seconds
- Supports common image formats: JPG, JPEG, PNG, GIF, WebP, HEIC
- Responsive design that fills the screen
- Converts HEIC images to JPEG on the fly

## Installation

1. Clone or download the repository
2. Install dependencies:
   ```bash
   pip install flask pillow pillow-heif
   ```

## Usage

Run the application with:

```bash
python app/app.py --photos /path/to/your/photos --port 5000
```

- `--photos`: Required. Path to the base folder containing your images
- `--port`: Optional. Port to run the server on (default: 5000)

Open your browser to `http://localhost:5000` to view the slideshow.

## How it works

- The Flask app walks through the specified photos directory and uses reservoir sampling to efficiently pick a random image without loading all files into memory
- The `/random` endpoint serves the selected image
- The frontend uses JavaScript to fetch new images every 30 seconds and fade them in
- HEIC images are automatically converted to JPEG for browser compatibility

## Requirements

- Python 3.6+
- Flask
- Pillow
- pillow-heif (for HEIC support)</content>
  <parameter name="filePath">c:\Users\shane\code\python\photomatic\README.md

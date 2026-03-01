# Photomatic API

Endpoints

- `/` (GET)

  - Serves the slideshow HTML page (`templates/index.html`).

- `/random` (GET)
  - Returns a single image for the slideshow.
  - Behavior: serves sequential same-day images per browser session; falls back to random selection from the full collection.

Responses

- 200: Image served as `image/jpeg` (or compatible). The response body is the JPEG bytes.
- 404: No images found (empty photo directory or cache).
- 503: Cache is currently being (re)built; try again.
- 500: Internal error while processing or resizing the image.

Examples

- Save a single image to disk:

```bash
curl -f -o sample.jpg http://localhost:5000/random
```

- Inspect headers (show content-type):

```bash
curl -I http://localhost:5000/random
```

Notes for integrators

- The server uses file-based caches under the Flask `instance` path (see `docs/README.md`).
- Cached JPEG filenames are deterministic: `md5(original_path).jpg`.
- Logs include cache hits, compression stats, client IP and user-agent in `instance/log/photomatic.log`.

# Photomatic API

Endpoints

- `/` (GET)

  - Serves the slideshow HTML page (`templates/index.html`).

- `/random` (GET)
  - Returns a single image for the slideshow.
  - Behavior: serves sequential same-day images per client IP; falls back to random selection from the general photo pool.
  - The client IP comes from Flask's `request.remote_addr`; selection state uses its SHA-256 hash and is shared by requests from that address.
  - Behind a reverse proxy, `remote_addr` is the proxy address unless trusted-proxy forwarding is configured.

Responses

- 200: Image served as `image/jpeg` (or compatible). The response body is the JPEG bytes.
- 404: No images found (empty photo directory or cache).
- 503: The cache service has not yet built the SQLite photo index.
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

- The photo index and client tracking are stored in `instance/cache/photomatic_cache.sqlite3` (see `docs/README.md`).
- Client tracking expires after 48 hours without requests; the cache is rebuilt at midnight.
- `/healthcheck` reports cache-service liveness and photo-index freshness.
- Cached JPEG filenames are deterministic: `md5(original_path).jpg`.
- Logs include cache hits, compression stats, client IP and user-agent in `instance/log/photomatic.log`.

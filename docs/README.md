# Photomatic Documentation

This folder contains lightweight developer documentation for Photomatic.

- Module reference: [modules.md](modules.md)
- HTTP API: [API.md](API.md)

Quick start

1. Create and activate a virtualenv, then install dependencies:

```bash
pip install -r requirements.txt
```

2. In a service terminal, build the index and keep the midnight/TTL service running:

```bash
python -m app.cache_service --build-once
python -m app.cache_service --schedule
```

3. In another terminal, run the app pointing to your photo folder:

```bash
python -m app.app --photos /path/to/photos --port 5000
```

4. Open the slideshow at http://localhost:5000

Where things live

- Photo index and client tracking: `instance/cache/photomatic_cache.sqlite3`
- Cached JPEGs: `instance/cache/photos/` (MD5(path).jpg)
- Logs: `instance/log/photomatic.log`

The cache service builds the SQLite photo index at startup and rebuilds it at
midnight. It classifies photos matching today's month and day (across years)
separately. Selection state is keyed by a SHA-256 hash of the client IP and
expires after 48 hours without requests. `/healthcheck` reports service
heartbeat and index status. `/clear_cache` clears the index and client tracking.
To reset manually, stop Photomatic and delete `photomatic_cache.sqlite3`; the
service recreates it on startup.

Client IP tracking uses Flask's `request.remote_addr`. When running behind a
reverse proxy, configure trusted proxy handling if per-device addresses are
needed; otherwise clients may share the proxy's tracking key.

If you want a runnable smoke test or a small Postman collection, tell me and I’ll add it.

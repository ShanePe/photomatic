# Photomatic Documentation

This folder contains lightweight developer documentation for Photomatic.

- Module reference: [modules.md](modules.md)
- HTTP API: [API.md](API.md)

Quick start

1. Create and activate a virtualenv, then install dependencies:

```bash
pip install -r requirements.txt
```

2. Run the app pointing to your photo folder:

```bash
python -m app.app --photos /path/to/photos --port 5000
```

3. Open the slideshow at http://localhost:5000

Where things live

- Cache files: `instance/cache/cache_all.txt`, `instance/cache/cache_same_day.txt`
- Cached JPEGs: `instance/cache/photos/` (MD5(path).jpg)
- Logs: `instance/log/photomatic.log`

If you want a runnable smoke test or a small Postman collection, tell me and I’ll add it.

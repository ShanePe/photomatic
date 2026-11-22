# Photomatic — Module Reference

This document lists the main modules in the Photomatic codebase and summarizes their responsibilities and public functions. Use this as a quick reference when navigating the code.

**app package**

- File: [app/**init**.py](app/__init__.py)

  - Exports: `app` (Flask instance), `create_app(instance_path=None)` — ensures instance directories exist and returns the shared Flask app.

- File: [app/globals.py](app/globals.py)

  - Purpose: Centralized, shared runtime state and configuration.
  - Key variables:
    - `app` — shared Flask instance.
    - `CONFIG` — settings loaded from `config.yaml` via `config_manager.load_config()`.
    - `MAX_WIDTH`, `MAX_HEIGHT` — image resizing limits.
    - `CACHE_DIR`, `CACHE_DIR_PHOTO`, `CACHE_DIR_LOG` — writable cache/log directories under `app.instance_path`.
    - `CACHE_LIMIT`, `SAME_DAY_CYCLE` — caching policies.
    - `PHOTO_ROOT`, `CACHE_DATE`, `BUILDING_CACHE`, `CACHE_COUNT`, `SAME_DAY_KEYS` — mutable runtime state used by cache/image modules.
    - `logger` — configured rotating file handler writing to `instance/log/photomatic.log`.

- File: [app/config_manager.py](app/config_manager.py)

  - Purpose: Load YAML configuration with safe defaults.
  - Publics:
    - `DEFAULT_CONFIG` — in-code defaults.
    - `load_config(path="config.yaml")` — merges file values into `DEFAULT_CONFIG`, ignoring unknown keys.
  - Usage: other modules call `load_config()` at startup to populate `CONFIG`.

- File: [app/image_utils.py](app/image_utils.py)

  - Purpose: Image reading, resizing, compression, HEIC conversion and caching.
  - Publics:
    - `resize_and_compress(path: str, overlay_text: str = "", quality: int = 75) -> BytesIO` —
      - Produces a JPEG BytesIO buffer.
      - Uses MD5(path) to name cached JPEGs in `instance/cache/photos/`.
      - Preserves orientation via EXIF transpose, resizes to `MAX_WIDTH`/`MAX_HEIGHT`, optionally draws overlay text, strips EXIF.
      - Logs original vs compressed sizes and triggers `prune_cache()` after writing new cache files.
    - `convert_heic_to_jpg(heic_path)` — simple HEIC -> JPEG conversion wrapper.

- File: [app/cache_manager.py](app/cache_manager.py)
  - Purpose: Build and maintain the SQLite photo index and prune cached JPEGs.
  - Publics / important functions:
    - `build_cache(base_dir)` —
      - Walks `base_dir` and transactionally stores photo paths with a same-day flag in `instance/cache/photomatic_cache.sqlite3`.
      - Same-day photos match today's month and day across years.
      - Fills `SAME_DAY_KEYS` with MD5(path) values for same-day photos so pruning retains them.
      - Uses `get_photo_date()` for date resolution.
    - `get_photo_date(path)` — determines date priority: filename patterns → EXIF (`DateTimeOriginal`, `DateTimeDigitized`, `DateTime`) → file mtime.
    - `parse_date_from_filename(filename)` — extracts YYYYMMDD or YYYY-MM-DD patterns.
    - `prune_cache()` — memory-efficient min-heap-based removal of oldest cached JPEGs until `CACHE_COUNT <= CACHE_LIMIT`; retains MD5 keys in `SAME_DAY_KEYS`.
    - `pick_file(base_dir)` — selects from the prebuilt SQLite index and never scans or rebuilds the photo directory.
    - `format_date_with_suffix(dt)` — helper to add ordinal suffixes to day numbers (e.g., `1st Jan 2020`).

- File: [app/cache_service.py](app/cache_service.py)
  - Purpose: Build the photo index at startup, rebuild it at midnight, expire inactive client records, and expose service health through the SQLite database.

- File: [app/client_photo_tracker.py](app/client_photo_tracker.py)
  - Purpose: Track photo selection state per SHA-256 hash of the client IP. Entries expire after 48 hours without activity.

**Top-level entry**

- File: [app/app.py](app/app.py)
  - Purpose: Application entrypoint and route handlers (keeps routes and session glue only).
  - Behavior:
    - Imports the shared `G` module (package-relative) and other helpers from `image_utils` and `cache_manager`.
    - Defines routes:
      - `/` — renders `templates/index.html`.
      - `/random` and `/api/random` — select from the prebuilt SQLite index and return an image or photo metadata.
      - `/healthcheck` — reports application API status and cache-service heartbeat/index status.
    - CLI helpers:
      - `parse_args()` — `--photos` and `--port`.
      - `run_app(args)` — sets `G.PHOTO_ROOT`, prunes initial cache if needed, and starts `G.app.run()`.

**Templates**

- File: [templates/index.html](templates/index.html)
  - Simple fullscreen slideshow UI (served by `/`). The JS front-end requests `/api/random` for photo metadata and displays the returned image with transitions.

Notes / Conventions

- The photo index and client tracking state share `instance/cache/photomatic_cache.sqlite3`; deleting it resets both.
- Cached JPEG filenames are MD5 hashes of the original path. `SAME_DAY_KEYS` stores those MD5 keys to prevent pruning the same-day images.
- Date resolution is deterministic and tolerant of missing EXIF — `get_photo_date()` falls back to mtime.
- All modules use package-relative imports (e.g., `from . import globals as G`) so code runs correctly using `python -m app.app` or `python -m app`.

If you'd like, I can also:

- generate an `API.md` that contains example calls and expected outputs for `/random`.
- add inline docstring expansions for any specific function you care about.

"""SQLite storage shared by the photo index and per-client tracking."""

import os
import sqlite3
import threading
from contextlib import contextmanager

_SCHEMA_LOCK = threading.RLock()
_INITIALIZED_PATHS = set()


def database_path():
    from . import globals as G

    return os.path.join(G.CACHE_DIR, G.CACHE_DATABASE_FILENAME)


def connect():
    """Open the cache database and ensure its schema exists."""
    from . import globals as G

    os.makedirs(G.CACHE_DIR, exist_ok=True)
    path = database_path()
    initialize_wal = not os.path.exists(path)
    connection = sqlite3.connect(path, timeout=30)
    with _SCHEMA_LOCK:
        if initialize_wal:
            connection.execute("PRAGMA journal_mode = WAL")
        if initialize_wal or path not in _INITIALIZED_PATHS:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS photos (
                    path TEXT PRIMARY KEY,
                    same_day INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS photos_by_day_and_path
                    ON photos (same_day, path);
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS clients (
                    client_key TEXT PRIMARY KEY,
                    last_seen REAL NOT NULL,
                    state_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cache_service_health (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    status TEXT NOT NULL,
                    heartbeat_at REAL NOT NULL,
                    last_success_at REAL,
                    last_error TEXT
                );
                """
            )
            _INITIALIZED_PATHS.add(path)
    return connection


@contextmanager
def open_database():
    """Provide a transaction-scoped connection that is always closed."""
    connection = connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def clear_database():
    """Clear indexed photos, build metadata, and all client state."""
    with open_database() as connection:
        connection.execute("DELETE FROM photos")
        connection.execute("DELETE FROM cache_metadata")
        connection.execute("DELETE FROM clients")


def cache_built_today():
    """Return whether the indexed photo collection is current for today."""
    if not os.path.isfile(database_path()):
        return False
    with open_database() as connection:
        row = connection.execute(
            "SELECT value FROM cache_metadata WHERE key = 'built_date'"
        ).fetchone()
    if not row:
        return False
    from datetime import date

    return row[0] == date.today().isoformat()


def set_cache_service_health(status, last_error=None, succeeded=False, now=None):
    """Persist cache-service liveness and the last build result."""
    import time

    heartbeat = time.time() if now is None else now
    with open_database() as connection:
        connection.execute(
            """
            INSERT INTO cache_service_health
                (id, status, heartbeat_at, last_success_at, last_error)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                heartbeat_at = excluded.heartbeat_at,
                last_success_at = COALESCE(
                    excluded.last_success_at,
                    cache_service_health.last_success_at
                ),
                last_error = excluded.last_error
            """,
            (
                status,
                heartbeat,
                heartbeat if succeeded else None,
                last_error,
            ),
        )


def get_cache_service_health(now=None, max_age_seconds=90):
    """Return whether the cache service is healthy and its latest error."""
    import time

    if not os.path.isfile(database_path()):
        return {
            "ok": False,
            "status": "unavailable",
            "last_error": "Cache service has not started",
        }
    now = time.time() if now is None else now
    with open_database() as connection:
        row = connection.execute(
            """
            SELECT status, heartbeat_at, last_success_at, last_error
            FROM cache_service_health WHERE id = 1
            """
        ).fetchone()
    if row is None:
        return {
            "ok": False,
            "status": "unavailable",
            "last_error": "Cache service health is unavailable",
        }
    status, heartbeat_at, last_success_at, last_error = row
    fresh = now - heartbeat_at <= max_age_seconds
    healthy = status == "healthy" and fresh and cache_built_today()
    if status == "building" and fresh:
        last_error = "Photo index rebuild is in progress"
    elif not fresh and not last_error:
        last_error = "Cache service heartbeat is stale"
    return {
        "ok": healthy,
        "status": status,
        "last_error": None if healthy else last_error or "Photo cache is not current",
        "last_heartbeat_at": heartbeat_at,
        "last_success_at": last_success_at,
    }


def cache_service_is_building():
    """Return whether the background service is rebuilding the photo index."""
    if not os.path.isfile(database_path()):
        return False
    with open_database() as connection:
        row = connection.execute(
            "SELECT status FROM cache_service_health WHERE id = 1"
        ).fetchone()
    return bool(row and row[0] == "building")

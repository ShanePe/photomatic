"""Persistent, per-client photo selection state."""

import datetime
import hashlib
import ipaddress
import json
import os
import random
import time

from .cache_database import database_path, open_database

CLIENT_TTL_SECONDS = 48 * 60 * 60


class CacheNotReadyError(RuntimeError):
    """Raised when the cache service has not built its photo indexes."""


def client_key_from_ip(client_ip):
    """Hash a normalized client IP so the raw address is never stored."""
    try:
        normalized_ip = ipaddress.ip_address(client_ip).compressed
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid client IP address") from exc
    return hashlib.sha256(normalized_ip.encode("ascii")).hexdigest()


def _default_state(today):
    return {
        "date": today,
        "phase": "same_day",
        "same_day_index": 0,
        "random_count": 0,
    }


def select_photo(client_key, random_pool_size=100):
    """Select and persist the next photo for a hashed client IP."""
    if not isinstance(client_key, str) or len(client_key) != 64:
        raise ValueError("Invalid client key")

    today = str(datetime.date.today())
    now = time.time()
    pool_size = max(0, int(random_pool_size))

    with open_database() as connection:
        connection.execute("BEGIN IMMEDIATE")
        cache_date = connection.execute(
            "SELECT value FROM cache_metadata WHERE key = 'built_date'"
        ).fetchone()
        if not cache_date or cache_date[0] != today:
            raise CacheNotReadyError("Photo cache indexes are not ready")
        connection.execute(
            "DELETE FROM clients WHERE last_seen <= ?",
            (now - CLIENT_TTL_SECONDS,),
        )
        row = connection.execute(
            "SELECT state_json FROM clients WHERE client_key = ?",
            (client_key,),
        ).fetchone()
        try:
            state = json.loads(row[0]) if row else _default_state(today)
        except (TypeError, json.JSONDecodeError):
            state = _default_state(today)
        if state.get("date") != today:
            state = _default_state(today)

        phase = state.get("phase")
        if phase not in {"same_day", "random"}:
            state = _default_state(today)
            phase = "same_day"

        same_day_count = connection.execute(
            "SELECT COUNT(*) FROM photos WHERE same_day = 1"
        ).fetchone()[0]
        all_count = connection.execute(
            "SELECT COUNT(*) FROM photos WHERE same_day = 0"
        ).fetchone()[0]
        path = None

        if phase == "random" and state.get("random_count", 0) >= pool_size:
            state = _default_state(today)
            phase = "same_day"

        if phase == "same_day":
            same_day_index = max(0, int(state.get("same_day_index", 0)))
            if same_day_index < same_day_count:
                row = connection.execute(
                    """
                    SELECT path FROM photos WHERE same_day = 1
                    ORDER BY path LIMIT 1 OFFSET ?
                    """,
                    (same_day_index,),
                ).fetchone()
                path = row[0] if row else None
                state["same_day_index"] = same_day_index + 1
            elif all_count:
                state["phase"] = "random"
                state["random_count"] = 0
                phase = "random"

        if path is None and phase == "random" and all_count:
            path = connection.execute(
                """
                SELECT path FROM photos WHERE same_day = 0
                ORDER BY path LIMIT 1 OFFSET ?
                """,
                (random.randrange(all_count),),
            ).fetchone()[0]
            if path:
                state["random_count"] = int(state.get("random_count", 0)) + 1

        # If today's set is the only available pool, cycle it without failing.
        if path is None and same_day_count:
            path = connection.execute(
                "SELECT path FROM photos WHERE same_day = 1 ORDER BY path LIMIT 1"
            ).fetchone()[0]
            state = _default_state(today)
            state["same_day_index"] = 1

        connection.execute(
            """
            INSERT INTO clients (client_key, last_seen, state_json)
            VALUES (?, ?, ?)
            ON CONFLICT(client_key) DO UPDATE SET
                last_seen = excluded.last_seen,
                state_json = excluded.state_json
            """,
            (client_key, now, json.dumps(state)),
        )
        return path


def clear_client_photo_tracking():
    """Forget all browser selection state without removing the database file."""
    if not os.path.exists(database_path()):
        return
    with open_database() as connection:
        connection.execute("DELETE FROM clients")


def remove_expired_clients(now=None):
    """Delete browser state untouched for at least 48 hours."""
    now = time.time() if now is None else now
    if not os.path.exists(database_path()):
        return 0
    with open_database() as connection:
        cursor = connection.execute(
            "DELETE FROM clients WHERE last_seen <= ?",
            (now - CLIENT_TTL_SECONDS,),
        )
        return cursor.rowcount

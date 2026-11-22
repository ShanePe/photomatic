"""Tests for persistent IP-keyed photo tracking."""

import datetime
import os
import sqlite3
import time

import pytest

from app import globals as G
from app.cache_database import (
    get_cache_service_health,
    open_database,
    set_cache_service_health,
)
from app.client_photo_tracker import (
    CLIENT_TTL_SECONDS,
    CacheNotReadyError,
    client_key_from_ip,
    remove_expired_clients,
    select_photo,
)


def setup_cache(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    G.CACHE_DIR = str(cache_dir)
    today = datetime.date.today()
    same_day = tmp_path / f"{today.strftime('%Y%m%d')}_today.jpg"
    other_day = tmp_path / "20180101_other.jpg"
    with open_database() as connection:
        connection.executemany(
            "INSERT INTO photos (path, same_day) VALUES (?, ?)",
            [(str(same_day), 1), (str(other_day), 0)],
        )
        connection.execute(
            "INSERT INTO cache_metadata (key, value) VALUES ('built_date', ?)",
            (today.isoformat(),),
        )
    return cache_dir, str(same_day), str(other_day)


def test_ip_key_is_stable_and_does_not_store_raw_ip():
    key = client_key_from_ip("192.168.1.20")

    assert key == client_key_from_ip("192.168.1.20")
    assert key != client_key_from_ip("192.168.1.21")
    assert len(key) == 64
    assert "192.168.1.20" not in key


def test_selection_state_is_persisted_by_client_ip(tmp_path):
    setup_cache(tmp_path)
    key = client_key_from_ip("192.168.1.20")

    assert select_photo(key, random_pool_size=1).endswith("_today.jpg")
    assert select_photo(key, random_pool_size=1).endswith("_other.jpg")
    assert select_photo(key, random_pool_size=1).endswith("_today.jpg")

    connection = sqlite3.connect(os.path.join(G.CACHE_DIR, "photomatic_cache.sqlite3"))
    try:
        count = connection.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    finally:
        connection.close()
    assert count == 1


def test_expired_client_state_is_removed(tmp_path):
    cache_dir, _, _ = setup_cache(tmp_path)
    key = client_key_from_ip("192.168.1.20")
    select_photo(key)
    database = os.path.join(cache_dir, "photomatic_cache.sqlite3")
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "UPDATE clients SET last_seen = ? WHERE client_key = ?",
            (time.time() - CLIENT_TTL_SECONDS - 1, key),
        )
        connection.commit()
    finally:
        connection.close()

    assert remove_expired_clients() == 1


def test_selection_fails_when_cache_indexes_are_missing(tmp_path):
    G.CACHE_DIR = str(tmp_path / "empty-cache")
    os.makedirs(G.CACHE_DIR)

    with pytest.raises(CacheNotReadyError):
        select_photo(client_key_from_ip("192.168.1.20"))


def test_selection_fails_when_cache_index_is_stale(tmp_path):
    setup_cache(tmp_path)
    with open_database() as connection:
        connection.execute(
            "UPDATE cache_metadata SET value = '2000-01-01' WHERE key = 'built_date'"
        )

    with pytest.raises(CacheNotReadyError):
        select_photo(client_key_from_ip("192.168.1.20"))


def test_cache_service_health_requires_fresh_heartbeat(tmp_path):
    setup_cache(tmp_path)
    set_cache_service_health("healthy", succeeded=True, now=1000)

    assert get_cache_service_health(now=1090)["ok"]
    stale = get_cache_service_health(now=1091)
    assert not stale["ok"]
    assert stale["last_error"] == "Cache service heartbeat is stale"

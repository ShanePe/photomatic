"""Session-based photo tracking using hash-based duplicate prevention.

Each browser gets a unique session ID. We track the MD5 hash of each
photo path served in that session, preventing duplicates within the same
session. Sessions automatically expire after EXPIRATION_HOURS.

The serving pattern is:
1. Serve all today's photos sequentially (same_day_photos)
2. Serve N random photos (random_pool_size from config)
3. Repeat from step 1

This ensures today's photos appear regularly without being drowned out by
the larger general photo pool.
"""

import hashlib
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from . import globals as G

# Session data structure:
# {
#   session_id: {
#       "created": timestamp,
#       "cycle_phase": "same_day" | "random",
#       "same_day_hashes": {hash1, hash2, ...},  # hashes of same-day photos shown
#       "random_shown_count": int,                # count of random photos shown in current cycle
#       "cycle_random_pool_size": int,            # how many random photos in this cycle
#   }
# }
_sessions = {}
_sessions_lock = threading.RLock()

# How many hours before a session is considered expired
EXPIRATION_HOURS = 24


def _get_hash_for_path(path: str) -> str:
    """Get MD5 hash of a photo path for deduplication."""
    return hashlib.md5(path.encode()).hexdigest()


def _cleanup_expired_sessions():
    """Remove sessions older than EXPIRATION_HOURS."""
    with _sessions_lock:
        now = time.time()
        expired = [
            sid for sid, data in _sessions.items()
            if now - data["created"] > (EXPIRATION_HOURS * 3600)
        ]
        for sid in expired:
            del _sessions[sid]
            G.logger.info("[SessionHashTracker] Expired session: %s", sid)


def register_session(session_id: str, random_pool_size: int = 100) -> None:
    """Register a new session or touch an existing one.
    
    Args:
        session_id: Unique identifier for this browser session
        random_pool_size: How many random photos to show before cycling back to same-day
    """
    _cleanup_expired_sessions()
    with _sessions_lock:
        _sessions[session_id] = {
            "created": time.time(),
            "cycle_phase": "same_day",
            "same_day_hashes": set(),
            "random_shown_count": 0,
            "cycle_random_pool_size": random_pool_size,
        }
    G.logger.debug("[SessionHashTracker] Registered session: %s (pool_size=%d)", 
                   session_id, random_pool_size)


def get_cycle_phase(session_id: str) -> str:
    """Get the current cycle phase for this session: 'same_day' or 'random'."""
    _cleanup_expired_sessions()
    with _sessions_lock:
        if session_id not in _sessions:
            return "same_day"
        return _sessions[session_id]["cycle_phase"]


def mark_same_day_photo_served(session_id: str, path: str) -> None:
    """Mark a same-day photo as served in this session."""
    _cleanup_expired_sessions()
    path_hash = _get_hash_for_path(path)
    with _sessions_lock:
        if session_id not in _sessions:
            register_session(session_id)
        _sessions[session_id]["same_day_hashes"].add(path_hash)
    G.logger.debug(
        "[SessionHashTracker] Marked same-day photo in session %s: %s",
        session_id,
        path,
    )


def mark_random_photo_served(session_id: str) -> None:
    """Increment the random photo count for the current cycle phase."""
    _cleanup_expired_sessions()
    with _sessions_lock:
        if session_id not in _sessions:
            register_session(session_id)
        _sessions[session_id]["random_shown_count"] += 1
    G.logger.debug(
        "[SessionHashTracker] Random photo served in session %s (count=%d)",
        session_id,
        _sessions[session_id]["random_shown_count"],
    )


def has_same_day_photo_been_served(session_id: str, path: str) -> bool:
    """Check if a same-day photo has already been served in this cycle."""
    _cleanup_expired_sessions()
    path_hash = _get_hash_for_path(path)
    with _sessions_lock:
        if session_id not in _sessions:
            return False
        return path_hash in _sessions[session_id]["same_day_hashes"]


def should_transition_to_random_phase(session_id: str) -> bool:
    """Check if we've exhausted same-day photos and should move to random phase."""
    _cleanup_expired_sessions()
    with _sessions_lock:
        if session_id not in _sessions:
            return False
        return _sessions[session_id]["cycle_phase"] == "same_day"


def should_transition_to_same_day_phase(session_id: str) -> bool:
    """Check if we've shown enough random photos and should cycle back to same-day."""
    _cleanup_expired_sessions()
    with _sessions_lock:
        if session_id not in _sessions:
            return False
        
        data = _sessions[session_id]
        return (
            data["cycle_phase"] == "random"
            and data["random_shown_count"] >= data["cycle_random_pool_size"]
        )


def transition_to_random_phase(session_id: str) -> None:
    """Move the session to the random photo phase."""
    with _sessions_lock:
        if session_id in _sessions:
            _sessions[session_id]["cycle_phase"] = "random"
            _sessions[session_id]["random_shown_count"] = 0
    G.logger.info("[SessionHashTracker] Session %s transitioned to RANDOM phase", session_id)


def transition_to_same_day_phase(session_id: str) -> None:
    """Move the session back to the same-day photo phase and reset tracking."""
    with _sessions_lock:
        if session_id in _sessions:
            _sessions[session_id]["cycle_phase"] = "same_day"
            _sessions[session_id]["same_day_hashes"] = set()
            _sessions[session_id]["random_shown_count"] = 0
    G.logger.info("[SessionHashTracker] Session %s transitioned to SAME_DAY phase", session_id)


def reset_session(session_id: str, random_pool_size: int = 100) -> None:
    """Reset session to start fresh from same-day photos."""
    with _sessions_lock:
        _sessions[session_id] = {
            "created": time.time(),
            "cycle_phase": "same_day",
            "same_day_hashes": set(),
            "random_shown_count": 0,
            "cycle_random_pool_size": random_pool_size,
        }
    G.logger.info("[SessionHashTracker] Reset session: %s", session_id)


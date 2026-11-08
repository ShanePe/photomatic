"""Server-side slideshow session state helpers."""

import os
from datetime import timedelta

from cachelib import FileSystemCache
from flask import g, session as flask_session
from flask_session import Session

from . import globals as G

PHOTO_STATE_SESSION_KEY = "photo_state"
_session_extension = Session()


def configure_server_sessions():
    """Configure filesystem-backed sessions for the current instance path."""
    session_dir = os.path.join(G.app.instance_path, "sessions")
    os.makedirs(session_dir, exist_ok=True)

    secure_cookie = os.environ.get("SESSION_COOKIE_SECURE", "").strip().lower()
    G.app.config.update(
        SESSION_TYPE="cachelib",
        SESSION_CACHELIB=FileSystemCache(session_dir, threshold=10000),
        SESSION_PERMANENT=True,
        PERMANENT_SESSION_LIFETIME=timedelta(days=365),
        SESSION_COOKIE_NAME="photomatic_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=secure_cookie in {"1", "true", "yes", "on"},
    )
    _session_extension.init_app(G.app)


def _coerce_non_negative_int(value, default: int = 0) -> int:
    """Coerce a session value to a non-negative integer."""
    try:
        return max(0, int(value if value is not None else default))
    except (TypeError, ValueError):
        return default


def default_photo_state() -> dict[str, int | str | None]:
    """Return the default ordered photo state for a client session."""
    return {
        "photo_date": None,
        "photo_index": 0,
        "photo_served": 0,
        "same_day_exhausted_date": None,
        "initialized": True,
    }


def get_photo_state() -> dict[str, int | str | None]:
    """Read slideshow order state from the server-side client session."""
    cached = getattr(g, "photo_state", None)
    if isinstance(cached, dict):
        return cached

    state = flask_session.get(PHOTO_STATE_SESSION_KEY)
    if not isinstance(state, dict):
        state = default_photo_state()

    cleaned = default_photo_state()
    cleaned.update(
        {
            "photo_date": state.get("photo_date"),
            "same_day_exhausted_date": state.get("same_day_exhausted_date"),
            "initialized": bool(state.get("initialized", True)),
        }
    )
    cleaned["photo_index"] = _coerce_non_negative_int(state.get("photo_index", 0))
    cleaned["photo_served"] = _coerce_non_negative_int(state.get("photo_served", 0))

    g.photo_state = cleaned
    return cleaned


def persist_photo_state(response, state: dict | None = None):
    """Persist slideshow state in the server-side client session."""
    safe_state = default_photo_state()
    state_to_persist = state or get_photo_state()
    if isinstance(state_to_persist, dict):
        safe_state.update(state_to_persist)

    safe_state["photo_index"] = _coerce_non_negative_int(
        safe_state.get("photo_index", 0)
    )
    safe_state["photo_served"] = _coerce_non_negative_int(
        safe_state.get("photo_served", 0)
    )
    safe_state["initialized"] = bool(safe_state.get("initialized", True))

    flask_session[PHOTO_STATE_SESSION_KEY] = safe_state
    flask_session.permanent = True
    g.photo_state = safe_state
    return response


def clear_photo_state():
    """Remove slideshow state from the current client session."""
    flask_session.pop(PHOTO_STATE_SESSION_KEY, None)
    g.pop("photo_state", None)

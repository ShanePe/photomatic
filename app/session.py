"""Browser-local slideshow state helpers.

The photo rotation order is stored in a cookie so it is scoped to each browser
instead of a server-side Flask session.
"""

import json

from flask import g, request

PHOTO_STATE_COOKIE = "photomatic_photo_state"


def _coerce_non_negative_int(value, default: int = 0) -> int:
    """Coerce a cookie value to a non-negative integer."""
    try:
        return max(0, int(value if value is not None else default))
    except (TypeError, ValueError):
        return default


def default_photo_state() -> dict[str, int | str | None]:
    """Return the default ordered photo state for a browser."""
    return {
        "photo_date": None,
        "photo_index": 0,
        "photo_served": 0,
        "same_day_exhausted_date": None,
        "initialized": True,
    }


def get_photo_state() -> dict[str, int | str | None]:
    """Read the slideshow order state from the browser's cookie."""
    cached = getattr(g, "photo_state", None)
    if isinstance(cached, dict):
        return cached

    raw = request.cookies.get(PHOTO_STATE_COOKIE)
    if not raw:
        return default_photo_state()

    try:
        state = json.loads(raw)
    except (TypeError, ValueError):
        return default_photo_state()

    if not isinstance(state, dict):
        return default_photo_state()

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


def encode_photo_state(state: dict | None) -> str:
    """Serialize slideshow state for storage in a browser cookie."""
    safe_state = default_photo_state()
    if isinstance(state, dict):
        safe_state.update(state)

    return json.dumps(
        {
            "photo_date": safe_state.get("photo_date"),
            "photo_index": _coerce_non_negative_int(safe_state.get("photo_index", 0)),
            "photo_served": _coerce_non_negative_int(safe_state.get("photo_served", 0)),
            "same_day_exhausted_date": safe_state.get("same_day_exhausted_date"),
            "initialized": bool(safe_state.get("initialized", True)),
        },
        separators=(",", ":"),
    )


def persist_photo_state(response, state: dict | None = None):
    """Persist the browser-scoped slideshow state on the current response."""
    cookie_value = encode_photo_state(state or get_photo_state())
    response.set_cookie(
        PHOTO_STATE_COOKIE,
        cookie_value,
        max_age=60 * 60 * 24 * 365,
        path="/",
        samesite="None",
        secure=True,
        httponly=True,
    )
    return response

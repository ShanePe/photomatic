"""Session management utilities for photo tracking."""

from flask import session

from . import globals as G


@G.app.before_request
def reset_on_first_visit():
    """
    Reset session state on first visit.

    Clears the session and initializes default values for photo tracking
    if this is the user's first visit to the application.
    """
    if "initialized" not in session:
        session.clear()
        session["photo_index"] = 0
        session["photo_served"] = 0
        session["initialized"] = True

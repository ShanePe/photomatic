"""WSGI entrypoint for production servers (e.g., Gunicorn)."""

from . import routes  # pylint: disable=unused-import
from . import session  # pylint: disable=unused-import
from .globals import app as application
from .utils import initialize_app_state

initialize_app_state()

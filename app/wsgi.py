"""WSGI entrypoint for production servers (e.g., Gunicorn)."""

from . import routes  # pylint: disable=unused-import
from . import session  # pylint: disable=unused-import
from . import globals as G
from .utils import initialize_app_state

initialize_app_state()
application = G.app

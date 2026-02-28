"""Application entrypoint that wires routes to split modules."""

from . import routes  # pylint: disable=unused-import
from . import session  # pylint: disable=unused-import
from .utils import run_app


if __name__ == "__main__":
    run_app()

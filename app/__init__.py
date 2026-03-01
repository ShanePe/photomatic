"""Photomatic application package initializer.

Exports the shared Flask `app` (from `globals`) and a minimal
`create_app()` factory that ensures instance directories exist.
"""

from .globals import app, ensure_instance_dirs, logger, CONFIG

__all__ = ["app", "create_app", "logger", "CONFIG"]


def create_app(instance_path: str | None = None):
    """Return the shared Flask `app`, optionally setting `instance_path` first.

    If `instance_path` is provided, `app.instance_path` is updated before
    ensuring required instance directories (`cache`, `cache/photos`, `log`).
    """
    if instance_path:
        app.instance_path = instance_path

    ensure_instance_dirs(app.instance_path)
    logger.info("Photomatic app initialized; instance_path=%s", app.instance_path)
    return app

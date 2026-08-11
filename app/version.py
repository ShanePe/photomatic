"""Application version helpers."""

from pathlib import Path


def _read_version(default: str = "0.0.0") -> str:
    """Read semantic version from repository VERSION file."""
    version_file = Path(__file__).resolve().parent.parent / "VERSION"
    try:
        value = version_file.read_text(encoding="utf-8").strip()
        return value or default
    except OSError:
        return default


__version__ = _read_version()

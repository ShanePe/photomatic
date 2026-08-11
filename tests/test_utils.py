"""Tests for startup utility behavior."""

# cspell:ignore delenv

import importlib
import sys

import app.utils as U


class _LoggerStub:
    def __init__(self):
        """Initialize captured logger call lists for assertions."""
        self.info_calls = []
        self.warning_calls = []

    def info(self, msg, *args):
        """Record info-level log calls."""
        self.info_calls.append((msg, args))

    def warning(self, msg, *args):
        """Record warning-level log calls."""
        self.warning_calls.append((msg, args))


class _AppStub:
    def __init__(self):
        """Initialize collected app.run call arguments."""
        self.run_calls = []

    def run(self, **kwargs):
        """Capture app.run kwargs for assertions."""
        self.run_calls.append(kwargs)


def test_run_app_uses_port_env_override(monkeypatch):
    """PORT env var should override config app.port when valid."""
    app_stub = _AppStub()
    logger_stub = _LoggerStub()

    monkeypatch.setenv("PORT", "8081")
    monkeypatch.setattr(
        U.G, "CONFIG", {"app": {"port": 5000}, "paths": {"photo_dir": "/x"}}
    )
    monkeypatch.setattr(U.G, "app", app_stub)
    monkeypatch.setattr(U.G, "logger", logger_stub)
    monkeypatch.setattr(U.G, "CACHE_LIMIT_ENABLED", False)
    monkeypatch.setattr(U.G, "CACHE_COUNT", 0)
    monkeypatch.setattr(U.G, "CACHE_LIMIT", 10)

    U.run_app()

    assert app_stub.run_calls[0]["port"] == 8081


def test_run_app_falls_back_to_config_port_on_invalid_env(monkeypatch):
    """Invalid PORT env var should log warning and use config port."""
    app_stub = _AppStub()
    logger_stub = _LoggerStub()

    monkeypatch.setenv("PORT", "not-a-number")
    monkeypatch.setattr(
        U.G, "CONFIG", {"app": {"port": 5000}, "paths": {"photo_dir": "/x"}}
    )
    monkeypatch.setattr(U.G, "app", app_stub)
    monkeypatch.setattr(U.G, "logger", logger_stub)
    monkeypatch.setattr(U.G, "CACHE_LIMIT_ENABLED", False)
    monkeypatch.setattr(U.G, "CACHE_COUNT", 0)
    monkeypatch.setattr(U.G, "CACHE_LIMIT", 10)

    U.run_app()

    assert app_stub.run_calls[0]["port"] == 5000
    assert logger_stub.warning_calls


def test_run_app_disables_reloader_when_debugger_attached(monkeypatch):
    """Debugger-attached runs should disable Flask reloader to avoid SystemExit."""
    app_stub = _AppStub()
    logger_stub = _LoggerStub()

    monkeypatch.setenv("APP_DEBUG", "1")
    monkeypatch.setattr(
        U.G, "CONFIG", {"app": {"port": 5000}, "paths": {"photo_dir": "/x"}}
    )
    monkeypatch.setattr(U.G, "app", app_stub)
    monkeypatch.setattr(U.G, "logger", logger_stub)
    monkeypatch.setattr(U.G, "CACHE_LIMIT_ENABLED", False)
    monkeypatch.setattr(U.G, "CACHE_COUNT", 0)
    monkeypatch.setattr(U.G, "CACHE_LIMIT", 10)
    monkeypatch.setattr(U, "_is_debugger_attached", lambda: True)

    U.run_app()

    assert app_stub.run_calls[0]["debug"] is True
    assert app_stub.run_calls[0]["use_reloader"] is False


def test_run_app_enables_reloader_when_debug_no_debugger(monkeypatch):
    """Debug runs without debugger should keep reloader enabled."""
    app_stub = _AppStub()
    logger_stub = _LoggerStub()

    monkeypatch.setenv("APP_DEBUG", "true")
    monkeypatch.setattr(
        U.G, "CONFIG", {"app": {"port": 5000}, "paths": {"photo_dir": "/x"}}
    )
    monkeypatch.setattr(U.G, "app", app_stub)
    monkeypatch.setattr(U.G, "logger", logger_stub)
    monkeypatch.setattr(U.G, "CACHE_LIMIT_ENABLED", False)
    monkeypatch.setattr(U.G, "CACHE_COUNT", 0)
    monkeypatch.setattr(U.G, "CACHE_LIMIT", 10)
    monkeypatch.setattr(U, "_is_debugger_attached", lambda: False)

    U.run_app()

    assert app_stub.run_calls[0]["debug"] is True
    assert app_stub.run_calls[0]["use_reloader"] is True


def test_run_app_debug_defaults_off(monkeypatch):
    """Without env toggles, debug mode should default to off."""
    app_stub = _AppStub()
    logger_stub = _LoggerStub()

    monkeypatch.delenv("APP_DEBUG", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    monkeypatch.setattr(
        U.G, "CONFIG", {"app": {"port": 5000}, "paths": {"photo_dir": "/x"}}
    )
    monkeypatch.setattr(U.G, "app", app_stub)
    monkeypatch.setattr(U.G, "logger", logger_stub)
    monkeypatch.setattr(U.G, "CACHE_LIMIT_ENABLED", False)
    monkeypatch.setattr(U.G, "CACHE_COUNT", 0)
    monkeypatch.setattr(U.G, "CACHE_LIMIT", 10)
    monkeypatch.setattr(U, "_is_debugger_attached", lambda: False)

    U.run_app()

    assert app_stub.run_calls[0]["debug"] is False
    assert app_stub.run_calls[0]["use_reloader"] is False


def test_redact_sensitive_values_masks_known_sensitive_keys():
    """Sensitive key-like fields should be redacted in startup config logging."""
    data = {
        "weather": {"api_key": "abc", "token": "def", "enabled": True},
        "plain": "ok",
    }

    result = U.redact_sensitive_values(data)

    assert result["weather"]["api_key"] == "***REDACTED***"
    assert result["weather"]["token"] == "***REDACTED***"
    assert result["weather"]["enabled"] is True
    assert result["plain"] == "ok"


def test_initialize_app_state_sets_photo_root(monkeypatch):
    """Shared initialization should set PHOTO_ROOT from config paths."""
    logger_stub = _LoggerStub()

    monkeypatch.setattr(
        U.G, "CONFIG", {"paths": {"photo_dir": "/photos"}, "app": {"port": 5000}}
    )
    monkeypatch.setattr(U.G, "logger", logger_stub)
    monkeypatch.setattr(U.G, "CACHE_LIMIT_ENABLED", False)
    monkeypatch.setattr(U.G, "CACHE_COUNT", 0)
    monkeypatch.setattr(U.G, "CACHE_LIMIT", 10)
    monkeypatch.setattr(U.G, "PHOTO_ROOT", None)

    U.initialize_app_state()

    assert U.G.PHOTO_ROOT == "/photos"


def test_wsgi_import_initializes_photo_root(monkeypatch):
    """Importing app.wsgi should initialize shared runtime state for Gunicorn."""
    logger_stub = _LoggerStub()

    monkeypatch.setattr(
        U.G, "CONFIG", {"paths": {"photo_dir": "/photos"}, "app": {"port": 5000}}
    )
    monkeypatch.setattr(U.G, "logger", logger_stub)
    monkeypatch.setattr(U.G, "CACHE_LIMIT_ENABLED", False)
    monkeypatch.setattr(U.G, "CACHE_COUNT", 0)
    monkeypatch.setattr(U.G, "CACHE_LIMIT", 10)
    monkeypatch.setattr(U.G, "PHOTO_ROOT", None)
    monkeypatch.setattr(U.G.app, "_got_first_request", False)

    sys.modules.pop("app.wsgi", None)
    wsgi = importlib.import_module("app.wsgi")

    importlib.reload(wsgi)

    assert U.G.PHOTO_ROOT == "/photos"

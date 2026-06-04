"""Tests for startup utility behavior."""

import app.utils as U


class _LoggerStub:
    def __init__(self):
        self.info_calls = []
        self.warning_calls = []

    def info(self, msg, *args):
        self.info_calls.append((msg, args))

    def warning(self, msg, *args):
        self.warning_calls.append((msg, args))


class _AppStub:
    def __init__(self):
        self.run_calls = []

    def run(self, **kwargs):
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

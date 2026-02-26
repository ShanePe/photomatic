"""Weather mapping utilities for standardizing different API responses."""

import time
from . import globals as G

# Open-Meteo WMO weather codes to standardized condition names
OPENMETEO_CODE_MAP = {
    0: "clear-day",
    1: "partly-cloudy-day",
    2: "cloudy",
    3: "overcast",
    45: "fog",
    48: "fog",
    51: "drizzle",
    53: "drizzle",
    55: "drizzle",
    61: "rain",
    63: "rain",
    65: "rain",
    71: "snow",
    73: "snow",
    75: "snow",
    80: "rain",
    81: "rain",
    82: "rain",
    95: "thunderstorms",
    96: "thunderstorms",
    99: "thunderstorms",
}

# Met.no symbol codes to standardized condition names
METNO_SYMBOL_MAP = {
    "clearsky_day": "clear-day",
    "clearsky_night": "clear-day",
    "fair_day": "clear-day",
    "fair_night": "clear-day",
    "partlycloudy_day": "partly-cloudy-day",
    "partlycloudy_night": "partly-cloudy-day",
    "cloudy": "cloudy",
    "overcast": "cloudy",
    "fog": "fog",
    "rain": "rain",
    "lightrain": "drizzle",
    "rainandthunder": "thunderstorms",
    "lightsnow": "snow",
    "snow": "snow",
    "rainandsnow": "snow",
    "sleet": "rain",
    "snowandthunder": "thunderstorms",
    "drizzle": "drizzle",
    "lightsleet": "rain",
    "heavysnowandthunder": "thunderstorms",
    "heavyrainandthunder": "thunderstorms",
    "heavyrain": "rain",
    "lightsnowandthunder": "thunderstorms",
    "heavysleet": "rain",
    "heavysleetandthunder": "thunderstorms",
}


def map_openmeteo_code(code: int) -> str:
    """Map Open-Meteo weather code to standardized condition name."""
    return OPENMETEO_CODE_MAP.get(code, "cloudy")


# Weather cache: stores responses with timestamps
# Format: { "lat,lon": {"data": {...}, "timestamp": time.time()} }
_weather_cache = {}
_CACHE_TTL = 30 * 60  # 30 minutes in seconds
_MAX_CACHE_ENTRIES = 100  # Prevent unbounded memory growth


def _cleanup_expired_cache():
    """Remove all expired entries from weather cache."""
    current_time = time.time()
    expired_keys = [
        key
        for key, data in _weather_cache.items()
        if current_time - data["timestamp"] >= _CACHE_TTL
    ]
    for key in expired_keys:
        del _weather_cache[key]
    if expired_keys:
        G.logger.info(
            "Weather cache cleanup: removed %d expired entries", len(expired_keys)
        )


def _enforce_cache_limit():
    """Enforce maximum cache size by removing oldest entries if needed."""
    if len(_weather_cache) > _MAX_CACHE_ENTRIES:
        # Remove oldest 20% of entries
        entries_to_remove = len(_weather_cache) // 5
        oldest = sorted(_weather_cache.items(), key=lambda x: x[1]["timestamp"])[
            :entries_to_remove
        ]
        for key, _ in oldest:
            del _weather_cache[key]
        G.logger.info(
            "Weather cache limited: removed %d oldest entries", entries_to_remove
        )


def get_cached_weather(lat: str, lon: str) -> dict | None:
    """Get cached weather data if it exists and hasn't expired."""
    _cleanup_expired_cache()
    cache_key = f"{lat},{lon}"
    if cache_key in _weather_cache:
        cached = _weather_cache[cache_key]
        if time.time() - cached["timestamp"] < _CACHE_TTL:
            return cached["data"]
    return None


def set_cached_weather(lat: str, lon: str, data: dict) -> None:
    """Cache weather data with current timestamp."""
    _cleanup_expired_cache()
    _enforce_cache_limit()
    cache_key = f"{lat},{lon}"
    _weather_cache[cache_key] = {"data": data, "timestamp": time.time()}
    G.logger.info(
        "Added cached weather for %s (cache size: %d)", cache_key, len(_weather_cache)
    )


def map_metno_symbol(symbol_code: str) -> str:
    """Map Met.no symbol code to standardized condition name."""
    return METNO_SYMBOL_MAP.get(symbol_code, "cloudy")

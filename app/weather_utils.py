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


def get_cached_weather(lat: str, lon: str) -> dict | None:
    """Get cached weather data if it exists and hasn't expired."""
    cache_key = f"{lat},{lon}"
    if cache_key in _weather_cache:
        cached = _weather_cache[cache_key]
        if time.time() - cached["timestamp"] < _CACHE_TTL:
            return cached["data"]
        else:
            # Cache expired, remove it
            del _weather_cache[cache_key]
    return None


def set_cached_weather(lat: str, lon: str, data: dict) -> None:
    """Cache weather data with current timestamp."""
    cache_key = f"{lat},{lon}"
    _weather_cache[cache_key] = {"data": data, "timestamp": time.time()}
    G.logger.info("Added cached weather for %s", cache_key)


def map_metno_symbol(symbol_code: str) -> str:
    """Map Met.no symbol code to standardized condition name."""
    return METNO_SYMBOL_MAP.get(symbol_code, "cloudy")

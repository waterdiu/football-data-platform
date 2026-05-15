from __future__ import annotations

import json
import os
from urllib.parse import urlencode
from urllib.request import urlopen

OPENWEATHER_CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"


def _float_or_none(value: object) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    if value in ("", None):
        return None
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _weather_item(payload: dict) -> dict:
    weather = payload.get("weather") or []
    return weather[0] if weather and isinstance(weather[0], dict) else {}


def _rain_1h(payload: dict) -> float | None:
    rain = payload.get("rain") or {}
    return _float_or_none(rain.get("1h") or rain.get("one_hour"))


def _risk_flags(*, condition: str, wind_speed_mps: float | None, rain_1h_mm: float | None) -> list[str]:
    flags: list[str] = []
    if condition.casefold() in {"rain", "drizzle", "thunderstorm"} or (rain_1h_mm is not None and rain_1h_mm > 0):
        flags.append("rain")
    if wind_speed_mps is not None and wind_speed_mps >= 8:
        flags.append("strong_wind")
    return flags


def normalize_openweather_snapshot(*, fixture: dict, venue: dict, payload: dict, fetched_at: str) -> dict:
    main = payload.get("main") or {}
    wind = payload.get("wind") or {}
    clouds = payload.get("clouds") or {}
    weather = _weather_item(payload)
    condition = str(weather.get("main") or "").strip()
    rain_1h_mm = _rain_1h(payload)
    wind_speed_mps = _float_or_none(wind.get("speed"))
    normalized = {
        "venue_id": str(venue.get("venue_id") or fixture.get("venue_id") or ""),
        "venue_name": str(venue.get("name") or fixture.get("venue_name") or ""),
        "city": str(venue.get("city") or fixture.get("host_city") or ""),
        "latitude": _float_or_none(venue.get("latitude")),
        "longitude": _float_or_none(venue.get("longitude")),
        "condition": condition,
        "description": str(weather.get("description") or "").strip(),
        "temperature_c": _float_or_none(main.get("temp")),
        "humidity_percent": _int_or_none(main.get("humidity")),
        "wind_speed_mps": wind_speed_mps,
        "wind_degrees": _int_or_none(wind.get("deg")),
        "rain_1h_mm": rain_1h_mm,
        "cloud_cover_percent": _int_or_none(clouds.get("all")),
        "risk_flags": _risk_flags(condition=condition, wind_speed_mps=wind_speed_mps, rain_1h_mm=rain_1h_mm),
    }
    source_status = "available" if normalized["temperature_c"] is not None and wind_speed_mps is not None else "partial"
    match_id = str(fixture.get("match_id") or "")
    return {
        "match_id": match_id,
        "source": "openweather",
        "confidence": "medium" if source_status == "available" else "low",
        "source_status": source_status,
        "fetched_at": fetched_at,
        "valid_at": fixture.get("date_utc"),
        "normalized": normalized,
        "raw": payload,
    }


def fetch_openweather_payload(*, latitude: float, longitude: float, api_key: str | None = None) -> dict | None:
    key = (api_key or os.environ.get("OPENWEATHER_API_KEY") or "").strip()
    if not key:
        return None
    query = urlencode(
        {
            "lat": latitude,
            "lon": longitude,
            "appid": key,
            "units": "metric",
        }
    )
    with urlopen(f"{OPENWEATHER_CURRENT_URL}?{query}", timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))

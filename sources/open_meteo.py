from __future__ import annotations

import json
import ssl
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import urlopen

try:
    import certifi
except ImportError:  # pragma: no cover - fallback for minimal Python runtimes.
    certifi = None

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_HORIZON_DAYS = 16


WEATHER_CODES = {
    0: ("Clear", "clear sky"),
    1: ("Mainly clear", "mainly clear"),
    2: ("Partly cloudy", "partly cloudy"),
    3: ("Overcast", "overcast"),
    45: ("Fog", "fog"),
    48: ("Fog", "depositing rime fog"),
    51: ("Drizzle", "light drizzle"),
    53: ("Drizzle", "moderate drizzle"),
    55: ("Drizzle", "dense drizzle"),
    56: ("Freezing drizzle", "light freezing drizzle"),
    57: ("Freezing drizzle", "dense freezing drizzle"),
    61: ("Rain", "slight rain"),
    63: ("Rain", "moderate rain"),
    65: ("Rain", "heavy rain"),
    66: ("Freezing rain", "light freezing rain"),
    67: ("Freezing rain", "heavy freezing rain"),
    71: ("Snow", "slight snow fall"),
    73: ("Snow", "moderate snow fall"),
    75: ("Snow", "heavy snow fall"),
    77: ("Snow", "snow grains"),
    80: ("Rain showers", "slight rain showers"),
    81: ("Rain showers", "moderate rain showers"),
    82: ("Rain showers", "violent rain showers"),
    85: ("Snow showers", "slight snow showers"),
    86: ("Snow showers", "heavy snow showers"),
    95: ("Thunderstorm", "thunderstorm"),
    96: ("Thunderstorm", "thunderstorm with slight hail"),
    99: ("Thunderstorm", "thunderstorm with heavy hail"),
}


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


def _parse_utc(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _nearest_hour(payload: dict, target_utc: datetime) -> tuple[int, dict] | None:
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        return None
    times = hourly.get("time")
    if not isinstance(times, list) or not times:
        return None

    utc_offset_seconds = _int_or_none(payload.get("utc_offset_seconds")) or 0
    nearest_index: int | None = None
    nearest_delta: float | None = None
    for index, raw_time in enumerate(times):
        try:
            local_time = datetime.fromisoformat(str(raw_time))
        except ValueError:
            continue
        sample_utc = (local_time - timedelta(seconds=utc_offset_seconds)).replace(tzinfo=timezone.utc)
        delta = abs((sample_utc - target_utc).total_seconds())
        if nearest_delta is None or delta < nearest_delta:
            nearest_index = index
            nearest_delta = delta

    if nearest_index is None:
        return None
    if nearest_delta is not None and nearest_delta > 90 * 60:
        return None

    row = {}
    for key, values in hourly.items():
        if isinstance(values, list) and nearest_index < len(values):
            row[key] = values[nearest_index]
    return nearest_index, row


def _risk_flags(*, condition: str, wind_speed_mps: float | None, rain_1h_mm: float | None) -> list[str]:
    flags: list[str] = []
    normalized_condition = condition.casefold()
    if "rain" in normalized_condition or "drizzle" in normalized_condition or "thunderstorm" in normalized_condition:
        flags.append("rain")
    if rain_1h_mm is not None and rain_1h_mm > 0:
        flags.append("rain")
    if wind_speed_mps is not None and wind_speed_mps >= 8:
        flags.append("strong_wind")
    return sorted(set(flags))


def fetch_open_meteo_payload(*, latitude: float, longitude: float, forecast_days: int = FORECAST_HORIZON_DAYS) -> dict:
    query = urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(
                [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "precipitation",
                    "rain",
                    "weather_code",
                    "cloud_cover",
                    "wind_speed_10m",
                    "wind_direction_10m",
                ]
            ),
            "wind_speed_unit": "ms",
            "timezone": "auto",
            "forecast_days": max(1, min(forecast_days, FORECAST_HORIZON_DAYS)),
        }
    )
    context = ssl.create_default_context(cafile=certifi.where() if certifi else None)
    with urlopen(f"{OPEN_METEO_FORECAST_URL}?{query}", timeout=20, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_open_meteo_snapshot(*, fixture: dict, venue: dict, payload: dict, fetched_at: str) -> dict | None:
    kickoff = _parse_utc(fixture.get("date_utc"))
    if kickoff is None:
        return None
    nearest = _nearest_hour(payload, kickoff)
    if nearest is None:
        return None
    _, hourly = nearest
    weather_code = _int_or_none(hourly.get("weather_code"))
    condition, description = WEATHER_CODES.get(weather_code or -1, ("Unknown", "unknown"))
    rain_1h_mm = _float_or_none(hourly.get("rain") if hourly.get("rain") is not None else hourly.get("precipitation"))
    wind_speed_mps = _float_or_none(hourly.get("wind_speed_10m"))
    normalized = {
        "venue_id": str(venue.get("venue_id") or fixture.get("venue_id") or ""),
        "venue_name": str(venue.get("name") or fixture.get("venue_name") or ""),
        "city": str(venue.get("city") or fixture.get("host_city") or ""),
        "latitude": _float_or_none(venue.get("latitude")),
        "longitude": _float_or_none(venue.get("longitude")),
        "condition": condition,
        "description": description,
        "temperature_c": _float_or_none(hourly.get("temperature_2m")),
        "humidity_percent": _int_or_none(hourly.get("relative_humidity_2m")),
        "wind_speed_mps": wind_speed_mps,
        "wind_degrees": _int_or_none(hourly.get("wind_direction_10m")),
        "rain_1h_mm": rain_1h_mm,
        "cloud_cover_percent": _int_or_none(hourly.get("cloud_cover")),
        "risk_flags": _risk_flags(condition=condition, wind_speed_mps=wind_speed_mps, rain_1h_mm=rain_1h_mm),
    }
    source_status = "available" if normalized["temperature_c"] is not None and wind_speed_mps is not None else "partial"
    return {
        "match_id": str(fixture.get("match_id") or ""),
        "source": "open_meteo",
        "confidence": "medium" if source_status == "available" else "low",
        "source_status": source_status,
        "fetched_at": fetched_at,
        "valid_at": fixture.get("date_utc"),
        "normalized": normalized,
        "raw": {
            "provider": "open_meteo",
            "weather_code": weather_code,
            "hourly_sample": hourly,
        },
    }

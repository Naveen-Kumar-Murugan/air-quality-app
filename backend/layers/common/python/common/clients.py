from __future__ import annotations

import os
import httpx
from common.util import get_logger

logger = get_logger(__name__)

_OPENAQ_API_KEY: str | None = None


def get_openaq_api_key() -> str:
    global _OPENAQ_API_KEY
    if _OPENAQ_API_KEY is not None:
        return _OPENAQ_API_KEY
    key = os.environ.get("OPENAQ_KEY") or os.environ.get("OPENAQ_API_KEY")
    if not key:
        try:
            import boto3
            ssm = boto3.client("ssm")
            res = ssm.get_parameter(Name="/airquality/openaq_api_key", WithDecryption=True)
            key = res.get("Parameter", {}).get("Value", "")
        except Exception:
            key = ""
    _OPENAQ_API_KEY = key or ""
    return _OPENAQ_API_KEY


async def fetch_weather(lat: float, lon: float) -> dict | None:
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m"
    async with httpx.AsyncClient(timeout=3.0) as client:
        for attempt in range(2):
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    current = data.get("current", {})
                    if (
                        "relative_humidity_2m" in current
                        and "wind_speed_10m" in current
                        and "surface_pressure" in current
                        and "temperature_2m" in current
                    ):
                        return {
                            "humidity": float(current["relative_humidity_2m"]),
                            "wind_speed": float(current["wind_speed_10m"]),
                            "pressure": float(current["surface_pressure"]),
                            "temp": float(current["temperature_2m"]),
                        }
            except Exception as e:
                if attempt == 1:
                    logger.error(f"Weather API error: {e}")
                    return None
    return None


async def fetch_openaq_stations(
    lat: float | None = None,
    lon: float | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> list[dict]:
    url = "https://api.openaq.org/v2/locations"
    if bbox is not None:
        params = {"bbox": f"{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]}", "parameter": "pm25", "limit": 100}
    elif lat is not None and lon is not None:
        params = {"coordinates": f"{lat},{lon}", "radius": 15000, "parameter": "pm25", "limit": 100}
    else:
        return []

    headers = {}
    api_key = get_openaq_api_key()
    if api_key:
        headers["X-API-Key"] = api_key

    async with httpx.AsyncClient(timeout=3.0) as client:
        for attempt in range(2):
            try:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("results", [])
            except Exception as e:
                if attempt == 1:
                    logger.error(f"OpenAQ API error: {e}")
                    return []
    return []

from __future__ import annotations

import os
import httpx
from .util import get_logger

logger = get_logger(__name__)

_OPENAQ_API_KEY: str | None = None


def get_openaq_api_key() -> str:
    global _OPENAQ_API_KEY
    if _OPENAQ_API_KEY is not None:
        return _OPENAQ_API_KEY
    logger.info("Fetching OpenAQ API key")
    key = os.environ.get("OPENAQ_KEY") or os.environ.get("OPENAQ_API_KEY")
    if not key:
        try:
            import boto3
            ssm = boto3.client("ssm")
            logger.debug("Fetching OpenAQ API key from SSM parameter store")
            res = ssm.get_parameter(Name="/airquality/openaq_api_key", WithDecryption=True)
            key = res.get("Parameter", {}).get("Value", "")
        except Exception as e:
            logger.error("Failed to fetch OpenAQ API key from SSM", extra={"error": str(e)})
            key = ""
    _OPENAQ_API_KEY = key or ""
    logger.info("OpenAQ API key loaded", extra={"has_key": bool(_OPENAQ_API_KEY)})
    return _OPENAQ_API_KEY


async def fetch_weather(lat: float, lon: float) -> dict | None:
    logger.info("Fetching weather data", extra={"lat": lat, "lon": lon})
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m"
    async with httpx.AsyncClient(timeout=3.0) as client:
        for attempt in range(2):
            try:
                logger.debug("Making weather API request", extra={"attempt": attempt + 1, "url": url})
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
                        result = {
                            "humidity": float(current["relative_humidity_2m"]),
                            "wind_speed": float(current["wind_speed_10m"]),
                            "pressure": float(current["surface_pressure"]),
                            "temp": float(current["temperature_2m"]),
                        }
                        logger.info("Weather data fetched successfully", extra=result)
                        return result
                    else:
                        logger.warning("Weather API response missing required fields", extra={"current_keys": list(current.keys())})
            except Exception as e:
                if attempt == 1:
                    logger.error(f"Weather API error: {e}", extra={"lat": lat, "lon": lon})
                    return None
    logger.warning("Weather fetch failed after retries")
    return None


async def fetch_openaq_stations(
    lat: float | None = None,
    lon: float | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> list[dict]:
    """
    Fetch air quality stations with PM2.5 data using OpenAQ v3 API.
    
    Uses /locations/{id}/latest endpoint to get both location info and latest PM2.5
    measurements efficiently, filtering only PM2.5 parameter (id=2).
    """
    logger.info("Fetching OpenAQ stations", extra={"lat": lat, "lon": lon, "bbox": bbox})
    locations_url = "https://api.openaq.org/v3/locations"

    if bbox is not None:
        params = {
            "bbox": f"{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]}",
            "parameters_id": 2,
            "limit": 100,
        }
    elif lat is not None and lon is not None:
        params = {
            "coordinates": f"{lat},{lon}",
            "radius": 15000,
            "parameters_id": 2,
            "limit": 100,
        }
    else:
        logger.warning("fetch_openaq_stations called without lat/lon or bbox")
        return []

    headers = {
        "X-API-Key": get_openaq_api_key(),
    }

    results = []

    try:
        logger.debug("Making OpenAQ locations API request", extra={"params": params})
        async with httpx.AsyncClient(timeout=5.0) as client:
            locations_resp = await client.get(
                locations_url,
                params=params,
                headers=headers,
            )
            locations_resp.raise_for_status()
            locations = locations_resp.json().get("results", [])
            logger.info("OpenAQ locations fetched", extra={"count": len(locations)})
            for location in locations:
                location_id = location.get("id")
                coordinates = location.get("coordinates") or {}
                lat_val = coordinates.get("latitude")
                lon_val = coordinates.get("longitude")

                if lat_val is None or lon_val is None:
                    continue

                try:
                    latest_url = f"https://api.openaq.org/v3/locations/{location_id}/latest"
                    logger.debug("Fetching latest data for location", extra={"location_id": location_id})
                    latest_resp = await client.get(
                        latest_url,
                        params={"parameters_id": 2}, 
                        headers=headers,
                    )
                    latest_resp.raise_for_status()
                    latest_results = latest_resp.json().get("results", [])
                    pm25_value = None
                    measurement_datetime = None

                    for measurement in latest_results:
                        if measurement.get("sensorsId") is not None:
                            pm25_value = measurement.get("value")
                            measurement_datetime = measurement.get("datetime")
                            break

                    if pm25_value is not None:
                        results.append({
                            "id": location_id,
                            "name": location.get("name"),
                            "coordinates": {
                                "latitude": lat_val,
                                "longitude": lon_val,
                            },
                            "pm25": pm25_value,
                            "datetime": measurement_datetime,
                        })
                except httpx.HTTPError as e:
                    logger.warning(
                        f"Failed to fetch latest data for location {location_id}: {e}",
                        extra={"location_id": location_id, "error": str(e)}
                    )
                    continue

    except httpx.HTTPError as e:
        logger.error(f"OpenAQ API error: {e}", extra={"error": str(e)})
        return []

    logger.info("OpenAQ stations fetched", extra={"count": len(results)})
    return results
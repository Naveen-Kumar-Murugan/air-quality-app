import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "layers", "common", "python"))

from common.clients import fetch_weather, fetch_openaq_stations, get_openaq_api_key, _OPENAQ_API_KEY


@pytest.mark.asyncio
async def test_fetch_weather_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "current": {
            "relative_humidity_2m": 65,
            "wind_speed_10m": 3.5,
            "surface_pressure": 1012.5,
            "temperature_2m": 25.0,
        }
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res = await fetch_weather(12.97, 77.59)
        assert res is not None
        assert res["humidity"] == 65.0
        assert res["wind_speed"] == 3.5
        assert res["pressure"] == 1012.5
        assert res["temp"] == 25.0


@pytest.mark.asyncio
async def test_fetch_weather_failure():
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = Exception("Network error")
        res = await fetch_weather(12.97, 77.59)
        assert res is None


@pytest.mark.asyncio
async def test_fetch_openaq_stations_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {"id": 1, "name": "Station A", "coordinates": {"latitude": 12.97, "longitude": 77.59}}
        ]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res = await fetch_openaq_stations(lat=12.97, lon=77.59)
        assert len(res) == 1
        assert res[0]["id"] == 1


@pytest.mark.asyncio
async def test_fetch_openaq_stations_failure():
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = Exception("Timeout")
        res = await fetch_openaq_stations(bbox=(12.0, 77.0, 13.0, 78.0))
        assert res == []


def test_get_openaq_api_key(monkeypatch):
    import common.clients as clients_mod
    monkeypatch.setattr(clients_mod, "_OPENAQ_API_KEY", None)
    monkeypatch.setenv("OPENAQ_KEY", "test-key-123")
    key = get_openaq_api_key()
    assert key == "test-key-123"

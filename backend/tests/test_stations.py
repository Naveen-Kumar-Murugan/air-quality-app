import os
import sys
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "layers", "common", "python"))

from common.stations import get_nearest_station, haversine


def test_haversine():
    dist = haversine(12.9716, 77.5946, 12.9716, 77.5946)
    assert dist == 0.0

    dist_known = haversine(12.9716, 77.5946, 13.0, 77.5946)
    assert 3.0 < dist_known < 4.0


@pytest.mark.asyncio
async def test_get_nearest_station_cached_fresh():
    mock_table = MagicMock()
    now_iso = datetime.now(timezone.utc).isoformat()

    def mock_query(KeyConditionExpression=None, **kwargs):
        return {
            "Items": [
                {"pk": "G#tdr1", "sk": "META", "fetchedAt": now_iso},
                {
                    "pk": "G#tdr1",
                    "sk": "STATION#st1",
                    "id": "st1",
                    "name": "Central Station",
                    "lat": 12.9720,
                    "lon": 77.5950,
                    "pm25": 25.0,
                    "aqi": 78,
                    "fetchedAt": now_iso,
                },
            ]
        }

    mock_table.query.side_effect = mock_query

    res = await get_nearest_station(12.9716, 77.5946, mock_table)
    assert res is not None
    assert res["id"] == "st1"
    assert res["name"] == "Central Station"
    assert res["distance_km"] < 1.0
    assert res["aqi"] == 78


@pytest.mark.asyncio
async def test_get_nearest_station_stale_refresh():
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": []}

    res = await get_nearest_station(12.9716, 77.5946, mock_table)
    assert res is not None
    assert "id" in res
    assert "aqi" in res
    assert mock_table.put_item.called
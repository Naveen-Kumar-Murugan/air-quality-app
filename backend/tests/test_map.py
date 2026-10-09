import json
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "layers", "common"))

from functions.map import app


def event(bbox="77.5,12.9,77.7,13.1", zoom="15"):
    return {"queryStringParameters": {"bbox": bbox, "zoom": zoom}}


def body(response):
    return json.loads(response["body"])


def test_resolution_mapping():
    assert app._resolution(15) == 7
    assert app._resolution(13) == 6
    assert app._resolution(11) == 5
    assert app._resolution(10.9) is None


def test_parse_bbox_validates_combined_parameter():
    assert app._parse_bbox("77.5,12.9,77.7,13.1") == (77.5, 12.9, 77.7, 13.1)
    for bbox in (None, "77.5,12.9,77.7", "77.7,12.9,77.5,13.1", "77.5,91,77.7,92"):
        try:
            app._parse_bbox(bbox)
            assert False, bbox
        except ValueError:
            pass


def test_zoom_too_far_out_response():
    response = app.handler(event(zoom="10"), None)
    assert response["statusCode"] == 400
    assert body(response)["error"] == "ZOOM_IN"


def test_bad_request_response_for_invalid_bbox():
    response = app.handler(event(bbox="77.7,12.9,77.5,13.1"), None)
    assert response["statusCode"] == 400
    assert body(response)["error"] == "BAD_REQUEST"


def test_cell_result_filters_stale_and_formats_current_cell():
    now = datetime.now(timezone.utc)
    item = {
        "sk": "7#tdr1wxy",
        "aqi": Decimal("100.6"),
        "wSum": Decimal("4.1"),
        "n": 6,
        "lastTs": now.isoformat(),
    }
    result = app._cell_result(item, (-180, -90, 180, 90), now)
    assert result["id"] == "tdr1wxy"
    assert result["aqi"] == 101
    assert result["category"] == "Unhealthy for Sensitive Groups"
    assert result["n"] == 6
    assert result["effW"] > 4
    assert len(result["centre"]) == 2
    assert len(result["bounds"]) == 4

    stale = dict(item, wSum=Decimal("0.04"), lastTs=(now - timedelta(hours=12)).isoformat())
    assert app._cell_result(stale, (-180, -90, 180, 90), now) is None


def test_handler_queries_cells_and_stations():
    now = datetime.now(timezone.utc)
    geo_table = Mock()
    station_table = Mock()
    dynamodb = Mock()
    dynamodb.Table.side_effect = lambda name: geo_table if name == "GeoCellsTable" else station_table
    geo_table.query.return_value = {
        "Items": [
            {
                "sk": "7#tdr1wxy",
                "aqi": Decimal("101"),
                "wSum": Decimal("2"),
                "n": 3,
                "lastTs": now.isoformat(),
            }
        ]
    }
    station_table.query.return_value = {
        "Items": [
            {
                "pk": "G#tdr1",
                "sk": "ST#station-1",
                "id": "station-1",
                "name": "Station 1",
                "lat": Decimal("13.0"),
                "lon": Decimal("77.6"),
                "aqi": Decimal("112"),
                "fetchedAt": now.isoformat(),
            }
        ]
    }
    with patch("boto3.resource", return_value=dynamodb):
        response = app.handler(event(bbox="77.5,12.9,77.7,13.1", zoom="15"), None)
    payload = body(response)
    assert response["statusCode"] == 200
    assert payload["res"] == 7
    assert len(payload["cells"]) <= 400
    assert payload["stations"] == [
        {
            "id": "station-1",
            "name": "Station 1",
            "lat": 13.0,
            "lon": 77.6,
            "aqi": 112,
            "measuredAt": now.isoformat(),
        }
    ]
    assert geo_table.query.called
    assert station_table.query.called


def test_resolution_five_uses_batch_get_items():
    now = datetime.now(timezone.utc)
    geo_table = Mock()
    station_table = Mock()
    dynamodb = Mock()
    dynamodb.Table.side_effect = lambda name: geo_table if name == "GeoCellsTable" else station_table
    geo_table.name = "GeoCellsTable"
    geo_table.meta.client = dynamodb
    dynamodb.batch_get_item.return_value = {
        "Responses": {
            "GeoCellsTable": [
                {
                    "sk": "5#tdr1w",
                    "aqi": Decimal("75"),
                    "wSum": Decimal("1"),
                    "n": 1,
                    "lastTs": now.isoformat(),
                }
            ]
        }
    }
    station_table.query.return_value = {"Items": []}
    with patch("boto3.resource", return_value=dynamodb):
        response = app.handler(event(bbox="77.5,12.9,77.7,13.1", zoom="11"), None)
    assert response["statusCode"] == 200
    assert body(response)["res"] == 5
    assert dynamodb.batch_get_item.called


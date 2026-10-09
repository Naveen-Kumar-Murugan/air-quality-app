import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "layers", "common"))

from functions.route import app


# ---------------------------------------------------------------------------
# Resampling
# ---------------------------------------------------------------------------

def test_resample_straight_line_approx_100m_steps():
    # ~1.0 km straight along equator (lon delta ~0.009 degrees ~= 1000 m)
    coords = [[77.0, 12.0], [77.0090, 12.0]]
    resampled = app._resample(coords, 100.0)
    assert len(resampled) >= 8
    distances = []
    for i in range(len(resampled) - 1):
        distances.append(app._haversine_m(resampled[i][0], resampled[i][1], resampled[i + 1][0], resampled[i + 1][1]))
    for d in distances:
        assert 70 <= d <= 130
    assert resampled[0] == (12.0, 77.0)
    assert resampled[-1][0] == 12.0
    assert abs(resampled[-1][1] - 77.0090) < 0.001


def test_resample_degenerate_single_point():
    assert app._resample([[77.0, 12.0]], 100.0) == [(12.0, 77.0)]


def test_resample_zero_length_segment():
    resampled = app._resample([[77.0, 12.0], [77.0, 12.0]], 100.0)
    assert len(resampled) == 1


# ---------------------------------------------------------------------------
# Fallback resolution & AQI logic
# ---------------------------------------------------------------------------

def _make_now():
    return datetime.now(timezone.utc)


def test_fallback_gh7_own_fresh_cell():
    now = _make_now()
    gh7 = "tdr1yc2"
    cells = {
        gh7: {
            "sk": f"7#{gh7}",
            "aqi": Decimal("100"),
            "wSum": Decimal("2"),
            "lastTs": now.isoformat(),
        }
    }
    stations = [{"id": "s1", "lat": 12.9, "lon": 77.5, "aqi": 150.0}]
    result = app._resolve_point(12.9716, 77.6412, cells, stations, now)
    assert result["level"] == "gh7"
    assert result["real"] is True
    # blended with nearby station 150 => (2*100 + 0.5*150)/2.5 = 110.0
    assert abs(result["aqi"] - 110.0) < 0.5


def test_fallback_neighbours_weighted_mean():
    now = _make_now()
    gh7 = "tdr1yc2"
    # make own stale (effW < 0.2) by using 12h old timestamp and wSum 2 (factor ~0.0625 -> 0.125)
    from datetime import timedelta
    stale = {
        "sk": f"7#{gh7}",
        "aqi": Decimal("100"),
        "wSum": Decimal("2"),
        "lastTs": (now - timedelta(hours=12)).isoformat(),
    }
    neighbours = ["tdr1y9p", "tdr1yc0"]
    cells = {gh7: stale}
    for idx, nb in enumerate(neighbours):
        cells[nb] = {
            "sk": f"7#{nb}",
            "aqi": Decimal(str(50 + idx * 100)),
            "wSum": Decimal("1"),
            "lastTs": now.isoformat(),
        }
    stations = [{"id": "s1", "lat": 12.9, "lon": 77.5, "aqi": 120.0}]
    result = app._resolve_point(12.9716, 77.6412, cells, stations, now)
    assert result["level"] == "neighbours"
    assert result["real"] is True
    # neighbours 50 & 150 weighted = 100; blended with station 120 => 104.0
    assert abs(result["aqi"] - 104.0) < 1.0


def test_fallback_gh6_parent():
    now = _make_now()
    gh7 = "tdr1yc2"
    parent = gh7[:6]
    cells = {
        parent: {
            "sk": f"6#{parent}",
            "aqi": Decimal("80"),
            "wSum": Decimal("1"),
            "lastTs": now.isoformat(),
        }
    }
    stations = [{"id": "s1", "lat": 12.9, "lon": 77.5, "aqi": 90.0}]
    result = app._resolve_point(12.9716, 77.6412, cells, stations, now)
    assert result["level"] == "gh6"
    assert result["real"] is False
    # blend with station 90 => (1*80 + 0.5*90)/(1.5) = 83.33
    assert abs(result["aqi"] - 83.33) < 0.5


def test_fallback_station_baseline_no_cells():
    now = _make_now()
    stations = [{"id": "s1", "lat": 12.9716, "lon": 77.6412, "aqi": 110.0}]
    result = app._resolve_point(12.9716, 77.6412, {}, stations, now)
    assert result["level"] == "station"
    assert result["real"] is False
    assert abs(result["aqi"] - 110.0) < 0.1


# ---------------------------------------------------------------------------
# Metric scoring & labeling
# ---------------------------------------------------------------------------

def test_route_scoring_and_labels():
    routes = [
        {"minutes": 10.0, "avgAqi": 100.0, "exposure": 1000.0},
        {"minutes": 15.0, "avgAqi": 60.0, "exposure": 900.0},
        {"minutes": 20.0, "avgAqi": 70.0, "exposure": 1400.0},
    ]
    labels, warnings = app._score_routes(routes)
    assert labels["fastest"] == 0
    assert labels["cleanest"] == 1
    assert labels["balanced"] == 0
    assert any("both" in w and "Fastest" in w and "Balanced" in w for w in warnings)


def test_low_coverage_warning():
    metrics = app._route_metrics({"distanceM": 500}, [(12.0, 77.0)], [{"aqi": 50.0, "level": "station", "real": False}])
    assert metrics["lowCoverage"] is True
    assert metrics["coverage"] == 0.0


def test_coverage_above_threshold():
    metrics = app._route_metrics({"distanceM": 500}, [(12.0, 77.0)], [{"aqi": 50.0, "level": "gh7", "real": True}])
    assert metrics["lowCoverage"] is False
    assert metrics["coverage"] == 1.0


# ---------------------------------------------------------------------------
# Mapbox parsing & mock fallback
# ---------------------------------------------------------------------------

def test_parse_directions_success():
    data = {
        "routes": [
            {
                "geometry": {"coordinates": [[77.0, 12.0], [77.01, 12.01]]},
                "distance": 1500.5,
                "duration": 300.0,
            }
        ]
    }
    parsed = app._parse_directions(data)
    assert len(parsed) == 1
    assert parsed[0]["source"] == "mapbox"
    assert parsed[0]["distanceM"] == 1500.5


def test_direction_fallback_missing_token():
    origin = {"lat": 12.0, "lon": 77.0}
    dest = {"lat": 12.01, "lon": 77.01}
    result = app._directions(origin, dest, "walking", "")
    assert len(result) == 1
    assert result[0]["source"] == "fallback"
    assert result[0]["fallbackReason"] == "missing_token"


def test_direction_fallback_on_http_error():
    def bad_get(url, params):
        raise Exception("connection refused")

    origin = {"lat": 12.0, "lon": 77.0}
    dest = {"lat": 12.01, "lon": 77.01}
    result = app._directions(origin, dest, "walking", "fake_token", http_get=bad_get)
    assert result[0]["source"] == "fallback"
    assert result[0]["fallbackReason"] == "mapbox_error"


def test_direction_success_with_mock_get():
    def mock_get(url, params):
        assert "walking" in url
        assert params.get("alternatives") == "true"
        return {
            "routes": [
                {
                    "geometry": {"coordinates": [[77.0, 12.0], [77.01, 12.01]]},
                    "distance": 200.0,
                    "duration": 120.0,
                }
            ]
        }

    origin = {"lat": 12.0, "lon": 77.0}
    dest = {"lat": 12.01, "lon": 77.01}
    result = app._directions(origin, dest, "walking", "token", http_get=mock_get)
    assert len(result) == 1
    assert result[0]["source"] == "mapbox"


# ---------------------------------------------------------------------------
# Request parsing
# ---------------------------------------------------------------------------

def test_parse_request_json_nested():
    event = {"body": json.dumps({"origin": {"lat": 12.9, "lon": 77.5}, "destination": {"lat": 13.0, "lon": 77.6}, "mode": "cycling"})}
    origin, dest, mode = app._parse_request(event)
    assert origin["lat"] == 12.9
    assert dest["lon"] == 77.6
    assert mode == "cycling"


def test_parse_request_query_flat():
    event = {"queryStringParameters": {"originLat": "12.9", "originLon": "77.5", "destinationLat": "13.0", "destinationLon": "77.6", "mode": "driving"}}
    origin, dest, mode = app._parse_request(event)
    assert origin == {"lat": 12.9, "lon": 77.5}
    assert dest == {"lat": 13.0, "lon": 77.6}


def test_parse_request_invalid_mode():
    event = {"queryStringParameters": {"originLat": "12.9", "originLon": "77.5", "destinationLat": "13.0", "destinationLon": "77.6", "mode": "flying"}}
    try:
        app._parse_request(event)
        assert False
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Handler integration with mocked tables
# ---------------------------------------------------------------------------

def test_handler_integration():
    now = datetime.now(timezone.utc)
    geo_table = Mock()
    station_table = Mock()

    geo_table.query.side_effect = lambda **kwargs: {
        "Items": [
            {
                "sk": "7#tdr1wxy",
                "aqi": Decimal("75"),
                "wSum": Decimal("2"),
                "lastTs": now.isoformat(),
            }
        ],
        "LastEvaluatedKey": None,
    }
    station_table.query.side_effect = lambda **kwargs: {
        "Items": [
            {
                "pk": "S#tdr1",
                "sk": "ST#station-1",
                "id": "station-1",
                "name": "Station 1",
                "lat": Decimal("12.9"),
                "lon": Decimal("77.6"),
                "aqi": Decimal("110"),
                "aqiUS": Decimal("110"),
                "measuredAt": now.isoformat(),
                "fetchedAt": now.isoformat(),
            }
        ],
        "LastEvaluatedKey": None,
    }

    dynamodb = Mock()
    dynamodb.Table.side_effect = lambda name: geo_table if name in ("GeoCellsTable", os.environ.get("GEOCELLS_TABLE", "GeoCellsTable")) else station_table

    def mock_directions(origin, dest, mode, token, http_get=None):
        return [{"coordinates": [[77.5, 12.9], [77.6, 13.0]], "distanceM": 12000, "durationSec": 900, "source": "mapbox"}]

    event = {"body": json.dumps({"origin": {"lat": 12.9, "lon": 77.5}, "destination": {"lat": 13.0, "lon": 77.6}, "mode": "walking"})}

    with patch("boto3.resource", return_value=dynamodb):
        with patch.object(app, "_directions", side_effect=mock_directions):
            response = app.handler(event, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "routes" in body
    assert len(body["routes"]) == 1
    assert body["routes"][0]["source"] == "mapbox"
    assert "labels" in body
    assert "fastest" in body["labels"]

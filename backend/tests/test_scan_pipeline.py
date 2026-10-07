import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "layers", "common", "python"))

import json
import base64
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch, AsyncMock
import boto3
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "functions", "upload_url"))
import importlib.util
spec = importlib.util.spec_from_file_location("upload_url_app", os.path.join(os.path.dirname(__file__), "..", "functions", "upload_url", "app.py"))
upload_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upload_app)
upload_handler = upload_app.handler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "functions", "scan"))
spec = importlib.util.spec_from_file_location("scan_app", os.path.join(os.path.dirname(__file__), "..", "functions", "scan", "app.py"))
scan_app_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan_app_mod)
scan_handler = scan_app_mod.handler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "functions", "scans_mine"))
spec = importlib.util.spec_from_file_location("scans_mine_app", os.path.join(os.path.dirname(__file__), "..", "functions", "scans_mine", "app.py"))
scans_mine_app_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scans_mine_app_mod)
mine_handler = scans_mine_app_mod.handler


def make_event(sub="user1", body={}):
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": sub}}}
        },
        "body": json.dumps(body) if body else "{}",
    }


def test_upload_url_success():
    with patch("boto3.resource") as mock_res:
        mock_table = MagicMock()
        mock_res.return_value.Table.return_value = mock_table
        mock_table.update_item.return_value = {"Attributes": {"count": Decimal("1")}}
        with patch("boto3.client") as mock_client:
            mock_client.return_value.generate_presigned_url.return_value = "http://example.com/upload"
            event = make_event(sub="user1")
            resp = upload_handler(event, None)
            assert resp["statusCode"] == 200
            body = json.loads(resp["body"])
            assert "scanId" in body
            assert "uploadUrl" in body


def test_upload_url_rate_limit():
    with patch("boto3.resource") as mock_res:
        mock_table = MagicMock()
        mock_res.return_value.Table.return_value = mock_table
        mock_table.update_item.return_value = {"Attributes": {"count": Decimal("21")}}
        event = make_event(sub="user1")
        resp = upload_handler(event, None)
        assert resp["statusCode"] == 429
        body = json.loads(resp["body"])
        assert body["error"] == "RATE_LIMITED"


def test_scan_bad_s3_key():
    event = make_event(sub="user1", body={
        "scanId": "test123",
        "s3Key": "bad/key.jpg",
        "lat": 12.0,
        "lon": 77.0,
        "accuracy": 10,
    })
    resp = scan_handler(event, None)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert "Invalid s3Key" in body.get("message", "")


def test_scan_oversized_image():
    event = make_event(sub="user1", body={
        "scanId": "test123",
        "s3Key": "scans/user1/test123.jpg",
        "lat": 12.0,
        "lon": 77.0,
        "accuracy": 10,
    })
    with patch("boto3.client") as mock_client:
        mock_client.return_value.head_object.side_effect = Exception("NoSuchKey")
        resp = scan_handler(event, None)
    assert resp["statusCode"] == 400


def test_scan_bad_accuracy_inmap_false():
    event = make_event(sub="user1", body={
        "scanId": "test456",
        "s3Key": "scans/user1/test456.jpg",
        "lat": 12.0,
        "lon": 77.0,
        "accuracy": 150,
    })
    with patch("boto3.resource") as mock_res, patch("boto3.client") as mock_client:
        mock_client.return_value.head_object.return_value = {"ContentLength": 1024}
        mock_client.return_value.get_object.return_value = {"Body": MagicMock(read=lambda: b"img")}
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": None}
        mock_res.return_value.Table.side_effect = lambda name: mock_table if name in ("ScansTable", "GeoCellsTable", "StationsTable") else MagicMock()
        with patch("common.predictor.get_predictor") as mock_pred:
            pred_inst = AsyncMock()
            pred_inst.predict.return_value = MagicMock(aqi=50, category="Good", confidence=0.5, source="station_stub", probabilities=None)
            mock_pred.return_value = pred_inst
            with patch("common.clients.fetch_weather", new_callable=AsyncMock) as mock_weather:
                mock_weather.return_value = {"humidity": 50, "wind_speed": 2.0}
                with patch("common.stations.get_nearest_station", new_callable=AsyncMock) as mock_station:
                    mock_station.return_value = {"aqi": 60, "distance_km": 5.0}
                    resp = scan_handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["inMap"] is False


def test_scans_mine_empty():
    with patch("boto3.resource") as mock_res:
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [], "LastEvaluatedKey": None}
        mock_res.return_value.Table.return_value = mock_table
        event = {
            "requestContext": {"authorizer": {"jwt": {"claims": {"sub": "user1"}}}},
            "queryStringParameters": {},
        }
        resp = mine_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["scans"] == []
        assert body["nextPageToken"] is None

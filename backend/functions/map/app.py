from __future__ import annotations

import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key


def _ensure_path() -> None:
    common_path = os.path.join(os.path.dirname(__file__), "..", "..", "layers", "common")
    if common_path not in sys.path:
        sys.path.insert(0, common_path)
    if "/opt/python" not in sys.path:
        sys.path.insert(0, "/opt/python")


def _resolution(zoom: float) -> int | None:
    if zoom >= 15:
        return 7
    if zoom >= 13:
        return 6
    if zoom >= 11:
        return 5
    return None


def _parse_bbox(value: str | None) -> tuple[float, float, float, float]:
    if not value:
        raise ValueError("bbox is required")
    parts = value.split(",")
    if len(parts) != 4:
        raise ValueError("bbox must be minLon,minLat,maxLon,maxLat")
    min_lon, min_lat, max_lon, max_lat = (float(part) for part in parts)
    if not all(math.isfinite(number) for number in (min_lon, min_lat, max_lon, max_lat)):
        raise ValueError("bbox values must be finite numbers")
    if min_lon < -180 or max_lon > 180 or min_lon >= max_lon:
        raise ValueError("bbox longitude bounds are invalid")
    if min_lat < -90 or max_lat > 90 or min_lat >= max_lat:
        raise ValueError("bbox latitude bounds are invalid")
    return min_lon, min_lat, max_lon, max_lat


def _query_cells(table: Any, gh5: str, resolution: int) -> list[dict]:
    response = table.query(
        KeyConditionExpression=Key("pk").eq(f"G#{gh5}") & Key("sk").begins_with(f"{resolution}#"),
        ProjectionExpression="pk, sk, aqi, wSum, n, lastTs",
    )
    items = list(response.get("Items", []))
    while response.get("LastEvaluatedKey"):
        response = table.query(
            KeyConditionExpression=Key("pk").eq(f"G#{gh5}") & Key("sk").begins_with(f"{resolution}#"),
            ProjectionExpression="pk, sk, aqi, wSum, n, lastTs",
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    return items


def _station_items(table: Any, partitions: set[str]) -> list[dict]:
    items: list[dict] = []
    for partition in partitions:
        response = table.query(
            KeyConditionExpression=Key("pk").eq(f"S#{partition}"),
            ProjectionExpression="pk, sk, id, #name, lat, lon, aqi, measuredAt, fetchedAt",
            ExpressionAttributeNames={"#name": "name"},
        )
        items.extend(response.get("Items", []))
        while response.get("LastEvaluatedKey"):
            response = table.query(
                KeyConditionExpression=Key("pk").eq(f"S#{partition}"),
                ProjectionExpression="pk, sk, id, #name, lat, lon, aqi, measuredAt, fetchedAt",
                ExpressionAttributeNames={"#name": "name"},
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))
    return items


def _cell_result(item: dict, bbox: tuple[float, float, float, float], now: datetime) -> dict | None:
    from common import geohash
    from common.aqi import aqi_to_category
    from common.cells import effective_weight

    min_lon, min_lat, max_lon, max_lat = bbox
    geohash_id = str(item.get("sk", "")).split("#", 1)[-1]
    south, west, north, east = geohash.decode_bbox(geohash_id)
    lat, lon = (south + north) / 2, (west + east) / 2
    if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
        return None

    last_ts = str(item.get("lastTs", ""))
    try:
        updated = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        age_hours = max(0.0, (now - updated.astimezone(timezone.utc)).total_seconds() / 3600)
    except (ValueError, TypeError):
        return None
    eff_w = effective_weight(float(item.get("wSum", 0) or 0), age_hours)
    if eff_w < 0.05:
        return None
    aqi = float(item.get("aqi", 0) or 0)
    rounded_aqi = round(aqi)
    return {
        "id": geohash_id,
        "centre": [lat, lon],
        "bounds": [south, west, north, east],
        "aqi": rounded_aqi,
        "category": aqi_to_category(rounded_aqi),
        "n": int(item.get("n", 0) or 0),
        "effW": eff_w,
        "updatedAt": last_ts,
    }


def _read_viewport(geo_table: Any, stations_table: Any, bbox: tuple[float, float, float, float], resolution: int) -> dict:
    from common import geohash

    min_lon, min_lat, max_lon, max_lat = bbox
    partitions = geohash.cells_covering(min_lat, min_lon, max_lat, max_lon, 5)
    station_partitions = geohash.cells_covering(min_lat, min_lon, max_lat, max_lon, 4)

    if resolution == 5:
        keys = [{"pk": f"G#{gh5}", "sk": f"5#{gh5}"} for gh5 in partitions]
        raw: list[dict] = []
        client = geo_table.meta.client
        table_name = geo_table.name
        for start in range(0, len(keys), 100):
            pending = keys[start : start + 100]
            while pending:
                response = client.batch_get_item(RequestItems={table_name: {"Keys": pending}})
                raw.extend(response.get("Responses", {}).get(table_name, []))
                pending = response.get("UnprocessedKeys", {}).get(table_name, {}).get("Keys", [])
    else:
        with ThreadPoolExecutor(max_workers=16) as pool:
            groups = list(pool.map(lambda gh5: _query_cells(geo_table, gh5, resolution), partitions))
        raw = [item for group in groups for item in group]

    now = datetime.now(timezone.utc)
    cells = []
    for item in raw:
        result = _cell_result(item, bbox, now)
        if result:
            cells.append(result)
            if len(cells) == 400:
                break

    raw_stations = _station_items(stations_table, station_partitions)
    stations = []
    for item in raw_stations:
        if item.get("sk") in ("META",) or not str(item.get("sk", "")).startswith(("ST#", "STATION#")):
            continue
        try:
            lat, lon = float(item["lat"]), float(item["lon"])
            if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                stations.append({
                    "id": str(item.get("id") or str(item["sk"]).split("#", 1)[-1]),
                    "name": str(item.get("name", "Unknown station")),
                    "lat": lat,
                    "lon": lon,
                    "aqi": int(float(item.get("aqiUS", item.get("aqi", 0)) or 0)),
                    "measuredAt": str(item.get("measuredAt") or item.get("fetchedAt") or ""),
                })
        except (KeyError, TypeError, ValueError):
            continue
    unique_stations = {station["id"]: station for station in stations}
    return {"res": resolution, "cells": cells, "stations": list(unique_stations.values())}


def handler(event, context):
    _ensure_path()
    from common.util import error_response, json_response

    query = event.get("queryStringParameters") or {}
    try:
        bbox = _parse_bbox(query.get("bbox"))
        zoom = float(query.get("zoom", "nan"))
        if zoom != zoom or abs(zoom) == float("inf") or zoom < 0 or zoom > 24:
            raise ValueError("zoom must be a number between 0 and 24")
    except (ValueError, TypeError) as exc:
        return error_response("BAD_REQUEST", str(exc), 400)
    resolution = _resolution(zoom)
    if resolution is None:
        return error_response("ZOOM_IN", "Zoom in to see air quality", 400)

    try:
        geo_table = boto3.resource("dynamodb").Table(os.environ.get("GEOCELLS_TABLE", "GeoCellsTable"))
        stations_table = boto3.resource("dynamodb").Table(os.environ.get("STATIONS_TABLE", "StationsTable"))
        payload = _read_viewport(geo_table, stations_table, bbox, resolution)
        return json_response(200, payload)
    except Exception:
        return error_response("INTERNAL_ERROR", "Unable to load map data", 500)

from __future__ import annotations

import json
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

ALPHA = 0.5
K_BLEND = 0.5
SAMPLE_STEP_M = 100.0
FRESH_EFF_WEIGHT = 0.2
MIN_EFF_WEIGHT = 0.05
LOW_COVERAGE_THRESHOLD = 0.40
MAX_ROUTE_M = 25000.0

_PROFILE = {"walking": "walking", "cycling": "cycling", "driving": "driving"}
_SPEED_MPS = {"walking": 1.4, "cycling": 4.2, "driving": 8.3}


def _ensure_path() -> None:
    common_path = os.path.join(os.path.dirname(__file__), "..", "..", "layers", "common")
    if common_path not in sys.path:
        sys.path.insert(0, common_path)
    if "/opt/python" not in sys.path:
        sys.path.insert(0, "/opt/python")


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_key(key: str) -> str:
    return key.strip().upper().replace(" ", "_").replace("-", "_")


def _read_env_file_token() -> str:
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
        os.path.join(os.getcwd(), ".env"),
    ]
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                for raw in handle:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    if _normalize_key(key) == "MAPBOX_TOKEN":
                        token = value.strip().strip('"').strip("'")
                        if token:
                            return token
        except OSError:
            continue
    return ""


def get_mapbox_token() -> str:
    return (
        os.environ.get("MAPBOX_TOKEN")
        or os.environ.get("MAPBOX_ACCESS_TOKEN")
        or _read_env_file_token()
        or ""
    )


def _resample(coordinates, step_m: float = SAMPLE_STEP_M):
    points = [(float(c[1]), float(c[0])) for c in coordinates]
    if len(points) < 2:
        return points

    cumulative = [0.0]
    for index in range(1, len(points)):
        previous = points[index - 1]
        current = points[index]
        cumulative.append(
            cumulative[-1] + _haversine_m(previous[0], previous[1], current[0], current[1])
        )

    total = cumulative[-1]
    if total <= 0:
        return [points[0]]

    targets = [index * step_m for index in range(int(total // step_m) + 1)]
    if targets[-1] < total:
        targets.append(total)
    else:
        targets[-1] = total

    result = []
    segment = 1
    for distance in targets:
        while segment < len(cumulative) and cumulative[segment] < distance:
            segment += 1
        if segment >= len(cumulative):
            result.append(points[-1])
            continue
        segment_length = cumulative[segment] - cumulative[segment - 1]
        ratio = 0.0 if segment_length == 0 else (distance - cumulative[segment - 1]) / segment_length
        start = points[segment - 1]
        end = points[segment]
        result.append(
            (start[0] + (end[0] - start[0]) * ratio, start[1] + (end[1] - start[1]) * ratio)
        )

    deduped = [result[0]]
    for point in result[1:]:
        if _haversine_m(deduped[-1][0], deduped[-1][1], point[0], point[1]) > 0.01:
            deduped.append(point)
    return deduped


def _sample_step(route: dict) -> float:
    distance = float(route.get("distanceM", 0.0) or 0.0)
    return SAMPLE_STEP_M if distance <= 10000 else 150.0


def _synthetic_route(origin: dict, destination: dict, mode: str, reason: str) -> list[dict]:
    coordinates = [
        [origin["lon"], origin["lat"]],
        [destination["lon"], destination["lat"]],
    ]
    distance = _haversine_m(origin["lat"], origin["lon"], destination["lat"], destination["lon"])
    speed = _SPEED_MPS.get(mode, _SPEED_MPS["driving"])
    return [
        {
            "coordinates": coordinates,
            "distanceM": distance,
            "durationSec": distance / speed if speed else 0.0,
            "source": "fallback",
            "fallbackReason": reason,
        }
    ]


def _parse_directions(data: dict) -> list[dict]:
    routes = []
    for raw in (data or {}).get("routes", []) or []:
        geometry = raw.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if len(coordinates) < 2:
            continue
        routes.append(
            {
                "coordinates": coordinates,
                "distanceM": float(raw.get("distance", 0.0) or 0.0),
                "durationSec": float(raw.get("duration", 0.0) or 0.0),
                "source": "mapbox",
            }
        )
    return routes


def _directions(origin: dict, destination: dict, mode: str, token: str, http_get=None) -> list[dict]:
    if not token:
        return _synthetic_route(origin, destination, mode, "missing_token")
    profile = _PROFILE.get(mode, "driving")
    url = (
        f"https://api.mapbox.com/directions/v5/mapbox/{profile}/"
        f"{origin['lon']},{origin['lat']};{destination['lon']},{destination['lat']}"
    )
    params = {
        "alternatives": "true",
        "geometries": "geojson",
        "overview": "full",
        "access_token": token,
    }
    try:
        if http_get is None:
            import httpx

            with httpx.Client(timeout=8.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        else:
            data = http_get(url, params)
        routes = _parse_directions(data)
        if not routes:
            return _synthetic_route(origin, destination, mode, "no_routes")
        return routes
    except Exception:
        return _synthetic_route(origin, destination, mode, "mapbox_error")


def _coord_from_mapping(value):
    if not isinstance(value, dict):
        return None
    lon = value.get("lon", value.get("lng", value.get("longitude")))
    lat = value.get("lat", value.get("latitude"))
    lat_f = _to_float(lat)
    lon_f = _to_float(lon)
    if lat_f is None or lon_f is None:
        return None
    return {"lat": lat_f, "lon": lon_f}


def _extract_coord(params: dict, key: str, aliases: list[str]):
    nested = params.get(key)
    coord = _coord_from_mapping(nested)
    if coord:
        return coord
    if isinstance(nested, str) and "," in nested:
        parts = nested.split(",")
        if len(parts) == 2:
            lat_f = _to_float(parts[0])
            lon_f = _to_float(parts[1])
            if lat_f is not None and lon_f is not None:
                return {"lat": lat_f, "lon": lon_f}
    for alias in aliases:
        candidates = (
            (f"{alias}Lat", f"{alias}Lon"),
            (f"{alias}Lat", f"{alias}Lng"),
            (f"{alias}_lat", f"{alias}_lon"),
            (f"{alias}_lat", f"{alias}_lng"),
            (f"{alias}_latitude", f"{alias}_longitude"),
        )
        for lat_key, lon_key in candidates:
            lat_f = _to_float(params.get(lat_key))
            lon_f = _to_float(params.get(lon_key))
            if lat_f is not None and lon_f is not None:
                return {"lat": lat_f, "lon": lon_f}
    return None


def _validate_coord(coord: dict, label: str) -> None:
    if not (-90.0 <= coord["lat"] <= 90.0):
        raise ValueError(f"{label} latitude out of range")
    if not (-180.0 <= coord["lon"] <= 180.0):
        raise ValueError(f"{label} longitude out of range")


def _parse_request(event: dict):
    params = dict(event.get("queryStringParameters") or {})
    body = event.get("body")
    if body:
        if isinstance(body, dict):
            data = body
        else:
            try:
                data = json.loads(body)
            except (ValueError, TypeError):
                data = None
        if isinstance(data, dict):
            params.update(data)

    origin = _extract_coord(params, "origin", ["origin", "from", "src"])
    destination = _extract_coord(params, "destination", ["destination", "dest", "to", "dst"])
    if origin is None:
        raise ValueError("origin (lat, lon) is required")
    if destination is None:
        raise ValueError("destination (lat, lon) is required")
    _validate_coord(origin, "origin")
    _validate_coord(destination, "destination")

    mode = str(params.get("mode", "driving")).lower()
    if mode not in _PROFILE:
        raise ValueError("mode must be walking, cycling or driving")
    return origin, destination, mode


def _cell_partitions(samples) -> set[str]:
    from common import geohash

    partitions: set[str] = set()
    for lat, lon in samples:
        gh7 = geohash.encode(lat, lon, 7)
        partitions.add(gh7[:5])
        for neighbour in geohash.neighbors(gh7):
            partitions.add(neighbour[:5])
    return partitions


def _station_partitions(samples) -> set[str]:
    from common import geohash

    if not samples:
        return set()
    lats = [point[0] for point in samples]
    lons = [point[1] for point in samples]
    return geohash.cells_covering(min(lats), min(lons), max(lats), max(lons), 4)


def _query_all(table, partition: str, prefix: str) -> list[dict]:
    response = table.query(
        KeyConditionExpression=Key("pk").eq(prefix) & Key("sk").begins_with(f"{partition}#")
    )
    items = list(response.get("Items", []))
    while response.get("LastEvaluatedKey"):
        response = table.query(
            KeyConditionExpression=Key("pk").eq(prefix) & Key("sk").begins_with(f"{partition}#"),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    return items


def _load_cells(geo_table, partitions) -> dict:
    def fetch(gh5: str):
        return _query_all(geo_table, gh5, f"G#{gh5}")

    cells: dict = {}
    if not partitions:
        return cells
    with ThreadPoolExecutor(max_workers=16) as pool:
        groups = list(pool.map(fetch, partitions))
    for group in groups:
        for item in group:
            sort_key = str(item.get("sk", ""))
            if "#" not in sort_key:
                continue
            _, geohash_id = sort_key.split("#", 1)
            cells[geohash_id] = item
    return cells


def _load_stations(stations_table, partitions) -> list[dict]:
    stations: list[dict] = []
    if not partitions:
        return stations
    for gh4 in partitions:
        response = stations_table.query(KeyConditionExpression=Key("pk").eq(f"S#{gh4}"))
        items = list(response.get("Items", []))
        while response.get("LastEvaluatedKey"):
            response = stations_table.query(
                KeyConditionExpression=Key("pk").eq(f"S#{gh4}"),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))
        for item in items:
            sort_key = str(item.get("sk", ""))
            if not sort_key.startswith("ST#"):
                continue
            try:
                lat = float(item["lat"])
                lon = float(item["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            aqi_value = item.get("aqiUS", item.get("aqi", 0))
            stations.append(
                {
                    "id": str(item.get("id") or sort_key.split("#", 1)[-1]),
                    "name": str(item.get("name", "Unknown station")),
                    "lat": lat,
                    "lon": lon,
                    "aqi": float(aqi_value or 0.0),
                }
            )
    return stations


def _age_hours(last_ts, now: datetime):
    try:
        updated = datetime.fromisoformat(str(last_ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    return max(0.0, (now - updated.astimezone(timezone.utc)).total_seconds() / 3600.0)


def _cell_signal(item, now: datetime):
    from common.cells import effective_weight

    if not item:
        return None
    age = _age_hours(item.get("lastTs", ""), now)
    if age is None:
        return None
    weight = effective_weight(float(item.get("wSum", 0.0) or 0.0), age)
    if weight < MIN_EFF_WEIGHT:
        return None
    return {"aqi": float(item.get("aqi", 0.0) or 0.0), "effW": weight}


def _nearest_station(lat: float, lon: float, stations):
    best = None
    best_distance = None
    for station in stations:
        distance = _haversine_m(lat, lon, station["lat"], station["lon"])
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best = station
    return best


def _resolve_point(lat: float, lon: float, cells: dict, stations, now: datetime) -> dict:
    from common import geohash
    from common.cells import blend_with_station

    gh7 = geohash.encode(lat, lon, 7)
    own_signal = _cell_signal(cells.get(gh7), now)

    level = None
    cell_aqi = None
    eff_weight = 0.0

    if own_signal and own_signal["effW"] >= FRESH_EFF_WEIGHT:
        level = "gh7"
        cell_aqi = own_signal["aqi"]
        eff_weight = own_signal["effW"]
    else:
        weighted_sum = 0.0
        weight_total = 0.0
        for neighbour in geohash.neighbors(gh7):
            signal = _cell_signal(cells.get(neighbour), now)
            if signal:
                weighted_sum += signal["aqi"] * signal["effW"]
                weight_total += signal["effW"]
        if weight_total > 0:
            level = "neighbours"
            cell_aqi = weighted_sum / weight_total
            eff_weight = weight_total
        else:
            for precision in (6, 5):
                parent = gh7[:precision]
                signal = _cell_signal(cells.get(parent), now)
                if signal:
                    level = f"gh{precision}"
                    cell_aqi = signal["aqi"]
                    eff_weight = signal["effW"]
                    break

    station = _nearest_station(lat, lon, stations)
    station_aqi = station["aqi"] if station else None

    if cell_aqi is not None:
        if station_aqi is not None:
            blended = blend_with_station(cell_aqi, eff_weight, station_aqi, K_BLEND)
        else:
            blended = cell_aqi
    elif station_aqi is not None:
        level = "station"
        blended = float(station_aqi)
    else:
        level = "none"
        blended = 0.0

    return {
        "aqi": blended,
        "level": level,
        "real": level in ("gh7", "neighbours"),
        "effW": eff_weight,
        "cellAqi": cell_aqi,
        "stationAqi": station_aqi,
    }


def _route_metrics(route: dict, samples, resolved) -> dict:
    from common.aqi import aqi_to_category

    count = len(resolved)
    if count == 0:
        return {
            "avgAqi": 0.0,
            "category": "Unknown",
            "minutes": 0.0,
            "durationSec": 0.0,
            "distanceM": 0.0,
            "exposure": 0.0,
            "coverage": 0.0,
            "lowCoverage": True,
            "sampleCount": 0,
        }

    segment_lengths = []
    for index in range(count - 1):
        segment_lengths.append(
            _haversine_m(
                samples[index][0],
                samples[index][1],
                samples[index + 1][0],
                samples[index + 1][1],
            )
        )
    total_length = sum(segment_lengths)
    if total_length > 0:
        weighted_sum = sum(
            resolved[index]["aqi"] * segment_lengths[index] for index in range(count - 1)
        )
        avg_aqi = weighted_sum / total_length
    else:
        avg_aqi = sum(point["aqi"] for point in resolved) / count

    real_count = sum(1 for point in resolved if point["real"])
    coverage = real_count / count
    duration_sec = float(route.get("durationSec", 0.0) or 0.0)
    minutes = duration_sec / 60.0
    exposure = avg_aqi * minutes
    distance_m = float(route.get("distanceM", 0.0) or 0.0) or total_length
    rounded = round(avg_aqi)

    return {
        "avgAqi": round(avg_aqi, 1),
        "category": aqi_to_category(rounded),
        "minutes": round(minutes, 1),
        "durationSec": round(duration_sec, 1),
        "distanceM": round(distance_m, 1),
        "exposure": round(exposure, 1),
        "coverage": round(coverage, 4),
        "lowCoverage": coverage < LOW_COVERAGE_THRESHOLD,
        "sampleCount": count,
    }


def _normalize(values, value: float) -> float:
    low = min(values)
    high = max(values)
    if high <= low:
        return 0.0
    return (value - low) / (high - low)


def _score_routes(routes):
    if not routes:
        return {}, []

    times = [route["minutes"] for route in routes]
    exposures = [route["exposure"] for route in routes]

    for route in routes:
        route["normalizedTime"] = round(_normalize(times, route["minutes"]), 4)
        route["normalizedExposure"] = round(_normalize(exposures, route["exposure"]), 4)
        route["combined"] = round(
            ALPHA * route["normalizedTime"] + (1 - ALPHA) * route["normalizedExposure"], 4
        )
        route["labels"] = []

    fastest = min(range(len(routes)), key=lambda index: (routes[index]["minutes"], index))
    cleanest = min(range(len(routes)), key=lambda index: (routes[index]["avgAqi"], index))
    balanced = min(range(len(routes)), key=lambda index: (routes[index]["combined"], index))

    label_map = {"fastest": fastest, "cleanest": cleanest, "balanced": balanced}
    display = {"fastest": "Fastest", "cleanest": "Cleanest", "balanced": "Balanced"}

    grouped: dict[int, list[str]] = {}
    for key, index in label_map.items():
        grouped.setdefault(index, []).append(display[key])

    warnings = []
    for index, names in grouped.items():
        routes[index]["labels"] = names
        if len(names) > 1:
            warnings.append(f"Route {index} is both {' and '.join(names)}.")

    return label_map, warnings


def handler(event, context):
    _ensure_path()
    from common.util import error_response, get_logger, json_response

    logger = get_logger(__name__)

    try:
        origin, destination, mode = _parse_request(event)
    except ValueError as exc:
        return error_response("BAD_REQUEST", str(exc), 400)

    token = get_mapbox_token()
    directions = _directions(origin, destination, mode, token)
    if not directions:
        return error_response(
            "ROUTING_UNAVAILABLE", "Unable to calculate a route from Mapbox", 502
        )

    now = datetime.now(timezone.utc)
    try:
        dynamodb = boto3.resource("dynamodb")
        geo_table = dynamodb.Table(
            os.environ.get("GEOCELLS_TABLE", os.environ.get("GEO_CELLS_TABLE", "GeoCellsTable"))
        )
        stations_table = dynamodb.Table(os.environ.get("STATIONS_TABLE", "StationsTable"))
    except Exception as exc:
        logger.error("Failed to initialise DynamoDB tables", extra={"error": str(exc)})
        geo_table = None
        stations_table = None

    warnings: list[str] = []
    prepared = []
    for index, route in enumerate(directions):
        samples = _resample(route["coordinates"], _sample_step(route))
        cells: dict = {}
        stations: list = []
        try:
            if geo_table is not None:
                cells = _load_cells(geo_table, _cell_partitions(samples))
            if stations_table is not None:
                stations = _load_stations(stations_table, _station_partitions(samples))
        except Exception as exc:
            logger.error("Failed to load air quality data", extra={"error": str(exc)})
            cells = cells or {}
            stations = stations or []

        resolved = [_resolve_point(lat, lon, cells, stations, now) for lat, lon in samples]
        metrics = _route_metrics(route, samples, resolved)
        metrics["id"] = index
        metrics["source"] = route.get("source", "mapbox")

        if route.get("fallbackReason"):
            metrics["fallbackReason"] = route["fallbackReason"]
            warnings.append(
                f"Route {index} used a fallback path because Mapbox was unavailable "
                f"({route['fallbackReason']})."
            )
        if metrics["lowCoverage"]:
            warnings.append(
                f"Limited local data for route {index}: "
                f"{int(round(metrics['coverage'] * 100))}% of samples resolved from scans. "
                "Estimate leans on nearby stations."
            )
        prepared.append((route, samples, metrics, resolved))

    metrics_list = [item[2] for item in prepared]
    label_routes, label_warnings = _score_routes(metrics_list)
    warnings.extend(label_warnings)

    routes_out = []
    for route, samples, metrics, resolved in prepared:
        routes_out.append(
            {
                "id": metrics["id"],
                "source": metrics["source"],
                "fallbackReason": metrics.get("fallbackReason"),
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[point[1], point[0]] for point in route["coordinates"]],
                },
                "samples": [[round(lat, 6), round(lon, 6)] for lat, lon in samples],
                "sampleLevels": [point["level"] for point in resolved],
                "avgAqi": metrics["avgAqi"],
                "category": metrics["category"],
                "minutes": metrics["minutes"],
                "durationSec": metrics["durationSec"],
                "distanceM": metrics["distanceM"],
                "exposure": metrics["exposure"],
                "coverage": metrics["coverage"],
                "lowCoverage": metrics["lowCoverage"],
                "sampleCount": metrics["sampleCount"],
                "normalizedTime": metrics.get("normalizedTime"),
                "normalizedExposure": metrics.get("normalizedExposure"),
                "combined": metrics.get("combined"),
                "labels": metrics.get("labels", []),
            }
        )

    payload = {
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "routes": routes_out,
        "labels": {
            "fastest": label_routes.get("fastest"),
            "cleanest": label_routes.get("cleanest"),
            "balanced": label_routes.get("balanced"),
        },
        "warnings": warnings,
    }
    return json_response(200, payload)


lambda_handler = handler

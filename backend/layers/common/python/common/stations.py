from __future__ import annotations

import math
import os
import time
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from common import geohash
from common.aqi import pm25_to_aqi
from common.clients import fetch_openaq_stations
from common.util import float_to_decimal, get_logger

logger = get_logger(__name__)


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def _get_table(table_or_resource: Any) -> Any:
    if table_or_resource is None:
        table_name = os.environ.get("STATION_TABLE_NAME", os.environ.get("STATIONS_TABLE", "Stations"))
        return boto3.resource("dynamodb").Table(table_name)
    if hasattr(table_or_resource, "put_item"):
        return table_or_resource
    if hasattr(table_or_resource, "Table"):
        table_name = os.environ.get("STATION_TABLE_NAME", os.environ.get("STATIONS_TABLE", "Stations"))
        return table_or_resource.Table(table_name)
    return table_or_resource


async def get_nearest_station(
    lat: float,
    lon: float,
    dynamodb_resource_or_table: Any = None,
) -> dict | None:
    table = _get_table(dynamodb_resource_or_table)
    center_gh4 = geohash.encode(lat, lon, 4)
    neighbors_gh4 = geohash.neighbors(center_gh4)
    partitions = [center_gh4] + neighbors_gh4

    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    ttl_val = int(time.time()) + (7 * 86400)

    stale_partitions = []
    partition_items = {}

    for gh4 in partitions:
        pk_val = f"G#{gh4}"
        try:
            res = table.query(KeyConditionExpression=Key("pk").eq(pk_val))
            items = res.get("Items", [])
        except Exception as e:
            logger.error(f"Error querying partition {pk_val}: {e}")
            items = []

        partition_items[gh4] = list(items)

        meta_item = next((item for item in items if item.get("sk") == "META"), None)
        is_stale = True
        if meta_item and "fetchedAt" in meta_item:
            try:
                fetched_dt = datetime.fromisoformat(str(meta_item["fetchedAt"]).replace("Z", "+00:00"))
                if fetched_dt.tzinfo is None:
                    fetched_dt = fetched_dt.replace(tzinfo=timezone.utc)
                if 0 <= (now_dt - fetched_dt).total_seconds() < 1800:
                    is_stale = False
            except Exception:
                is_stale = True

        if is_stale:
            stale_partitions.append(gh4)

    partitions_to_refresh = stale_partitions[:3]

    for gh4 in partitions_to_refresh:
        min_lat, min_lon, max_lat, max_lon = geohash.decode_bbox(gh4)
        raw_stations = await fetch_openaq_stations(bbox=(min_lat, min_lon, max_lat, max_lon))

        new_items = []
        meta_record = {
            "pk": f"G#{gh4}",
            "sk": "META",
            "fetchedAt": now_iso,
            "ttl": ttl_val,
        }
        try:
            table.put_item(Item=float_to_decimal(meta_record))
        except Exception as e:
            logger.error(f"Error putting META item for {gh4}: {e}")
        new_items.append(meta_record)

        for st in raw_stations:
            st_id = str(st.get("id") or st.get("location") or "")
            if not st_id:
                continue

            st_name = str(st.get("name") or st.get("location") or "Unknown Station")
            coords = st.get("coordinates", {})
            st_lat = coords.get("latitude")
            st_lon = coords.get("longitude")
            if st_lat is None or st_lon is None:
                continue

            pm25_val = st.get("pm25")

            if pm25_val is None:
                continue

            aqi_val = pm25_to_aqi(pm25_val)
            st_item = {
                "pk": f"G#{gh4}",
                "sk": f"STATION#{st_id}",
                "id": st_id,
                "name": st_name,
                "lat": float(st_lat),
                "lon": float(st_lon),
                "pm25": float(pm25_val),
                "aqi": int(aqi_val),
                "fetchedAt": now_iso,
                "ttl": ttl_val,
            }
            try:
                table.put_item(Item=float_to_decimal(st_item))
            except Exception as e:
                logger.error(f"Error putting station item {st_id}: {e}")
            new_items.append(st_item)

        if len(new_items) > 1:
            partition_items[gh4] = new_items

    all_stations = []
    for gh4, items in partition_items.items():
        for item in items:
            sk_val = str(item.get("sk", ""))
            if sk_val.startswith("STATION#") or sk_val.startswith("ST#"):
                st_id = str(item.get("id", sk_val.split("#", 1)[-1]))
                st_name = str(item.get("name", "Unknown Station"))
                try:
                    st_lat = float(item["lat"])
                    st_lon = float(item["lon"])
                    pm25_val = float(item.get("pm25", 0.0))
                    aqi_val = int(item.get("aqi", pm25_to_aqi(pm25_val)))
                except (KeyError, ValueError, TypeError):
                    continue

                dist_km = haversine(lat, lon, st_lat, st_lon)
                if dist_km <= 15.0:
                    all_stations.append(
                        {
                            "id": st_id,
                            "name": st_name,
                            "distance_km": round(dist_km, 2),
                            "pm25": pm25_val,
                            "aqi": aqi_val,
                            "lat": st_lat,
                            "lon": st_lon,
                        }
                    )

    if not all_stations:
        return None

    all_stations.sort(key=lambda x: x["distance_km"])
    return all_stations[0]

#!/usr/bin/env python3
"""
Bangalore Region Data Seeding Script

Populates DynamoDB tables with realistic data for Bangalore:
- StationsTable: Official monitoring stations
- GeoCellsTable: Spatial AQI grid at resolutions 5, 6, 7
- ScansTable: Historical scan records with trend data

Supports both DynamoDB Local and AWS DynamoDB.
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "layers", "common"))
from common import geohash
from common.util import float_to_decimal

IST = timezone(timedelta(hours=5, minutes=30), name="IST")

BANGALORE_STATIONS = [
    {
        "id": "bangalore-silk-board",
        "name": "Silk Board",
        "lat": 12.9176,
        "lon": 77.6228,
        "pm25": 85.0,
        "description": "Major traffic junction, typically high pollution",
    },
    {
        "id": "bangalore-indiranagar",
        "name": "Indiranagar",
        "lat": 12.9716,
        "lon": 77.6412,
        "pm25": 65.0,
        "description": "Urban residential and commercial area",
    },
    {
        "id": "bangalore-peenya",
        "name": "Peenya Industrial Area",
        "lat": 13.0281,
        "lon": 77.5202,
        "pm25": 95.0,
        "description": "Industrial zone with elevated pollution",
    },
    {
        "id": "bangalore-hebbal",
        "name": "Hebbal",
        "lat": 13.0358,
        "lon": 77.5970,
        "pm25": 55.0,
        "description": "Near green spaces, relatively cleaner air",
    },
    {
        "id": "bangalore-whitefield",
        "name": "Whitefield",
        "lat": 12.9698,
        "lon": 77.7499,
        "pm25": 70.0,
        "description": "Tech corridor, moderate pollution",
    },
    {
        "id": "bangalore-mg-road",
        "name": "MG Road",
        "lat": 12.9754,
        "lon": 77.6063,
        "pm25": 75.0,
        "description": "Central business district",
    },
    {
        "id": "bangalore-electronic-city",
        "name": "Electronic City",
        "lat": 12.8451,
        "lon": 77.6600,
        "pm25": 78.0,
        "description": "IT hub with moderate traffic pollution",
    },
    {
        "id": "bangalore-jayanagar",
        "name": "Jayanagar",
        "lat": 12.9250,
        "lon": 77.5937,
        "pm25": 60.0,
        "description": "Planned residential area with parks",
    },
]

BANGALORE_BOUNDS = {
    "min_lat": 12.80,
    "max_lat": 13.15,
    "min_lon": 77.40,
    "max_lon": 77.75,
}


def pm25_to_aqi(pm25: float) -> int:
    """Convert PM2.5 to US AQI (simplified)."""
    if pm25 <= 12.0:
        return int((50 / 12.0) * pm25)
    elif pm25 <= 35.4:
        return int(50 + ((100 - 50) / (35.4 - 12.0)) * (pm25 - 12.0))
    elif pm25 <= 55.4:
        return int(100 + ((150 - 100) / (55.4 - 35.4)) * (pm25 - 35.4))
    elif pm25 <= 150.4:
        return int(150 + ((200 - 150) / (150.4 - 55.4)) * (pm25 - 55.4))
    elif pm25 <= 250.4:
        return int(200 + ((300 - 200) / (250.4 - 150.4)) * (pm25 - 150.4))
    else:
        return int(300 + ((500 - 300) / (500.4 - 250.4)) * (pm25 - 250.4))


def get_dynamodb_client(local: bool = False):
    """Get DynamoDB client for local or AWS."""
    if local:
        return boto3.resource(
            "dynamodb",
            endpoint_url="http://localhost:8000",
            region_name="us-east-1",
            aws_access_key_id="fakeAccessKeyId",
            aws_secret_access_key="fakeSecretAccessKey",
        )
    return boto3.resource("dynamodb")


def seed_stations(dynamodb: Any, table_name: str, dry_run: bool = False) -> int:
    """Seed official monitoring stations for Bangalore."""
    print(f"\n🏢 Seeding stations to {table_name}...")
    table = dynamodb.Table(table_name)
    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()
    ttl_val = int(time.time()) + (30 * 86400)
    count = 0

    for station in BANGALORE_STATIONS:
        gh4 = geohash.encode(station["lat"], station["lon"], 4)
        aqi = pm25_to_aqi(station["pm25"])
        
        item = {
            "pk": f"S#{gh4}",
            "sk": f"ST#{station['id']}",
            "id": station["id"],
            "name": station["name"],
            "lat": station["lat"],
            "lon": station["lon"],
            "pm25": station["pm25"],
            "aqi": aqi,
            "aqiUS": aqi,
            "measuredAt": now_iso,
            "fetchedAt": now_iso,
            "ttl": ttl_val,
            "description": station.get("description", ""),
        }
        
        if not dry_run:
            table.put_item(Item=float_to_decimal(item))
        
        print(f"  ✓ {station['name']} (gh4={gh4}, AQI={aqi})")
        count += 1

    for station in BANGALORE_STATIONS:
        gh4 = geohash.encode(station["lat"], station["lon"], 4)
        meta_item = {
            "pk": f"S#{gh4}",
            "sk": "META",
            "fetchedAt": now_iso,
            "ttl": ttl_val,
        }
        if not dry_run:
            table.put_item(Item=float_to_decimal(meta_item))

    return count


def interpolate_aqi(lat: float, lon: float, stations: list) -> float:
    """Interpolate AQI based on inverse distance weighting from stations."""
    import math
    
    def haversine(lat1, lon1, lat2, lon2):
        r = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    weighted_sum = 0.0
    weight_total = 0.0
    
    for st in stations:
        dist = haversine(lat, lon, st["lat"], st["lon"])
        if dist < 0.1:
            return float(pm25_to_aqi(st["pm25"]))
        weight = 1.0 / (dist ** 2)
        weighted_sum += weight * pm25_to_aqi(st["pm25"])
        weight_total += weight
    
    if weight_total > 0:
        return weighted_sum / weight_total
    return 75.0


def seed_geocells(dynamodb: Any, table_name: str, dry_run: bool = False) -> int:
    """Seed GeoCellsTable with spatial AQI grid for Bangalore."""
    print(f"\n🗺️  Seeding geo cells to {table_name}...")
    table = dynamodb.Table(table_name)
    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()
    ttl_val = int(time.time()) + (7 * 86400)
    count = 0

    for precision in [5, 6, 7]:
        print(f"  Resolution {precision}:")
        cells = geohash.cells_covering(
            BANGALORE_BOUNDS["min_lat"],
            BANGALORE_BOUNDS["min_lon"],
            BANGALORE_BOUNDS["max_lat"],
            BANGALORE_BOUNDS["max_lon"],
            precision,
        )
        
        for cell in cells:
            min_lat, min_lon, max_lat, max_lon = geohash.decode_bbox(cell)
            center_lat = (min_lat + max_lat) / 2
            center_lon = (min_lon + max_lon) / 2
            
            aqi_val = interpolate_aqi(center_lat, center_lon, BANGALORE_STATIONS)
            weight = 2.5 if precision == 7 else (1.8 if precision == 6 else 1.2)
            
            gh5 = cell[:5]
            item = {
                "pk": f"G#{gh5}",
                "sk": f"{precision}#{cell}",
                "aqi": aqi_val,
                "sumWx": aqi_val * weight,
                "wSum": weight,
                "n": 1,
                "lastTs": now_iso,
                "version": 1,
                "ttl": ttl_val,
            }
            
            if not dry_run:
                table.put_item(Item=float_to_decimal(item))
            
            count += 1
        
        print(f"    ✓ Created {len(cells)} cells at precision {precision}")
    
    return count


def seed_scans(dynamodb: Any, table_name: str, dry_run: bool = False) -> int:
    """Seed ScansTable with historical scan records for trend queries."""
    print(f"\n📊 Seeding historical scans to {table_name}...")
    table = dynamodb.Table(table_name)
    now_utc = datetime.now(timezone.utc)
    count = 0
    
    test_user_id = "test-user-bangalore"
    
    for hours_ago in range(0, 24, 2):
        timestamp = now_utc - timedelta(hours=hours_ago)
        timestamp_iso = timestamp.astimezone(IST).isoformat()
        
        for idx, station in enumerate(BANGALORE_STATIONS[:4]):
            lat = station["lat"] + (idx % 2 - 0.5) * 0.01
            lon = station["lon"] + (idx % 3 - 1) * 0.01
            
            aqi = pm25_to_aqi(station["pm25"]) + (hours_ago % 5 - 2) * 5
            aqi = max(20, min(180, aqi))
            
            scan_id = f"scan-{hours_ago}h-{idx}"
            gh6 = geohash.encode(lat, lon, 6)
            
            item = {
                "pk": f"U#{test_user_id}",
                "sk": f"S#{scan_id}",
                "scanId": scan_id,
                "timestamp": timestamp_iso,
                "lat": lat,
                "lon": lon,
                "accuracy": 15.0,
                "aqi": aqi,
                "category": "Moderate" if aqi < 100 else "Unhealthy for Sensitive Groups",
                "confidence": 0.85,
                "source": "fusion",
                "scanWeight": 1.0,
                "inMap": True,
                "gsi1pk": f"H#{gh6}",
                "gsi1sk": timestamp_iso,
                "s3Key": f"scans/{test_user_id}/{scan_id}.jpg",
            }
            
            if not dry_run:
                table.put_item(Item=float_to_decimal(item))
            
            count += 1
    
    print(f"  ✓ Created {count} historical scan records")
    return count


def main():
    parser = argparse.ArgumentParser(description="Seed Bangalore region data into DynamoDB")
    parser.add_argument("--local", action="store_true", help="Use DynamoDB Local (http://localhost:8000)")
    parser.add_argument("--dry-run", action="store_true", help="Print operations without writing to DynamoDB")
    parser.add_argument("--stations-table", default="air-quality-app-stack-StationsTable-SECWHYVHSBRH", help="Name of StationsTable")
    parser.add_argument("--geocells-table", default="air-quality-app-stack-GeoCellsTable-1BC7FJIRR3YQE", help="Name of GeoCellsTable")
    parser.add_argument("--scans-table", default="air-quality-app-stack-ScansTable-E4QOGAOE5SC5", help="Name of ScansTable")
    parser.add_argument("--skip-stations", action="store_true", help="Skip seeding stations")
    parser.add_argument("--skip-geocells", action="store_true", help="Skip seeding geo cells")
    parser.add_argument("--skip-scans", action="store_true", help="Skip seeding scans")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("🌏 Bangalore Air Quality Data Seeding Script")
    print("=" * 70)
    print(f"Mode: {'DynamoDB Local' if args.local else 'AWS DynamoDB'}")
    print(f"Dry run: {args.dry_run}")
    print(f"Region: {BANGALORE_BOUNDS}")
    
    dynamodb = get_dynamodb_client(local=args.local)
    
    total_count = 0
    
    if not args.skip_stations:
        count = seed_stations(dynamodb, args.stations_table, args.dry_run)
        total_count += count
    
    if not args.skip_geocells:
        count = seed_geocells(dynamodb, args.geocells_table, args.dry_run)
        total_count += count
    
    if not args.skip_scans:
        count = seed_scans(dynamodb, args.scans_table, args.dry_run)
        total_count += count
    
    print("\n" + "=" * 70)
    print(f"✅ Seeding complete! Total items: {total_count}")
    if args.dry_run:
        print("   (Dry run - no data was actually written)")
    print("=" * 70)


if __name__ == "__main__":
    main()

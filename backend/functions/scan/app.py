import asyncio
import json
import os
import time
from datetime import datetime, timedelta, timezone

import boto3

IST = timezone(timedelta(hours=5, minutes=30), name="IST")

sys_path_inserted = False

def _ensure_path():
    import sys
    common_path = os.path.join(os.path.dirname(__file__), "..", "..", "layers", "common")
    if common_path not in sys.path:
        sys.path.insert(0, common_path)
    opt_path = "/opt/python"
    if opt_path not in sys.path:
        sys.path.insert(0, opt_path)

def handler(event, context):
    _ensure_path()

    import sys
    from common.predictor import get_predictor, Prediction
    from common.fusion import fuse_predictions
    from common.clients import fetch_weather
    from common.stations import get_nearest_station
    import common.geohash as geohash
    from common.cells import update_cell
    from common.util import float_to_decimal, decimal_to_float, json_response, error_response, get_logger
    from decimal import Decimal

    logger = get_logger(__name__)
    logger.info("Scan handler invoked")

    try:
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {}).get("sub", "")
        body = json.loads(event.get("body", "{}"))
        logger.debug("Request body parsed", extra={"keys": list(body.keys())})
    except Exception as e:
        logger.error("Failed to parse request body", extra={"error": str(e)})
        return error_response("BAD_REQUEST", str(e), 400)

    if not user_id:
        logger.warning("Unauthorized request - missing user identity")
        return error_response("UNAUTHORIZED", "Missing user identity", 401)

    scan_id = body.get("scanId")
    s3_key = body.get("s3Key")
    lat = body.get("lat")
    lon = body.get("lon")
    accuracy = body.get("accuracy")
    timestamp_str = body.get("timestamp")
    pressure = body.get("pressure")
    tag = body.get("tag")

    logger.info("Processing scan submission", extra={"user_id": user_id,"scan_id": scan_id,"lat": lat,"lon": lon,"accuracy": accuracy})

    if not scan_id or not s3_key:
        logger.warning("Missing required fields", extra={"scan_id": scan_id, "s3_key": s3_key})
        return error_response("BAD_REQUEST", "Missing scanId or s3Key", 400)

    expected_s3_key = f"scans/{user_id}/{scan_id}.jpg"
    if s3_key != expected_s3_key:
        logger.warning("Invalid s3Key", extra={"provided": s3_key, "expected": expected_s3_key})
        return error_response("BAD_REQUEST", "Invalid s3Key", 400)

    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except Exception as e:
        logger.warning("Invalid lat/lon format", extra={"lat": lat, "lon": lon, "error": str(e)})
        return error_response("BAD_REQUEST", "Invalid lat or lon", 400)

    if lat_f < -90 or lat_f > 90:
        logger.warning("Lat out of range", extra={"lat": lat_f})
        return error_response("BAD_REQUEST", "lat out of range", 400)
    if lon_f < -180 or lon_f > 180:
        logger.warning("Lon out of range", extra={"lon": lon_f})
        return error_response("BAD_REQUEST", "lon out of range", 400)

    if not isinstance(accuracy, (int, float)):
        logger.warning("Invalid accuracy format", extra={"accuracy": accuracy})
        return error_response("BAD_REQUEST", "Invalid accuracy", 400)
    accuracy_f = float(accuracy)
    logger.debug("Location validation passed", extra={"lat": lat_f, "lon": lon_f, "accuracy": accuracy_f})

    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(IST)
    now_ts = now_utc.timestamp()

    if timestamp_str is not None:
        try:
            if isinstance(timestamp_str, (int, float)) or (isinstance(timestamp_str, str) and timestamp_str.isdigit()):
                timestamp_f = float(timestamp_str)
                ts_dt = datetime.fromtimestamp(timestamp_f, tz=IST)
            else:
                ts_str = str(timestamp_str).replace("Z", "+00:00")
                ts_dt = datetime.fromisoformat(ts_str)
                if ts_dt.tzinfo is None:
                    ts_dt = ts_dt.replace(tzinfo=IST)
                timestamp_f = ts_dt.timestamp()
            delta_sec = timestamp_f - now_ts
            if delta_sec < -3600 or delta_sec > 600:
                logger.warning("Timestamp out of allowed range", extra={"delta_sec": delta_sec, "timestamp_str": timestamp_str})
                return error_response("BAD_REQUEST", "timestamp out of allowed range", 400)
            timestamp_for_scan = ts_dt.astimezone(IST).isoformat()
        except Exception as e:
            logger.warning("Invalid timestamp format", extra={"timestamp_str": timestamp_str, "error": str(e)})
            return error_response("BAD_REQUEST", "Invalid timestamp", 400)
    else:
        timestamp_for_scan = now_ist.isoformat()
        logger.debug("Using current timestamp")

    bucket_name = os.environ.get("SCANS_BUCKET", "")
    s3_client = boto3.client("s3")

    logger.debug("Checking if image exists in S3", extra={"bucket": bucket_name, "key": s3_key})

    try:
        head_resp = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
        content_length = head_resp.get("ContentLength", 0)
        logger.debug("Image found in S3", extra={"content_length": content_length})
        if content_length > 1048576:
            logger.warning("Image exceeds size limit", extra={"content_length": content_length})
            return error_response("BAD_REQUEST", "Image exceeds 1MB limit", 400)
    except Exception as e:
        logger.warning("Image not found in S3", extra={"key": s3_key, "error": str(e)})
        return error_response("BAD_REQUEST", "Image not found or error", 400)

    stations_table_name = os.environ.get("STATIONS_TABLE", os.environ.get("STATION_TABLE_NAME", "Stations"))
    dynamodb = boto3.resource("dynamodb")
    stations_table_res = dynamodb.Table(stations_table_name)

    logger.debug("Fetching weather and station data", extra={"lat": lat_f, "lon": lon_f})

    try:
        async def run_async():
            weather_task = asyncio.create_task(fetch_weather(lat_f, lon_f))
            station_task = asyncio.create_task(get_nearest_station(lat_f, lon_f, stations_table_res))
            weather_result = await weather_task
            station_result = await station_task
            return weather_result, station_result
        weather_result, station_result = asyncio.run(run_async())
    except Exception as e:
        logger.error("Failed to fetch external data", extra={"error": str(e)})
        weather_result = None
        station_result = None

    station_dict = station_result
    station_dist = station_dict.get("distance_km") if station_dict else None
    logger.info("External data fetched", extra={"has_weather": weather_result is not None, "has_station": station_dict is not None})

    try:
        image_resp = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        image_bytes = image_resp["Body"].read()
        logger.debug("Image read from S3", extra={"size_bytes": len(image_bytes)})
    except Exception as e:
        logger.error("Failed to read image from S3", extra={"error": str(e)})
        return error_response("BAD_REQUEST", "Failed to read image from S3", 400)

    predictor = get_predictor()
    ctx = {
        "station": station_dict,
        "station_aqi": station_dict.get("aqi") if station_dict else None,
        "weather": weather_result,
        "lat": lat_f,
        "lon": lon_f,
    }
    logger.debug("Running prediction model")
    try:
        model_pred = asyncio.run(predictor.predict(image_bytes, ctx))
        logger.info("Prediction complete", extra={"aqi": model_pred.aqi, "category": model_pred.category, "confidence": model_pred.confidence})
    except Exception as e:
        logger.error("Prediction failed, using fallback", extra={"error": str(e)})
        model_pred = Prediction(aqi=75, category="Moderate", confidence=0.4, source="station_stub", probabilities=None)

    logger.debug("Fusing predictions with station data")
    fusion_result = fuse_predictions(
        station=station_dict,
        model_pred=model_pred,
        distance_km=station_dist,
        image_quality=1.0,
        gps_accuracy_m=accuracy_f,
    )

    aqi_val = fusion_result.get("aqi", 0)
    category_val = fusion_result.get("category", "Unknown")
    confidence_val = fusion_result.get("confidence", 0.0)
    source_val = fusion_result.get("source", "unknown")
    scan_weight_val = fusion_result.get("scan_weight", 0.0)

    in_map_val = accuracy_f <= 100
    logger.info("Scan processing complete", extra={"aqi": aqi_val,"category": category_val,"confidence": confidence_val,"in_map": in_map_val})

    scans_table_name = os.environ.get("SCANS_TABLE", "ScansTable")
    scans_table = dynamodb.Table(scans_table_name)

    scan_item = {
        "pk": f"U#{user_id}",
        "sk": f"S#{scan_id}",
        "scanId": scan_id,
        "timestamp": timestamp_for_scan,
        "lat": float_to_decimal(lat_f),
        "lon": float_to_decimal(lon_f),
        "accuracy": float_to_decimal(accuracy_f),
        "aqi": float_to_decimal(aqi_val),
        "category": category_val,
        "confidence": float_to_decimal(confidence_val),
        "source": source_val,
        "station": station_dict,
        "scanWeight": float_to_decimal(scan_weight_val),
        "s3Key": s3_key,
        "inMap": in_map_val,
    }
    if tag is not None:
        scan_item["tag"] = tag
    if pressure is not None:
        scan_item["pressure"] = float_to_decimal(float(pressure))

    logger.debug("Saving scan to DynamoDB", extra={"scan_id": scan_id, "table": scans_table_name})
    try:
        scans_table.put_item(
            Item=scan_item,
            ConditionExpression="attribute_not_exists(sk)",
        )
        saved_item = scan_item
        logger.info("Scan saved to DynamoDB successfully", extra={"scan_id": scan_id})
    except Exception as e:
        err_str = str(e)
        if "ConditionalCheckFailedException" in err_str:
            logger.warning("Scan already exists, fetching existing item", extra={"scan_id": scan_id})
            existing_resp = scans_table.get_item(Key={"pk": f"U#{user_id}", "sk": f"S#{scan_id}"})
            existing_item = existing_resp.get("Item")
            if existing_item:
                saved_item = existing_item
            else:
                saved_item = scan_item
        else:
            logger.error("Failed to save scan to DynamoDB", extra={"error": str(e)})
            saved_item = scan_item

    if in_map_val:
        geo_table_name = os.environ.get("GEO_CELLS_TABLE", os.environ.get("GEOCELLS_TABLE", "GeoCellsTable"))
        geo_table = dynamodb.Table(geo_table_name)
        precisions = [7, 6, 5] if accuracy_f <= 20 else [6, 5]
        logger.debug("Updating geo cells", extra={"precisions": precisions, "accuracy": accuracy_f})
        for p in precisions:
            gh_full = geohash.encode(lat_f, lon_f, p)
            gh5 = gh_full[:5]
            pk_cell = f"G#{gh5}"
            sk_cell = f"{p}#{gh_full}"
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    cell_resp = geo_table.get_item(Key={"pk": pk_cell, "sk": sk_cell})
                    cell_item = cell_resp.get("Item")
                    if cell_item:
                        old_sumWx = float(cell_item.get("sumWx", 0) or 0)
                        old_wSum = float(cell_item.get("wSum", 0) or 0)
                        old_lastTs = str(cell_item.get("lastTs", timestamp_for_scan) or timestamp_for_scan)
                        old_version = int(cell_item.get("version", 0) or 0)
                        old_n = int(cell_item.get("n", 0) or 0)
                    else:
                        old_sumWx = 0.0
                        old_wSum = 0.0
                        old_lastTs = timestamp_for_scan
                        old_version = 0
                        old_n = 0

                    logger.debug("Geo cell update", extra={"precision": p,"geohash": gh_full,"old_sumWx": old_sumWx,"old_wSum": old_wSum,"old_version": old_version,"old_n": old_n})
                    cell_result = update_cell(old_sumWx, old_wSum, old_lastTs, float(aqi_val), float(scan_weight_val), timestamp_for_scan)
                    new_version = old_version + 1
                    new_n = old_n + 1

                    geo_table.update_item(
                        Key={"pk": pk_cell, "sk": sk_cell},
                        UpdateExpression="SET sumWx = :sw, wSum = :ws, aqi = :aqi, lastTs = :lts, #v = :new_v, n = :n, #ttl = :ttl",
                        ExpressionAttributeNames={"#v": "version", "#ttl": "ttl"},
                        ExpressionAttributeValues={
                            ":sw": Decimal(str(cell_result["sumWx"])),
                            ":ws": Decimal(str(cell_result["wSum"])),
                            ":aqi": Decimal(str(cell_result["aqi"])),
                            ":lts": timestamp_for_scan,
                            ":new_v": new_version,
                            ":n": new_n,
                            ":ttl": int(datetime.fromisoformat(timestamp_for_scan.replace("Z", "+00:00")).timestamp()) + 7 * 86400,
                            ":old_v": old_version,
                        },
                        ConditionExpression="attribute_not_exists(#v) OR #v = :old_v",
                    )
                    logger.info("Geo cell updated successfully", extra={"precision": p,"geohash": gh_full,"new_version": new_version,"new_n": new_n,"aqi": cell_result["aqi"]})
                    break
                except Exception as cell_e:
                    if "ConditionalCheckFailedException" in str(cell_e) and attempt < max_retries - 1:
                        logger.debug("Conditional check failed, retrying", extra={"attempt": attempt + 1,"max_retries": max_retries,"precision": p})
                        time.sleep(0.05 * (attempt + 1))
                    else:
                        logger.error("Failed to update geo cell", extra={"precision": p,"geohash": gh_full,"error": str(cell_e),"attempt": attempt + 1})
                        raise
        logger.info("Geo cells update completed", extra={"precisions_updated": len(precisions)})

    result_body = {
        "scanId": scan_id,
        "aqi": aqi_val,
        "category": category_val,
        "confidence": confidence_val,
        "source": source_val,
        "station": station_dict,
        "inMap": in_map_val,
        "scanWeight": scan_weight_val,
    }
    logger.info("Scan handler completed successfully", extra={"scan_id": scan_id,"aqi": aqi_val,"confidence": confidence_val,"source": source_val})
    return json_response(200, result_body)

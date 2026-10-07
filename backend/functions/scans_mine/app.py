import base64
import json
import os

sys_path_inserted = False

def handler(event, context):
    import sys
    common_path = os.path.join(os.path.dirname(__file__), "..", "..", "layers", "common", "python")
    if common_path not in sys.path:
        sys.path.insert(0, common_path)
    opt_path = "/opt/python"
    if opt_path not in sys.path:
        sys.path.insert(0, opt_path)

    import boto3
    from common.util import json_response, error_response

    try:
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {}).get("sub", "")
    except Exception:
        return error_response("UNAUTHORIZED", "Missing user identity", 401)

    if not user_id:
        return error_response("UNAUTHORIZED", "Missing user identity", 401)

    table_name = os.environ.get("SCANS_TABLE", "ScansTable")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    page_token = event.get("queryStringParameters", {}).get("pageToken") if event.get("queryStringParameters") else None
    exclusive_start_key = None
    if page_token:
        try:
            decoded = base64.urlsafe_b64decode(page_token.encode("ascii"))
            exclusive_start_key = json.loads(decoded)
        except Exception:
            exclusive_start_key = None

    try:
        from boto3.dynamodb.conditions import Key
        query_params = {
            "KeyConditionExpression": Key("pk").eq(f"U#{user_id}") & Key("sk").begins_with("S#"),
            "ScanIndexForward": False,
            "Limit": 20,
        }
        if exclusive_start_key:
            query_params["ExclusiveStartKey"] = exclusive_start_key
        response = table.query(**query_params)
    except Exception as e:
        return error_response("QUERY_ERROR", str(e), 500)

    items = response.get("Items", [])
    last_evaluated_key = response.get("LastEvaluatedKey")
    next_token = None
    if last_evaluated_key:
        next_token = base64.urlsafe_b64encode(json.dumps(last_evaluated_key, default=str).encode("ascii")).decode("ascii")

    scans = []
    for item in items:
        scan_obj = {
            "scanId": item.get("scanId"),
            "timestamp": item.get("timestamp"),
            "aqi": float(item.get("aqi", 0)) if item.get("aqi") is not None else None,
            "category": item.get("category"),
            "confidence": float(item.get("confidence", 0)) if item.get("confidence") is not None else None,
            "source": item.get("source"),
            "lat": float(item.get("lat", 0)) if item.get("lat") is not None else None,
            "lon": float(item.get("lon", 0)) if item.get("lon") is not None else None,
            "inMap": item.get("inMap"),
        }
        scans.append(scan_obj)

    return json_response(200, {"scans": scans, "nextPageToken": next_token})

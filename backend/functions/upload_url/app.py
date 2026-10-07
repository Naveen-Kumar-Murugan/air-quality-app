import json
import os
import boto3
from datetime import datetime, timezone

def handler(event, context):
    import sys
    common_path = os.path.join(os.path.dirname(__file__), "..", "..", "layers", "common", "python")
    if common_path not in sys.path:
        sys.path.insert(0, common_path)
    opt_path = "/opt/python"
    if opt_path not in sys.path:
        sys.path.insert(0, opt_path)

    from common.util import generate_ulid, json_response, error_response

    user_id = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {}).get("sub", "")
    if not user_id:
        return error_response("UNAUTHORIZED", "Missing user identity", 401)

    table_name = os.environ.get("RATE_LIMITS_TABLE", "RateLimitsTable")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    now_utc = datetime.now(timezone.utc)
    hour_str = now_utc.strftime("%Y-%m-%d-%H")
    ttl_val = int(now_utc.timestamp()) + 7200

    try:
        response = table.update_item(
            Key={"pk": f"USER#{user_id}", "sk": f"HOUR#{hour_str}"},
            UpdateExpression="SET #count = if_not_exists(#count, :zero) + :one SET #ttl = :ttl",
            ExpressionAttributeNames={"#count": "count", "#ttl": "ttl"},
            ExpressionAttributeValues={":zero": 0, ":one": 1, ":ttl": ttl_val},
            ReturnValues="UPDATED_NEW",
        )
        new_count = int(response["Attributes"].get("count", 1))
        if new_count > 20:
            return error_response("RATE_LIMITED", "Hourly scan limit reached (20 scans/hour)", 429)
    except Exception as e:
        return error_response("INTERNAL_ERROR", str(e), 500)

    scan_id = generate_ulid()
    s3_key = f"scans/{user_id}/{scan_id}.jpg"
    bucket_name = os.environ.get("SCANS_BUCKET", "")
    s3_client = boto3.client("s3")
    expires_in = 300
    try:
        upload_url = s3_client.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket_name, "Key": s3_key, "ContentType": "image/jpeg"},
            ExpiresIn=expires_in,
        )
    except Exception as e:
        return error_response("S3_ERROR", str(e), 500)

    expires_at = (now_utc.timestamp() + expires_in)

    return json_response(200, {
        "scanId": scan_id,
        "uploadUrl": upload_url,
        "s3Key": s3_key,
        "expiresAt": int(expires_at),
    })

import json


def handler(event, context):
    import sys
    import os
    common_path = os.path.join(os.path.dirname(__file__), "..", "..", "layers", "common")
    if common_path not in sys.path:
        sys.path.insert(0, common_path)
    opt_path = "/opt/python"
    if opt_path not in sys.path:
        sys.path.insert(0, opt_path)

    from common.util import get_logger

    logger = get_logger(__name__)
    logger.info("Hello handler invoked")

    try:
        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        logger.info("User authenticated", extra={"user_id": user_id})
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"userId": user_id, "message": "Auth works"})
        }
    except Exception as e:
        logger.error("Failed to extract user ID", extra={"error": str(e)})
        return {
            "statusCode": 401,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "UNAUTHORIZED", "message": "Missing user identity"})
        }

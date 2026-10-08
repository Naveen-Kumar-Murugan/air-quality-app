import json

from common.util import get_logger


def handler(event, context):
    logger = get_logger(__name__)
    logger.info("Hello handler invoked")

    try:
        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        logger.info("User authenticated",extra={"user_id": user_id})
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "userId": user_id,
                "message": "Auth works"
            })
        }

    except Exception as e:
        logger.error(
            "Failed to extract user ID", extra={"error": str(e)})
        return {
            "statusCode": 401,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "UNAUTHORIZED",
                "message": "Missing user identity"
            })
        }
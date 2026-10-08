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
    logger.info("Pre-signup trigger invoked")

    event["response"]["autoConfirmUser"] = True
    event["response"]["autoVerifyEmail"] = False

    logger.info("User auto-confirmed", extra={"user_id": event.get("userName", "unknown")})
    return event

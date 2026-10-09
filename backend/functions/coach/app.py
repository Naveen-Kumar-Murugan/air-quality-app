import sys
import os

# Add backend directory and common layer path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "layers", "common")))

print(f"SYSPATH: {sys.path}")

import json
import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from common.util import json_response, error_response, get_logger

logger = get_logger(__name__)

# --- Tools ---

@tool
def get_area_aqi(lat: float, lon: float, radius_m: int = 500) -> dict:
    """Query GeoCells & Stations and compute area blended AQI."""
    # Simplified implementation for the exercise
    return {"aqi": 75, "count": 12, "freshness": "recent"}

@tool
def get_trend(lat: float, lon: float, hours: int = 24) -> dict:
    """Determine AQI trend direction."""
    # Simplified implementation
    return {"trend": "rising"}

@tool
def compare_routes(route_context: dict) -> dict:
    """Explain metrics and why a route is cleanest/balanced."""
    return {"comparison": "Route A is cleaner than Route B."}

# --- Response Engine ---

def get_template_response(message: str, context: dict) -> dict:
    # A simple deterministic fallback
    return {
        "text": "Coach Engine (Fallback): AQI is moderate. Rising trend detected. Route A is recommended.",
        "metrics": {"aqi": 75, "trend": "rising"}
    }

# --- Strands Agent Setup ---

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
REGION = os.environ.get("BEDROCK_REGION", "ap-south-1")

model = BedrockModel(model_id=MODEL_ID, region_name=REGION)
coach_agent = Agent(
    model=model,
    tools=[get_area_aqi, get_trend, compare_routes],
    system_prompt="""
        You are an Air Quality Coach.
        - Rules: tools first before numbers, cautious health guidance (no medical claims), concise replies (<120 words).
        - Always use provided tools to get real data before answering.
    """
)
# Removed tool registration lines that were causing issues

# --- Lambda Handler ---

def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        message = body.get("message", "Status?")
        ctx = body.get("context", {})

        try:
            # Attempt AI inference
            response = coach_agent(message)
            return json_response(200, {"text": str(response)})
        except Exception as e:
            logger.error(f"Bedrock/Agent failed, falling back: {e}")
            # Fallback logic
            fallback = get_template_response(message, ctx)
            return json_response(200, fallback)

    except Exception as e:
        logger.error(f"Handler error: {e}")
        return error_response("INTERNAL_ERROR", "Unable to coach", 500)

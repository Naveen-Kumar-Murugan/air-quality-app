import pytest
import os
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "layers", "common"))

from functions.coach.app import get_area_aqi, get_trend, compare_routes, get_template_response, lambda_handler

def test_tool_functions():
    assert get_area_aqi(12.9, 77.5) == {"aqi": 75, "count": 12, "freshness": "recent"}
    assert get_trend(12.9, 77.5) == {"trend": "rising"}
    assert compare_routes({"route": "A"}) == {"comparison": "Route A is cleaner than Route B."}

def test_template_fallback():
    resp = get_template_response("test", {})
    assert "Rising" in resp["text"]
    assert resp["metrics"]["aqi"] == 75

@patch("functions.coach.app.coach_agent")
def test_handler_success(mock_agent):
    mock_agent.return_value = "AI Response"
    event = {"body": '{"message": "hello", "context": {}}'}
    resp = lambda_handler(event, None)
    assert resp["statusCode"] == 200
    assert "AI Response" in resp["body"]

@patch("functions.coach.app.coach_agent")
def test_handler_fallback_on_error(mock_agent):
    mock_agent.side_effect = Exception("Bedrock error")
    event = {"body": '{"message": "hello", "context": {}}'}
    resp = lambda_handler(event, None)
    assert resp["statusCode"] == 200
    assert "falling back" not in resp["body"]
    assert "rising" in resp["body"]

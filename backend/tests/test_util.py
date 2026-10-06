"""Tests for shared utility functions."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "layers", "common", "python"))

import json
from decimal import Decimal

from common.util import (
    json_response,
    error_response,
    decimal_to_float,
    float_to_decimal,
    generate_ulid,
    get_logger,
)


def test_json_response_format():
    """Response should have correct Lambda structure."""
    resp = json_response(200, {"key": "value"})
    assert resp["statusCode"] == 200
    assert "application/json" in resp["headers"]["Content-Type"]
    assert '"key"' in resp["body"]

    # Body should be valid JSON
    parsed = json.loads(resp["body"])
    assert parsed["key"] == "value"


def test_json_response_with_decimal():
    """Decimal values should be serialised without error."""
    resp = json_response(200, {"aqi": Decimal("123.45")})
    assert resp["statusCode"] == 200
    parsed = json.loads(resp["body"])
    assert abs(parsed["aqi"] - 123.45) < 0.01


def test_error_response():
    """Error response should have code and message."""
    resp = error_response("INVALID_INPUT", "Bad latitude", status=400)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert body["error"] == "INVALID_INPUT"
    assert body["message"] == "Bad latitude"


def test_error_response_custom_status():
    """Error response should accept custom status codes."""
    resp = error_response("RATE_LIMITED", "Too many requests", status=429)
    assert resp["statusCode"] == 429


def test_decimal_to_float_simple():
    """Decimal values should convert to float."""
    result = decimal_to_float(Decimal("3.14"))
    assert isinstance(result, float)
    assert abs(result - 3.14) < 0.001


def test_decimal_to_float_int():
    """Decimal values that are whole numbers should convert to int."""
    result = decimal_to_float(Decimal("42"))
    assert isinstance(result, int)
    assert result == 42


def test_decimal_conversion_roundtrip():
    """float → Decimal → float should preserve value."""
    original = {"aqi": 123.45, "count": 10}
    as_decimal = float_to_decimal(original)
    assert isinstance(as_decimal["aqi"], Decimal)
    assert isinstance(as_decimal["count"], int)  # int stays int

    back_to_float = decimal_to_float(as_decimal)
    assert abs(back_to_float["aqi"] - 123.45) < 0.01


def test_float_to_decimal_nested():
    """Nested structures should be converted recursively."""
    original = {"scan": {"aqi": 42.5, "coords": [12.0, 77.0]}}
    converted = float_to_decimal(original)
    assert isinstance(converted["scan"]["aqi"], Decimal)
    assert isinstance(converted["scan"]["coords"][0], Decimal)


def test_decimal_to_float_nested():
    """Nested Decimal structures should be converted back."""
    data = {"scan": {"aqi": Decimal("42.5"), "items": [Decimal("1"), Decimal("2.5")]}}
    converted = decimal_to_float(data)
    assert isinstance(converted["scan"]["aqi"], float)
    assert converted["scan"]["items"] == [1, 2.5]


def test_ulid_format():
    """ULID should be 26 characters, alphanumeric."""
    ulid = generate_ulid()
    assert len(ulid) == 26
    assert ulid.isalnum()


def test_ulid_uniqueness():
    """Two ULIDs should be different."""
    a = generate_ulid()
    b = generate_ulid()
    assert a != b


def test_ulid_sortable():
    """ULIDs generated later should sort after earlier ones."""
    import time

    a = generate_ulid()
    time.sleep(0.002)
    b = generate_ulid()
    assert b > a


def test_get_logger():
    """Logger should be returned and configured."""
    logger = get_logger("test_module")
    assert logger.name == "test_module"
    assert len(logger.handlers) > 0


def test_get_logger_idempotent():
    """Calling get_logger twice should not add duplicate handlers."""
    logger1 = get_logger("test_idem")
    handler_count = len(logger1.handlers)
    logger2 = get_logger("test_idem")
    assert logger1 is logger2
    assert len(logger2.handlers) == handler_count

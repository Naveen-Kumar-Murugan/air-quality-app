"""Shared helpers: Lambda responses, DynamoDB type conversion, ULID, logging."""

from __future__ import annotations

import json
import logging
import os
import random
import string
import struct
import time
from decimal import Decimal
from typing import Any


# ---------------------------------------------------------------------------
# Lambda response builders
# ---------------------------------------------------------------------------


def json_response(status_code: int, body: dict) -> dict:
    """Build an API Gateway v2 (HTTP API) Lambda proxy response."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=_json_default),
    }


def error_response(code: str, message: str, status: int = 400) -> dict:
    """Build a standardised error response."""
    return json_response(status, {"error": code, "message": message})


# ---------------------------------------------------------------------------
# Decimal ↔ float conversion (DynamoDB requires Decimal for numbers)
# ---------------------------------------------------------------------------


def decimal_to_float(obj: Any) -> Any:
    """Recursively convert ``Decimal`` values to ``float`` / ``int``."""
    if isinstance(obj, Decimal):
        if obj == int(obj):
            return int(obj)
        return float(obj)
    if isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [decimal_to_float(v) for v in obj]
    return obj


def float_to_decimal(obj: Any) -> Any:
    """Recursively convert ``float`` values to ``Decimal`` for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: float_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [float_to_decimal(v) for v in obj]
    return obj


# ---------------------------------------------------------------------------
# ULID generation (time-sortable, 26 chars, Crockford base32)
# ---------------------------------------------------------------------------

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_ulid() -> str:
    """Generate a ULID (Universally Unique Lexicographically Sortable Identifier).

    Returns a 26-character Crockford base32 string.
    """
    # 48-bit timestamp (milliseconds since Unix epoch)
    ts_ms = int(time.time() * 1000) & 0xFFFF_FFFF_FFFF

    # 80 bits of randomness
    rand_bytes = os.urandom(10)
    rand_hi = struct.unpack(">H", rand_bytes[:2])[0]
    rand_lo = struct.unpack(">Q", rand_bytes[2:])[0]

    # Encode timestamp (10 chars)
    ts_chars: list[str] = []
    for _ in range(10):
        ts_chars.append(_CROCKFORD[ts_ms & 0x1F])
        ts_ms >>= 5
    ts_chars.reverse()

    # Encode randomness (16 chars)
    rand_val = (rand_hi << 64) | rand_lo
    rand_chars: list[str] = []
    for _ in range(16):
        rand_chars.append(_CROCKFORD[rand_val & 0x1F])
        rand_val >>= 5
    rand_chars.reverse()

    return "".join(ts_chars) + "".join(rand_chars)


# ---------------------------------------------------------------------------
# Structured logger
# ---------------------------------------------------------------------------


def get_logger(name: str) -> logging.Logger:
    """Return a JSON-structured logger configured for Lambda / CloudWatch."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                '{"level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
            )
        )
        logger.addHandler(handler)
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    return logger


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _json_default(obj: Any) -> Any:
    """Fallback serialiser for ``json.dumps``."""
    if isinstance(obj, Decimal):
        if obj == int(obj):
            return int(obj)
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

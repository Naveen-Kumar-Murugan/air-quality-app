from __future__ import annotations

import asyncio
import json
import math
import os
from dataclasses import dataclass
from typing import Any, Protocol

from .aqi import CLASS_MIDPOINTS, aqi_to_category
from .util import get_logger

logger = get_logger(__name__)


@dataclass
class Prediction:
    aqi: int
    category: str
    confidence: float
    source: str
    probabilities: list[float] | None = None


class Predictor(Protocol):
    async def predict(self, image_bytes: bytes, ctx: dict) -> Prediction:
        ...


class StubPredictor:
    async def predict(self, image_bytes: bytes, ctx: dict) -> Prediction:
        logger.info("StubPredictor.predict called", extra={"image_size": len(image_bytes), "ctx_keys": list(ctx.keys())})
        station = ctx.get("station")
        station_aqi = ctx.get("station_aqi")

        if isinstance(station, dict) and "aqi" in station:
            base_aqi = float(station["aqi"])
            has_station = True
            logger.debug("Using station AQI from station dict", extra={"station_aqi": base_aqi})
        elif station_aqi is not None:
            base_aqi = float(station_aqi)
            has_station = True
            logger.debug("Using station AQI from context", extra={"station_aqi": base_aqi})
        else:
            base_aqi = 75.0
            has_station = False
            logger.debug("No station data, using default AQI", extra={"default_aqi": base_aqi})

        weather = ctx.get("weather") or {}
        humidity = weather.get("humidity")
        wind_speed = weather.get("wind_speed")

        if humidity is not None and humidity > 80:
            base_aqi *= 1.10
            logger.debug("Applied humidity adjustment", extra={"humidity": humidity, "adjustment_factor": 1.10})

        if wind_speed is not None and wind_speed > 5:
            base_aqi *= 0.90
            logger.debug("Applied wind speed adjustment", extra={"wind_speed": wind_speed, "adjustment_factor": 0.90})

        final_aqi = max(0, min(500, round(base_aqi)))
        cat = aqi_to_category(final_aqi)
        conf = 0.7 if has_station else 0.4
        logger.info("Prediction complete", extra={"aqi": final_aqi, "category": cat, "confidence": conf, "has_station": has_station})

        return Prediction(
            aqi=final_aqi,
            category=cat,
            confidence=conf,
            source="station_stub",
            probabilities=None,
        )


class SageMakerPredictor:
    def __init__(
        self,
        endpoint_name: str | None = None,
        timeout_seconds: float | None = None,
        runtime_client: Any | None = None,
        fallback: Predictor | None = None,
    ):
        self.endpoint_name = endpoint_name or os.environ.get("SAGEMAKER_ENDPOINT_NAME") or os.environ.get("SAGEMAKER_ENDPOINT")
        self.timeout_seconds = _timeout_seconds(timeout_seconds)
        self._runtime_client = runtime_client
        self._fallback = fallback or StubPredictor()

    async def predict(self, image_bytes: bytes, ctx: dict) -> Prediction:
        if not self.endpoint_name:
            logger.warning("SageMaker endpoint name missing, using fallback")
            return await self._fallback.predict(image_bytes, ctx)

        try:
            payload = await asyncio.wait_for(asyncio.to_thread(self._invoke_endpoint, image_bytes), timeout=self.timeout_seconds)
            probabilities = _extract_probabilities(payload)
            aqi = _expected_aqi(probabilities)
            category = aqi_to_category(aqi)
            confidence = round(max(probabilities), 3)
            logger.info(
                "SageMaker prediction complete",
                extra={"endpoint": self.endpoint_name, "aqi": aqi, "category": category, "confidence": confidence},
            )
            return Prediction(
                aqi=aqi,
                category=category,
                confidence=confidence,
                source="sagemaker",
                probabilities=[round(prob, 6) for prob in probabilities],
            )
        except Exception as e:
            logger.error("SageMaker prediction failed, using fallback", extra={"endpoint": self.endpoint_name, "error": str(e)})
            return await self._fallback.predict(image_bytes, ctx)

    def _invoke_endpoint(self, image_bytes: bytes) -> dict:
        client = self._runtime_client or self._build_runtime_client()
        response = client.invoke_endpoint(
            EndpointName=self.endpoint_name,
            ContentType="image/jpeg",
            Accept="application/json",
            Body=image_bytes,
        )
        body = response.get("Body")
        if body is None:
            raise ValueError("SageMaker response missing body")
        raw = body.read() if hasattr(body, "read") else body
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        if isinstance(raw, str):
            decoded = json.loads(raw)
        elif isinstance(raw, dict):
            decoded = raw
        else:
            raise ValueError("Unsupported SageMaker response body")
        if not isinstance(decoded, dict):
            raise ValueError("SageMaker response must be a JSON object")
        return decoded

    def _build_runtime_client(self):
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "sagemaker-runtime",
            config=Config(
                connect_timeout=min(3.0, self.timeout_seconds),
                read_timeout=self.timeout_seconds,
                retries={"total_max_attempts": 1, "mode": "standard"},
            ),
        )
        self._runtime_client = client
        return client


def get_predictor(mode: str | None = None) -> Predictor:
    target_mode = mode or os.environ.get("MODEL_MODE", "stub")
    logger.info("Getting predictor", extra={"mode": target_mode})
    if target_mode.lower() == "sagemaker":
        logger.info("Using SageMakerPredictor")
        return SageMakerPredictor()
    logger.info("Using StubPredictor")
    return StubPredictor()


def _timeout_seconds(value: float | None) -> float:
    raw_value = value if value is not None else os.environ.get("SAGEMAKER_INVOKE_TIMEOUT_SECONDS", "20")
    try:
        parsed = float(raw_value)
    except (TypeError, ValueError):
        parsed = 20.0
    return max(1.0, min(25.0, parsed))


def _extract_probabilities(payload: dict) -> list[float]:
    raw = payload.get("probs") or payload.get("probabilities") or payload.get("scores")
    if raw is None and isinstance(payload.get("prediction"), dict):
        prediction = payload["prediction"]
        raw = prediction.get("probs") or prediction.get("probabilities") or prediction.get("scores")
    if raw is None and isinstance(payload.get("predictions"), list) and payload["predictions"]:
        first = payload["predictions"][0]
        if isinstance(first, dict):
            raw = first.get("probs") or first.get("probabilities") or first.get("scores")
        else:
            raw = first
    if not isinstance(raw, (list, tuple)):
        raise ValueError("SageMaker response probabilities must be a list")
    if len(raw) != len(CLASS_MIDPOINTS):
        raise ValueError(f"Expected {len(CLASS_MIDPOINTS)} probabilities, got {len(raw)}")
    try:
        probabilities = [float(value) for value in raw]
    except (TypeError, ValueError) as error:
        raise ValueError("SageMaker probabilities must be numeric") from error
    if any(not math.isfinite(value) or value < 0 for value in probabilities):
        raise ValueError("SageMaker probabilities must be finite and non-negative")
    total = sum(probabilities)
    if not math.isfinite(total) or total <= 0:
        raise ValueError("SageMaker probabilities must sum to a positive value")
    return [value / total for value in probabilities]


def _expected_aqi(probabilities: list[float]) -> int:
    expected = sum(prob * midpoint for prob, midpoint in zip(probabilities, CLASS_MIDPOINTS))
    return max(0, min(500, round(expected)))

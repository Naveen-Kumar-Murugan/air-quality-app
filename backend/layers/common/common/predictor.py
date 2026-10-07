from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from backend.layers.common.common.aqi import aqi_to_category


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
        station = ctx.get("station")
        station_aqi = ctx.get("station_aqi")

        if isinstance(station, dict) and "aqi" in station:
            base_aqi = float(station["aqi"])
            has_station = True
        elif station_aqi is not None:
            base_aqi = float(station_aqi)
            has_station = True
        else:
            base_aqi = 75.0
            has_station = False

        weather = ctx.get("weather") or {}
        humidity = weather.get("humidity")
        wind_speed = weather.get("wind_speed")

        if humidity is not None and humidity > 80:
            base_aqi *= 1.10

        if wind_speed is not None and wind_speed > 5:
            base_aqi *= 0.90

        final_aqi = max(0, min(500, round(base_aqi)))
        cat = aqi_to_category(final_aqi)
        conf = 0.7 if has_station else 0.4

        return Prediction(
            aqi=final_aqi,
            category=cat,
            confidence=conf,
            source="station_stub",
            probabilities=None,
        )


class SageMakerPredictor:
    async def predict(self, image_bytes: bytes, ctx: dict) -> Prediction:
        raise NotImplementedError("SageMakerPredictor will be implemented in Phase 3")


def get_predictor(mode: str | None = None) -> Predictor:
    target_mode = mode or os.environ.get("MODEL_MODE", "stub")
    if target_mode.lower() == "sagemaker":
        return SageMakerPredictor()
    return StubPredictor()

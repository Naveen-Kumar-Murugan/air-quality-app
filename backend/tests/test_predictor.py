import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "layers", "common"))

from common.predictor import StubPredictor, SageMakerPredictor, get_predictor, Prediction, _extract_probabilities


@pytest.mark.asyncio
async def test_stub_predictor_with_station():
    predictor = StubPredictor()
    ctx = {"station": {"aqi": 120}}
    pred = await predictor.predict(b"image_bytes", ctx)
    assert isinstance(pred, Prediction)
    assert pred.aqi == 120
    assert pred.category == "Unhealthy for Sensitive Groups"
    assert pred.confidence == 0.7
    assert pred.source == "station_stub"


@pytest.mark.asyncio
async def test_stub_predictor_no_station():
    predictor = StubPredictor()
    ctx = {}
    pred = await predictor.predict(b"image_bytes", ctx)
    assert pred.aqi == 75
    assert pred.category == "Moderate"
    assert pred.confidence == 0.4
    assert pred.source == "station_stub"


@pytest.mark.asyncio
async def test_stub_predictor_weather_adjustments():
    predictor = StubPredictor()

    ctx_humidity = {"station_aqi": 100, "weather": {"humidity": 85, "wind_speed": 2.0}}
    pred1 = await predictor.predict(b"", ctx_humidity)
    assert pred1.aqi == 110

    ctx_wind = {"station_aqi": 100, "weather": {"humidity": 50, "wind_speed": 10.0}}
    pred2 = await predictor.predict(b"", ctx_wind)
    assert pred2.aqi == 90

    ctx_both = {"station_aqi": 100, "weather": {"humidity": 85, "wind_speed": 10.0}}
    pred3 = await predictor.predict(b"", ctx_both)
    assert pred3.aqi == 99


class RecordingFallback:
    def __init__(self):
        self.calls = []

    async def predict(self, image_bytes, ctx):
        self.calls.append((image_bytes, ctx))
        return Prediction(aqi=88, category="Moderate", confidence=0.4, source="station_stub")


class RuntimeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def invoke_endpoint(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


@pytest.mark.asyncio
async def test_sagemaker_predictor_invokes_endpoint_and_converts_expected_aqi():
    client = RuntimeClient({"Body": io.BytesIO(json.dumps({"probs": [0, 0.5, 0.5, 0, 0, 0]}).encode())})
    predictor = SageMakerPredictor(endpoint_name="aq-sky-classifier", runtime_client=client)

    prediction = await predictor.predict(b"jpeg", {})

    assert client.calls == [{
        "EndpointName": "aq-sky-classifier",
        "ContentType": "image/jpeg",
        "Accept": "application/json",
        "Body": b"jpeg",
    }]
    assert prediction.aqi == 100
    assert prediction.category == "Moderate"
    assert prediction.confidence == 0.5
    assert prediction.source == "sagemaker"
    assert prediction.probabilities == [0.0, 0.5, 0.5, 0.0, 0.0, 0.0]


@pytest.mark.asyncio
async def test_sagemaker_predictor_normalizes_valid_probability_scores():
    client = RuntimeClient({"Body": io.BytesIO(b'{"probabilities": [1, 1, 2, 0, 0, 0]}')})
    predictor = SageMakerPredictor(endpoint_name="endpoint", runtime_client=client)

    prediction = await predictor.predict(b"jpeg", {})

    assert prediction.aqi == 88
    assert prediction.probabilities == [0.25, 0.25, 0.5, 0.0, 0.0, 0.0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        {"Body": io.BytesIO(b'{"probs": [0, 0, 0, 0, 0, 0]}')},
        {"Body": io.BytesIO(b'{"probs": [1, 2]}')},
        {"Body": io.BytesIO(b'{"probs": [1, -1, 0, 0, 0, 0]}')},
        {"Body": io.BytesIO(b'{"probs": [1, "NaN", 0, 0, 0, 0]}')},
        {"Body": io.BytesIO(b'{"label": "Moderate"}')},
        {"Body": io.BytesIO(b'not-json')},
    ],
)
async def test_sagemaker_predictor_falls_back_for_invalid_responses(response):
    fallback = RecordingFallback()
    predictor = SageMakerPredictor(endpoint_name="endpoint", runtime_client=RuntimeClient(response), fallback=fallback)

    prediction = await predictor.predict(b"jpeg", {"station_aqi": 120})

    assert prediction.source == "station_stub"
    assert prediction.aqi == 88
    assert fallback.calls == [(b"jpeg", {"station_aqi": 120})]


@pytest.mark.asyncio
async def test_sagemaker_predictor_falls_back_on_runtime_error_and_missing_endpoint():
    fallback = RecordingFallback()
    failed_predictor = SageMakerPredictor(
        endpoint_name="endpoint",
        runtime_client=RuntimeClient(error=TimeoutError("timed out")),
        fallback=fallback,
    )

    failed_prediction = await failed_predictor.predict(b"jpeg", {})
    missing_endpoint_prediction = await SageMakerPredictor(endpoint_name="", fallback=fallback).predict(b"jpeg2", {})

    assert failed_prediction.source == "station_stub"
    assert missing_endpoint_prediction.source == "station_stub"
    assert fallback.calls == [(b"jpeg", {}), (b"jpeg2", {})]


def test_probability_validation_rejects_non_sequence_and_non_finite_values():
    with pytest.raises(ValueError, match="must be a list"):
        _extract_probabilities({"probs": "not-a-list"})
    with pytest.raises(ValueError, match="finite"):
        _extract_probabilities({"probs": [1, float("inf"), 0, 0, 0, 0]})


def test_get_predictor_factory(monkeypatch):
    monkeypatch.setenv("MODEL_MODE", "stub")
    p1 = get_predictor()
    assert isinstance(p1, StubPredictor)

    monkeypatch.setenv("MODEL_MODE", "sagemaker")
    p2 = get_predictor()
    assert isinstance(p2, SageMakerPredictor)

    p3 = get_predictor("stub")
    assert isinstance(p3, StubPredictor)

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "layers", "common","common"))

from common.predictor import StubPredictor, SageMakerPredictor, get_predictor, Prediction


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


@pytest.mark.asyncio
async def test_sagemaker_predictor_stub():
    predictor = SageMakerPredictor()
    with pytest.raises(NotImplementedError):
        await predictor.predict(b"", {})


def test_get_predictor_factory(monkeypatch):
    monkeypatch.setenv("MODEL_MODE", "stub")
    p1 = get_predictor()
    assert isinstance(p1, StubPredictor)

    monkeypatch.setenv("MODEL_MODE", "sagemaker")
    p2 = get_predictor()
    assert isinstance(p2, SageMakerPredictor)

    p3 = get_predictor("stub")
    assert isinstance(p3, StubPredictor)

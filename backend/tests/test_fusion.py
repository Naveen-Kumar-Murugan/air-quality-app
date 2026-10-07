import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "layers", "common"))

from common.fusion import fuse_predictions
from common.predictor import Prediction


def test_fuse_predictions_no_station():
    model_pred = Prediction(aqi=80, category="Moderate", confidence=0.8, source="model")
    res = fuse_predictions(station=None, model_pred=model_pred, distance_km=None)
    assert res["aqi"] == 80
    assert res["category"] == "Moderate"
    assert res["confidence"] == 0.4
    assert res["source"] == "model"
    assert res["station"] is None


def test_fuse_predictions_with_station_decay():
    station = {"id": "st1", "aqi": 120}
    model_pred = Prediction(aqi=80, category="Moderate", confidence=0.8, source="station_stub")

    res_close = fuse_predictions(station=station, model_pred=model_pred, distance_km=0.0)
    assert res_close["aqi"] == 120

    res_far = fuse_predictions(station=station, model_pred=model_pred, distance_km=15.0)
    assert res_far["aqi"] < 120
    assert res_far["aqi"] > 80


def test_fuse_predictions_gps_and_source_weights():
    model_pred = Prediction(aqi=50, category="Good", confidence=1.0, source="model")
    res1 = fuse_predictions(station=None, model_pred=model_pred, distance_km=None, gps_accuracy_m=10.0)
    assert res1["scan_weight"] == round(1.0 * 0.5 * 1.0, 3)

    res2 = fuse_predictions(station=None, model_pred=model_pred, distance_km=None, gps_accuracy_m=70.0)
    assert res2["scan_weight"] < res1["scan_weight"]

    stub_pred = Prediction(aqi=50, category="Good", confidence=1.0, source="station_stub")
    res3 = fuse_predictions(station=None, model_pred=stub_pred, distance_km=None, gps_accuracy_m=10.0)
    assert res3["scan_weight"] == round(0.8 * 0.5 * 1.0, 3)

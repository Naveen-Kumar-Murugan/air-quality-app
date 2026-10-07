from __future__ import annotations

import math
from common.aqi import aqi_to_category
from common.predictor import Prediction


def fuse_predictions(
    station: dict | None,
    model_pred: Prediction,
    distance_km: float | None,
    image_quality: float = 1.0,
    gps_accuracy_m: float = 10.0,
) -> dict:
    if station is not None and distance_km is not None:
        decay = math.exp(-distance_km / 12.0)
        w_station = max(0.3, min(1.0, decay))
        w_model = 1.0 - w_station
        station_aqi = float(station.get("aqi", 0))
    else:
        w_station = 0.0
        w_model = 1.0
        station_aqi = 0.0

    raw_aqi = w_model * model_pred.aqi + w_station * station_aqi
    final_aqi = max(0, min(500, round(raw_aqi)))
    category = aqi_to_category(final_aqi)

    raw_conf = model_pred.confidence * (0.5 + 0.5 * w_station) * image_quality
    confidence = min(1.0, max(0.1, raw_conf))

    if gps_accuracy_m <= 20.0:
        gps_factor = 1.0
    else:
        gps_factor = max(0.2, 1.0 - (gps_accuracy_m - 20.0) / 100.0)

    src_factor = 1.0 if model_pred.source in ("model", "sagemaker") else 0.8
    scan_weight = src_factor * confidence * gps_factor

    return {
        "aqi": final_aqi,
        "category": category,
        "confidence": round(confidence, 2),
        "source": model_pred.source,
        "scan_weight": round(scan_weight, 3),
        "station": station,
    }

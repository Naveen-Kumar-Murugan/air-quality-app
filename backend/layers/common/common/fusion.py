from __future__ import annotations

import math
from .aqi import aqi_to_category
from .predictor import Prediction
from .util import get_logger

logger = get_logger(__name__)


def fuse_predictions(
    station: dict | None,
    model_pred: Prediction,
    distance_km: float | None,
    image_quality: float = 1.0,
    gps_accuracy_m: float = 10.0,
) -> dict:
    logger.info("Fusing predictions", extra={"has_station": station is not None,"distance_km": distance_km,"model_aqi": model_pred.aqi,"image_quality": image_quality,"gps_accuracy_m": gps_accuracy_m})
    
    if station is not None and distance_km is not None:
        decay = math.exp(-distance_km / 12.0)
        w_station = max(0.3, min(1.0, decay))
        w_model = 1.0 - w_station
        station_aqi = float(station.get("aqi", 0))
        logger.debug("Station-based fusion", extra={"w_station": w_station, "w_model": w_model, "station_aqi": station_aqi, "decay": decay})
    else:
        w_station = 0.0
        w_model = 1.0
        station_aqi = 0.0
        logger.debug("Model-only fusion (no station)")

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
    logger.info("Fusion complete", extra={"final_aqi": final_aqi, "category": category, "confidence": round(confidence, 2), "scan_weight": round(scan_weight, 3), "source": model_pred.source})

    return {
        "aqi": final_aqi,
        "category": category,
        "confidence": round(confidence, 2),
        "source": model_pred.source,
        "scan_weight": round(scan_weight, 3),
        "station": station,
    }

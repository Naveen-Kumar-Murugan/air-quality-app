"""GeoCells decay math: weighted running average with exponential time-decay.

Half-life default: 3 hours — after 3 h an observation carries half its
original weight.  See `03_data_modelling_and_geohash.md` section 4.2.
"""

from __future__ import annotations

from datetime import datetime


def compute_decay_factor(
    time_delta_hours: float,
    half_life_hours: float = 3.0,
) -> float:
    """Return the decay multiplier: ``0.5 ** (time_delta / half_life)``."""
    if time_delta_hours <= 0:
        return 1.0
    return 0.5 ** (time_delta_hours / half_life_hours)


def update_cell(
    old_sumWx: float,
    old_wSum: float,
    old_lastTs: str,
    new_aqi: float,
    new_weight: float,
    new_ts: str,
) -> dict:
    """Compute updated cell aggregates after a new scan.

    Parameters
    ----------
    old_sumWx : float
        Previous decayed weighted AQI sum.
    old_wSum : float
        Previous decayed sum of weights.
    old_lastTs : str
        ISO-8601 timestamp of the previous update.
    new_aqi : float
        AQI value from the new scan.
    new_weight : float
        Weight of the new scan (srcFactor × confidence × gpsFactor).
    new_ts : str
        ISO-8601 timestamp of the new scan.

    Returns
    -------
    dict
        ``{"sumWx": float, "wSum": float, "aqi": float, "lastTs": str}``
    """
    if old_wSum == 0:
        # First scan in this cell
        return {
            "sumWx": new_weight * new_aqi,
            "wSum": new_weight,
            "aqi": new_aqi,
            "lastTs": new_ts,
        }

    # Time delta in hours between old and new timestamps
    old_dt = datetime.fromisoformat(old_lastTs.replace("Z", "+00:00"))
    new_dt = datetime.fromisoformat(new_ts.replace("Z", "+00:00"))
    delta_hours = max((new_dt - old_dt).total_seconds() / 3600.0, 0.0)

    f = compute_decay_factor(delta_hours)
    new_wSum = old_wSum * f + new_weight
    new_sumWx = old_sumWx * f + new_weight * new_aqi
    computed_aqi = new_sumWx / new_wSum if new_wSum > 0 else 0.0

    return {
        "sumWx": new_sumWx,
        "wSum": new_wSum,
        "aqi": computed_aqi,
        "lastTs": new_ts,
    }


def effective_weight(
    wSum: float,
    age_hours: float,
    half_life_hours: float = 3.0,
) -> float:
    """Return the time-decayed effective weight of a cell.

    Used to judge staleness: if ``effective_weight < 0.05`` treat as no data.
    """
    return wSum * compute_decay_factor(age_hours, half_life_hours)


def blend_with_station(
    cell_aqi: float,
    cell_eff_weight: float,
    station_aqi: float,
    k: float = 0.5,
) -> float:
    """Blend a cell AQI with the nearest station reading.

    ``blended = (effW × cellAqi + K × stationAqi) / (effW + K)``

    This prevents thin crowd-sourced data from dominating when a reliable
    station is nearby.
    """
    total = cell_eff_weight + k
    if total == 0:
        return station_aqi
    return (cell_eff_weight * cell_aqi + k * station_aqi) / total

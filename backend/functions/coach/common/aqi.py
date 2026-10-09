"""EPA 2024 PM2.5 → US AQI conversion and category mapping."""

from __future__ import annotations

# EPA 2024 revised PM2.5 breakpoints.
# Each tuple: (pm25_low, pm25_high, aqi_low, aqi_high)
_BREAKPOINTS: list[tuple[float, float, int, int]] = [
    (0.0, 9.0, 0, 50),
    (9.1, 35.4, 51, 100),
    (35.5, 55.4, 101, 150),
    (55.5, 125.4, 151, 200),
    (125.5, 225.4, 201, 300),
    (225.5, 500.4, 301, 500),
]

# Model class midpoints used to convert class probabilities → expected AQI.
CLASS_MIDPOINTS: list[int] = [25, 75, 125, 175, 250, 400]


def pm25_to_aqi(pm25: float) -> int:
    """Convert a PM2.5 concentration (µg/m³) to a US AQI value (0-500).

    Uses the 2024 EPA breakpoint table for PM2.5.
    """
    if pm25 < 0:
        return 0

    for bp_lo, bp_hi, aqi_lo, aqi_hi in _BREAKPOINTS:
        if pm25 <= bp_hi:
            aqi = ((aqi_hi - aqi_lo) / (bp_hi - bp_lo)) * (pm25 - bp_lo) + aqi_lo
            return round(aqi)

    # Beyond the highest breakpoint — cap at 500
    return 500


def aqi_to_category(aqi: int) -> str:
    """Map a US AQI value to its category label."""
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Moderate"
    if aqi <= 150:
        return "Unhealthy for Sensitive Groups"
    if aqi <= 200:
        return "Unhealthy"
    if aqi <= 300:
        return "Very Unhealthy"
    return "Hazardous"

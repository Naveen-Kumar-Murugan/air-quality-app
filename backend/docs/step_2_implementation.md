# Step 2: Common Layer Implementation

Phase 1, Step 2 — shared Python modules in the `CommonLayer` Lambda layer.

## Modules Added

### `layers/common/python/common/geohash.py`
Pure-Python geohash encoder/decoder (~110 lines, zero dependencies).

| Function | Purpose |
|---|---|
| `encode(lat, lon, precision)` | Lat/lon → geohash string |
| `decode_bbox(geohash)` | Geohash → `(min_lat, min_lon, max_lat, max_lon)` |
| `neighbors(geohash)` | 8 surrounding cells at the same precision |
| `cells_covering(min_lat, min_lon, max_lat, max_lon, precision)` | Set of geohashes covering a bounding box |

Supports precisions 4–7 per the data-modelling doc. Tested against the reference vectors `encode(42.6, -5.6, 5) == "ezs42"` and `encode(57.64911, 10.40744, 11) == "u4pruydqqvj"`.

### `layers/common/python/common/aqi.py`
EPA 2024 PM2.5 → US AQI conversion (~50 lines).

| Function / Constant | Purpose |
|---|---|
| `pm25_to_aqi(pm25)` | PM2.5 µg/m³ → AQI (0–500) using 2024 breakpoints |
| `aqi_to_category(aqi)` | AQI integer → category string (Good … Hazardous) |
| `CLASS_MIDPOINTS` | `[25, 75, 125, 175, 250, 400]` for model probability → AQI |

### `layers/common/python/common/cells.py`
Exponential-decay running-average math for GeoCells (~90 lines).

| Function | Purpose |
|---|---|
| `compute_decay_factor(delta_h, half_life)` | `0.5^(Δt/H)` decay multiplier |
| `update_cell(...)` | Apply a new scan to a cell's aggregates |
| `effective_weight(wSum, age_h, half_life)` | Time-decayed confidence for staleness checks |
| `blend_with_station(cell_aqi, eff_w, station_aqi, k)` | Blend crowd-sourced AQI with nearest official station |

Default half-life is 3 hours per the data-modelling spec.

### `layers/common/python/common/util.py`
Shared helpers (~100 lines).

| Function | Purpose |
|---|---|
| `json_response(status, body)` | API Gateway v2 Lambda proxy response |
| `error_response(code, message, status)` | Standardised error envelope |
| `decimal_to_float(obj)` | Recursive `Decimal` → `float`/`int` for JSON |
| `float_to_decimal(obj)` | Recursive `float` → `Decimal` for DynamoDB |
| `generate_ulid()` | 26-char Crockford base32 time-sortable ID |
| `get_logger(name)` | JSON-structured logger for CloudWatch |

## Test Files

| File | Covers |
|---|---|
| `tests/test_geohash.py` | encode, decode_bbox, neighbors, cells_covering |
| `tests/test_aqi.py` | All breakpoint boundaries, categories, midpoints |
| `tests/test_cells.py` | Decay math, cell updates, blending |
| `tests/test_util.py` | Response builders, Decimal round-trips, ULID format/uniqueness |

## Directory Structure

```
backend/
  layers/
    common/
      python/
        common/
          __init__.py
          geohash.py
          aqi.py
          cells.py
          util.py
  tests/
    test_geohash.py
    test_aqi.py
    test_cells.py
    test_util.py
```

## Verification

All 8 Python files pass `python3 -m py_compile` with no errors.

"""Pure-Python geohash encoder / decoder.

No external dependencies — vendored to avoid native-build issues in Lambda.
Reference vectors:
    encode(42.6, -5.6, 5)          == "ezs42"
    encode(57.64911, 10.40744, 11) == "u4pruydqqvj"
"""

from __future__ import annotations

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
_DECODE_MAP = {c: i for i, c in enumerate(_BASE32)}

# Approximate cell size in degrees for each precision (lat, lon).
# Used by cells_covering to step across a bounding box.
CELL_DEG: dict[int, tuple[float, float]] = {
    4: (0.176, 0.352),
    5: (0.0439, 0.0439),
    6: (0.0055, 0.0110),
    7: (0.00137, 0.00137),
}


def encode(lat: float, lon: float, precision: int = 7) -> str:
    """Encode *lat* / *lon* to a geohash string of length *precision*."""
    lat_range = (-90.0, 90.0)
    lon_range = (-180.0, 180.0)
    geohash: list[str] = []
    bits = 0
    char_idx = 0
    is_lon = True

    while len(geohash) < precision:
        if is_lon:
            mid = (lon_range[0] + lon_range[1]) / 2
            if lon >= mid:
                char_idx = (char_idx << 1) | 1
                lon_range = (mid, lon_range[1])
            else:
                char_idx = char_idx << 1
                lon_range = (lon_range[0], mid)
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat >= mid:
                char_idx = (char_idx << 1) | 1
                lat_range = (mid, lat_range[1])
            else:
                char_idx = char_idx << 1
                lat_range = (lat_range[0], mid)
        is_lon = not is_lon
        bits += 1
        if bits == 5:
            geohash.append(_BASE32[char_idx])
            bits = 0
            char_idx = 0

    return "".join(geohash)


def decode_bbox(geohash: str) -> tuple[float, float, float, float]:
    """Decode a geohash into its bounding box (min_lat, min_lon, max_lat, max_lon)."""
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]
    is_lon = True

    for ch in geohash:
        val = _DECODE_MAP[ch]
        for bit in (16, 8, 4, 2, 1):
            if is_lon:
                mid = (lon_range[0] + lon_range[1]) / 2
                if val & bit:
                    lon_range[0] = mid
                else:
                    lon_range[1] = mid
            else:
                mid = (lat_range[0] + lat_range[1]) / 2
                if val & bit:
                    lat_range[0] = mid
                else:
                    lat_range[1] = mid
            is_lon = not is_lon

    return (lat_range[0], lon_range[0], lat_range[1], lon_range[1])


def neighbors(geohash: str) -> list[str]:
    """Return the 8 neighbouring geohash cells (same precision)."""
    min_lat, min_lon, max_lat, max_lon = decode_bbox(geohash)
    lat_centre = (min_lat + max_lat) / 2
    lon_centre = (min_lon + max_lon) / 2
    lat_step = max_lat - min_lat
    lon_step = max_lon - min_lon
    precision = len(geohash)

    result: list[str] = []
    for dlat in (-lat_step, 0, lat_step):
        for dlon in (-lon_step, 0, lon_step):
            if dlat == 0 and dlon == 0:
                continue
            neighbour = encode(lat_centre + dlat, lon_centre + dlon, precision)
            result.append(neighbour)
    return result


def cells_covering(
    min_lat: float,
    min_lon: float,
    max_lat: float,
    max_lon: float,
    precision: int = 5,
) -> set[str]:
    """Return the set of geohash cells that cover the given bounding box."""
    if precision not in CELL_DEG:
        raise ValueError(f"Unsupported precision {precision}; use one of {sorted(CELL_DEG)}")

    dlat, dlon = CELL_DEG[precision]

    def _frange(start: float, stop: float, step: float) -> list[float]:
        vals: list[float] = []
        v = start
        while v <= stop:
            vals.append(v)
            v += step
        if vals and vals[-1] < stop:
            vals.append(stop)
        return vals

    lats = _frange(min_lat, max_lat, dlat)
    lons = _frange(min_lon, max_lon, dlon)
    return {encode(la, lo, precision) for la in lats for lo in lons}

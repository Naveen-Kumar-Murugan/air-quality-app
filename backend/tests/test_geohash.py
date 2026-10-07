"""Tests for the pure-Python geohash module."""

import sys
import os

# Add the common layer to the path so imports work outside Lambda
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "layers", "common","common"))

from common.geohash import encode, decode_bbox, neighbors, cells_covering


def test_encode_known_vectors():
    """Test against documented reference values."""
    assert encode(42.6, -5.6, 5) == "ezs42"
    assert encode(57.64911, 10.40744, 11) == "u4pruydqqvj"


def test_encode_default_precision():
    """Default precision is 7."""
    gh = encode(12.0, 77.0)
    assert len(gh) == 7


def test_neighbors_coverage():
    """Neighbors should return 8 cells, excluding center."""
    center = "u4pru"
    n = neighbors(center)
    assert len(n) == 8
    assert center not in n
    # All neighbors should have same length as center
    assert all(len(nb) == len(center) for nb in n)


def test_neighbors_surround_center():
    """Each neighbour's decoded centre should differ from the
    original centre by roughly one cell width."""
    center = "tdr1w"
    n = neighbors(center)
    c_min_lat, c_min_lon, c_max_lat, c_max_lon = decode_bbox(center)
    c_lat = (c_min_lat + c_max_lat) / 2
    c_lon = (c_min_lon + c_max_lon) / 2
    lat_step = c_max_lat - c_min_lat
    lon_step = c_max_lon - c_min_lon

    for nb in n:
        nb_min_lat, nb_min_lon, nb_max_lat, nb_max_lon = decode_bbox(nb)
        nb_lat = (nb_min_lat + nb_max_lat) / 2
        nb_lon = (nb_min_lon + nb_max_lon) / 2
        dlat = abs(nb_lat - c_lat)
        dlon = abs(nb_lon - c_lon)
        # Each should be within ~1.5 cell widths
        assert dlat < lat_step * 1.5
        assert dlon < lon_step * 1.5


def test_cells_covering():
    """Small bbox should return a handful of precision-5 cells."""
    cells = cells_covering(12.0, 77.0, 12.1, 77.1, 5)
    assert len(cells) > 0
    assert len(cells) < 20  # Sanity check — 0.1° shouldn't need many cells
    assert all(len(c) == 5 for c in cells)


def test_cells_covering_single_point():
    """A zero-area bbox should still return at least one cell."""
    cells = cells_covering(12.0, 77.0, 12.0, 77.0, 5)
    assert len(cells) >= 1


def test_decode_bbox():
    """Decode should invert encode within cell bounds."""
    gh = encode(42.6, -5.6, 7)
    min_lat, min_lon, max_lat, max_lon = decode_bbox(gh)
    assert min_lat <= 42.6 <= max_lat
    assert min_lon <= -5.6 <= max_lon


def test_decode_bbox_precision_5():
    """Bounding box at precision 5 should be reasonable."""
    gh = encode(12.0, 77.0, 5)
    min_lat, min_lon, max_lat, max_lon = decode_bbox(gh)
    assert max_lat - min_lat > 0
    assert max_lon - min_lon > 0
    assert min_lat <= 12.0 <= max_lat
    assert min_lon <= 77.0 <= max_lon


def test_encode_negative_coords():
    """Encoding should work for negative coordinates."""
    gh = encode(-33.8688, 151.2093, 7)  # Sydney, Australia
    assert len(gh) == 7
    min_lat, min_lon, max_lat, max_lon = decode_bbox(gh)
    assert min_lat <= -33.8688 <= max_lat
    assert min_lon <= 151.2093 <= max_lon


def test_cells_covering_unsupported_precision():
    """Unsupported precision should raise ValueError."""
    try:
        cells_covering(12.0, 77.0, 12.1, 77.1, 3)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

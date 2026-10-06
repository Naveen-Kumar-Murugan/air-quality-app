"""Tests for GeoCells decay math."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "layers", "common", "python"))

from datetime import datetime, timedelta, timezone

from common.cells import (
    compute_decay_factor,
    update_cell,
    effective_weight,
    blend_with_station,
)


def test_decay_zero_hours():
    """No time elapsed → no decay."""
    factor = compute_decay_factor(0.0)
    assert factor == 1.0


def test_decay_half_life():
    """After 3 hours (one half-life), weight should be 0.5."""
    factor = compute_decay_factor(3.0, half_life_hours=3.0)
    assert abs(factor - 0.5) < 0.01


def test_decay_two_half_lives():
    """After 6 hours (two half-lives), weight should be 0.25."""
    factor = compute_decay_factor(6.0, half_life_hours=3.0)
    assert abs(factor - 0.25) < 0.01


def test_decay_negative_time():
    """Negative time delta returns 1.0 (no decay)."""
    factor = compute_decay_factor(-1.0)
    assert factor == 1.0


def test_update_cell_first_scan():
    """First scan in a cell: wSum = weight, sumWx = weight × aqi."""
    now = datetime.now(timezone.utc).isoformat()
    result = update_cell(0.0, 0.0, now, new_aqi=100.0, new_weight=1.0, new_ts=now)

    assert result["wSum"] == 1.0
    assert result["sumWx"] == 100.0
    assert result["aqi"] == 100.0


def test_update_cell_second_scan_no_delay():
    """Two scans at the same time should average equally."""
    ts = "2026-10-05T08:00:00+00:00"
    result = update_cell(100.0, 1.0, ts, new_aqi=200.0, new_weight=1.0, new_ts=ts)

    # No decay, so: sumWx = 100 + 200 = 300, wSum = 1 + 1 = 2, aqi = 150
    assert abs(result["wSum"] - 2.0) < 0.01
    assert abs(result["sumWx"] - 300.0) < 0.01
    assert abs(result["aqi"] - 150.0) < 0.1


def test_update_cell_with_decay():
    """Second scan 3 hours later should show decay of old data."""
    ts1 = "2026-10-05T08:00:00+00:00"
    ts2 = "2026-10-05T11:00:00+00:00"  # 3h later
    result = update_cell(100.0, 1.0, ts1, new_aqi=200.0, new_weight=1.0, new_ts=ts2)

    # After 3h: old decays by 0.5
    # wSum = 1.0 * 0.5 + 1.0 = 1.5
    # sumWx = 100.0 * 0.5 + 200.0 = 250.0
    # aqi = 250 / 1.5 ≈ 166.67
    assert abs(result["wSum"] - 1.5) < 0.01
    assert abs(result["sumWx"] - 250.0) < 0.01
    assert abs(result["aqi"] - 166.67) < 0.1


def test_effective_weight_staleness():
    """wSum=1.0, age=6h (2 half-lives) → effW ≈ 0.25."""
    eff = effective_weight(1.0, age_hours=6.0, half_life_hours=3.0)
    assert abs(eff - 0.25) < 0.01


def test_effective_weight_fresh():
    """Fresh data (age=0) should have full weight."""
    eff = effective_weight(2.0, age_hours=0.0)
    assert eff == 2.0


def test_blend_with_station():
    """Blend should weight by effective weight."""
    # High confidence cell (effW=1.0) and station (k=0.5)
    blended = blend_with_station(cell_aqi=100, cell_eff_weight=1.0, station_aqi=150, k=0.5)
    # (1.0 × 100 + 0.5 × 150) / (1.0 + 0.5) = 175 / 1.5 ≈ 116.67
    assert abs(blended - 116.67) < 0.1

    # Low confidence cell (effW=0.1) → station dominates
    blended = blend_with_station(cell_aqi=100, cell_eff_weight=0.1, station_aqi=150, k=0.5)
    # (0.1 × 100 + 0.5 × 150) / (0.1 + 0.5) = 85 / 0.6 ≈ 141.67
    assert abs(blended - 141.67) < 0.1


def test_blend_zero_weight():
    """If cell has zero effective weight, station dominates entirely."""
    blended = blend_with_station(cell_aqi=50, cell_eff_weight=0.0, station_aqi=120, k=0.5)
    assert abs(blended - 120.0) < 0.1

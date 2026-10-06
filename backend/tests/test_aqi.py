"""Tests for the EPA 2024 PM2.5 → AQI conversion module."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "layers", "common", "python"))

from common.aqi import pm25_to_aqi, aqi_to_category, CLASS_MIDPOINTS


def test_pm25_breakpoints():
    """Test EPA 2024 breakpoints exactly."""
    assert pm25_to_aqi(0.0) == 0
    assert pm25_to_aqi(9.0) == 50
    assert pm25_to_aqi(9.1) == 51
    assert pm25_to_aqi(35.4) == 100
    assert pm25_to_aqi(35.5) == 101
    assert pm25_to_aqi(55.4) == 150
    assert pm25_to_aqi(55.5) == 151
    assert pm25_to_aqi(125.4) == 200
    assert pm25_to_aqi(125.5) == 201


def test_pm25_mid_range():
    """Values within a bracket should be linearly interpolated."""
    aqi = pm25_to_aqi(4.5)  # midpoint of 0-9.0 range
    assert 0 < aqi < 50
    assert aqi == 25


def test_pm25_above_max():
    """Values above 500.4 µg/m³ should cap at 500."""
    assert pm25_to_aqi(600.0) == 500
    assert pm25_to_aqi(1000.0) == 500


def test_pm25_negative():
    """Negative PM2.5 should return 0."""
    assert pm25_to_aqi(-1.0) == 0


def test_category_mapping():
    """Test AQI to category conversion."""
    assert aqi_to_category(0) == "Good"
    assert aqi_to_category(25) == "Good"
    assert aqi_to_category(50) == "Good"
    assert aqi_to_category(51) == "Moderate"
    assert aqi_to_category(100) == "Moderate"
    assert aqi_to_category(101) == "Unhealthy for Sensitive Groups"
    assert aqi_to_category(150) == "Unhealthy for Sensitive Groups"
    assert aqi_to_category(151) == "Unhealthy"
    assert aqi_to_category(200) == "Unhealthy"
    assert aqi_to_category(201) == "Very Unhealthy"
    assert aqi_to_category(300) == "Very Unhealthy"
    assert aqi_to_category(301) == "Hazardous"
    assert aqi_to_category(500) == "Hazardous"


def test_class_midpoints():
    """Midpoints used for model probability to AQI conversion."""
    assert CLASS_MIDPOINTS == [25, 75, 125, 175, 250, 400]
    assert len(CLASS_MIDPOINTS) == 6

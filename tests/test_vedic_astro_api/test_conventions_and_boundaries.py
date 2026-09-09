"""Conventions, Timezone Transitions, and Hard Ephemeris Boundary Stress Tests.

Validates:
1. Hard JPL DE421 ephemeris boundaries (1899 and 2054 return structured 422 error).
2. IANA Timezone DST boundaries (US Spring Forward, US Fall Back, London BST).
3. Leap Year (Feb 29) and Midnight boundaries (23:59:59 -> 00:00:00).
4. Classical 5th-weekday-lord rule for Night Choghadiya start.
5. Sunrise conventions: Hindu (0° geometric center) vs Astronomical (-50' refracted).
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from vedic_astro_api.calculations.panchang import calculate_panchang, NIGHT_CHOGHADIYA_START, CHOGHADIYA_CYCLE
from vedic_astro_api.core.ephemeris import (
    OutOfEphemerisRangeError,
    datetime_to_time,
    KERNEL_MIN_JD,
    KERNEL_MAX_JD,
    KERNEL_MIN_DATE,
    KERNEL_MAX_DATE,
)
from vedic_astro_api.core.ayanamsha import compute_ayanamsha_deg
from vedic_astro_api.api.app import app

client = TestClient(app)


# ===========================================================================
# 1. HARD EPHEMERIS BOUNDARY TESTS
# ===========================================================================

def test_out_of_range_ephemeris_raises_structured_error():
    """Asserts dates outside supported query range raise OutOfEphemerisRangeError and return 422 JSON."""
    # Pre-kernel (1899-01-01)
    with pytest.raises(OutOfEphemerisRangeError) as exc_info:
        calculate_panchang(datetime(1899, 1, 1), 28.6139, 77.2090)
    assert f"Supported query range is {KERNEL_MIN_DATE.isoformat()} to {KERNEL_MAX_DATE.isoformat()}" in str(exc_info.value)

    # Post-kernel (2054-06-01)
    with pytest.raises(OutOfEphemerisRangeError) as exc_info:
        calculate_panchang(datetime(2054, 6, 1), 28.6139, 77.2090)
    assert f"Supported query range is {KERNEL_MIN_DATE.isoformat()} to {KERNEL_MAX_DATE.isoformat()}" in str(exc_info.value)


def test_api_out_of_range_returns_http_422():
    """Asserts FastAPI returns HTTP 422 with structured JSON for out-of-range dates."""
    resp = client.get("/v1/vedic/basic_panchang", params={
        "year": 1850, "month": 6, "day": 1, "hour": 12, "min": 0, "sec": 0,
        "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
    })
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"] == "DateOutOfRange"
    assert "supported_query_range" in data
    assert "supported_range" in data


# ===========================================================================
# 2. TIMEZONE & DST STRESS TESTS
# ===========================================================================

def test_us_spring_forward_dst_transition():
    """Asserts New York Spring Forward DST boundary (2024-03-10) calculates without crashing."""
    # 2024-03-10 01:30 (EST -5)
    p_before = calculate_panchang(datetime(2024, 3, 10, 1, 30), 40.7128, -74.0060, tz_str="America/New_York")
    assert p_before.tithi_number >= 1

    # 2024-03-10 03:30 (EDT -4, post-jump)
    p_after = calculate_panchang(datetime(2024, 3, 10, 3, 30), 40.7128, -74.0060, tz_str="America/New_York")
    assert p_after.tithi_number >= 1


def test_us_fall_back_dst_transition():
    """Asserts New York Fall Back DST boundary (2024-11-03) handles repeated hour correctly."""
    p_fall = calculate_panchang(datetime(2024, 11, 3, 1, 30), 40.7128, -74.0060, tz_str="America/New_York")
    assert p_fall.tithi_number >= 1
    assert p_fall.sunrise is not None


def test_london_bst_transition():
    """Asserts London GMT -> BST transition (2024-03-31) succeeds."""
    p_lon = calculate_panchang(datetime(2024, 3, 31, 2, 0), 51.5074, -0.1278, tz_str="Europe/London")
    assert p_lon.tithi_number >= 1


def test_leap_year_feb_29():
    """Asserts Feb 29 on leap year (2024-02-29) computes cleanly."""
    p_leap = calculate_panchang(datetime(2024, 2, 29, 12, 0), 28.6139, 77.2090, tz_str="Asia/Kolkata")
    assert p_leap.tithi_number >= 1
    assert "2024-02-29" in p_leap.sunrise


def test_midnight_boundary():
    """Asserts 23:59:59 to 00:00:00 transition handles cleanly."""
    p_eve = calculate_panchang(datetime(2026, 9, 9, 23, 59, 59), 28.6139, 77.2090, tz_str="Asia/Kolkata")
    p_morn = calculate_panchang(datetime(2026, 9, 10, 0, 0, 0), 28.6139, 77.2090, tz_str="Asia/Kolkata")
    assert p_eve.tithi_number >= 1
    assert p_morn.tithi_number >= 1


# ===========================================================================
# 3. NIGHT CHOGHADIYA 5TH-WEEKDAY LORD VALIDATION
# ===========================================================================

def test_night_choghadiya_classical_starting_lords():
    """Asserts Night Choghadiya start lord strictly follows the 5th weekday rule for all 7 days."""
    expected_starts = {
        0: "Shubh",  # Sun night: Jupiter / Thursday
        1: "Char",   # Mon night: Venus / Friday
        2: "Kaal",   # Tue night: Saturn / Saturday
        3: "Udveg",  # Wed night: Sun / Sunday
        4: "Amrit",  # Thu night: Moon / Monday
        5: "Rog",    # Fri night: Mars / Tuesday
        6: "Labh",   # Sat night: Mercury / Wednesday
    }

    for weekday_idx, expected_chog in expected_starts.items():
        actual_idx = NIGHT_CHOGHADIYA_START[weekday_idx]
        actual_chog = CHOGHADIYA_CYCLE[actual_idx]
        assert actual_chog == expected_chog, f"Weekday {weekday_idx} night expected {expected_chog}, got {actual_chog}"


# ===========================================================================
# 4. DUAL SUNRISE CONVENTIONS (HINDU VS ASTRONOMICAL)
# ===========================================================================

def test_dual_sunrise_conventions_and_time_delta():
    """Asserts Hindu sunrise (0° geometric center) runs ~3.5-4 min later than Astronomical (-50')."""
    dt = datetime(2026, 9, 9, 12, 0, 0)
    
    # Hindu convention (middle limb, no refraction)
    p_hindu = calculate_panchang(dt, 28.6139, 77.2090, tz_str="Asia/Kolkata", sunrise_convention="hindu")
    
    # Astronomical convention (-50' upper limb refracted)
    p_astro = calculate_panchang(dt, 28.6139, 77.2090, tz_str="Asia/Kolkata", sunrise_convention="astronomical")

    # In Delhi on Sept 9, 2026:
    # Astronomical sunrise is ~06:03:04 IST
    # Hindu sunrise is ~06:06:53 IST (approx 3m 49s later)
    assert p_astro.sunrise == "2026-09-09 06:03:04"
    assert p_hindu.sunrise == "2026-09-09 06:06:53"

    # Both responses expose dual sunrises
    assert p_astro.sunrise_astronomical == "2026-09-09 06:03:04"
    assert p_astro.sunrise_hindu == "2026-09-09 06:06:53"
    assert p_hindu.sunrise_astronomical == "2026-09-09 06:03:04"
    assert p_hindu.sunrise_hindu == "2026-09-09 06:06:53"


# ===========================================================================
# 5. SCHEMA CONVENTIONS & VALIDATION STRESS TESTS
# ===========================================================================

def test_schema_rejects_tzone_with_http_422():
    """Asserts passing deprecated 'tzone' returns HTTP 422 with explicit message."""
    resp = client.get("/v1/vedic/basic_panchang", params={
        "year": 2026, "month": 9, "day": 9, "hour": 12, "min": 0, "sec": 0,
        "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata", "tzone": 5.5
    })
    assert resp.status_code == 422
    assert "tzone' is removed" in resp.text


def test_schema_rejects_fake_calendar_date_with_http_422():
    """Asserts impossible dates (e.g. Feb 30) return HTTP 422 instead of HTTP 500."""
    resp = client.get("/v1/vedic/basic_panchang", params={
        "year": 2026, "month": 2, "day": 30, "hour": 12, "min": 0, "sec": 0,
        "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
    })
    assert resp.status_code == 422
    assert "is not a real calendar date" in resp.text


def test_schema_rejects_unknown_iana_timezone_with_http_422():
    """Asserts invalid IANA timezone string returns HTTP 422."""
    resp = client.get("/v1/vedic/basic_panchang", params={
        "year": 2026, "month": 9, "day": 9, "hour": 12, "min": 0, "sec": 0,
        "lat": 28.6139, "lon": 77.2090, "timezone": "Mars/Olympus_Mons"
    })
    assert resp.status_code == 422
    assert "Unknown IANA timezone" in resp.text


def test_meta_conventions_echoed_in_response():
    """Asserts meta.conventions and exact JD/time metadata are echoed in response."""
    resp = client.get("/v1/vedic/basic_panchang", params={
        "year": 2026, "month": 9, "day": 9, "hour": 12, "minute": 0, "second": 0,
        "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata",
        "ayanamsha": "lahiri", "sunrise_convention": "astronomical"
    })
    assert resp.status_code == 200
    meta = resp.json()["meta"]
    assert meta["ephemeris"] == "DE421"
    assert "conventions" in meta
    conv = meta["conventions"]
    assert conv["ayanamsha"] == "lahiri"
    t_q = datetime_to_time(datetime(2026, 9, 9, 6, 30, tzinfo=timezone.utc))
    assert abs(conv["ayanamsha_deg"] - compute_ayanamsha_deg(t_q, "lahiri")) < 1e-4
    assert conv["sunrise"] == "astronomical"
    assert conv["hora"] == "indian_60min"
    assert conv["choghadiya_night_lord"] == "classical_v1"
    assert "jd_tt" in meta
    assert "jd_ut1" in meta
    assert "local" in meta
    assert "utc" in meta


def test_health_endpoint_exposes_ephemeris_bounds():
    """Asserts /health surfaces dynamically derived NASA JPL DE421 kernel bounds and probed query bounds."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "ephemeris_bounds" in data
    bounds = data["ephemeris_bounds"]
    assert "spk_segment_tdb" in bounds
    assert "supported_query_range" in bounds
    assert bounds["spk_segment_tdb"]["min_jd"] == KERNEL_MIN_JD
    assert bounds["spk_segment_tdb"]["max_jd"] == KERNEL_MAX_JD
    assert bounds["supported_query_range"]["start"] == KERNEL_MIN_DATE.isoformat()
    assert bounds["supported_query_range"]["end"] == KERNEL_MAX_DATE.isoformat()


def test_valid_edge_dates_1899_and_2053_succeed():
    """Asserts safe boundary edge dates succeed without error."""
    # First safe day: 1899-07-31
    resp_start = client.get("/v1/vedic/basic_panchang", params={
        "year": 1899, "month": 7, "day": 31, "hour": 12, "min": 0, "sec": 0,
        "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
    })
    assert resp_start.status_code == 200
    data_start = resp_start.json()
    assert data_start["tithi"]["name"] == "Krishna Dashami"

    # Last safe day: 2053-10-07
    resp_end = client.get("/v1/vedic/basic_panchang", params={
        "year": 2053, "month": 10, "day": 7, "hour": 12, "min": 0, "sec": 0,
        "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
    })
    assert resp_end.status_code == 200
    data_end = resp_end.json()
    assert data_end["tithi"]["name"] == "Krishna Ekadashi"

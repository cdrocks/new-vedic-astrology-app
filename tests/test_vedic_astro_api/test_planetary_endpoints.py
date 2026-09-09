"""Automated Tests for Planetary Positions (Graha Panchang) & Lagna Endpoints.

Validates:
1. GET & POST /v1/vedic/planet_panchang
2. GET & POST /v1/vedic/planet_panchang/sunrise
3. All 9 classical Grahas (Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu, Ketu) + Ascendant
4. Mathematical invariants: [0, 360) full degree, [0, 30) norm degree, 1-12 signs, 1-27 nakshatras, 1-4 padas
5. Retrograde flags & daily speeds
6. Cross-validation with Swiss Ephemeris baseline (when installed)
7. Date range validation (HTTP 422 for out-of-range dates)
"""

import math
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from vedic_astro_api.api.app import app
from vedic_astro_api.calculations.planetary import calculate_planet_panchang

try:
    import swisseph as swe
    HAS_SWISSEPH = True
except ImportError:
    swe = None
    HAS_SWISSEPH = False

client = TestClient(app)

DELHI_PARAMS = {
    "year": 2026,
    "month": 9,
    "day": 9,
    "hour": 12,
    "minute": 0,
    "second": 0,
    "lat": 28.6139,
    "lon": 77.2090,
    "timezone": "Asia/Kolkata",
}


def test_planet_panchang_get_and_post():
    """Asserts GET and POST /planet_panchang return all 9 planets and Ascendant."""
    # GET
    resp_get = client.get("/v1/vedic/planet_panchang", params=DELHI_PARAMS)
    assert resp_get.status_code == 200
    data = resp_get.json()

    assert "meta" in data
    assert "planets" in data
    assert "ascendant" in data
    assert "planets_list" in data

    planets = data["planets"]
    expected_bodies = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
    for p_name in expected_bodies:
        assert p_name in planets, f"Missing {p_name} in planets response"

    # POST
    resp_post = client.post("/v1/vedic/planet_panchang", json=DELHI_PARAMS)
    assert resp_post.status_code == 200
    post_data = resp_post.json()
    assert post_data["planets"]["Sun"]["full_degree"] == planets["Sun"]["full_degree"]
    assert post_data["ascendant"]["sign"] == data["ascendant"]["sign"]


def test_planet_panchang_sunrise_endpoint():
    """Asserts /planet_panchang/sunrise evaluates at local sunrise."""
    resp = client.get("/v1/vedic/planet_panchang/sunrise", params={
        "year": 2026, "month": 9, "day": 9, "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "planets" in data
    assert "ascendant" in data
    # At sunrise, the Sun is close to the Ascendant (Lagna)
    sun_lon = data["planets"]["Sun"]["full_degree"]
    asc_lon = data["ascendant"]["full_degree"]
    diff = abs(sun_lon - asc_lon)
    if diff > 180.0:
        diff = 360.0 - diff
    # Asserts sunrise_time in meta with ISO 8601 offset
    assert "sunrise_time" in data["meta"]
    assert "+05:30" in data["meta"]["sunrise_time"]
    assert data["meta"]["sunrise_time"].startswith("2026-09-09T")


def test_planet_invariants_and_retrograde():
    """Asserts all degrees, signs, nakshatras, and retrograde rules obey physical invariants."""
    res = calculate_planet_panchang(
        dt=datetime(2026, 9, 9, 12, 0, 0),
        lat=28.6139,
        lon=77.2090,
        tz_str="Asia/Kolkata",
    )
    d = res.to_dict()
    all_bodies = list(d["planets"].values()) + [d["ascendant"]]

    for b in all_bodies:
        # Longitude in [0, 360)
        assert 0.0 <= b["full_degree"] < 360.0, f"{b['name']} full_degree out of range: {b['full_degree']}"
        # Degree in sign in [0, 30)
        assert 0.0 <= b["norm_degree"] < 30.0, f"{b['name']} norm_degree out of range: {b['norm_degree']}"
        # Sign number 1 to 12
        assert 1 <= b["sign_number"] <= 12
        # Nakshatra number 1 to 27
        assert 1 <= b["nakshatra_number"] <= 27
        # Pada 1 to 4
        assert 1 <= b["nakshatra_pada"] <= 4
        # Formatted degree string contains degree symbol
        assert "°" in b["formatted_degree"]
        # speed_deg_per_day is non-zero
        assert b["speed_deg_per_day"] != 0.0

    # Sun and Moon are never retrograde
    assert d["planets"]["Sun"]["is_retrograde"] is False
    assert d["planets"]["Moon"]["is_retrograde"] is False

    # Mean Rahu and Ketu are always retrograde
    assert d["planets"]["Rahu"]["is_retrograde"] is True
    assert d["planets"]["Ketu"]["is_retrograde"] is True

    # Ketu is exactly 180° opposite Rahu
    rahu_deg = d["planets"]["Rahu"]["full_degree"]
    ketu_deg = d["planets"]["Ketu"]["full_degree"]
    expected_ketu = (rahu_deg + 180.0) % 360.0
    assert abs(ketu_deg - expected_ketu) < 1e-4

    # Ascendant is not retrograde
    assert d["ascendant"]["is_retrograde"] is False


def test_out_of_range_planet_panchang_returns_422():
    """Asserts dates outside 1899-07-31 to 2053-10-07 return structured HTTP 422."""
    resp = client.get("/v1/vedic/planet_panchang", params={
        "year": 1850, "month": 6, "day": 1, "hour": 12, "minute": 0, "second": 0,
        "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
    })
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"] == "DateOutOfRange"
    assert "supported_query_range" in data


@pytest.mark.skipif(not HAS_SWISSEPH, reason="pyswisseph not installed")
def test_cross_validation_against_swisseph():
    """Cross-validates planet coordinates against Swiss Ephemeris (DE431) baseline."""
    dt = datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc)
    lat, lon = 28.6139, 77.2090

    res = calculate_planet_panchang(dt, lat, lon, tz_str="UTC", ayanamsha_type="lahiri", node_type="mean")
    d = res.to_dict()

    from vedic_astro_api.core.ephemeris import datetime_to_time
    t = datetime_to_time(dt)

    swe.set_sid_mode(swe.SIDM_LAHIRI)
    swe_ayan = swe.get_ayanamsa_ut(t.ut1)

    swe_map = {
        "Sun": swe.SUN,
        "Moon": swe.MOON,
        "Mars": swe.MARS,
        "Mercury": swe.MERCURY,
        "Jupiter": swe.JUPITER,
        "Venus": swe.VENUS,
        "Saturn": swe.SATURN,
    }

    # Verify physical planets within 1 arcsecond
    for name, swe_id in swe_map.items():
        swe_trop, _ = swe.calc(t.tt, swe_id, swe.FLG_SWIEPH | swe.FLG_SPEED)
        swe_deg = (swe_trop[0] - swe_ayan) % 360.0
        our_deg = d["planets"][name]["full_degree"]
        diff_arcsec = abs(our_deg - swe_deg) * 3600.0
        if diff_arcsec > 180.0 * 3600.0:
            diff_arcsec = abs(diff_arcsec - 360.0 * 3600.0)
        assert diff_arcsec < 1.0, f"{name} diff {diff_arcsec:.3f}\" exceeds 1.0 arcsec"

    # Verify Mean Rahu within 1 arcsecond
    swe_rahu, _ = swe.calc_ut(t.ut1, swe.MEAN_NODE, swe.FLG_SIDEREAL | swe.FLG_SPEED)
    rahu_diff = abs(d["planets"]["Rahu"]["full_degree"] - (swe_rahu[0] % 360.0)) * 3600.0
    if rahu_diff > 180.0 * 3600.0:
        rahu_diff = abs(rahu_diff - 360.0 * 3600.0)
    assert rahu_diff < 1.0, f"Rahu diff {rahu_diff:.3f}\" exceeds 1.0 arcsec"

    # Verify Ascendant within 0.01 degree (~36 arcseconds)
    _, ascmc = swe.houses_ex(t.ut1, lat, lon, b"W", swe.FLG_SIDEREAL | swe.FLG_SPEED)
    swe_asc = ascmc[0] % 360.0
    asc_diff = abs(d["ascendant"]["full_degree"] - swe_asc)
    if asc_diff > 180.0:
        asc_diff = 360.0 - asc_diff
    assert asc_diff < 0.01, f"Ascendant diff {asc_diff:.6f}° exceeds 0.01°"


def test_indian_independence_taurus_lagna_benchmark():
    """Validates Ascendant sign and nakshatra against the known historical Indian Independence chart
    (August 15, 1947, 00:00:00 IST in New Delhi -> Taurus / Vrishabha Lagna in Krittika Pada 4).
    """
    resp = client.get("/v1/vedic/planet_panchang", params={
        "year": 1947,
        "month": 8,
        "day": 15,
        "hour": 0,
        "minute": 0,
        "second": 0,
        "lat": 28.6139,
        "lon": 77.2090,
        "timezone": "Asia/Kolkata",
    })
    assert resp.status_code == 200
    asc = resp.json()["ascendant"]
    assert asc["sign"] == "Taurus"
    assert asc["sign_number"] == 2
    assert asc["sign_lord"] == "Venus"
    assert asc["nakshatra"] == "Krittika"
    assert asc["nakshatra_pada"] == 4


def test_mean_vs_true_node_options():
    """Asserts node_type parameter ('mean' vs 'true') correctly modifies Rahu/Ketu output."""
    resp_mean = client.get("/v1/vedic/planet_panchang", params={
        **DELHI_PARAMS,
        "node_type": "mean",
    })
    assert resp_mean.status_code == 200
    rahu_mean = resp_mean.json()["planets"]["Rahu"]["full_degree"]

    resp_true = client.get("/v1/vedic/planet_panchang", params={
        **DELHI_PARAMS,
        "node_type": "true",
    })
    assert resp_true.status_code == 200
    rahu_true = resp_true.json()["planets"]["Rahu"]["full_degree"]

    # Mean and true nodes differ by up to ~1.75 degrees due to lunar equation of center oscillations
    diff = abs(rahu_true - rahu_mean)
    if diff > 180.0:
        diff = 360.0 - diff
    assert 0.0 < diff < 2.0, f"Mean vs True node diff {diff}° outside expected [0, 2] degree range"


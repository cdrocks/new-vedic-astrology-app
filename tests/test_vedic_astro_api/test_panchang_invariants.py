"""Property-based invariant and boundary stress tests for Panchanga & Muhurtha.

Uses hypothesis to test mathematical conservation laws, physical boundary conditions,
and polar safety.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from hypothesis import given, strategies as st, settings
from fastapi.testclient import TestClient

from vedic_astro_api.calculations.panchang import calculate_panchang, PanchangResult
from vedic_astro_api.api.app import app

client = TestClient(app)


# ===========================================================================
# HYPOTHESIS PROPERTY TESTS
# ===========================================================================

@settings(max_examples=50, deadline=None)
@given(
    year=st.integers(min_value=1950, max_value=2040),
    month=st.integers(min_value=1, max_value=12),
    day=st.integers(min_value=1, max_value=28),  # safe day for all months
    hour=st.integers(min_value=0, max_value=23),
    minute=st.integers(min_value=0, max_value=59),
    lat=st.floats(min_value=-55.0, max_value=55.0),  # non-polar latitudes
    lon=st.floats(min_value=-170.0, max_value=170.0),
)
def test_panchang_property_invariants(year, month, day, hour, minute, lat, lon):
    """Property test: asserts core mathematical boundaries across randomized global inputs."""
    dt = datetime(year, month, day, hour, minute, 0)
    res = calculate_panchang(dt, lat=lat, lon=lon, tz_str="UTC")

    # 1. Tithi Bounds
    assert 1 <= res.tithi_number <= 30
    assert res.paksha in ("Shukla", "Krishna")
    assert 1 <= res.paksha_tithi_number <= 15
    assert 0.0 <= res.tithi_elapsed_pct <= 100.0

    # 2. Nakshatra Bounds
    assert 1 <= res.nakshatra_number <= 27
    assert 1 <= res.nakshatra_pada <= 4
    assert 0.0 <= res.nakshatra_elapsed_pct <= 100.0

    # 3. Yoga & Karana Bounds
    assert 1 <= res.yoga_number <= 27
    assert 1 <= res.karana_number <= 60
    assert res.karana_type in ("Fixed (Sthira)", "Movable (Chara)")

    # 4. Ayanamsha Range (approx 23° to 25° for 1950-2040)
    assert 22.0 < res.ayanamsha_deg < 25.5


# ===========================================================================
# MUHURTHA PARTITION & CONSERVATION LAWS
# ===========================================================================

def test_choghadiya_partition_conservation():
    """Asserts Day Choghadiya partitions Dina Mana exactly without gaps or overlaps."""
    dt = datetime(2026, 9, 9, 12, 0, 0)
    res = calculate_panchang(dt, lat=28.6139, lon=77.2090, tz_str="Asia/Kolkata")

    day_chogs = res.choghadiya_day
    assert len(day_chogs) == 8, "Must have exactly 8 Day Choghadiyas"

    # Check contiguity
    for i in range(len(day_chogs) - 1):
        curr_end = day_chogs[i]["end"]
        next_start = day_chogs[i + 1]["start"]
        assert curr_end == next_start, f"Discontinuity at Day Choghadiya {i+1}->{i+2}"

    # First starts at sunrise, last ends at sunset
    assert day_chogs[0]["start"] == res.sunrise
    assert day_chogs[-1]["end"] == res.sunset


def test_hora_partition_conservation():
    """Asserts 24 Indian Horas are contiguous 60-minute blocks starting at sunrise."""
    dt = datetime(2026, 9, 9, 12, 0, 0)
    res = calculate_panchang(dt, lat=28.6139, lon=77.2090, tz_str="Asia/Kolkata")

    horas = res.hora
    assert len(horas) == 24, "Must have exactly 24 Horas"
    assert horas[0]["start"] == res.sunrise

    for i in range(len(horas) - 1):
        assert horas[i]["end"] == horas[i + 1]["start"]
        t_start = datetime.strptime(horas[i]["start"], "%Y-%m-%d %H:%M:%S")
        t_end = datetime.strptime(horas[i]["end"], "%Y-%m-%d %H:%M:%S")
        assert (t_end - t_start).total_seconds() == 3600.0


def test_abhijit_muhurta_dynamic_scaling():
    """Asserts Abhijit duration is exactly Dina Mana / 15 and Wednesday taint is flagged."""
    # Wednesday test (2026-09-09 is Wednesday)
    dt_wed = datetime(2026, 9, 9, 12, 0, 0)
    res_wed = calculate_panchang(dt_wed, lat=28.6139, lon=77.2090, tz_str="Asia/Kolkata")
    abhijit_wed = res_wed.abhijit_muhurta

    assert abhijit_wed is not None
    assert abhijit_wed["is_inauspicious_wednesday"] is True
    assert "Inauspicious" in abhijit_wed["status"]

    dina_mana_min = res_wed.dina_mana_hours * 60.0
    expected_duration = round(dina_mana_min / 15.0, 1)
    assert abs(abhijit_wed["duration_minutes"] - expected_duration) <= 0.1

    # Thursday test (2026-09-10 is Thursday)
    dt_thu = datetime(2026, 9, 10, 12, 0, 0)
    res_thu = calculate_panchang(dt_thu, lat=28.6139, lon=77.2090, tz_str="Asia/Kolkata")
    abhijit_thu = res_thu.abhijit_muhurta

    assert abhijit_thu["is_inauspicious_wednesday"] is False
    assert "Auspicious" in abhijit_thu["status"]


def test_vara_lord_before_sunrise():
    """Asserts birth before sunrise maps to the previous calendar day's Vara lord."""
    # On Wednesday 2026-09-09, Sunrise in Delhi is ~06:03 IST.
    # At 05:00 IST (before sunrise), the Vedic day is still Tuesday (Mangalavara / Mars)!
    dt_early = datetime(2026, 9, 9, 5, 0, 0)
    res_early = calculate_panchang(dt_early, lat=28.6139, lon=77.2090, tz_str="Asia/Kolkata")

    assert res_early.vara_name == "Mangalavara", f"Expected Mangalavara but got {res_early.vara_name}"
    assert res_early.vara_lord == "Mars"

    # At 07:00 IST (after sunrise), the Vedic day flips to Wednesday (Budhavara / Mercury)!
    dt_after = datetime(2026, 9, 9, 7, 0, 0)
    res_after = calculate_panchang(dt_after, lat=28.6139, lon=77.2090, tz_str="Asia/Kolkata")

    assert res_after.vara_name == "Budhavara"
    assert res_after.vara_lord == "Mercury"


# ===========================================================================
# POLAR HIGH-LATITUDE SAFETY TESTS
# ===========================================================================

def test_polar_midnight_sun_safety():
    """Asserts Tromso during summer solstice returns midnight_sun without crashing."""
    dt_summer = datetime(2026, 6, 21, 12, 0, 0)
    res = calculate_panchang(dt_summer, lat=69.6492, lon=18.9553, tz_str="UTC")

    assert res.polar_phenomenon == "midnight_sun"
    assert res.sunrise is None
    assert res.sunset is None
    assert res.is_daytime is True
    # Five limbs still calculate perfectly
    assert 1 <= res.tithi_number <= 30
    assert 1 <= res.nakshatra_number <= 27


def test_polar_night_safety():
    """Asserts Tromso during winter solstice returns polar_night without crashing."""
    dt_winter = datetime(2026, 12, 21, 12, 0, 0)
    res = calculate_panchang(dt_winter, lat=69.6492, lon=18.9553, tz_str="UTC")

    assert res.polar_phenomenon == "polar_night"
    assert res.sunrise is None
    assert res.sunset is None
    assert res.is_daytime is False
    assert 1 <= res.tithi_number <= 30


# ===========================================================================
# REST API CONTRACT TESTS (GET + POST)
# ===========================================================================

def test_api_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["license"] == "MIT (Commercially Unencumbered)"
    assert data["ephemeris_file_ready"] is True


def test_api_dual_get_and_post():
    # 1. Basic Panchang GET
    resp_get = client.get(
        "/v1/vedic/basic_panchang?year=2026&month=9&day=9&hour=12&min=0&lat=28.6139&lon=77.2090&timezone=Asia/Kolkata"
    )
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert data_get["tithi"]["name"] == "Krishna Trayodashi"
    assert data_get["meta"]["engine_version"] == "0.1.0"

    # 2. Basic Panchang POST
    resp_post = client.post(
        "/v1/vedic/basic_panchang",
        json={
            "year": 2026, "month": 9, "day": 9, "hour": 12, "min": 0, "sec": 0,
            "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
        }
    )
    assert resp_post.status_code == 200
    data_post = resp_post.json()
    assert data_post["tithi"]["name"] == data_get["tithi"]["name"]

    # 3. Advanced Panchang POST
    resp_adv = client.post(
        "/v1/vedic/advanced_panchang",
        json={
            "year": 2026, "month": 9, "day": 9, "hour": 12, "min": 0, "sec": 0,
            "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
        }
    )
    assert resp_adv.status_code == 200
    data_adv = resp_adv.json()
    assert len(data_adv["choghadiya_day"]) == 8
    assert len(data_adv["hora"]) == 24

    # 4. Choghadiya Endpoint
    resp_chog = client.get(
        "/v1/vedic/choghadiya_muhurta?year=2026&month=9&day=9&hour=12&min=0&lat=28.6139&lon=77.2090&timezone=Asia/Kolkata"
    )
    assert resp_chog.status_code == 200
    assert len(resp_chog.json()["day_choghadiya"]) == 8

    # 5. Hora Endpoint
    resp_hora = client.get(
        "/v1/vedic/hora_muhurta?year=2026&month=9&day=9&hour=12&min=0&lat=28.6139&lon=77.2090&timezone=Asia/Kolkata"
    )
    assert resp_hora.status_code == 200
    assert len(resp_hora.json()["hora"]) == 24

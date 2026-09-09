"""Tests for Sunrise-specific and Monthly Panchang endpoints.

Validates:
1. GET & POST /v1/vedic/basic_panchang/sunrise
2. GET & POST /v1/vedic/advanced_panchang/sunrise
3. GET & POST /v1/vedic/monthly_panchang
4. Correct day counts across 30-day, 31-day, 28-day, and 29-day (leap year) months
5. Exact evaluation timestamp matching local sunrise
"""

import pytest
from fastapi.testclient import TestClient

from vedic_astro_api.api.app import app

client = TestClient(app)

DELHI_PARAMS = {
    "year": 2026,
    "month": 9,
    "day": 9,
    "lat": 28.6139,
    "lon": 77.2090,
    "timezone": "Asia/Kolkata",
}


def test_basic_panchang_at_sunrise_get_and_post():
    """Asserts /basic_panchang/sunrise evaluates at sunrise time and returns 200."""
    # GET
    resp_get = client.get("/v1/vedic/basic_panchang/sunrise", params=DELHI_PARAMS)
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert "tithi" in data_get
    assert "nakshatra" in data_get
    assert "solar" in data_get
    sunrise_str = data_get["solar"]["sunrise"]
    # The evaluation time in meta should match sunrise
    assert data_get["meta"]["query_local"].startswith(sunrise_str[:16])

    # POST
    resp_post = client.post("/v1/vedic/basic_panchang/sunrise", json=DELHI_PARAMS)
    assert resp_post.status_code == 200
    data_post = resp_post.json()
    assert data_post["tithi"]["name"] == data_get["tithi"]["name"]
    assert data_post["nakshatra"]["name"] == data_get["nakshatra"]["name"]


def test_advanced_panchang_at_sunrise_get_and_post():
    """Asserts /advanced_panchang/sunrise returns full muhurthas at sunrise."""
    # GET
    resp_get = client.get("/v1/vedic/advanced_panchang/sunrise", params=DELHI_PARAMS)
    assert resp_get.status_code == 200
    data = resp_get.json()
    assert "choghadiya_day" in data
    assert "choghadiya_night" in data
    assert "hora" in data
    assert "rahu_kalam" in data
    assert len(data["choghadiya_day"]) == 8
    assert len(data["choghadiya_night"]) == 8
    assert len(data["hora"]) == 24

    # POST
    resp_post = client.post("/v1/vedic/advanced_panchang/sunrise", json=DELHI_PARAMS)
    assert resp_post.status_code == 200
    assert resp_post.json()["rahu_kalam"] == data["rahu_kalam"]


def test_monthly_panchang_calendar_counts():
    """Asserts monthly panchang accurately returns days for 30-day, 31-day, and leap/non-leap Feb."""
    # 1. September 2026 (30 days)
    resp_sep = client.get("/v1/vedic/monthly_panchang", params={
        "year": 2026, "month": 9, "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
    })
    assert resp_sep.status_code == 200
    data_sep = resp_sep.json()
    assert data_sep["meta"]["total_days"] == 30
    assert len(data_sep["days"]) == 30
    assert data_sep["days"][0]["day"] == 1
    assert data_sep["days"][0]["date"] == "2026-09-01"
    assert data_sep["days"][29]["day"] == 30
    assert data_sep["days"][29]["date"] == "2026-09-30"

    # 2. January 2026 (31 days)
    resp_jan = client.post("/v1/vedic/monthly_panchang", json={
        "year": 2026, "month": 1, "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
    })
    assert resp_jan.status_code == 200
    assert len(resp_jan.json()["days"]) == 31

    # 3. February 2024 (Leap year -> 29 days)
    resp_feb24 = client.post("/v1/vedic/monthly_panchang", json={
        "year": 2024, "month": 2, "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
    })
    assert resp_feb24.status_code == 200
    assert len(resp_feb24.json()["days"]) == 29

    # 4. February 2025 (Common year -> 28 days)
    resp_feb25 = client.post("/v1/vedic/monthly_panchang", json={
        "year": 2025, "month": 2, "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
    })
    assert resp_feb25.status_code == 200
    assert len(resp_feb25.json()["days"]) == 28


def test_monthly_panchang_day_item_structure():
    """Asserts each day item in monthly panchang has complete panchang limbs and sunrise/sunset."""
    resp = client.get("/v1/vedic/monthly_panchang", params={
        "year": 2026, "month": 9, "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
    })
    assert resp.status_code == 200
    day_1 = resp.json()["days"][0]

    assert "day" in day_1
    assert "date" in day_1
    assert "weekday" in day_1
    assert "tithi" in day_1 and "name" in day_1["tithi"] and "number" in day_1["tithi"]
    assert "nakshatra" in day_1 and "name" in day_1["nakshatra"] and "pada" in day_1["nakshatra"]
    assert "yoga" in day_1 and "name" in day_1["yoga"]
    assert "karana" in day_1 and "name" in day_1["karana"]
    assert "sunrise" in day_1 and ":" in day_1["sunrise"]
    assert "sunset" in day_1 and ":" in day_1["sunset"]

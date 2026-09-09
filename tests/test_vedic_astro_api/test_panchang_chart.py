"""Automated Tests for Panchang Kundli Chart & Vedic Time (Ishtakala).

Validates:
1. GET & POST /v1/vedic/panchang_chart
2. GET & POST /v1/vedic/panchang_chart/sunrise
3. Sign-by-sign planetary mappings across 12 signs (Aries to Pisces)
4. Exactly one sign marked as is_ascendant_sign matching the Ascendant
5. planets_by_sign lookup table
6. Vedic Time (Ishtakala: Ghati, Pala, Vipala, Dinamana, Ratrimana) in basic and advanced panchang
7. Precision comparison against DrikPanchang Pune benchmark (Sep 9, 2026)
8. Out-of-bounds date validation (HTTP 422)
"""

from datetime import datetime
import pytest
from fastapi.testclient import TestClient

from vedic_astro_api.api.app import app

client = TestClient(app)

PUNE_PARAMS = {
    "year": 2026,
    "month": 9,
    "day": 9,
    "hour": 17,
    "minute": 29,
    "second": 21,
    "lat": 18.5204,
    "lon": 73.8567,
    "timezone": "Asia/Kolkata",
}


def test_panchang_chart_get_and_post():
    """Asserts GET and POST /panchang_chart return all 12 signs and proper planetary assignments."""
    # GET
    resp_get = client.get("/v1/vedic/panchang_chart", params=PUNE_PARAMS)
    assert resp_get.status_code == 200
    data = resp_get.json()

    assert "meta" in data
    assert "ascendant" in data
    assert "chart" in data
    assert "planets_by_sign" in data

    chart = data["chart"]
    assert len(chart) == 12, f"Expected 12 signs in chart, got {len(chart)}"

    # Signs 1 to 12 in order
    sign_names = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
    ]
    asc_sign_num = data["ascendant"]["sign_number"]
    asc_found = 0

    total_planets_found = 0
    for idx, s in enumerate(chart):
        assert s["sign_number"] == idx + 1
        assert s["sign_name"] == sign_names[idx]
        assert "sign_lord" in s
        if s["is_ascendant_sign"]:
            asc_found += 1
            assert s["sign_number"] == asc_sign_num

        # Verify all planets in this sign actually belong to this sign
        for p in s["planets"]:
            assert p["sign_number"] == s["sign_number"]
            assert p["sign"] == s["sign_name"]
            total_planets_found += 1

    # Exactly one sign is the Ascendant sign
    assert asc_found == 1
    # Exactly 9 Grahas in chart (Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu, Ketu)
    assert total_planets_found == 9

    # Verify planets_by_sign matches chart
    for s in chart:
        assert len(data["planets_by_sign"][s["sign_name"]]) == len(s["planets"])

    # POST
    resp_post = client.post("/v1/vedic/panchang_chart", json=PUNE_PARAMS)
    assert resp_post.status_code == 200
    post_data = resp_post.json()
    assert post_data["ascendant"]["full_degree"] == data["ascendant"]["full_degree"]
    assert len(post_data["chart"]) == 12


def test_panchang_chart_sunrise_endpoint():
    """Asserts /panchang_chart/sunrise returns planetary placements at sunrise."""
    resp = client.get("/v1/vedic/panchang_chart/sunrise", params={
        "year": 2026,
        "month": 9,
        "day": 9,
        "lat": 18.5204,
        "lon": 73.8567,
        "timezone": "Asia/Kolkata",
    })
    assert resp.status_code == 200
    data = resp.json()

    # Sunrise time should be present in meta
    assert "sunrise_time" in data["meta"]
    assert "+05:30" in data["meta"]["sunrise_time"]

    # At sunrise on Sep 9, 2026 in Pune:
    # Sun is in Leo (Simha, sign 5)
    # Moon is in Cancer (Karka, sign 4)
    # Ascendant is in Leo (Simha, sign 5)
    chart = data["chart"]
    leo_sign = chart[4]  # index 4 is Sign 5 (Leo)
    cancer_sign = chart[3]  # index 3 is Sign 4 (Cancer)

    assert leo_sign["is_ascendant_sign"] is True
    leo_planet_names = [p["name"] for p in leo_sign["planets"]]
    assert "Sun" in leo_planet_names

    cancer_planet_names = [p["name"] for p in cancer_sign["planets"]]
    assert "Moon" in cancer_planet_names


def test_vedic_time_ishtakala_drikpanchang_benchmark():
    """Validates Vedic Time (Ishtakala) in Ghati, Pala, Vipala against DrikPanchang screenshot.
    Screenshot Ground Truth for Pune at 17:29:21 on Sep 9, 2026:
    - Vedic Time: 27:02:50 (Ghati:Pala:Vipala)
    - Dinamana: ~12 Hours 21 Mins
    """
    resp = client.get("/v1/vedic/advanced_panchang", params=PUNE_PARAMS)
    assert resp.status_code == 200
    d = resp.json()

    assert "vedic_time" in d
    vt = d["vedic_time"]
    assert vt is not None

    # Ghati and Pala must match exactly
    assert vt["ghati"] == 27, f"Expected 27 Ghati, got {vt['ghati']}"
    assert vt["pala"] == 2, f"Expected 2 Pala, got {vt['pala']}"
    # Vipala within tight tolerance (< 15 vipala ~ 6 seconds)
    assert abs(vt["vipala"] - 50) < 15, f"Vipala {vt['vipala']} deviated too much from 50"

    # Dinamana: 12 Hours 21 Mins
    assert "12 Hours 21 Mins" in vt["dinamana"]
    assert "11 Hours 38 Mins" in vt["ratrimana"] or "11 Hours 39 Mins" in vt["ratrimana"]

    # Also test basic_panchang returns the same vedic_time
    resp_basic = client.get("/v1/vedic/basic_panchang", params=PUNE_PARAMS)
    assert resp_basic.status_code == 200
    vt_basic = resp_basic.json()["vedic_time"]
    assert vt_basic["ishta_kala"] == vt["ishta_kala"]


def test_out_of_range_chart_returns_422():
    """Asserts out-of-range dates return HTTP 422 with supported_query_range."""
    resp = client.get("/v1/vedic/panchang_chart", params={
        "year": 1850, "month": 6, "day": 1, "hour": 12, "minute": 0, "second": 0,
        "lat": 18.5204, "lon": 73.8567, "timezone": "Asia/Kolkata"
    })
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"] == "DateOutOfRange"
    assert "supported_query_range" in data

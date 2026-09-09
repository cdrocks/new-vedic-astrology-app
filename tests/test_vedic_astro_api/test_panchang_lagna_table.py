"""Automated Tests for Panchang Lagna Table (Udaya Lagna 24-Hour Rising Signs).

Validates:
1. GET & POST /v1/vedic/panchang_lagna_table
2. Exactly 12 rising signs covering the 24-hour diurnal cycle
3. Continuous contiguous timeline: entry[i].end_time == entry[i+1].start_time
4. Exactly one sign marked as is_sunrise_lagna (active at local sunrise)
5. Precision validation against DrikPanchang Pune benchmark (Sep 9, 2026):
   - Simha (Leo) ends ~06:57 AM
   - Kanya (Virgo) ~06:57 AM to 09:04 AM
   - Kumbha (Aquarius) ~05:24 PM to 07:01 PM
   - Mesha (Aries) ~08:36 PM to 10:20 PM
   - Karka (Cancer) ~02:33 AM to 04:46 AM
6. Out-of-bounds date validation (HTTP 422)
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
    "lat": 18.5204,
    "lon": 73.8567,
    "timezone": "Asia/Kolkata",
}


def test_panchang_lagna_table_get_and_post():
    """Asserts GET and POST /panchang_lagna_table return all 12 signs in contiguous sequence."""
    # GET
    resp_get = client.get("/v1/vedic/panchang_lagna_table", params=PUNE_PARAMS)
    assert resp_get.status_code == 200
    data = resp_get.json()

    assert "meta" in data
    assert "lagna_table" in data
    table = data["lagna_table"]
    assert len(table) == 12, f"Expected 12 lagna signs, got {len(table)}"

    sunrise_lagna_count = 0
    for idx, item in enumerate(table):
        assert 1 <= item["lagna_number"] <= 12
        assert len(item["lagna_name"]) > 0
        assert len(item["lagna_sanskrit"]) > 0
        assert len(item["sign_lord"]) > 0
        assert item["duration_minutes"] > 60.0  # Every sign rises for > 60 minutes
        assert "Hours" in item["duration"]

        if item["is_sunrise_lagna"]:
            sunrise_lagna_count += 1
            # For Pune on Sep 9, 2026, sunrise is ~06:21 AM, which falls into Simha (Leo, sign 5)
            assert item["lagna_number"] == 5
            assert item["lagna_name"] == "Leo"
            assert item["lagna_sanskrit"] == "Simha"

        # Check contiguous timeline with next sign
        if idx < len(table) - 1:
            next_item = table[idx + 1]
            assert item["end_time"] == next_item["start_time"], (
                f"Discontinuity between {item['lagna_name']} end ({item['end_time']}) "
                f"and {next_item['lagna_name']} start ({next_item['start_time']})"
            )
            # Consecutive zodiac order: next_number = (cur_number % 12) + 1
            expected_next_num = (item["lagna_number"] % 12) + 1
            assert next_item["lagna_number"] == expected_next_num

    assert sunrise_lagna_count == 1, "Exactly one sign must be marked is_sunrise_lagna"

    # POST
    resp_post = client.post("/v1/vedic/panchang_lagna_table", json=PUNE_PARAMS)
    assert resp_post.status_code == 200
    post_data = resp_post.json()
    assert len(post_data["lagna_table"]) == 12
    assert post_data["lagna_table"][0]["start_time"] == table[0]["start_time"]


def test_lagna_table_drikpanchang_pune_benchmark():
    """Validates start and end times against DrikPanchang 'Udaya Lagna Muhurta' for Pune (Sep 9, 2026).
    Reference:
    - Simha: 04:49 AM to 06:57 AM
    - Kanya: 06:57 AM to 09:03 AM
    - Tula: 09:03 AM to 11:14 AM
    - Vrishchika: 11:14 AM to 01:28 PM
    - Dhanu: 01:28 PM to 03:34 PM
    - Makara: 03:34 PM to 05:24 PM
    - Kumbha: 05:24 PM to 07:01 PM
    - Meena: 07:01 PM to 08:36 PM
    - Mesha: 08:36 PM to 10:20 PM
    - Vrishabha: 10:20 PM to 12:20 AM
    - Mithuna: 12:20 AM to 02:33 AM
    - Karka: 02:33 AM to 04:46 AM
    """
    resp = client.get("/v1/vedic/panchang_lagna_table", params=PUNE_PARAMS)
    assert resp.status_code == 200
    table = resp.json()["lagna_table"]

    # Map by name
    table_by_name = {item["lagna_name"]: item for item in table}

    def parse_time(dt_str):
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")

    # Check Simha (Leo)
    simha = table_by_name["Leo"]
    assert simha["is_sunrise_lagna"] is True
    # Start: ~04:50, End: ~06:57
    t_end = parse_time(simha["end_time"])
    assert t_end.hour == 6 and abs(t_end.minute - 57) <= 1

    # Check Kanya (Virgo)
    kanya = table_by_name["Virgo"]
    t_end = parse_time(kanya["end_time"])
    assert t_end.hour == 9 and abs(t_end.minute - 3) <= 1

    # Check Kumbha (Aquarius)
    kumbha = table_by_name["Aquarius"]
    t_start = parse_time(kumbha["start_time"])
    t_end = parse_time(kumbha["end_time"])
    assert t_start.hour == 17 and abs(t_start.minute - 24) <= 1
    assert t_end.hour == 19 and abs(t_end.minute - 1) <= 1

    # Check Mesha (Aries)
    mesha = table_by_name["Aries"]
    t_start = parse_time(mesha["start_time"])
    t_end = parse_time(mesha["end_time"])
    assert t_start.hour == 20 and abs(t_start.minute - 36) <= 1
    assert t_end.hour == 22 and abs(t_end.minute - 20) <= 1

    # Check Karka (Cancer)
    karka = table_by_name["Cancer"]
    t_start = parse_time(karka["start_time"])
    t_end = parse_time(karka["end_time"])
    assert t_start.hour == 2 and abs(t_start.minute - 33) <= 1
    assert t_end.hour == 4 and abs(t_end.minute - 46) <= 1


def test_out_of_range_lagna_table_returns_422():
    """Asserts out-of-range dates return HTTP 422 with supported_query_range."""
    resp = client.get("/v1/vedic/panchang_lagna_table", params={
        "year": 1850, "month": 6, "day": 1,
        "lat": 18.5204, "lon": 73.8567, "timezone": "Asia/Kolkata"
    })
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"] == "DateOutOfRange"
    assert "supported_query_range" in data

"""Tests for Spoon-Fed Human Guidance, Bilingual Terminology & Daily Verdict.

Validates:
1. Naming syllables provided for all 27 Nakshatras across all 4 Padas.
2. Real-time traffic light shifts (RED during Rahu Kalam / Yamaganda, GREEN during Shubh Choghadiya).
3. Bhadra (Vishti) Karana alerting and risk flagging.
4. Both GET and POST execution of /v1/vedic/daily_verdict.
5. Rich dos and don'ts attached to Tithis and Nakshatras.
"""

from __future__ import annotations

from datetime import datetime
import pytest
from fastapi.testclient import TestClient

from vedic_astro_api.calculations.panchang import (
    calculate_panchang,
    RAHU_KALAM_SEGMENTS,
    YAMAGANDA_SEGMENTS,
    GULIKA_SEGMENTS,
)
from vedic_astro_api.calculations.guidance import (
    get_tithi_rich_details,
    get_nakshatra_rich_details,
    get_yoga_rich_details,
    get_karana_rich_details,
    synthesize_daily_guidance,
)
from vedic_astro_api.api.app import app

client = TestClient(app)


def test_muhurtha_octant_tables_and_naming_syllables_spot_check():
    """Validates weekday-to-octant segments against classical Muhurtha Chintamani table,
    and spot-checks classical naming syllables for Ashwini, Magha, and Revati.
    """
    # Classical octant mapping (1-indexed 1/8th of day from sunrise, 0=Sun..6=Sat):
    # Sun: Rahu 8, Yama 5, Gulika 7
    # Mon: Rahu 2, Yama 4, Gulika 6
    # Tue: Rahu 7, Yama 3, Gulika 5
    # Wed: Rahu 5, Yama 2, Gulika 4
    # Thu: Rahu 6, Yama 1, Gulika 3
    # Fri: Rahu 4, Yama 7, Gulika 2
    # Sat: Rahu 3, Yama 6, Gulika 1
    classical_rahu = {0: 8, 1: 2, 2: 7, 3: 5, 4: 6, 5: 4, 6: 3}
    classical_yama = {0: 5, 1: 4, 2: 3, 3: 2, 4: 1, 5: 7, 6: 6}
    classical_gulika = {0: 7, 1: 6, 2: 5, 3: 4, 4: 3, 5: 2, 6: 1}

    assert RAHU_KALAM_SEGMENTS == classical_rahu, "Rahu Kalam octants differ from classical table"
    assert YAMAGANDA_SEGMENTS == classical_yama, "Yamaganda octants differ from classical table"
    assert GULIKA_SEGMENTS == classical_gulika, "Gulika Kalam octants differ from classical table"

    # Spot-check naming syllables:
    # 1. Ashwini: Chu, Che, Cho, La
    ashwini_syllables = [get_nakshatra_rich_details(1, p)["naming_syllable"] for p in (1, 2, 3, 4)]
    assert ashwini_syllables == ["Chu", "Che", "Cho", "La"]

    # 10. Magha: Ma, Mi (Mee), Mu, Me
    magha_syllables = [get_nakshatra_rich_details(10, p)["naming_syllable"] for p in (1, 2, 3, 4)]
    assert magha_syllables == ["Ma", "Mee", "Mu", "Me"]

    # 27. Revati: De, Do, Cha, Chi (Chee)
    revati_syllables = [get_nakshatra_rich_details(27, p)["naming_syllable"] for p in (1, 2, 3, 4)]
    assert revati_syllables == ["De", "Do", "Cha", "Chee"]


def test_naming_syllables_for_all_nakshatras():
    """Asserts all 27 Nakshatras have valid Sanskrit names and 4-pada naming syllables."""
    for nak_id in range(1, 28):
        for pada in range(1, 5):
            info = get_nakshatra_rich_details(nak_id, pada)
            assert info["name_sanskrit"] != "", f"Missing Sanskrit name for Nakshatra {nak_id}"
            assert info["naming_syllable"] != "", f"Missing Pada {pada} syllable for Nakshatra {nak_id}"
            assert len(info["suitable_activities"]) > 0
            assert len(info["unfavorable_activities"]) > 0


def test_tithi_rich_attributes():
    """Asserts Tithis have Devanagari names, deities, and classified categories."""
    for t_id in range(1, 31):
        info = get_tithi_rich_details(t_id)
        assert info["name_sanskrit"] != "", f"Missing Sanskrit name for Tithi {t_id}"
        assert info["category"] != "", f"Missing category for Tithi {t_id}"
        assert info["deity"] != "", f"Missing deity for Tithi {t_id}"
        assert len(info["suitable_activities"]) > 0


def test_traffic_light_red_during_rahu_kalam():
    """Asserts traffic light is RED when query is strictly inside Rahu Kalam."""
    # Delhi on 2026-09-09: Rahu Kalam is 12:18:21 to 13:52:10 IST.
    # At 12:45 IST, it must be RED with explicit mention of Rahu Kalam.
    resp = client.get("/v1/vedic/daily_verdict", params={
        "year": 2026, "month": 9, "day": 9, "hour": 12, "min": 45, "sec": 0,
        "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["traffic_light"] == "RED"
    assert "Rahu Kalam" in data["current_status"]
    assert "avoid" in data["actionable_advice"].lower()


def test_traffic_light_green_during_labh_choghadiya():
    """Asserts traffic light is GREEN during favorable Labh Choghadiya outside Rahu/Yama/Gulika."""
    # Delhi on 2026-09-09: Segment 1 (06:03 to 07:36 IST) is Labh Choghadiya.
    resp = client.get("/v1/vedic/daily_verdict", params={
        "year": 2026, "month": 9, "day": 9, "hour": 7, "minute": 0, "second": 0,
        "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["traffic_light"] == "GREEN"
    assert "Labh" in data["current_status"]


def test_daily_verdict_post_endpoint():
    """Asserts POST /v1/vedic/daily_verdict matches GET during auspicious window."""
    payload = {
        "year": 2026, "month": 9, "day": 9, "hour": 7, "minute": 0, "second": 0,
        "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
    }
    resp = client.post("/v1/vedic/daily_verdict", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["traffic_light"] == "GREEN"
    assert "display_title" in data
    assert "headline" in data
    assert "best_time_window" in data
    assert "danger_time_window" in data


def test_advanced_panchang_includes_guidance_and_sanskrit():
    """Asserts GET /v1/vedic/advanced_panchang contains rich guidance and Sanskrit fields."""
    resp = client.get("/v1/vedic/advanced_panchang", params={
        "year": 2026, "month": 9, "day": 9, "hour": 12, "min": 0, "sec": 0,
        "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
    })
    assert resp.status_code == 200
    data = resp.json()

    # Rich Tithi
    assert "name_sanskrit" in data["tithi"]
    assert data["tithi"]["name_sanskrit"] == "कृष्ण त्रयोदशी"
    assert len(data["tithi"]["suitable_activities"]) > 0

    # Rich Nakshatra
    assert "name_sanskrit" in data["nakshatra"]
    assert data["nakshatra"]["name_sanskrit"] == "आश्लेषा"
    assert data["nakshatra"]["naming_syllable"] == "Do"

    # Rich Guidance
    assert "guidance" in data
    assert data["guidance"]["traffic_light"] in ("GREEN", "YELLOW", "RED")
    assert "display_title" in data["guidance"]


def test_traffic_light_red_during_bhadra_vishti_overrides_shubh():
    """Asserts that Vishti (Bhadra) Karana strictly forces RED on real astronomical calculations."""
    # Delhi on 1947-08-15 06:30 IST: Krishna Chaturdashi, Karana is Vishti (Bhadra).
    resp = client.get("/v1/vedic/daily_verdict", params={
        "year": 1947, "month": 8, "day": 15, "hour": 6, "minute": 30, "second": 0,
        "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["traffic_light"] == "RED"
    assert "Bhadra" in data["current_status"] or "Vishti" in data["current_status"]


def test_traffic_light_red_during_gulika():
    """Asserts that Gulika Kalam strictly forces RED on real astronomical calculations."""
    # Delhi on 2026-09-09 11:00 IST: Shubh Choghadiya is active, but Gulika Kalam (10:44-12:18) forces RED.
    resp = client.get("/v1/vedic/daily_verdict", params={
        "year": 2026, "month": 9, "day": 9, "hour": 11, "minute": 0, "second": 0,
        "lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["traffic_light"] == "RED"
    assert "Gulika" in data["current_status"]

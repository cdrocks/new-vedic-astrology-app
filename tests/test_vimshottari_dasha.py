"""
tests/test_vimshottari_dasha.py - Comprehensive Unit & Parity Tests for Vimshottari Dasha Engine
================================================================================================
Validates classical Parashari proportionality and pre-birth elapsed offset for birth Mahadashas,
preventing compression of Antardashas into birth balance windows.
"""

from datetime import datetime, timedelta, timezone
import pytest
from engine import calculate_vimshottari_dasha
from inspect_chart import compute_antardasha_sequence


def test_birth_in_venus_md_one_year_remaining():
    """
    Test native born with exactly 1.0 year remaining in a 20-year Venus Mahadasha.
    Classical expectation:
    - 20-year Venus MD: Venus-Venus (3.333y), Venus-Sun (1.000y), Venus-Moon (1.667y),
      Venus-Mars (1.167y), Venus-Rahu (3.000y), Venus-Jupiter (2.667y), Venus-Saturn (3.167y),
      Venus-Mercury (2.833y), Venus-Ketu (1.167y) -> Cumulative 18.833y to 20.000y.
    - Native born at MD-year 19.0 -> Must be in Venus-Ketu at birth.
    - Elapsed in Venus-Ketu at birth = 0.167y (~2 months).
    - Remaining in Venus-Ketu = 1.0 year (exactly equals the MD balance!).
    - ad_end_dt equals md_end_dt.
    - next_md is Sun, next_ad is Sun.
    """
    # Bharani Nakshatra (index 1: Venus, span 13.333333333333334 to 26.666666666666668)
    # fraction_left = 1.0 / 20.0 = 0.05 -> fraction_passed = 0.95
    nak_len = 360.0 / 27.0
    moon_deg = 1 * nak_len + 0.95 * nak_len
    birth_dt = datetime(2000, 1, 1, 0, 0, tzinfo=timezone.utc)

    res = calculate_vimshottari_dasha(moon_deg, birth_dt, birth_dt)

    assert res["md"] == "Venus"
    assert res["ad"] == "Ketu"
    assert res["md_next"] == "Sun"
    assert res["ad_next"] == "Sun"

    # Internal consistency check: AD remainder must equal the birth balance
    assert res["ad_remaining_days"] == res["md_remaining_days"]
    assert 364 <= res["ad_remaining_days"] <= 366
    assert res["ad_end"] == res["md_end"]


def test_birth_in_venus_md_two_point_five_years_remaining():
    """
    Test native born with 2.5 years remaining in a 20-year Venus Mahadasha.
    Classical expectation:
    - Native born at MD-year 17.5.
    - Venus-Mercury runs from 16.0 to 18.833y.
    - Native is born inside Venus-Mercury with 1.333 years remaining.
    - Next Antardasha is Venus-Ketu (runs for 1.167 years).
    - Total remaining in Venus MD = 1.333 + 1.167 = 2.500 years.
    """
    nak_len = 360.0 / 27.0
    # fraction_left = 2.5 / 20.0 = 0.125 -> fraction_passed = 0.875
    moon_deg = 1 * nak_len + 0.875 * nak_len
    birth_dt = datetime(2000, 1, 1, 0, 0, tzinfo=timezone.utc)

    res = calculate_vimshottari_dasha(moon_deg, birth_dt, birth_dt)

    assert res["md"] == "Venus"
    assert res["ad"] == "Mercury"
    assert res["md_next"] == "Sun"
    assert res["ad_next"] == "Ketu"

    # Approx 1.333 years remaining in Mercury AD (486-488 days)
    assert 484 <= res["ad_remaining_days"] <= 488
    # 2.5 years remaining in Venus MD (912-914 days)
    assert 911 <= res["md_remaining_days"] <= 915

    # 2.0 years after birth: Native should now be in Venus-Ketu with 0.5 years remaining
    target_2y = birth_dt + timedelta(days=2.0 * 365.2425)
    res_2y = calculate_vimshottari_dasha(moon_deg, birth_dt, target_2y)
    assert res_2y["md"] == "Venus"
    assert res_2y["ad"] == "Ketu"
    assert res_2y["ad_next"] == "Sun"
    assert 181 <= res_2y["ad_remaining_days"] <= 184
    assert res_2y["ad_end"] == res_2y["md_end"]

    # 3.0 years after birth: Native should now be in Sun Mahadasha, Sun-Moon Antardasha
    target_3y = birth_dt + timedelta(days=3.0 * 365.2425)
    res_3y = calculate_vimshottari_dasha(moon_deg, birth_dt, target_3y)
    assert res_3y["md"] == "Sun"
    assert res_3y["ad"] == "Moon"
    assert res_3y["md_next"] == "Moon"


def test_inspect_chart_antardasha_sequence_uncompressed():
    """
    Verify that inspect_chart.py's compute_antardasha_sequence produces the uncompressed
    9-Antardasha sequence with correct is_past and is_active flags.
    """
    nak_len = 360.0 / 27.0
    moon_deg = 1 * nak_len + 0.95 * nak_len  # 1.0 year left of Venus
    birth_dt = datetime(2000, 1, 1, 0, 0, tzinfo=timezone.utc)

    seq_data = compute_antardasha_sequence(moon_deg, birth_dt, birth_dt)
    ad_seq = seq_data["ad_sequence"]

    assert len(ad_seq) == 9
    assert ad_seq[0]["planet"] == "Venus"
    assert ad_seq[-1]["planet"] == "Ketu"

    # For a native born in Venus-Ketu:
    # First 8 Antardashas occurred before birth and must be marked is_past=True
    for i in range(8):
        assert ad_seq[i]["is_past"] is True, f"AD {ad_seq[i]['planet']} should be in past"
        assert ad_seq[i]["is_active"] is False

    # The 9th Antardasha (Ketu) is active at birth
    assert ad_seq[8]["is_active"] is True
    assert 364 <= ad_seq[8]["days_left"] <= 366


def test_indore_fixture_mercury_birth_antardasha_parity():
    """
    Test using Indore reference birth data (1981-02-09, Moon in Uttarabhadrapada).
    Mercury Mahadasha balance at birth is 10.36 years (ends 21 Jun 1991).
    Elapsed before birth in Mercury MD (17-year total) = 6.64 years.
    - Mercury-Mercury (2.41y) ended in 1976.
    - Mercury-Ketu (0.99y) ended in 1977.
    - Mercury-Venus (2.83y) ended in Sep 1980.
    - Mercury-Sun (0.85y) runs from Sep 1980 to Jul 1981 -> Native was BORN inside Mercury-Sun!
    - At target date 1990-06-01: Native is in Mercury-Saturn (ended 21 Jun 1991).
    """
    # Uttarabhadrapada Nakshatra: Moon at approx 350.2 deg
    # In verify_full_report.py: Moon deg = 350.2017 deg, lord is Saturn (Wait, in verify_full_report it was Mercury)
    # Let's use exact Moon degree that gives 10.36 years balance in Mercury (lord_idx = 8)
    nak_len = 360.0 / 27.0
    # Mercury nakshatras: Ashlesha (8), Jyeshtha (17), Revati (26)
    # Revati (26): span 346.6666 to 360.0.
    # fraction_left = 10.36 / 17.0 = 0.60941176
    # fraction_passed = 1 - 0.60941176 = 0.39058824
    moon_deg = 26 * nak_len + (1.0 - 10.36 / 17.0) * nak_len
    birth_dt = datetime(1981, 2, 9, 8, 21, 55, tzinfo=timezone.utc)

    # At birth: must be Mercury-Sun!
    res_birth = calculate_vimshottari_dasha(moon_deg, birth_dt, birth_dt)
    assert res_birth["md"] == "Mercury"
    assert res_birth["ad"] == "Sun"

    # At 1990-06-01: must be Mercury-Saturn!
    target_1990 = datetime(1990, 6, 1, 0, 0, tzinfo=timezone.utc)
    res_1990 = calculate_vimshottari_dasha(moon_deg, birth_dt, target_1990)
    assert res_1990["md"] == "Mercury"
    assert res_1990["ad"] == "Saturn"
    assert "1991" in res_1990["ad_end"]

"""
tests/test_doshas.py - Unit and Integration Tests for doshas.py
"""

import json
from datetime import datetime, timedelta, timezone
import pytest
from doshas import (
    check_kaalsarp_dosha,
    check_manglik_dosha,
    check_pitra_dosha,
    calculate_doshas,
    DoshaCalculationError,
    MissingChartDataError,
    NODE_CONJUNCT_ORB_DEG
)


# ============================================================================
# FIXTURES
# ============================================================================

def make_mock_chart(
    asc_deg: float = 0.0,       # Aries 0° (Ascendant)
    rahu_deg: float = 15.0,     # Aries 15° (H1)
    ketu_deg: float = 195.0,    # Libra 15° (H7)
    planet_degs: dict = None,
    mars_deg: float = 45.0,     # Taurus 15° (H2)
    sun_deg: float = 75.0,      # Gemini 15° (H3)
    moon_deg: float = 105.0,    # Cancer 15° (H4)
    jup_deg: float = 135.0,     # Leo 15° (H5)
    ven_deg: float = 165.0,     # Virgo 15° (H6)
    sat_deg: float = 175.0,     # Virgo 25° (H6)
    mer_deg: float = 80.0,      # Gemini 20° (H3)
    mars_status: str = "Dir"
) -> dict:
    """Helper to construct deterministic synthetic chart_data."""
    degs = {
        "Sun": sun_deg,
        "Moon": moon_deg,
        "Mars": mars_deg,
        "Mercury": mer_deg,
        "Jupiter": jup_deg,
        "Venus": ven_deg,
        "Saturn": sat_deg
    }
    if planet_degs:
        degs.update(planet_degs)

    chart = {
        "Ascendant": {
            "sign_idx": int(asc_deg // 30) % 12,
            "degree_total": asc_deg,
            "degree_in_sign": asc_deg % 30.0,
            "house": 1
        },
        "Rahu": {
            "sign_idx": int(rahu_deg // 30) % 12,
            "degree_total": rahu_deg,
            "degree_in_sign": rahu_deg % 30.0,
            "house": int((int(rahu_deg // 30) - int(asc_deg // 30)) % 12) + 1,
            "status": "Rx"
        },
        "Ketu": {
            "sign_idx": int(ketu_deg // 30) % 12,
            "degree_total": ketu_deg,
            "degree_in_sign": ketu_deg % 30.0,
            "house": int((int(ketu_deg // 30) - int(asc_deg // 30)) % 12) + 1,
            "status": "Rx"
        }
    }

    for p, deg in degs.items():
        sign_idx = int(deg // 30) % 12
        h = int((sign_idx - int(asc_deg // 30)) % 12) + 1
        status = mars_status if p == "Mars" else "Dir"
        chart[p] = {
            "sign_idx": sign_idx,
            "degree_total": deg,
            "degree_in_sign": deg % 30.0,
            "house": h,
            "status": status
        }

    return chart


# ============================================================================
# KAAL SARP TESTS
# ============================================================================

def test_full_classical_kalsarpa():
    """All 7 planets between Rahu (15°) and Ketu (195°). Should be Full Anant Kaal Sarp."""
    chart = make_mock_chart(
        asc_deg=0.0,       # Aries Ascendant -> Rahu in H1
        rahu_deg=15.0,     # Rahu in Aries
        ketu_deg=195.0,    # Ketu in Libra
        planet_degs={
            "Sun": 45.0,      # H2 (Taurus)
            "Moon": 75.0,     # H3 (Gemini)
            "Mars": 105.0,    # H4 (Cancer)
            "Mercury": 80.0,  # H3 (Gemini)
            "Jupiter": 135.0, # H5 (Leo)
            "Venus": 165.0,   # H6 (Virgo)
            "Saturn": 175.0   # H6 (Virgo)
        }
    )
    res = check_kaalsarp_dosha(chart)

    assert res["is_present"] is True
    assert res["is_classical"] is True
    assert res["classification"] == "Full Kaal Sarp Dosha"
    assert res["type_name"] == "Anant"
    assert res["rahu_house"] == 1
    assert res["ketu_house"] == 7
    assert res["escaped_planet"] is None
    assert "Apsavya" in res["direction"]  # Arc Rahu -> Ketu
    assert len(res["remedies"]) > 0


def test_partial_anshik_kalsarpa_modern_label():
    """6 planets hemmed in Arc 1, but Jupiter escaped to 270° (H10 Capricorn in Arc 2)."""
    chart = make_mock_chart(
        asc_deg=0.0,
        rahu_deg=15.0,
        ketu_deg=195.0,
        planet_degs={
            "Sun": 45.0,
            "Moon": 75.0,
            "Mars": 105.0,
            "Mercury": 80.0,
            "Jupiter": 270.0,  # Escaped!
            "Venus": 165.0,
            "Saturn": 175.0
        }
    )
    res = check_kaalsarp_dosha(chart)

    assert res["is_present"] is True
    assert res["is_classical"] is False
    assert "Partial / Anshik" in res["classification"]
    assert "Modern Interpretation" in res["classification"]
    assert res["escaped_planet"] == "Jupiter"
    # Verify consumer note is included
    assert any("Classical Jyotish texts require all 7" in note for note in res["notes"])


def test_no_kalsarpa_planets_dispersed():
    """Planets widely distributed on both sides of the nodal axis."""
    chart = make_mock_chart(
        asc_deg=0.0,
        rahu_deg=15.0,
        ketu_deg=195.0,
        planet_degs={
            "Sun": 45.0,      # Arc 1
            "Moon": 75.0,     # Arc 1
            "Mars": 220.0,    # Arc 2
            "Mercury": 250.0, # Arc 2
            "Jupiter": 270.0, # Arc 2
            "Venus": 165.0,   # Arc 1
            "Saturn": 175.0   # Arc 1
        }
    )
    res = check_kaalsarp_dosha(chart)

    assert res["is_present"] is False
    assert res["is_classical"] is False
    assert res["classification"] == "None"
    assert res["type_name"] is None


def test_kalsarpa_nodal_axis_orb_boundary():
    """
    Planet (Jupiter at 195.8°) is within 0.8° of Ketu (195.0°).
    Even though mathematically (195.8 - 15.0) = 180.8° (falling slightly into Arc 2),
    because it's within NODE_CONJUNCT_ORB_DEG (1.5°), it must be classified as on-axis
    and not break the Full Kaal Sarp closure.
    """
    chart = make_mock_chart(
        asc_deg=0.0,
        rahu_deg=15.0,
        ketu_deg=195.0,
        planet_degs={
            "Sun": 45.0,
            "Moon": 75.0,
            "Mars": 105.0,
            "Mercury": 80.0,
            "Jupiter": 195.8,  # Conjunct Ketu within 0.8° orb!
            "Venus": 165.0,
            "Saturn": 175.0
        }
    )
    res = check_kaalsarp_dosha(chart)

    assert res["is_present"] is True
    assert res["is_classical"] is True
    assert "On-Axis Closure" in res["classification"]
    assert len(res["boundary_planets"]) == 1
    assert res["boundary_planets"][0]["planet"] == "Jupiter"
    assert res["boundary_planets"][0]["node"] == "Ketu"
    assert res["boundary_planets"][0]["orb_deg"] <= NODE_CONJUNCT_ORB_DEG


def test_kalsarpa_savya_direction():
    """All 7 planets in Ketu -> Rahu arc (Arc 2). Eastward progression advances into Rahu (Savya/Udit)."""
    chart = make_mock_chart(
        asc_deg=0.0,
        rahu_deg=15.0,
        ketu_deg=195.0,
        planet_degs={
            "Sun": 210.0,     # Scorpio (H8)
            "Moon": 240.0,    # Sagittarius (H9)
            "Mars": 270.0,    # Capricorn (H10)
            "Mercury": 280.0, # Capricorn (H10)
            "Jupiter": 300.0, # Aquarius (H11)
            "Venus": 330.0,   # Pisces (H12)
            "Saturn": 350.0   # Pisces (H12)
        }
    )
    res = check_kaalsarp_dosha(chart)

    assert res["is_present"] is True
    assert res["is_classical"] is True
    assert "Savya (Udit" in res["direction"]


def test_kalsarpa_apsavya_direction():
    """All 7 planets in Rahu -> Ketu arc (Arc 1). Eastward progression advances away from Rahu towards Ketu (Apsavya/Anudit)."""
    chart = make_mock_chart(
        asc_deg=0.0,       # Aries Ascendant -> Rahu in H1
        rahu_deg=15.0,     # Rahu in Aries
        ketu_deg=195.0,    # Ketu in Libra
        planet_degs={
            "Sun": 45.0,      # H2 (Taurus)
            "Moon": 75.0,     # H3 (Gemini)
            "Mars": 105.0,    # H4 (Cancer)
            "Mercury": 80.0,  # H3 (Gemini)
            "Jupiter": 135.0, # H5 (Leo)
            "Venus": 165.0,   # H6 (Virgo)
            "Saturn": 175.0   # H6 (Virgo)
        }
    )
    res = check_kaalsarp_dosha(chart)

    assert res["is_present"] is True
    assert res["is_classical"] is True
    assert "Apsavya (Anudit" in res["direction"]


def test_kalsarpa_12_type_names_mapping():
    """Verify that Rahu placed in houses 1 through 12 maps to the 12 canonical names."""
    expected_names = {
        1: "Anant",
        2: "Kulik",
        3: "Vasuki",
        4: "Shankhapal",
        5: "Padma",
        6: "Mahapadma",
        7: "Takshak",
        8: "Karkotak",
        9: "Shankhachur",
        10: "Ghatak",
        11: "Vishdhar",
        12: "Sheshnag"
    }
    for h, name in expected_names.items():
        # Ascendant at 0 (Aries). Rahu at sign (h-1)
        rahu_deg = (h - 1) * 30.0 + 15.0
        ketu_deg = (rahu_deg + 180.0) % 360.0
        # Place all 7 planets in Rahu->Ketu arc (e.g. +10 to +70 deg from Rahu)
        planet_degs = {
            p: (rahu_deg + 10.0 + i * 8.0) % 360.0
            for i, p in enumerate(["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"])
        }
        chart = make_mock_chart(
            asc_deg=0.0,
            rahu_deg=rahu_deg,
            ketu_deg=ketu_deg,
            planet_degs=planet_degs
        )
        res = check_kaalsarp_dosha(chart)
        assert res["is_present"] is True, f"Failed presence for Rahu in H{h}"
        assert res["rahu_house"] == h, f"Expected Rahu in house {h}, got {res['rahu_house']}"
        assert res["type_name"] == name, f"Expected {name} for house {h}, got {res['type_name']}"


# ============================================================================
# MANGLIK DOSHA TESTS
# ============================================================================

def test_manglik_lagna_and_moon_stack_high_severity():
    """
    Mars in 7th house from both Lagna and Moon (Aries Ascendant + Moon in Aries, Mars in Libra).
    Lagna (+40) + Moon (+30) = 70 pts -> High Severity (Band: >=66).
    """
    chart = make_mock_chart(
        asc_deg=0.0,       # Aries Ascendant
        mars_deg=190.0,    # Libra 10° (H7 from Lagna)
        moon_deg=15.0,     # Aries (H7 from Moon as well!)
        ven_deg=45.0,      # Taurus (H6 from Venus -> no Venus affliction)
        jup_deg=45.0       # Taurus (no aspect on Mars)
    )
    res = check_manglik_dosha(chart)

    assert res["is_manglik"] is True
    assert res["reference_afflictions"]["lagna"] is True
    assert res["reference_afflictions"]["moon"] is True
    assert res["reference_afflictions"]["venus"] is False
    assert res["raw_score"] == 70  # 40 (Lagna) + 30 (Moon)
    assert res["severity"] == "High"
    assert res["classically_cancelled"] is False
    assert res["mitigated_to_zero"] is False


def test_manglik_from_lagna_medium_severity():
    """
    Mars in 7th house from Lagna only (+40 pts), Moon unafflicted (H6 from Moon), no cancellations.
    Raw score = 40 pts -> Medium Severity (Band: 36 to 65).
    """
    chart = make_mock_chart(
        asc_deg=0.0,       # Aries Ascendant
        mars_deg=190.0,    # Libra 10° (H7 from Lagna -> +40 pts)
        moon_deg=45.0,     # Taurus 15° (H6 from Moon -> unafflicted)
        ven_deg=45.0,      # Taurus 15° (H6 from Venus -> unafflicted)
        jup_deg=45.0       # Taurus 15° (no aspect on Mars)
    )
    res = check_manglik_dosha(chart, age_years=25.0)  # under 28, no age deduction

    assert res["is_manglik"] is True
    assert res["reference_afflictions"]["lagna"] is True
    assert res["reference_afflictions"]["moon"] is False
    assert res["reference_afflictions"]["venus"] is False
    assert res["raw_score"] == 40
    assert res["severity_score"] == 40
    assert res["severity"] == "Medium"
    assert res["classically_cancelled"] is False
    assert res["mitigated_to_zero"] is False
    assert res["is_cancelled"] is False


def test_manglik_cancellation_mars_exalted_capricorn():
    """Mars in 10th sign (Capricorn, House 4 for Libra Ascendant -> Manglik house).
    Mars in Capricorn is Exalted -> triggers full classical cancellation (zeroes reference score).
    Native is classically NOT Manglik (is_manglik = False, severity = "None", score = 0)."""
    chart = make_mock_chart(
        asc_deg=180.0,     # Libra Ascendant (H1)
        mars_deg=280.0,    # Capricorn 10° (H4 from Lagna -> Manglik house!)
        moon_deg=45.0,     # Taurus (H9 from Moon -> no moon affliction)
        ven_deg=45.0,      # Taurus (H9 from Venus -> no venus affliction)
        jup_deg=0.0        # Aries (does not aspect Mars)
    )
    res = check_manglik_dosha(chart)

    assert res["has_placement"] is True
    assert res["reference_afflictions"]["lagna"] is True
    assert res["raw_score"] == 0
    assert any("Mars exalted in Capricorn" in c for c in res["cancellations"])
    assert res["severity_score"] == 0
    assert res["severity"] == "None"
    assert res["is_cancelled"] is True
    assert res["classically_cancelled"] is True
    assert res["mitigated_to_zero"] is False
    assert res["is_manglik"] is False


def test_manglik_cancellation_own_sign_aries_scorpio():
    """Mars in own sign (Aries or Scorpio) in a Kuja house classically nullifies dosha directly."""
    # Test Aries in H1 for Aries Lagna
    chart_aries = make_mock_chart(
        asc_deg=0.0,       # Aries Lagna
        mars_deg=15.0,     # Aries (H1)
        moon_deg=60.0,
        ven_deg=60.0,
        jup_deg=120.0
    )
    res_aries = check_manglik_dosha(chart_aries)
    assert res_aries["has_placement"] is True
    assert res_aries["raw_score"] == 0
    assert res_aries["severity_score"] == 0
    assert res_aries["severity"] == "None"
    assert res_aries["is_cancelled"] is True
    assert res_aries["is_manglik"] is False
    assert any("Mars in own sign (Aries)" in c for c in res_aries["cancellations"])

    # Test Scorpio in H8 for Aries Lagna
    chart_scorpio = make_mock_chart(
        asc_deg=0.0,       # Aries Lagna
        mars_deg=225.0,    # Scorpio (H8)
        moon_deg=60.0,
        ven_deg=60.0,
        jup_deg=120.0
    )
    res_scorpio = check_manglik_dosha(chart_scorpio)
    assert res_scorpio["has_placement"] is True
    assert res_scorpio["raw_score"] == 0
    assert res_scorpio["severity_score"] == 0
    assert res_scorpio["severity"] == "None"
    assert res_scorpio["is_cancelled"] is True
    assert res_scorpio["is_manglik"] is False
    assert any("Mars in own sign (Scorpio)" in c for c in res_scorpio["cancellations"])


def test_manglik_sign_house_exemption_h7_cancer():
    """Classical exemption: Mars in 7th house in Cancer (or Capricorn) carries no dosha."""
    chart = make_mock_chart(
        asc_deg=270.0,     # Capricorn Ascendant (H1). 7th house is Cancer!
        mars_deg=105.0,    # Cancer 15° (H7 from Lagna)
        moon_deg=30.0,     # Taurus (H11 from Moon)
        ven_deg=30.0,      # Taurus (H11 from Venus)
        jup_deg=0.0
    )
    res = check_manglik_dosha(chart)
    assert res["has_placement"] is True
    assert res["raw_score"] == 0
    assert res["severity_score"] == 0
    assert res["severity"] == "None"
    assert res["is_cancelled"] is True
    assert res["is_manglik"] is False
    assert any("Mars in 7th house in Cancer is classically exempt" in c for c in res["cancellations"])


def test_manglik_jupiter_aspect_cancellation():
    """Mars in 7th house (Aquarius) for Leo Ascendant (+40 pts base, non-exempt).
    Moon in Aries (H11 from Moon -> no moon affliction).
    Venus in Aries (H11 from Venus -> no venus affliction).
    Jupiter in Gemini (H11 from Lagna) casts 9th aspect (-30 pts softening).
    Native under 28: 40 - 30 = 10 pts (Low).
    Native over 28 (Age >= 28: -20 pts): 40 - 30 - 20 = 0 pts -> fully cancelled!"""
    chart = make_mock_chart(
        asc_deg=120.0,     # Leo Ascendant (H1)
        mars_deg=315.0,    # Aquarius 15° (H7 from Lagna: +40 pts)
        jup_deg=75.0,      # Gemini 15° (H11 from Lagna: (10 - 2)%12 + 1 = 9th aspect on Aquarius!)
        moon_deg=15.0,     # Aries 15° (H11 from Moon -> not a Kuja house)
        ven_deg=15.0       # Aries 15° (H11 from Venus -> not a Kuja house)
    )
    # Under 28
    res_under = check_manglik_dosha(chart, age_years=25.0)
    assert res_under["reference_afflictions"]["lagna"] is True
    assert res_under["raw_score"] == 40
    assert any("Jupiter casts full classical 9th aspect" in m for m in res_under["mitigations"])
    assert res_under["severity_score"] == 10
    assert res_under["severity"] == "Low"
    assert res_under["is_manglik"] is True

    # Over 28 (Jupiter -30 + Age -20 stacks to exceed base 40)
    res_over = check_manglik_dosha(chart, age_years=30.0)
    assert res_over["severity_score"] == 0
    assert res_over["severity"] == "None"
    assert res_over["is_cancelled"] is True
    assert res_over["classically_cancelled"] is False
    assert res_over["mitigated_to_zero"] is True
    assert res_over["is_manglik"] is False


def test_manglik_age_28_deterministic_as_of():
    """
    Test deterministic age calculation via injectable as_of date:
    - Native born 1995-01-01.
    - Mars in Aquarius (H7 from Leo Lagna, +40 pts base, no classical sign exemption).
    - as_of 2015-01-01 (age 20.0 yrs) -> under 28 branch: NO age mitigation deduction (Score 40 -> Medium).
    - as_of 2025-01-01 (age 30.0 yrs) -> >= 28 branch: age mitigation deduction (-20 pts -> Score 20 -> Low).
    - With Jupiter aspect (-30 pts) and age >= 28 (-20 pts): 40 - 30 - 20 = -10 -> 0 (None / is_cancelled).
    """
    chart = make_mock_chart(
        asc_deg=120.0,     # Leo Ascendant
        mars_deg=315.0,    # Aquarius (H7 from Lagna: +40 pts)
        moon_deg=180.0,    # Libra (H5 from Moon -> no moon affliction)
        ven_deg=180.0,     # Libra (H5 from Venus -> no venus affliction)
        jup_deg=0.0        # Aries (H9 from Lagna, 3rd to Aquarius -> no Jupiter aspect)
    )
    birth_dt = datetime(1995, 1, 1, tzinfo=timezone.utc)

    # Branch 1: Under 28 (Age 20.0) -> No age mitigation
    res_young = check_manglik_dosha(chart, birth_dt=birth_dt, as_of=datetime(2015, 1, 1, tzinfo=timezone.utc))
    assert res_young["effective_age"] == 20.01 or 19.9 <= res_young["effective_age"] <= 20.1
    assert len(res_young["mitigations"]) == 0
    assert res_young["severity_score"] == 40
    assert res_young["severity"] == "Medium"
    assert res_young["is_manglik"] is True

    # Branch 2: Over 28 (Age 30.0) -> Age mitigation applied (-20 pts) -> Score 40 - 20 = 20 pts (Low)
    res_mature = check_manglik_dosha(chart, birth_dt=birth_dt, as_of=datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert res_mature["effective_age"] == 30.02 or 29.9 <= res_mature["effective_age"] <= 30.1
    assert any("exceeds Mars planetary maturity age" in m for m in res_mature["mitigations"])
    assert res_mature["severity_score"] == 20
    assert res_mature["severity"] == "Low"
    assert res_mature["is_manglik"] is True

    # Branch 3: Over 28 with Jupiter aspect -> 40 - 30 (Jup) - 20 (Age) = -10 -> 0 (Cancelled)
    chart_with_jup = make_mock_chart(
        asc_deg=120.0,
        mars_deg=315.0,
        moon_deg=180.0,
        ven_deg=180.0,
        jup_deg=75.0       # Gemini (9th aspect on Aquarius)
    )
    res_canc = check_manglik_dosha(chart_with_jup, birth_dt=birth_dt, as_of=datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert res_canc["severity_score"] == 0
    assert res_canc["severity"] == "None"
    assert res_canc["is_cancelled"] is True
    assert res_canc["is_manglik"] is False

    # Also test explicit age_years parameter directly
    res_direct_age = check_manglik_dosha(chart, age_years=35.0)
    assert res_direct_age["effective_age"] == 35.0
    assert any("exceeds Mars planetary maturity age" in m for m in res_direct_age["mitigations"])


def test_manglik_venus_only_affliction_semantics():
    """
    Venus-reference hit alone:
    Mars is placed in H7 from Venus (afflicted from Venus),
    but in H3 from Lagna and H6 from Moon (non-afflicted houses).
    Classical Parashari convention: Venus is supplementary; top-level is_manglik is False.
    """
    chart = make_mock_chart(
        asc_deg=0.0,       # Aries (H1). Mars in Gemini (H3 -> not a Kuja house from Lagna)
        mars_deg=75.0,     # Gemini 15° (H3 from Lagna)
        moon_deg=285.0,    # Capricorn 15° (H10 from Lagna). Mars is in H6 from Moon -> not a Kuja house!
        ven_deg=255.0,     # Sagittarius 15° (H9 from Lagna). Mars is in H7 from Venus -> Afflicted from Venus!
        jup_deg=0.0
    )
    res = check_manglik_dosha(chart)

    assert res["has_placement"] is True
    assert res["reference_afflictions"]["lagna"] is False
    assert res["reference_afflictions"]["moon"] is False
    assert res["reference_afflictions"]["venus"] is True
    assert res["is_primary_manglik"] is False
    assert res["is_venus_only"] is True
    # Crucial distinction: top-level is_manglik remains False for Venus-only
    assert res["is_manglik"] is False


def test_manglik_mars_retrograde_does_not_break_dosha():
    """Retrograde status should not prevent detection of Kuja Dosha."""
    chart = make_mock_chart(
        asc_deg=0.0,
        mars_deg=190.0,    # Libra (H7 from Lagna)
        mars_status="Rx"
    )
    res = check_manglik_dosha(chart)

    assert res["reference_afflictions"]["lagna"] is True
    assert res["raw_score"] >= 40


def test_manglik_south_indian_2nd_house_flag():
    """Mars in 2nd house (Taurus for Aries Ascendant).
    Standard Classical: Not Manglik.
    South Indian (include_2nd_house=True): Manglik from Lagna."""
    chart = make_mock_chart(
        asc_deg=0.0,
        mars_deg=45.0,     # Taurus (H2 from Lagna)
        moon_deg=180.0,    # Libra
        ven_deg=135.0      # Leo
    )
    chart["Moon"]["sign_idx"] = 4  # Leo
    chart["Moon"]["degree_total"] = 135.0
    chart["Venus"]["sign_idx"] = 4  # Leo
    chart["Venus"]["degree_total"] = 135.0

    res_std = check_manglik_dosha(chart, include_2nd_house=False)
    assert res_std["reference_afflictions"]["lagna"] is False

    res_si = check_manglik_dosha(chart, include_2nd_house=True)
    assert res_si["reference_afflictions"]["lagna"] is True


# ============================================================================
# PITRA DOSHA TESTS
# ============================================================================

def test_pitra_dosha_sun_rahu_grahan():
    """Sun and Rahu conjunct in Aries within 2° orb (Grahan Yoga + tight conjunction bonus <=10°).
    Also Rahu in 9th house for Leo Ascendant (+30 pts)."""
    chart = make_mock_chart(
        asc_deg=120.0,     # Leo Ascendant (H1). 9th house is Aries (0°-30°)!
        sun_deg=10.0,      # Sun in Aries (H9)
        rahu_deg=12.0,     # Rahu in Aries (H9) -> Conjunct Sun (2° orb) AND occupies 9th house!
        ketu_deg=192.0,
        sat_deg=280.0
    )
    res = check_pitra_dosha(chart)

    assert res["is_present"] is True
    assert res["severity"] == "High"
    assert res["severity_score"] >= 75
    assert any("Grahan Yoga" in f for f in res["affliction_factors"])
    assert any("Tight Conjunction Bonus (<=10°): +15 pts" in f for f in res["affliction_factors"])
    assert any("Rahu occupies the 9th House" in f for f in res["affliction_factors"])
    assert len(res["remedies"]) > 0


def test_pitra_dosha_9th_lord_aspected_by_saturn_or_nodes():
    """
    9th Lord receiving Parashari aspect from Saturn or Rahu/Ketu gains +15 pts.
    Aries Ascendant -> 9th sign is Sagittarius -> 9th Lord is Jupiter.
    Jupiter in Gemini (sign 2 = House 3).
    Saturn in Aries (sign 0 = House 1).
    From Saturn (sign 0) to Jupiter (sign 2) is 3rd aspect (+15 pts)!
    """
    chart = make_mock_chart(
        asc_deg=0.0,       # Aries Lagna (9th house = Sagittarius, Lord = Jupiter)
        sun_deg=135.0,     # Sun in Leo (H5, clean)
        jup_deg=75.0,      # Jupiter (9th Lord) in Gemini (sign 2 = H3)
        sat_deg=15.0,      # Saturn in Aries (sign 0 = H1) -> aspects 3rd sign (Gemini, where 9th lord sits!)
        rahu_deg=45.0,     # Taurus (H2)
        ketu_deg=225.0     # Scorpio (H8)
    )
    res = check_pitra_dosha(chart)
    assert any("9th Lord (Jupiter) is aspected by Saturn" in f for f in res["affliction_factors"])
    assert res["severity_score"] >= 15


def test_pitra_dosha_ketu_5th_aspect_on_9th_house():
    """
    Ketu in 5th house (Cancer) casting full 5th-sign Parashari drishti on 9th house (Scorpio)
    for Pisces Ascendant:
    Ascendant: Pisces (sign 11)
    5th house: Cancer (sign 3) -> Ketu placed here
    9th house: Scorpio (sign 7) -> (7 - 3) % 12 + 1 = 5th aspect from Ketu!
    """
    chart = make_mock_chart(
        asc_deg=330.0,     # Pisces Ascendant (H1 = Pisces). 9th House is Scorpio (sign 7).
        ketu_deg=105.0,    # Cancer 15° (sign 3 = House 5)
        rahu_deg=285.0,    # Capricorn 15° (sign 9 = House 11)
        sun_deg=0.0,       # Aries (H2)
        sat_deg=30.0,      # Taurus (H3)
        jup_deg=0.0        # Aries (H2)
    )
    res = check_pitra_dosha(chart)

    assert any("Ketu casts full Parashari aspect on the 9th House" in f for f in res["affliction_factors"])
    assert res["severity_score"] >= 20


def test_pitra_dosha_9th_lord_in_dusthana():
    """
    9th Lord placed in Dusthana (6, 8, or 12).
    Aries Ascendant -> 9th sign is Sagittarius -> 9th Lord is Jupiter.
    Jupiter placed in Virgo (sign 5 = House 6 = Dusthana) -> +20 pts.
    """
    chart = make_mock_chart(
        asc_deg=0.0,       # Aries Ascendant (9th house = Sagittarius, Lord = Jupiter)
        jup_deg=165.0,     # Virgo 15° (sign 5 = House 6: Dusthana!)
        sun_deg=135.0,     # Leo (H5, Own sign, clean)
        rahu_deg=45.0,     # Taurus (H2)
        ketu_deg=225.0,    # Scorpio (H8)
        sat_deg=280.0      # Capricorn (H10, Own sign)
    )
    res = check_pitra_dosha(chart)

    assert any("9th Lord (Jupiter) is placed in Dusthana House 6" in f for f in res["affliction_factors"])
    assert res["severity_score"] >= 20


def test_pitra_dosha_none_harmonious():
    """Sun well placed in Leo (H5), 9th house clean (Sagittarius),
    Saturn in Capricorn (no aspect on Sun, 9th house, or 9th lord)."""
    chart = make_mock_chart(
        asc_deg=0.0,       # Aries Ascendant. 9th house is Sagittarius (lord: Jupiter).
        sun_deg=135.0,     # Sun in Leo (H5, Own sign)
        rahu_deg=45.0,     # Rahu in Taurus (H2)
        ketu_deg=225.0,    # Ketu in Scorpio (H8)
        sat_deg=280.0,     # Saturn in Capricorn (H10, Own sign - aspects Pisces, Cancer, Libra)
        jup_deg=250.0      # Jupiter (9th Lord) in Sagittarius (H9, Own sign!)
    )
    res = check_pitra_dosha(chart)

    assert res["is_present"] is False
    assert res["severity"] == "None"
    assert res["severity_score"] == 0


# ============================================================================
# MASTER CALCULATE_DOSHAS INTEGRATION TESTS
# ============================================================================

def test_calculate_doshas_wrapper_structure_and_json_roundtrip():
    """Verify clean JSON-serializable dictionary structure, single signature, and json.dumps round-trip."""
    chart = make_mock_chart()
    res = calculate_doshas(
        chart,
        birth_dt=datetime(1990, 1, 1, tzinfo=timezone.utc),
        as_of=datetime(2025, 1, 1, tzinfo=timezone.utc)
    )

    assert "summary" in res
    assert "kalsarpa" in res
    assert "manglik" in res
    assert "pitra_dosha" in res
    assert isinstance(res["summary"]["has_any_dosha"], bool)
    assert isinstance(res["summary"]["active_doshas"], list)
    assert res["summary"]["overall_severity"] in ["None", "Low", "Medium", "High"]

    # Assert exact json.dumps round-trip without serializing errors
    serialized = json.dumps(res)
    deserialized = json.loads(serialized)
    assert deserialized["summary"]["overall_severity"] == res["summary"]["overall_severity"]
    assert deserialized["manglik"]["is_manglik"] == res["manglik"]["is_manglik"]


def test_pitra_dosha_dual_aspect_compounding():
    """
    Validate that when the 9th Lord occupies the 9th House, an incoming malefic aspect
    (e.g., Ketu 5th aspect on Scorpio) strikes BOTH the 9th House (+20 pts) and the 9th Lord
    (+15 pts), totaling +35 pts from that single drishti event.
    Classically, this reinforces the affliction (Bhava + Bhava Lord simultaneous vulnerability).
    """
    chart = make_mock_chart(
        asc_deg=330.0,     # Pisces Ascendant (H1 = Pisces). 9th House is Scorpio (sign 7), Lord = Mars.
        mars_deg=225.0,    # Scorpio 15° (9th Lord seated in 9th House!)
        ketu_deg=105.0,    # Cancer 15° (sign 3 = House 5) -> 5th aspect on Scorpio (sign 7)
        rahu_deg=285.0,    # Capricorn 15° (sign 9 = House 11)
        sun_deg=0.0,       # Aries (H2)
        sat_deg=280.0,     # Capricorn (H11)
        jup_deg=0.0        # Aries (H2)
    )
    res = check_pitra_dosha(chart)

    has_house_drishti = any("Ketu casts full Parashari aspect on the 9th House" in f for f in res["affliction_factors"])
    has_lord_drishti = any("9th Lord (Mars) is aspected by Ketu (seated in 9th House - compounds Bhava drishti)" in f for f in res["affliction_factors"])

    assert has_house_drishti is True
    assert has_lord_drishti is True
    assert res["severity_score"] >= 35
    assert res["compounding_notes"] is not None
    assert "simultaneously afflicted" in res["compounding_notes"]


def test_doshas_rubric_version_emitted():
    """Verify that rubric_version is emitted at top-level and in each sub-dosha dictionary."""
    chart = make_mock_chart()
    res = calculate_doshas(chart)

    assert "rubric_version" in res
    assert res["rubric_version"] == "2026.09-v2"
    assert res["summary"]["rubric_version"] == "2026.09-v2"
    assert res["kalsarpa"]["rubric_version"] == "2026.09-v2"
    assert res["manglik"]["rubric_version"] == "2026.09-v2"
    assert res["pitra_dosha"]["rubric_version"] == "2026.09-v2"


def test_missing_planet_data_raises_custom_error():
    """Robust error handling when required planet is missing: raises MissingChartDataError."""
    bad_chart = {"Ascendant": {"sign_idx": 0, "degree_total": 0.0}}
    with pytest.raises(MissingChartDataError):
        calculate_doshas(bad_chart)

    # Verify custom exception hierarchy
    assert issubclass(MissingChartDataError, DoshaCalculationError)


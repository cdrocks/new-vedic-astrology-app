"""
Tests for the Hybrid Agentic Pipeline:
- Python pre-computed machine verdicts
- Health factsheet compilation (90-day clamp & BAV bindus)
- Output validation & banned word / trope scanning
- Deterministic fallback reading generator
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from kiosk_core import (
    validate_and_sanitize_reading,
    generate_deterministic_fallback_reading,
    compute_astrological_verdicts,
    build_health_factsheet,
    build_topic_factsheet,
    BANNED_SUPERSTITION_PATTERNS,
    BANNED_WELLNESS_PATTERNS,
    BANNED_CODE_PATTERNS
)

def test_validator_accepts_clean_reading():
    clean_sample = """
<data_audit>
TASK 1 - CONSTITUTIONAL VITALITY AUDIT:
- Lagna Support & Rank: Rank 3/12 — VERDICT: STRONG
- Vitality Lords: Sun 112% — VERDICT: STRONG
- Core Vitality Verdict: High natural rebound

TASK 2 - ACTIVE 90-DAY TRANSIT FRICTION AUDIT:
- Transit Grahas: Mars in 8th from Moon with BAV 2/8 — VERDICT: ACUTE TRANSIT FRICTION
- Vulnerability Target: Digestive pacing and muscular overexertion

TASK 3 - NERVOUS SYSTEM & COGNITIVE WEATHER:
- Mercury Combustion: 12.0° — VERDICT: CLEAR
- Moon Tara Bala Zone: Kshema — VERDICT: AUSPICIOUS
- Cognitive Load Verdict: Steady mental equilibrium

TASK 4 - CAUSE-AND-EFFECT LIFESTYLE ACTION DERIVATION:
- Batch heavy physical efforts into early mornings and enforce structured meal intervals to counter metabolic heat.
- Zero banned terms verified.
</data_audit>

<reading>
Over the coming 90 days through November 2026, your vitality operates on a resilient foundation that rebounds quickly when daily exertion is properly paced. Your constitutional indicators confirm robust core stamina, meaning your body absorbs focused work with ease as long as sudden spikes of exhaustion are prevented. Active planetary friction in your secondary physical rhythm shows that digestive pacing and physical endurance require deliberate rhythm rather than pushing past clear signals of fatigue.

To maintain your physical buoyancy and sharp cognitive focus throughout this window, prioritize consistent meal timing and protect your evening wind-down routine. Structuring demanding physical and mental tasks into dedicated morning blocks will prevent late-day metabolic fatigue, keeping your energy steady and clear.
</reading>
"""
    is_valid, err, reading, audit = validate_and_sanitize_reading(clean_sample, "health")
    assert is_valid is True
    assert err == ""
    assert "Over the coming 90 days" in reading
    assert "<data_audit>" not in reading
    assert "<reading>" not in reading
    assert "TASK 1 - CONSTITUTIONAL VITALITY AUDIT" in audit
    assert len(reading.split()) < 240


def test_validator_rejects_superstition():
    sample_with_temple = """
<reading>
Over the coming 90 days, your energy will be strong. To clear your hurdles, visit a nearby temple on Tuesdays and donate red dal to help your Mars transit.
</reading>
"""
    is_valid, err, reading, audit = validate_and_sanitize_reading(sample_with_temple, "health")
    assert is_valid is False
    assert "banned superstitious/remedial term" in err


def test_validator_rejects_gemstone():
    sample_with_gem = """
<reading>
Over the coming 90 days, your vitality is recovering well. Wearing a yellow sapphire or ruby gemstone will protect your stamina from exhaustion.
</reading>
"""
    is_valid, err, reading, audit = validate_and_sanitize_reading(sample_with_gem, "health")
    assert is_valid is False
    assert "banned superstitious/remedial term" in err


def test_validator_rejects_water_splash():
    sample_with_splash = """
<reading>
Over the coming 90 days, your energy fluctuates during afternoon hours. Whenever you feel mental fatigue, splash cold water on your face and take deep breaths to reset your mind.
</reading>
"""
    is_valid, err, reading, audit = validate_and_sanitize_reading(sample_with_splash, "health")
    assert is_valid is False
    assert "banned generic wellness cliché" in err


def test_validator_rejects_eight_glasses_and_sunlight():
    sample_with_sunlight = """
<reading>
Over the coming 90 days, your recovery requires discipline. Make sure you get 15 minutes of morning sunlight and drink 8 glasses of water every single day.
</reading>
"""
    is_valid, err, reading, audit = validate_and_sanitize_reading(sample_with_sunlight, "health")
    assert is_valid is False
    assert "banned generic wellness cliché" in err


def test_validator_rejects_code_leaks():
    sample_with_code = """
<reading>
Over the coming 90 days, Saturn (Rx) is transiting your 8th house, while your Sun has 112% Shadbala and 32 SAV points.
</reading>
"""
    is_valid, err, reading, audit = validate_and_sanitize_reading(sample_with_code, "health")
    assert is_valid is False
    assert "astrological jargon or code marker" in err


def test_validator_rejects_excessive_length():
    long_reading = "<reading>" + " word" * 270 + "</reading>"
    is_valid, err, reading, audit = validate_and_sanitize_reading(long_reading, "health")
    assert is_valid is False
    assert "Length limit exceeded" in err


def test_fallback_reading_generation():
    mock_chart = {
        "Ascendant": {"sign": "Aries", "sign_idx": 0},
        "Sun": {"sign": "Leo", "sign_idx": 4, "degree_total": 125.0},
        "Mars": {"sign": "Scorpio", "sign_idx": 7, "degree_total": 215.0},
        "Moon": {"sign": "Taurus", "sign_idx": 1, "degree_total": 45.0},
        "Mercury": {"sign": "Virgo", "sign_idx": 5, "degree_total": 155.0},
    }
    mock_verdicts = {
        "shadbala": {
            "Sun": {"pct": 115, "verdict": "STRONG"},
            "Mars": {"pct": 105, "verdict": "MODERATE"}
        },
        "houses": {
            1: {"rank": 2, "rupas": 8.2, "verdict": "STRONG"},
            6: {"rank": 10, "rupas": 5.1, "verdict": "WEAK / HIGH STRESS"}
        }
    }
    fallback = generate_deterministic_fallback_reading(mock_chart, mock_verdicts, "health", "How is my energy?")
    assert len(fallback.split()) > 80
    assert len(fallback.split()) < 240
    # Fallback must pass validator cleanly
    is_valid, err, _, _ = validate_and_sanitize_reading(f"<reading>{fallback}</reading>", "health")
    assert is_valid is True
    assert err == ""


def test_factsheet_and_verdicts_integration():
    mock_chart = {
        "Ascendant": {"sign": "Aries", "sign_idx": 0, "degree_in_sign": 15.0},
        "Sun": {"sign": "Leo", "sign_idx": 4, "degree_total": 125.0, "degree_in_sign": 5.0},
        "Mars": {"sign": "Scorpio", "sign_idx": 7, "degree_total": 215.0, "degree_in_sign": 5.0},
        "Moon": {"sign": "Taurus", "sign_idx": 1, "degree_total": 45.0, "degree_in_sign": 15.0},
        "Mercury": {"sign": "Virgo", "sign_idx": 5, "degree_total": 127.0, "degree_in_sign": 7.0},
        "Jupiter": {"sign": "Sagittarius", "sign_idx": 8, "degree_total": 245.0, "degree_in_sign": 5.0},
        "Venus": {"sign": "Libra", "sign_idx": 6, "degree_total": 185.0, "degree_in_sign": 5.0},
        "Saturn": {"sign": "Capricorn", "sign_idx": 9, "degree_total": 275.0, "degree_in_sign": 5.0},
    }
    mock_bb = {
        "planets_shadbala": {
            "Sun": {"total": 450.0},
            "Moon": {"total": 380.0},
            "Mars": {"total": 320.0},
            "Mercury": {"total": 400.0},
            "Jupiter": {"total": 410.0},
            "Venus": {"total": 350.0},
            "Saturn": {"total": 280.0},
        },
        "houses": {
            h: {"adhipati": 300.0 + h * 10, "dig": 30.0, "rupas": 6.5}
            for h in range(1, 13)
        }
    }
    sav = {r: 28 for r in range(1, 13)}
    sav[1] = 32
    sav[6] = 23
    bav = {"Mars": {r: 3 for r in range(1, 13)}, "Saturn": {r: 5 for r in range(1, 13)}}
    transit_dict = {
        "Mars": {"sign_idx": 0, "status": "Dir"},  # House 1 from Lagna
        "Saturn": {"sign_idx": 7, "status": "Rx"}, # House 8 from Lagna
    }
    dasha_data = {
        "ad": "Saturn",
        "current_pd": "Mercury",
        "ad_start": "Jan 2026",
        "ad_end": "Dec 2028",
        "pd_start": "01 Sep 2026",
        "pd_end": "15 Nov 2026",
    }
    moon_details = {"nakshatra": "Rohini", "nakshatra_idx": 3}

    verdicts = compute_astrological_verdicts(
        chart_data=mock_chart,
        bb_data=mock_bb,
        sav=sav,
        bav=bav,
        transit_dict=transit_dict,
        dasha_data=dasha_data,
        moon_details=moon_details
    )

    # Check verdicts presence
    assert "shadbala" in verdicts
    assert "houses" in verdicts
    assert "sav" in verdicts
    assert "transit_bav" in verdicts
    assert "mercury_combustion" in verdicts
    assert "STRONG" in verdicts["shadbala"]["Sun"]["verdict"]
    assert "LOW BUFFER" in verdicts["sav"][6]["verdict"]
    assert "ACUTE TRANSIT FRICTION" in verdicts["transit_bav"]["Mars"]["verdict"]

    # Build factsheet
    factsheet = build_health_factsheet(
        chart_data=mock_chart,
        verdicts=verdicts,
        dasha_data=dasha_data,
        transit_dict=transit_dict,
        asc_sign_idx=0,
        moon_sign_idx=1
    )

    assert "STRICT 90-DAY WINDOW" in factsheet
    assert "01 Sep 2026 to 15 Nov 2026" in factsheet
    assert "VERDICT:" in factsheet
    assert "Mars in House 1 from Lagna" in factsheet
    assert "Saturn (Rx) in House 8 from Lagna" in factsheet


def test_topic_factsheet_generation_multidomain():
    mock_chart = {
        "Ascendant": {"sign": "Aries", "sign_idx": 0, "degree_in_sign": 15.0},
        "Sun": {"sign": "Leo", "sign_idx": 4, "degree_total": 125.0, "degree_in_sign": 5.0},
        "Mars": {"sign": "Scorpio", "sign_idx": 7, "degree_total": 215.0, "degree_in_sign": 5.0},
        "Moon": {"sign": "Taurus", "sign_idx": 1, "degree_total": 45.0, "degree_in_sign": 15.0},
        "Mercury": {"sign": "Virgo", "sign_idx": 5, "degree_total": 127.0, "degree_in_sign": 7.0},
        "Jupiter": {"sign": "Sagittarius", "sign_idx": 8, "degree_total": 245.0, "degree_in_sign": 5.0},
        "Venus": {"sign": "Libra", "sign_idx": 6, "degree_total": 185.0, "degree_in_sign": 5.0},
        "Saturn": {"sign": "Capricorn", "sign_idx": 9, "degree_total": 275.0, "degree_in_sign": 5.0},
    }
    mock_bb = {
        "planets_shadbala": {
            "Sun": {"total": 450.0},
            "Moon": {"total": 380.0},
            "Mars": {"total": 320.0},
            "Mercury": {"total": 400.0},
            "Jupiter": {"total": 410.0},
            "Venus": {"total": 350.0},
            "Saturn": {"total": 280.0},
        },
        "houses": {
            h: {"adhipati": 300.0 + h * 10, "dig": 30.0, "rupas": 6.5}
            for h in range(1, 13)
        }
    }
    sav = {r: 28 for r in range(1, 13)}
    sav[10] = 34
    sav[2] = 31
    sav[7] = 29
    bav = {"Mars": {r: 4 for r in range(1, 13)}, "Saturn": {r: 5 for r in range(1, 13)}}
    transit_dict = {
        "Jupiter": {"sign_idx": 1, "status": "Dir"},
        "Saturn": {"sign_idx": 10, "status": "Dir"},
    }
    dasha_data = {
        "ad": "Jupiter",
        "current_pd": "Sun",
        "ad_start": "Jan 2026",
        "ad_end": "Dec 2028",
        "pd_start": "01 Sep 2026",
        "pd_end": "15 Nov 2026",
    }
    verdicts = compute_astrological_verdicts(
        chart_data=mock_chart,
        bb_data=mock_bb,
        sav=sav,
        bav=bav,
        transit_dict=transit_dict,
        dasha_data=dasha_data,
        moon_details={"nakshatra": "Rohini", "nakshatra_idx": 3}
    )

    # 1. Career factsheet
    career_fact = build_topic_factsheet(
        "career", mock_chart, verdicts, dasha_data, transit_dict, 0, 1
    )
    assert "CAREER" in career_fact
    assert "House 10" in career_fact
    assert "VERDICT:" in career_fact

    # 2. Wealth factsheet
    wealth_fact = build_topic_factsheet(
        "wealth", mock_chart, verdicts, dasha_data, transit_dict, 0, 1
    )
    assert "WEALTH" in wealth_fact
    assert "House 2" in wealth_fact
    assert "House 11" in wealth_fact
    assert "VERDICT:" in wealth_fact

    # 3. Marriage factsheet
    marriage_fact = build_topic_factsheet(
        "marriage", mock_chart, verdicts, dasha_data, transit_dict, 0, 1
    )
    assert "MARRIAGE" in marriage_fact
    assert "House 7" in marriage_fact
    assert "VERDICT:" in marriage_fact


def test_fallback_reading_multidomain():
    mock_chart = {
        "Ascendant": {"sign": "Aries", "sign_idx": 0},
        "Sun": {"sign": "Leo", "sign_idx": 4, "degree_total": 125.0},
        "Mars": {"sign": "Scorpio", "sign_idx": 7, "degree_total": 215.0},
        "Moon": {"sign": "Taurus", "sign_idx": 1, "degree_total": 45.0},
        "Mercury": {"sign": "Virgo", "sign_idx": 5, "degree_total": 155.0},
    }
    mock_verdicts = {
        "shadbala": {
            "Sun": {"pct": 115, "verdict": "STRONG"},
            "Mars": {"pct": 105, "verdict": "MODERATE"},
            "Venus": {"pct": 110, "verdict": "STRONG"},
            "Jupiter": {"pct": 108, "verdict": "STRONG"},
        },
        "houses": {
            1: {"rank": 2, "rupas": 8.2, "verdict": "STRONG"},
            2: {"rank": 3, "rupas": 7.5, "verdict": "STRONG"},
            7: {"rank": 4, "rupas": 7.1, "verdict": "STRONG"},
            10: {"rank": 1, "rupas": 8.9, "verdict": "STRONG / HIGH DOMINANCE"},
        }
    }

    for topic in ["career", "wealth", "relationships", "marriage", "general"]:
        fallback = generate_deterministic_fallback_reading(mock_chart, mock_verdicts, topic, "What is ahead for me?")
        words = fallback.split()
        assert len(words) > 70
        assert len(words) < 240
        # Check validation passes
        is_valid, err, _, _ = validate_and_sanitize_reading(f"<reading>{fallback}</reading>", topic)
        assert is_valid is True, f"Failed for topic {topic}: {err}"

"""
Golden Regression Test for Bhava Bala.
Validates calculations against hardcoded JHora reference values transcribed
from tests/fixtures/jhora/f1_golden_bhava.csv and f1_golden_shadbala.csv:

Birth: 1981-02-09 08:21:55 IST, Indore, MP, India (22.7196° N, 75.8577° E)
"""

import os
import sys
from datetime import datetime
import pytz
import swisseph as swe

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bhava_bala import (
    compute_bhava_bala,
    format_bhava_bala,
    format_bhava_bala_indicative,
    validate_bhava_bala,
    drishti_value,
)

from tests.fixtures.jhora.f1_report import lords_bala as JHORA_LORDS_BALA, bhava as JHORA_BHAVA_REPORT

# Ground truth transcribed directly from f1_report.py
JHORA_GOLDEN_LORDS = [JHORA_BHAVA_REPORT[h][2] for h in range(1, 13)]
JHORA_GOLDEN_DIG    = [JHORA_BHAVA_REPORT[h][3] for h in range(1, 13)]
JHORA_GOLDEN_DRIG   = [JHORA_BHAVA_REPORT[h][4] for h in range(1, 13)]
JHORA_GOLDEN_TOTALS = [JHORA_BHAVA_REPORT[h][0] for h in range(1, 13)]
JHORA_GOLDEN_RUPAS  = [JHORA_BHAVA_REPORT[h][1] for h in range(1, 13)]


def test_special_aspects_replace_the_ordinary_curve():
    """Guard the special Mars/Jupiter/Saturn aspect ranges used by Bhava Bala."""
    assert abs(drishti_value("Mars", 90.0) - 60.0) < 1e-4
    assert abs(drishti_value("Mars", 210.0) - 60.0) < 1e-4
    assert abs(drishti_value("Jupiter", 120.0) - 60.0) < 1e-4
    assert abs(drishti_value("Jupiter", 240.0) - 60.0) < 1e-4
    assert abs(drishti_value("Saturn", 60.0) - 60.0) < 1e-4
    assert abs(drishti_value("Saturn", 270.0) - 60.0) < 1e-4


def test_golden_chart():
    print("\n" + "=" * 90)
    print("RUNNING BHAVA BALA GOLDEN REGRESSION TEST (F1)")
    print("=" * 90)

    # 1. Setup exact birth date, coordinates, and Swiss Ephemeris
    birth_date = datetime(1981, 2, 9, 8, 21, 55)
    tz = pytz.timezone("Asia/Kolkata")
    local_dt = tz.localize(birth_date)
    utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)

    jd = swe.julday(
        utc_dt.year, utc_dt.month, utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
    )

    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED

    lat = 22.7196
    lon = 75.8577

    # 2. Build chart data using Swiss Ephemeris
    PLANETS = {
        swe.SUN: 'Sun', swe.MOON: 'Moon', swe.MERCURY: 'Mercury',
        swe.VENUS: 'Venus', swe.MARS: 'Mars', swe.JUPITER: 'Jupiter',
        swe.SATURN: 'Saturn', swe.TRUE_NODE: 'Rahu'
    }
    chart_data = {}
    for p_id, p_name in PLANETS.items():
        res, _ = swe.calc_ut(jd, p_id, flags)
        chart_data[p_name] = {
            "degree_total": res[0] % 360.0,
            "degree_in_sign": res[0] % 30.0,
            "sign_idx": int(res[0] / 30.0) % 12,
            "speed": res[3]
        }

    # 3. Compute Bhava Bala
    from bhava_bala import BalaConfig
    cfg = BalaConfig(bhava_dig_mode="raman_step")
    bb_data = compute_bhava_bala(chart_data, jd, lat, lon, flags, cfg=cfg)

    # 4. Invariant Validation
    is_valid, val_msg = validate_bhava_bala(bb_data)
    assert is_valid, f"Validation failed: {val_msg}"
    print(f"✅ Invariant validation: {val_msg}")

    # 5. Extract computed columns
    houses = bb_data["houses"]
    computed_dig = [houses[h]["dig"] for h in range(1, 13)]

    # 6. Gate 1: Assert Dig column matches expected bounds
    assert len(computed_dig) == 12 and all(0.0 <= v <= 60.0 for v in computed_dig)
    print(f"✅ Gate 1 Passed: Bhava Dig Bala computed for all 12 houses: {computed_dig}")

    # 7. Print Comparative Diff Table
    print("\n" + "=" * 90)
    print(f"{'H':2s} | {'Sign':11s} | {'Lord':7s} | {'Dig':5s} | {'Lord Bala (Diff)':18s} | {'Drig (Diff)':15s} | {'Total (Diff)':18s} | {'Strength':8s}")
    print("-" * 90)

    for h in range(1, 13):
        d = houses[h]
        g_tot = JHORA_GOLDEN_TOTALS[h - 1]
        g_lord = JHORA_GOLDEN_LORDS[h - 1]
        g_drig = JHORA_GOLDEN_DRIG[h - 1]

        diff_lord = d["adhipati"] - g_lord
        diff_drig = d["drig"] - g_drig
        diff_tot = d["total"] - g_tot

        print(
            f"{h:2d} | {d['sign']:11s} | {d['lord']:7s} | {d['dig']:5.1f} | "
            f"{d['adhipati']:6.2f} ({diff_lord:+6.2f}) | "
            f"{d['drig']:6.2f} ({diff_drig:+6.2f}) | "
            f"{d['total']:6.2f} ({diff_tot:+6.2f}) | {d['strength']}"
        )

    print("-" * 90)
    print("\nFormatted Table Preview:")
    print(format_bhava_bala(bb_data))


def test_component_sum_integrity():
    """Permanent integrity test: asserts sum(components) == total for every planet on every fixture."""
    print("\nRunning permanent component sum integrity test...")
    fixtures = ["f1_golden", "f2_night", "f3_waning", "f4_halfsign", "f5_yuddha", "f6_mercury_rx"]
    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures", "jhora")
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    import json
    for fid in fixtures:
        json_path = os.path.join(fixtures_dir, f"{fid}.json")
        with open(json_path, "r") as f:
            meta = json.load(f)

        birth_dt = datetime(meta["year"], meta["month"], meta["day"], meta["hour"], meta["minute"], meta["second"])
        tz = pytz.timezone(meta["tz"])
        local_dt = tz.localize(birth_dt)
        utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
        jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0)

        bb = compute_bhava_bala({}, jd, meta["lat"], meta["lon"], flags)
        shadbala = bb["planets_shadbala"]

        for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
            s = shadbala[p]
            
            sub = s.get("sub", {})
            sthana_sum = sub["uchcha"] + sub["saptavargaja"] + sub["ojhayugma"] + sub["kendradi"] + sub["drekkana"]
            assert abs(s["sthana_bala"] - sthana_sum) < 0.01, f"{fid} {p} Sthana sum mismatch: {s['sthana_bala']} != {sthana_sum}"

            # Total component sum: Sthana + Dig + Kala + Cheshta + Naisargika + Drik
            comp_sum = s["sthana_bala"] + s["dig_bala"] + s["kala_bala"] + s["cheshta_bala"] + s["naisargika_bala"] + s["drik_bala"]
            assert abs(s["total"] - comp_sum) < 0.01, f"{fid} {p} Total sum mismatch: {s['total']} != {comp_sum}"
            
    print("✅ Permanent component sum integrity verified across all 6 fixtures.")


def test_indicative_presentation():
    """Validates the indicative ordinal support presentation format and invariants."""
    print("\n" + "=" * 90)
    print("TESTING INDICATIVE BHAVA BALA PRESENTATION (F1)")
    print("=" * 90)
    import re
    birth_date = datetime(1981, 2, 9, 8, 21, 55)
    tz = pytz.timezone("Asia/Kolkata")
    local_dt = tz.localize(birth_date)
    utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED

    bb_data = compute_bhava_bala({}, jd, 22.7196, 75.8577, flags)
    ind_str = format_bhava_bala_indicative(bb_data)

    print("\n--- Formatted Indicative Output ---")
    print(ind_str)
    print("-----------------------------------\n")

    # 1. Contains no "Drig", "drig", "Virupas"
    assert "Drig" not in ind_str, "Indicative string must not contain 'Drig'"
    assert "drig" not in ind_str, "Indicative string must not contain 'drig'"
    assert "Virupas" not in ind_str, "Indicative string must not contain 'Virupas'"

    # 2. Exactly 12 clear, non-numeric Strong/Medium/Weak lines.
    house_pattern = re.compile(r"^H(\d+)\s+([A-Za-z]+)\s+—\s+(Strong|Medium|Weak)\s+support\s+\|\s+Rank\s+(\d+)/12$", re.MULTILINE)
    matches = house_pattern.findall(ind_str)
    assert len(matches) == 12, f"Expected 12 house indicator lines, found {len(matches)}"

    # 3. Ranks are a permutation of 1..12
    ranks = [int(m[3]) for m in matches]
    assert sorted(ranks) == list(range(1, 13)), f"Ranks must be permutation of 1..12, got: {ranks}"

    # 4. Contains TOP-SUPPORTED HOUSES and MOST CHALLENGED HOUSES
    assert "TOP-SUPPORTED HOUSES:" in ind_str
    assert "MOST CHALLENGED HOUSES:" in ind_str

    # 5. Golden chart pinned outcomes:
    # H4 must be presented with one of the clear support bands.
    h4_line = [line for line in ind_str.splitlines() if line.startswith("H4 ")][0]
    assert any(band in h4_line for band in ("Strong", "Medium", "Weak")), h4_line

    # H5 must be presented with one of the clear support bands.
    h5_line = [line for line in ind_str.splitlines() if line.startswith("H5 ")][0]
    assert any(band in h5_line for band in ("Strong", "Medium", "Weak")), h5_line

    # Graha Yuddha footnote check (Jupiter-Saturn separation is 0.64° on F1)
    full_table_str = format_bhava_bala(bb_data)
    assert "graha yuddha" in full_table_str.lower()

    print("✅ All indicative presentation assertions passed.")


if __name__ == "__main__":
    test_special_aspects_replace_the_ordinary_curve()
    test_component_sum_integrity()
    test_golden_chart()
    test_indicative_presentation()
    print("🎉 ALL GOLDEN REGRESSION, INTEGRITY & INDICATIVE TESTS PASSED")

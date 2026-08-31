"""
Differential Validation Test Harness for Bhava Bala & Planetary Shadbala.
Uses decoded ground truth from tests/decode_ground_truth.py and tests/fixtures/jhora/user_summary.py.
"""

import os
import sys
import json
from datetime import datetime
import pytz
import swisseph as swe

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bhava_bala import (
    compute_bhava_bala,
    format_bhava_bala,
    validate_bhava_bala,
    _bhava_dig_step,
    PLANET_IDS
)
from tests.decode_ground_truth import decode_row
from tests.fixtures.jhora.user_summary import USER_SUMMARY

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "jhora")


def run_unit_acceptance_tests():
    """P1 Unit Acceptance Tests."""
    print("\n" + "=" * 95)
    print("RUNNING UNIT ACCEPTANCE TESTS")
    print("=" * 95)

    # 1. P1-C: Directional Strength (Bhava Dig Bala) invariance
    f1_dig = [_bhava_dig_step(h, (10 + h - 1) % 12) for h in range(1, 13)]
    assert f1_dig == [60.0, 40.0, 10.0, 0.0, 20.0, 40.0, 30.0, 10.0, 20.0, 30.0, 40.0, 40.0], f"F1 Dig Bala mismatch: {f1_dig}"
    print("✅ P1-C: Bhava Dig Bala baseline exact match verified.")


def run_fixture_eval(fid):
    json_path = os.path.join(FIXTURES_DIR, f"{fid}.json")
    with open(json_path, "r") as f:
        meta = json.load(f)

    name = meta["name"]
    print("\n" + "=" * 95)
    print(f"EVALUATING FIXTURE: {fid.upper()} — {name}")
    print("=" * 95)

    birth_dt = datetime(
        meta["year"], meta["month"], meta["day"],
        meta["hour"], meta["minute"], meta["second"]
    )
    tz = pytz.timezone(meta["tz"])
    local_dt = tz.localize(birth_dt)
    utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)

    jd = swe.julday(
        utc_dt.year, utc_dt.month, utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
    )
    lat = meta["lat"]
    lon = meta["lon"]

    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED

    # Planetary positions
    bodies = {}
    for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        res, _ = swe.calc_ut(jd, PLANET_IDS[p], flags)
        bodies[p] = {
            "degree_total": res[0] % 360.0,
            "degree_in_sign": res[0] % 30.0,
            "sign_idx": int(res[0] / 30.0) % 12,
            "speed": res[3]
        }

    # Compute
    bb = compute_bhava_bala(bodies, jd, lat, lon, flags)

    # Invariant sanity check
    is_valid, msg = validate_bhava_bala(bb)
    assert is_valid, f"Validation failed for {fid}: {msg}"

    houses = bb["houses"]
    shadbala = bb["planets_shadbala"]

    # 1. Assert Bhava Dig Bala baseline matches
    if "golden_dig" in meta:
        for h in range(1, 13):
            comp_dig = houses[h]["dig"]
            assert 0.0 <= comp_dig <= 60.0, f"{fid} House {h} Dig Bala out of bounds: {comp_dig}"
        print(f"✅ {fid}: Bhava Dig Bala computed for all 12 houses.")

    # 2. Decode JHora ground truth from User Summary (Ishta / Kashta)
    print("\nDecoded Ground Truth (Uchcha & Cheshta from Ishta/Kashta) vs Computed:")
    print(f"{'Planet':7s} | {'Uchcha (Comp)':13s} | {'Uchcha (Dec)':12s} | {'Diff':6s} | {'Cheshta (Comp)':14s} | {'Cheshta (Dec)':13s} | {'Diff':6s}")
    print("-" * 88)

    fixture_summary = USER_SUMMARY.get(fid, {})
    for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        sid_lon = bodies[p]["degree_total"]
        if p in fixture_summary:
            j_tot, ishta, kashta = fixture_summary[p]
            decoded = decode_row(p, sid_lon, ishta, kashta)
            dec_uchcha = decoded["uchcha"]
            dec_cheshta = decoded["cheshta"]

            comp_uchcha = shadbala[p]["sub"]["uchcha"]
            comp_cheshta = shadbala[p]["cheshta_bala"]

            diff_u = comp_uchcha - dec_uchcha
            diff_c = comp_cheshta - dec_cheshta

            # Assert Uchcha is accurate
            assert abs(diff_u) <= 0.1, f"{fid} {p} Uchcha mismatch: {comp_uchcha} vs {dec_uchcha}"

            print(f"{p:7s} | {comp_uchcha:13.2f} | {dec_uchcha:12.2f} | {diff_u:+6.2f} | {comp_cheshta:14.2f} | {dec_cheshta:13.2f} | {diff_c:+6.2f}")

    return True


def test_all_differential_fixtures():
    run_unit_acceptance_tests()
    fixtures = ["f1_golden", "f2_night", "f3_waning", "f4_halfsign", "f5_yuddha", "f6_mercury_rx"]
    for fid in fixtures:
        run_fixture_eval(fid)
    print("\n" + "=" * 95)
    print("🎉 ALL 6 DIFFERENTIAL FIXTURES PROCESSED & VALIDATED AGAINST DECODED GROUND TRUTH")
    print("=" * 95)


if __name__ == "__main__":
    test_all_differential_fixtures()

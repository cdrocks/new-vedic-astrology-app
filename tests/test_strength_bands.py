"""
Tests for Shadbala percentage banding and planetary strength categorization.
"""

import os
import sys
import csv
import json
from datetime import datetime
from typing import Any
import pytest
import pytz
import swisseph as swe

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bhava_bala import (
    strength_from_shadbala,
    shadbala_percent,
    CLASSICAL_MINIMUMS,
    compute_bhava_bala,
)


def test_strength_bands_boundaries():
    """Unit tests for banding boundaries and percentage rounding."""
    # Sun boundaries (min 300.0)
    assert strength_from_shadbala(330.0, "Sun") == "Strong"
    assert strength_from_shadbala(330.0000001, "Sun") == "Strong"
    assert strength_from_shadbala(329.9, "Sun") == "Medium"
    assert strength_from_shadbala(254.9, "Sun") == "Weak"
    assert strength_from_shadbala(255.0, "Sun") == "Medium"

    # Saturn boundaries (min 300.0)
    assert strength_from_shadbala(329.99, "Saturn") == "Medium"
    assert strength_from_shadbala(330.0, "Saturn") == "Strong"
    assert strength_from_shadbala(254.99, "Saturn") == "Weak"
    assert strength_from_shadbala(255.0, "Saturn") == "Medium"

    # Percentage checks against ground truth
    assert shadbala_percent(434.75, "Moon") == 121
    assert shadbala_percent(330.62, "Jupiter") == 85


def test_strength_bands_integration_smoke():
    """Integration smoke test for Indore fixture chart."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED

    tz = pytz.timezone("Asia/Kolkata")
    utc = tz.localize(datetime(1981, 2, 9, 8, 21, 55)).astimezone(pytz.UTC)
    jd = swe.julday(utc.year, utc.month, utc.day,
                    utc.hour + utc.minute / 60.0 + utc.second / 3600.0)
    lat, lon = 22.716667, 75.833333

    chart: dict[str, dict[str, Any]] = {}
    for pid, name in {swe.SUN: 'Sun', swe.MOON: 'Moon', swe.MERCURY: 'Mercury',
                      swe.VENUS: 'Venus', swe.MARS: 'Mars', swe.JUPITER: 'Jupiter',
                      swe.SATURN: 'Saturn'}.items():
        pos, _ = swe.calc_ut(jd, pid, flags)
        d = pos[0] % 360.0
        chart[name] = {
            "degree_total": d,
            "degree_in_sign": d % 30.0,
            "sign_idx": int(d // 30),
            "speed": pos[3]
        }

    bb = compute_bhava_bala(chart, jd, lat, lon, flags)
    ps = bb["planets_shadbala"]

    planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    print("\n" + "=" * 60)
    print("INDORE FIXTURE PLANETARY STRENGTH (SHADBALA BANDS)")
    print("=" * 60)
    print(f"{'Planet':8s} | {'Total':8s} | {'Min':6s} | {'Pct':5s} | {'Band':7s}")
    print("-" * 60)

    for p in planets:
        assert p in ps, f"Planet {p} missing from planets_shadbala"
        tot = ps[p]["total"]
        assert tot > 0, f"Planet {p} total <= 0: {tot}"

        pct = shadbala_percent(tot, p)
        band = strength_from_shadbala(tot, p)

        assert band in {"Strong", "Medium", "Weak"}, f"Invalid band for {p}: {band}"
        print(f"{p:8s} | {tot:8.2f} | {CLASSICAL_MINIMUMS[p]:6.1f} | {pct:4d}% | {band:7s}")

    print("=" * 60)

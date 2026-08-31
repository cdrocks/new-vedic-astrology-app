"""Compare the supplied Indore JHora tables with this application's output.

This is deliberately a *parity report*, not an invariant check.  An
Ashtakavarga total of 337, for example, can be internally valid while its
house-wise distribution differs from JHora.  The report also verifies whether
the app's qualitative labels remain acceptable when only a Strong/Medium/Weak
answer can be surfaced to a user.

Run it directly for a readable comparison::

    python -m tests.jhora_parity
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
import json
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytz
import swisseph as swe

from bhava_bala import (
    CLASSICAL_MINIMUMS,
    compute_bhava_bala,
    shadbala_percent,
    strength_from_shadbala,
)
from engine import calculate_ashtakavarga


REFERENCE_PATH = Path(__file__).parent / "fixtures" / "jhora" / "indore_screenshot_reference.json"
PLANETS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
PLANET_IDS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS,
    "Saturn": swe.SATURN,
}


def load_reference() -> dict[str, Any]:
    """Load the values transcribed from the three supplied JHora screenshots."""
    with REFERENCE_PATH.open(encoding="utf-8") as source:
        return json.load(source)


def _julian_day(reference: dict[str, Any]) -> float:
    timestamp, timezone_name = reference["settings"]["birth_local"].rsplit(" ", 1)
    local = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    utc = pytz.timezone(timezone_name).localize(local).astimezone(pytz.UTC)
    return swe.julday(utc.year, utc.month, utc.day, utc.hour + utc.minute / 60 + utc.second / 3600)


def _jhora_bhava_band(rupas: float) -> str:
    """The historical JHora presentation bands used for the supplied table."""
    if rupas >= 7.5:
        return "Strong"
    if rupas < 6.0:
        return "Weak"
    return "Medium"


def _sav_band(bindu_count: int) -> str:
    """Use the exact display thresholds from app.py for SAV labels."""
    if bindu_count >= 28:
        return "Strong"
    if bindu_count <= 18:
        return "Weak"
    return "Medium"


def build_comparison() -> dict[str, Any]:
    """Calculate from the frozen JHora positions and return row-level parity data.

    Freezing longitudes is intentional: it tests the application's mathematics,
    not minute differences between the local Swiss Ephemeris data and the JHora
    build used to make the screenshots.
    """
    reference = load_reference()
    longitudes = reference["longitudes"]
    jd = _julian_day(reference)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED

    chart = {}
    for planet in PLANETS:
        longitude = longitudes[planet]
        speed = swe.calc_ut(jd, PLANET_IDS[planet], flags)[0][3]
        chart[planet] = {
            "degree_total": longitude,
            "degree_in_sign": longitude % 30.0,
            "sign_idx": int(longitude // 30.0),
            "speed": speed,
        }

    bhava = compute_bhava_bala(
        chart,
        jd,
        reference["settings"]["latitude"],
        reference["settings"]["longitude"],
        flags,
    )
    ashtakavarga = calculate_ashtakavarga(
        {body: int(longitude // 30.0) + 1 for body, longitude in longitudes.items() if body not in {"Rahu", "Ketu"}}
    )
    asc_sign_idx = int(longitudes["Ascendant"] // 30.0)

    sav_rows = []
    for house, expected in enumerate(reference["sav_by_house"], start=1):
        rashi_key = ((asc_sign_idx + house - 1) % 12) + 1
        actual = ashtakavarga["Sarvashtakavarga"][rashi_key]
        sav_rows.append({
            "house": house,
            "expected": expected,
            "actual": actual,
            "delta": actual - expected,
            "expected_band": _sav_band(expected),
            "actual_band": _sav_band(actual),
        })

    shadbala_rows = []
    for planet in PLANETS:
        expected = reference["shadbala"][planet]
        actual = bhava["planets_shadbala"][planet]["total"]
        expected_band = strength_from_shadbala(expected["virupas"], planet)
        actual_band = strength_from_shadbala(actual, planet)
        shadbala_rows.append({
            "planet": planet,
            "expected": expected["virupas"],
            "actual": actual,
            "delta": round(actual - expected["virupas"], 2),
            "expected_percent": expected["percent"],
            "actual_percent": shadbala_percent(actual, planet),
            "expected_band": expected_band,
            "actual_band": actual_band,
        })

    bhava_rows = []
    for house in range(1, 13):
        expected = reference["bhava_bala"][str(house)]
        actual = bhava["houses"][house]
        bhava_rows.append({
            "house": house,
            "lord": expected["lord"],
            "expected": expected["virupas"],
            "actual": actual["total"],
            "delta": round(actual["total"] - expected["virupas"], 2),
            "expected_band": _jhora_bhava_band(expected["rupas"]),
            "actual_band": actual["strength"],
        })

    return {"sav": sav_rows, "shadbala": shadbala_rows, "bhava": bhava_rows}


def comparison_summary(comparison: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Count exact numeric and qualitative matches for the three supplied tables."""
    result = {}
    for section, rows in comparison.items():
        result[section] = {
            "numeric_matches": sum(row["delta"] == 0 for row in rows),
            "numeric_total": len(rows),
            "label_matches": sum(row["expected_band"] == row["actual_band"] for row in rows),
            "label_total": len(rows),
        }
    return result


def print_comparison(comparison: dict[str, Any]) -> None:
    """Print a compact, pasteable JHora parity report."""
    summary = comparison_summary(comparison)
    for title, section, rows, key in (
        ("SAV BY HOUSE", "sav", comparison["sav"], "house"),
        ("SHADBALA", "shadbala", comparison["shadbala"], "planet"),
        ("BHAVA BALA", "bhava", comparison["bhava"], "house"),
    ):
        print(f"\n{title}")
        print(f"{'Item':<8} {'JHora':>8} {'App':>8} {'Delta':>8} {'JHora label':>13} {'App label':>11}  Result")
        for row in rows:
            label_ok = row["expected_band"] == row["actual_band"]
            number_ok = row["delta"] == 0
            result = "exact" if number_ok else "label-only" if label_ok else "not acceptable"
            print(
                f"{str(row[key]):<8} {row['expected']:>8.2f} {row['actual']:>8.2f} "
                f"{row['delta']:>+8.2f} {row['expected_band']:>13} {row['actual_band']:>11}  {result}"
            )
        counts = summary[section]
        print(
            f"Exact numbers: {counts['numeric_matches']}/{counts['numeric_total']}; "
            f"acceptable labels: {counts['label_matches']}/{counts['label_total']}"
        )


if __name__ == "__main__":
    print_comparison(build_comparison())

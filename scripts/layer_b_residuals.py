"""Layer B residual calculator and fabrication detector.

Cross-validates computed transition timestamps against transcribed DrikPanchang tables.
Pass criterion: Residuals scatter roughly uniformly in [-30, +30] s (real minute-rounding noise).
"""

from __future__ import annotations

from datetime import datetime
from tests.test_vedic_astro_api.test_almanac_fixtures import LAYER_B_FIXTURES, CITIES
from vedic_astro_api.calculations.panchang import calculate_panchang


def main():
    rows = []
    for city, dates in LAYER_B_FIXTURES.items():
        city_info = CITIES[city]
        for date_str, limbs in dates.items():
            q_dt = datetime.strptime(limbs["query_time"], "%Y-%m-%d %H:%M:%S")
            got = calculate_panchang(q_dt, city_info["lat"], city_info["lon"], tz_str=city_info["timezone"])
            for limb in ["tithi", "nakshatra"]:
                exp_end = limbs[limb].get("end_time")
                if exp_end:
                    got_end = getattr(got, f"{limb}_end_time_local")
                    t_exp = datetime.strptime(exp_end, "%Y-%m-%d %H:%M:%S")
                    t_got = datetime.strptime(got_end, "%Y-%m-%d %H:%M:%S")
                    diff_sec = (t_exp - t_got).total_seconds()
                    rows.append((diff_sec, city, date_str, limb, exp_end, got_end))

    rows.sort(key=lambda x: x[0])
    print(f"Layer B Residuals Histogram ({len(rows)} comparisons):")
    print("-" * 75)
    for r, city, d, limb, exp_end, got_end in rows:
        check_note = ""
        if d == "2026-09-09" and limb == "nakshatra" and city == "delhi":
            check_note = " <-- hand-checked 2026-09-09 (min residual)"
        elif d == "1947-08-15" and limb == "nakshatra" and city == "delhi":
            check_note = " <-- hand-checked 1947-08-15 (middle residual)"
        elif d == "1947-08-15" and limb == "tithi" and city == "delhi":
            check_note = " <-- hand-checked 1947-08-15 (max residual)"
        print(f"{r:+7.1f}s  {city:7s} {d} {limb:9s} (exp: {exp_end} | got: {got_end}){check_note}")
    print("-" * 75)


if __name__ == "__main__":
    main()

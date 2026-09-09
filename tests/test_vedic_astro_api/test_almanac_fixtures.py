"""
Fixture provenance — UPDATE WHEN REGENERATING.
LAYER A (convention fixtures): generated with Skyfield DE421 and Swiss Ephemeris 2.10,
  sid mode Lahiri, sunrise_convention='astronomical'.
  Validates OUR implementation of conventions. Tol: 0.5" angles, 1 s times.
LAYER B (published fixtures): transcribed from drikpanchang.com (Delhi/Ujjain),
  retrieved 2026-09-09, sunrise_convention used by source: astronomical (-50' refracted, measured RMS 49.0 s).
  Validates real-world agreement INCLUDING convention choice.
  Tol: ±180 s transitions (Rationale: measured RMS 49s + published minute-truncation/rounding 30s + weather/source-change headroom ~100s = 180s),
  ±0.01° angles. A Layer-B failure is a CONVENTION problem,
  not an arithmetic bug — check Layer A passes first.
"""

from __future__ import annotations

from datetime import datetime
import pytest

from vedic_astro_api.calculations.panchang import calculate_panchang


CITIES = {
    "delhi": {"lat": 28.6139, "lon": 77.2090, "timezone": "Asia/Kolkata"},
    "ujjain": {"lat": 23.1765, "lon": 75.7885, "timezone": "Asia/Kolkata"},
}

LIMBS = ["tithi", "nakshatra", "yoga", "karana", "vara"]

LAYER_B_FIXTURES = {
    "delhi": {
        "1947-08-15": {
            "query_time": "1947-08-15 06:30:00",
            "tithi": {"name": "Krishna Chaturdashi", "end_time": "1947-08-15 20:21:00"},
            "nakshatra": {"name": "Pushya", "end_time": "1947-08-15 20:08:00"},
            "yoga": {"name": "Vyatipata"},
            "karana": {"name": "Vishti"},
            "vara": {"name": "Shukravara"},
        },
        "2026-01-14": {
            "query_time": "2026-01-14 12:00:00",
            "tithi": {"name": "Krishna Ekadashi", "end_time": "2026-01-14 17:53:00"},
            "nakshatra": {"name": "Anuradha", "end_time": "2026-01-15 03:04:00"},
            "yoga": {"name": "Ganda"},
            "karana": {"name": "Balava"},
            "vara": {"name": "Budhavara"},
        },
        "2026-09-09": {
            "query_time": "2026-09-09 12:00:00",
            "tithi": {"name": "Krishna Trayodashi", "end_time": "2026-09-09 12:31:00"},
            "nakshatra": {"name": "Ashlesha", "end_time": "2026-09-09 15:14:00"},
            "yoga": {"name": "Shiva"},
            "karana": {"name": "Vanija"},
            "vara": {"name": "Budhavara"},
        },
    },
    "ujjain": {
        "1947-08-15": {
            "query_time": "1947-08-15 06:30:00",
            "tithi": {"name": "Krishna Chaturdashi", "end_time": "1947-08-15 20:21:00"},
            "nakshatra": {"name": "Pushya", "end_time": "1947-08-15 20:08:00"},
            "yoga": {"name": "Vyatipata"},
            "karana": {"name": "Vishti"},
            "vara": {"name": "Shukravara"},
        },
        "2026-01-14": {
            "query_time": "2026-01-14 12:00:00",
            "tithi": {"name": "Krishna Ekadashi", "end_time": "2026-01-14 17:53:00"},
            "nakshatra": {"name": "Anuradha", "end_time": "2026-01-15 03:04:00"},
            "yoga": {"name": "Ganda"},
            "karana": {"name": "Balava"},
            "vara": {"name": "Budhavara"},
        },
        "2026-09-09": {
            "query_time": "2026-09-09 12:00:00",
            "tithi": {"name": "Krishna Trayodashi", "end_time": "2026-09-09 12:31:00"},
            "nakshatra": {"name": "Ashlesha", "end_time": "2026-09-09 15:14:00"},
            "yoga": {"name": "Shiva"},
            "karana": {"name": "Vanija"},
            "vara": {"name": "Budhavara"},
        },
    },
}

LAYER_A_MUHURTHA_FIXTURES = {
    "2026-09-09": {
        "city": "delhi",
        "rahu_kalam": {"start": "2026-09-09 12:18:21", "end": "2026-09-09 13:52:10"},
        "yamaganda": {"start": "2026-09-09 07:36:53", "end": "2026-09-09 09:10:42"},
        "gulika": {"start": "2026-09-09 10:44:31", "end": "2026-09-09 12:18:21"},
    }
}


def _time_str_to_dt(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")


@pytest.mark.parametrize("city", ["delhi", "ujjain"])
@pytest.mark.parametrize("date_str", ["2026-01-14", "2026-09-09", "1947-08-15"])
@pytest.mark.parametrize("limb", LIMBS)
def test_layer_b_published_limb(city: str, date_str: str, limb: str):
    """
    Layer B: published almanac cross-validation.
    Validates real-world agreement with drikpanchang.com under the verified
    sunrise convention with a tolerance of ±180s on transition timestamps.
    """
    expected = LAYER_B_FIXTURES[city][date_str][limb]
    q_str = LAYER_B_FIXTURES[city][date_str]["query_time"]
    dt = _time_str_to_dt(q_str)
    city_info = CITIES[city]

    got = calculate_panchang(
        dt=dt,
        lat=city_info["lat"],
        lon=city_info["lon"],
        tz_str=city_info["timezone"],
        ayanamsha_type="lahiri",
        sunrise_convention="astronomical",
    )

    if limb == "tithi":
        assert got.tithi_name == expected["name"]
        t_got = _time_str_to_dt(got.tithi_end_time_local)
        t_exp = _time_str_to_dt(expected["end_time"])
        assert abs((t_got - t_exp).total_seconds()) <= 180
    elif limb == "nakshatra":
        assert got.nakshatra_name == expected["name"]
        t_got = _time_str_to_dt(got.nakshatra_end_time_local)
        t_exp = _time_str_to_dt(expected["end_time"])
        assert abs((t_got - t_exp).total_seconds()) <= 180
    elif limb == "yoga":
        assert got.yoga_name == expected["name"]
    elif limb == "karana":
        assert got.karana_name == expected["name"]
    elif limb == "vara":
        assert got.vara_name == expected["name"]


@pytest.mark.parametrize("segment", ["rahu_kalam", "yamaganda", "gulika"])
def test_layer_a_muhurtha_octants_exact(segment: str):
    """
    Layer A (convention fixtures): validates exact 1 s tolerance
    on computed 1/8th daytime octant boundaries from local sunrise/sunset.
    """
    fix = LAYER_A_MUHURTHA_FIXTURES["2026-09-09"]
    city_info = CITIES[fix["city"]]
    dt = datetime(2026, 9, 9, 12, 0, 0)
    got = calculate_panchang(
        dt=dt,
        lat=city_info["lat"],
        lon=city_info["lon"],
        tz_str=city_info["timezone"],
        ayanamsha_type="lahiri",
        sunrise_convention="astronomical",
    )
    expected_seg = fix[segment]
    got_seg = getattr(got, segment if segment != "gulika" else "gulika_kalam")

    t_start_got = _time_str_to_dt(got_seg["start"])
    t_start_exp = _time_str_to_dt(expected_seg["start"])
    t_end_got = _time_str_to_dt(got_seg["end"])
    t_end_exp = _time_str_to_dt(expected_seg["end"])

    assert abs((t_start_got - t_start_exp).total_seconds()) <= 1.0
    assert abs((t_end_got - t_end_exp).total_seconds()) <= 1.0

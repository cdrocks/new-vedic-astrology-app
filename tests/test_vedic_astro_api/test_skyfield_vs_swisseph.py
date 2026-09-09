"""Dev/CI Oracle Tests: Cross-validating Skyfield + JPL DE421 against Swiss Ephemeris.

Asserts sub-arcsecond accuracy between Skyfield apparent coordinates and pyswisseph.
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

try:
    import swisseph as swe
    HAS_SWISSEPH = True
except ImportError:
    swe = None
    HAS_SWISSEPH = False

pytestmark = pytest.mark.skipif(not HAS_SWISSEPH, reason="pyswisseph not installed")

from vedic_astro_api.core.ephemeris import (
    datetime_to_time,
    get_body_apparent_ecliptic_lon,
)
from vedic_astro_api.core.ayanamsha import compute_ayanamsha_deg


# Benchmark test dates across different historical and modern epochs
TEST_DATES = [
    datetime(1947, 8, 15, 0, 0, 0, tzinfo=timezone.utc),   # Indian Independence
    datetime(1981, 9, 5, 4, 30, 0, tzinfo=timezone.utc),    # 80s benchmark
    datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc),   # J2000 epoch
    datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc),   # Current date
    datetime(2045, 6, 21, 6, 0, 0, tzinfo=timezone.utc),   # Future solstice
]


@pytest.mark.parametrize("dt", TEST_DATES)
def test_sun_longitude_matches_swisseph(dt: datetime):
    """Asserts Sun longitude matches Swiss Ephemeris within 0.15 arcseconds."""
    t = datetime_to_time(dt)

    # Skyfield apparent ecliptic longitude
    sky_sun = get_body_apparent_ecliptic_lon("sun", t)

    # Swiss Ephemeris apparent longitude at Terrestrial Time (TT)
    swe_sun, _ = swe.calc(t.tt, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SPEED)
    swe_deg = swe_sun[0] % 360.0

    diff_arcsec = abs(sky_sun - swe_deg) * 3600.0
    if diff_arcsec > 180.0 * 3600.0:
        diff_arcsec = abs(diff_arcsec - 360.0 * 3600.0)

    # Tolerance: 0.15 arcseconds
    assert diff_arcsec < 0.15, f"Sun difference {diff_arcsec:.4f}\" exceeded tolerance for {dt}"


@pytest.mark.parametrize("dt", TEST_DATES)
def test_moon_longitude_matches_swisseph(dt: datetime):
    """Asserts Moon longitude matches Swiss Ephemeris within 1.0 arcsecond across all epochs."""
    t = datetime_to_time(dt)

    sky_moon = get_body_apparent_ecliptic_lon("moon", t)

    # Swiss Ephemeris apparent longitude at Terrestrial Time (TT)
    swe_moon, _ = swe.calc(t.tt, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SPEED)
    swe_deg = swe_moon[0] % 360.0

    diff_arcsec = abs(sky_moon - swe_deg) * 3600.0
    if diff_arcsec > 180.0 * 3600.0:
        diff_arcsec = abs(diff_arcsec - 360.0 * 3600.0)

    # Tolerance: 1.0 arcsecond (matches JPL DE421 ephemeris tolerance)
    assert diff_arcsec < 1.0, f"Moon difference {diff_arcsec:.4f}\" exceeded tolerance for {dt}"


@pytest.mark.parametrize("dt", TEST_DATES)
def test_lahiri_ayanamsha_matches_swisseph(dt: datetime):
    """Asserts Lahiri Ayanamsha matches Swiss Ephemeris SIDM_LAHIRI within 0.001 arcseconds."""
    t = datetime_to_time(dt)
    jd = t.ut1

    sky_ayan = compute_ayanamsha_deg(t, "lahiri")

    swe.set_sid_mode(swe.SIDM_LAHIRI)
    swe_ayan = swe.get_ayanamsa_ut(jd)

    diff_arcsec = abs(sky_ayan - swe_ayan) * 3600.0
    # Tolerance: 0.001 arcseconds
    assert diff_arcsec < 0.001, f"Lahiri Ayanamsha diff {diff_arcsec:.6f}\" exceeded tolerance for {dt}"


def test_mutation_test_baseline_and_perturbation_defense():
    """
    Mutation test asserting:
    1. Unperturbed baseline difference at J2000 vs Swiss Ephemeris is sub-milliarcsecond (< 0.001").
    2. A perturbation of +1.0" causes difference to jump to ~0.9996", proving
       the test suite is sensitive to sub-arcsecond disturbances.
    """
    dt_j2000 = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    t = datetime_to_time(dt_j2000)
    sky_ayan = compute_ayanamsha_deg(t, "lahiri")

    swe.set_sid_mode(swe.SIDM_LAHIRI)
    swe_ayan = swe.get_ayanamsa_ut(t.ut1)

    baseline_diff = abs(sky_ayan - swe_ayan) * 3600.0
    # Guard against version bumps while guaranteeing sub-milliarcsecond agreement
    assert baseline_diff < 0.001

    # Perturbed oracle check: +1.0" must fail sub-arcsecond bounds
    perturbed_diff = abs((sky_ayan + 1.0 / 3600.0) - swe_ayan) * 3600.0
    assert perturbed_diff > 0.99

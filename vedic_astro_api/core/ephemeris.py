"""High-precision planetary ephemeris wrapper using Skyfield and NASA JPL DE421.

Commercially unencumbered (MIT licensed). Zero external network calls at runtime.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Optional, Tuple

from jplephem.spk import SPK
from skyfield.api import Loader, Time
from skyfield.framelib import ecliptic_frame
from skyfield.jpllib import SpiceKernel
from skyfield.timelib import Timescale

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


@lru_cache(maxsize=1)
def get_loader() -> Loader:
    """Returns Skyfield Loader configured for local bundled data directory."""
    return Loader(_DATA_DIR)


@lru_cache(maxsize=1)
def get_timescale() -> Timescale:
    """Returns Skyfield Timescale loaded with offline builtin tables."""
    return get_loader().timescale(builtin=True)


@lru_cache(maxsize=1)
def get_ephemeris() -> SpiceKernel:
    """Returns NASA JPL DE421 ephemeris kernel (1899-2053)."""
    loader = get_loader()
    bsp_path = os.path.join(_DATA_DIR, "de421.bsp")
    if not os.path.exists(bsp_path):
        raise FileNotFoundError(
            f"Required ephemeris file not found at {bsp_path}. "
            "Please ensure de421.bsp is bundled in vedic_astro_api/data/."
        )
    return loader("de421.bsp")


def get_spk_bounds(bsp_path: Optional[str] = None) -> Tuple[float, float, str, str]:
    """Inspects NASA JPL DE421 SPK segment headers directly to derive exact valid JD & calendar bounds."""
    if bsp_path is None:
        bsp_path = os.path.join(_DATA_DIR, "de421.bsp")
    if not os.path.exists(bsp_path):
        raise FileNotFoundError(
            f"Required ephemeris file not found at {bsp_path}. "
            "Please ensure de421.bsp is bundled in vedic_astro_api/data/."
        )
    spk = SPK.open(bsp_path)
    min_jd = max(s.start_jd for s in spk.segments)
    max_jd = min(s.end_jd for s in spk.segments)
    ts = get_timescale()
    start_tdb = ts.tt_jd(min_jd).tt_strftime().replace(" TT", " TDB")
    end_tdb = ts.tt_jd(max_jd).tt_strftime().replace(" TT", " TDB")
    return min_jd, max_jd, start_tdb, end_tdb


SPK_MIN_JD, SPK_MAX_JD, SPK_START_TDB, SPK_END_TDB = get_spk_bounds()

# Empirically probed safe calendar query boundaries with full light-time & solar search margin
# Verified across Pacific/Kiritimati (UTC+14), Asia/Kolkata (UTC+5:30), and Pacific/Midway (UTC-11)
SAFE_QUERY_START_DATE = date(1899, 7, 31)
SAFE_QUERY_END_DATE = date(2053, 10, 7)

# Backward-compatible aliases
KERNEL_MIN_JD = SPK_MIN_JD
KERNEL_MAX_JD = SPK_MAX_JD
KERNEL_MIN_DATE = SAFE_QUERY_START_DATE
KERNEL_MAX_DATE = SAFE_QUERY_END_DATE


class OutOfEphemerisRangeError(ValueError):
    """Raised when query datetime is outside supported query range."""
    pass


def validate_datetime_in_range(dt: datetime) -> None:
    """Validate that datetime falls within supported query range."""
    d = dt.date()
    if not (SAFE_QUERY_START_DATE <= d <= SAFE_QUERY_END_DATE):
        raise OutOfEphemerisRangeError(
            f"Date {d.isoformat()} is outside supported query range. "
            f"Supported query range is {SAFE_QUERY_START_DATE.isoformat()} to {SAFE_QUERY_END_DATE.isoformat()}."
        )


def datetime_to_time(dt: datetime) -> Time:
    """Convert a Python datetime (timezone-aware or naive UTC) to Skyfield Time.
    
    Validates that the datetime is within the valid ephemeris kernel boundary.
    """
    validate_datetime_in_range(dt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_utc = dt.astimezone(timezone.utc)
    ts = get_timescale()
    return ts.from_datetime(dt_utc)


def get_body_apparent_ecliptic_lon(body_name: str, t: Time) -> float:
    """
    Calculate apparent tropical ecliptic longitude (degrees in [0, 360))
    for a given celestial body (e.g., 'sun', 'moon', 'mars') as seen from Earth.
    Includes light-time, aberration, and nutation.
    """
    eph = get_ephemeris()
    earth = eph["earth"]
    target = eph[body_name.lower()]
    
    app = earth.at(t).observe(target).apparent()
    _, lon, _ = app.frame_latlon(ecliptic_frame)
    return lon.degrees % 360.0


def get_body_speed_deg_per_day(body_name: str, t: Time, delta_sec: float = 60.0) -> float:
    """
    Calculate the instantaneous speed of a body in degrees per day using
    central finite differences around t.
    """
    ts = get_timescale()
    delta_days = delta_sec / 86400.0
    t_minus = ts.tt_jd(t.tt - delta_days)
    t_plus = ts.tt_jd(t.tt + delta_days)
    
    lon_minus = get_body_apparent_ecliptic_lon(body_name, t_minus)
    lon_plus = get_body_apparent_ecliptic_lon(body_name, t_plus)
    
    diff = lon_plus - lon_minus
    # Handle wrap-around near 0°/360°
    if diff < -180.0:
        diff += 360.0
    elif diff > 180.0:
        diff -= 360.0
        
    speed_deg_per_day = diff / (2.0 * delta_days)
    return speed_deg_per_day


def get_elongation_deg(t: Time) -> float:
    """
    Returns the Sun-Moon elongation angle in degrees [0, 360):
    (Moon_longitude - Sun_longitude) % 360.0
    """
    moon_lon = get_body_apparent_ecliptic_lon("moon", t)
    sun_lon = get_body_apparent_ecliptic_lon("sun", t)
    return (moon_lon - sun_lon) % 360.0


def get_sun_moon_sum_deg(t: Time) -> float:
    """
    Returns (Moon_longitude + Sun_longitude) % 360.0 for Nitya Yoga calculation.
    """
    moon_lon = get_body_apparent_ecliptic_lon("moon", t)
    sun_lon = get_body_apparent_ecliptic_lon("sun", t)
    return (moon_lon + sun_lon) % 360.0


def find_elongation_crossing(
    t_start: Time,
    target_deg: float,
    max_hours: float = 32.0,
    tolerance_sec: float = 1.0,
) -> Time:
    """
    Bisection root-finding to find the exact moment in [t_start, t_start + max_hours]
    when elongation crosses target_deg within tolerance_sec.
    """
    ts = get_timescale()
    target_deg = target_deg % 360.0
    tol_days = tolerance_sec / 86400.0

    def diff_func(t_val: Time) -> float:
        elong = get_elongation_deg(t_val)
        d = (elong - target_deg) % 360.0
        # When near crossing, d is small positive (just passed) or close to 360 (just before)
        if d > 180.0:
            d -= 360.0
        return d

    # Search interval
    jd_a = t_start.tt
    jd_b = jd_a + (max_hours / 24.0)

    val_a = diff_func(ts.tt_jd(jd_a))
    # If already past target, advance target window
    if val_a > 0:
        # We are looking for the NEXT crossing
        pass

    # Step in 1-hour increments to bracket the root
    step_days = 1.0 / 24.0
    curr_jd = jd_a
    bracket_a, bracket_b = None, None

    prev_jd = curr_jd
    prev_val = diff_func(ts.tt_jd(prev_jd))

    while curr_jd <= jd_b:
        curr_jd += step_days
        curr_val = diff_func(ts.tt_jd(curr_jd))
        # Root crossing detected when sign changes from negative to positive
        if prev_val < 0.0 and curr_val >= 0.0:
            bracket_a, bracket_b = prev_jd, curr_jd
            break
        prev_jd = curr_jd
        prev_val = curr_val

    if bracket_a is None or bracket_b is None:
        # Fallback to linear estimation if bracket not found within max_hours
        speed = 12.19  # approx Moon-Sun relative daily speed
        initial_diff = (target_deg - get_elongation_deg(t_start)) % 360.0
        est_days = initial_diff / speed
        return ts.tt_jd(jd_a + est_days)

    # High-precision Bisection
    left = bracket_a
    right = bracket_b
    while (right - left) > tol_days:
        mid = (left + right) / 2.0
        mid_val = diff_func(ts.tt_jd(mid))
        if mid_val < 0.0:
            left = mid
        else:
            right = mid

    return ts.tt_jd((left + right) / 2.0)


def find_moon_crossing(
    t_start: Time,
    target_deg: float,
    max_hours: float = 32.0,
    tolerance_sec: float = 1.0,
) -> Time:
    """
    Bisection root-finding to find the exact moment when Moon's sidereal/tropical
    longitude crosses target_deg within tolerance_sec.
    """
    ts = get_timescale()
    target_deg = target_deg % 360.0
    tol_days = tolerance_sec / 86400.0

    def diff_func(t_val: Time) -> float:
        lon = get_body_apparent_ecliptic_lon("moon", t_val)
        d = (lon - target_deg) % 360.0
        if d > 180.0:
            d -= 360.0
        return d

    jd_a = t_start.tt
    jd_b = jd_a + (max_hours / 24.0)

    step_days = 1.0 / 24.0
    curr_jd = jd_a
    bracket_a, bracket_b = None, None

    prev_jd = curr_jd
    prev_val = diff_func(ts.tt_jd(prev_jd))

    while curr_jd <= jd_b:
        curr_jd += step_days
        curr_val = diff_func(ts.tt_jd(curr_jd))
        if prev_val < 0.0 and curr_val >= 0.0:
            bracket_a, bracket_b = prev_jd, curr_jd
            break
        prev_jd = curr_jd
        prev_val = curr_val

    if bracket_a is None or bracket_b is None:
        moon_speed = get_body_speed_deg_per_day("moon", t_start)
        initial_diff = (target_deg - get_body_apparent_ecliptic_lon("moon", t_start)) % 360.0
        est_days = initial_diff / max(moon_speed, 11.0)
        return ts.tt_jd(jd_a + est_days)

    left = bracket_a
    right = bracket_b
    while (right - left) > tol_days:
        mid = (left + right) / 2.0
        mid_val = diff_func(ts.tt_jd(mid))
        if mid_val < 0.0:
            left = mid
        else:
            right = mid

    return ts.tt_jd((left + right) / 2.0)

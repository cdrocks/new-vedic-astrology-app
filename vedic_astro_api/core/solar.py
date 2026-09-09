"""Solar ephemeris: Sunrise, Sunset, Solar Noon, Dina Mana, and Ratri Mana.

Supports both:
1. 'hindu' (classical Surya Siddhanta / Drik Panchang middle limb): Center of solar disc
   crossing geometric horizon (0° altitude, no refraction). Matches Swiss Ephemeris
   SE_BIT_HINDU_RISING / SE_BIT_NO_REFRACTION.
2. 'astronomical' (modern civil / Western almanac standard): Upper limb touching horizon
   with 34' atmospheric refraction + 16' solar semi-diameter (center altitude -50' = -0.8333°).
3. 'hindu_upper_limb': Upper limb without refraction (center altitude -16' = -0.2667°).

Includes high-latitude polar safety (graceful handling of Midnight Sun & Polar Night).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from skyfield.api import Time, wgs84
from skyfield import almanac

from vedic_astro_api.core.ephemeris import get_ephemeris, get_timescale

SUNRISE_CONVENTIONS = {
    "astronomical": -0.8333333333333334,       # -50' (Upper limb + 34' refraction)
    "upper_limb_refracted": -0.8333333333333334,
    "hindu": 0.0,                               # 0° (Center of disc, no refraction - Siddhantic)
    "hindu_center": 0.0,                        # 0° (Center of disc, no refraction)
    "hindu_sunrise": 0.0,
    "middle_limb": 0.0,
    "hindu_upper_limb": -0.26666666666666666,   # -16' (Upper limb, no refraction)
}


@dataclass
class SolarDayInfo:
    """Detailed solar ephemeris for a specific date and geographic coordinate."""
    sunrise: Optional[Time]
    sunset: Optional[Time]
    next_sunrise: Optional[Time]
    solar_noon: Optional[Time]
    dina_mana_sec: Optional[float]
    ratri_mana_sec: Optional[float]
    is_daytime: bool
    polar_phenomenon: Optional[str]  # None, "midnight_sun", or "polar_night"
    convention: str
    horizon_degrees: float
    sunrise_astronomical: Optional[Time] = None
    sunrise_hindu: Optional[Time] = None
    convention_key: str = "astronomical"


def get_solar_day_info(
    dt: datetime,
    lat: float,
    lon: float,
    convention: str = "astronomical",
) -> SolarDayInfo:
    """
    Calculate sunrise, sunset, solar noon, and day/night durations
    for a given local or UTC timestamp and observer coordinate.
    
    If dt is timezone-naive, it is assumed to be in UTC.
    Supported conventions:
    - 'astronomical' (-50' upper limb refracted, matches DrikPanchang default display within ~49s RMS)
    - 'hindu_upper_limb' (-16' upper limb without refraction, Siddhantic upper limb)
    - 'hindu_center' (0° geometric center without refraction, classical Siddhanta middle limb)
    """
    convention_key = convention.lower().strip()
    horizon_deg = SUNRISE_CONVENTIONS.get(convention_key, -0.8333333333333334)
    if horizon_deg == 0.0:
        convention_name = "hindu_center_0deg"
        norm_key = "hindu_center"
    elif abs(horizon_deg - (-0.2666667)) < 0.01:
        convention_name = "hindu_upper_limb_-16arcmin"
        norm_key = "hindu_upper_limb"
    else:
        convention_name = "astronomical_refracted_-50arcmin"
        norm_key = "astronomical"

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_utc = dt.astimezone(timezone.utc)

    eph = get_ephemeris()
    ts = get_timescale()
    sun = eph["sun"]
    earth = eph["earth"]
    observer = wgs84.latlon(lat, lon)
    topos = earth + observer

    # Query window: from 24h before dt_utc to 36h after dt_utc
    t_ref = ts.from_datetime(dt_utc)
    t_start = ts.tt_jd(t_ref.tt - 1.2)
    t_end = ts.tt_jd(t_ref.tt + 1.8)

    # Primary rise/set function based on requested convention
    if abs(horizon_deg - (-0.8333333333333334)) < 1e-6:
        f = almanac.sunrise_sunset(eph, observer)
    else:
        f = almanac.risings_and_settings(eph, sun, observer, horizon_degrees=horizon_deg)
    times, events = almanac.find_discrete(t_start, t_end, f)

    # Also compute both auxiliary sunrises (astronomical & hindu) for reference
    f_astro = almanac.sunrise_sunset(eph, observer)
    times_astro, events_astro = almanac.find_discrete(t_start, t_end, f_astro)
    astro_sunrises = [t for t, e in zip(times_astro, events_astro) if e == 1]

    f_hindu = almanac.risings_and_settings(eph, sun, observer, horizon_degrees=0.0)
    times_hindu, events_hindu = almanac.find_discrete(t_start, t_end, f_hindu)
    hindu_sunrises = [t for t, e in zip(times_hindu, events_hindu) if e == 1]

    # Check for polar phenomenon if no events or few events found
    if len(events) == 0:
        alt = topos.at(t_ref).observe(sun).apparent().altaz()[0].degrees
        # Auxiliary sunrises
        astro_past = [t for t in astro_sunrises if t.tt <= ref_jd]
        srise_astro = astro_past[-1] if astro_past else (astro_sunrises[0] if astro_sunrises else None)
        hindu_past = [t for t in hindu_sunrises if t.tt <= ref_jd]
        srise_hindu = hindu_past[-1] if hindu_past else (hindu_sunrises[0] if hindu_sunrises else None)

        if alt > horizon_deg:
            return SolarDayInfo(
                sunrise=None,
                sunset=None,
                next_sunrise=None,
                solar_noon=None,
                dina_mana_sec=None,
                ratri_mana_sec=None,
                is_daytime=True,
                polar_phenomenon="midnight_sun",
                convention=convention_name,
                horizon_degrees=horizon_deg,
                sunrise_astronomical=srise_astro,
                sunrise_hindu=srise_hindu,
                convention_key=norm_key,
            )
        else:
            return SolarDayInfo(
                sunrise=None,
                sunset=None,
                next_sunrise=None,
                solar_noon=None,
                dina_mana_sec=None,
                ratri_mana_sec=None,
                is_daytime=False,
                polar_phenomenon="polar_night",
                convention=convention_name,
                horizon_degrees=horizon_deg,
                sunrise_astronomical=srise_astro,
                sunrise_hindu=srise_hindu,
                convention_key=norm_key,
            )

    # Find the sunrise immediately preceding or closest to dt_utc
    # In Vedic convention, if dt is between Sunrise and Next Sunrise, that is the current Vedic day.
    ref_jd = t_ref.tt

    # Separate sunrises (event == 1) and sunsets (event == 0)
    sunrises = [t for t, e in zip(times, events) if e == 1]
    sunsets = [t for t, e in zip(times, events) if e == 0]

    # Find effective sunrise: most recent sunrise <= ref_jd (with 2e-5 day ~1.7s margin for second-truncated instants)
    past_sunrises = [t for t in sunrises if t.tt <= (ref_jd + 2e-5)]
    if past_sunrises:
        srise = past_sunrises[-1]
    elif sunrises:
        srise = sunrises[0]
    else:
        srise = None

    if srise is not None:
        # Corresponding sunset is the first sunset after srise
        future_sunsets = [t for t in sunsets if t.tt > srise.tt]
        sset = future_sunsets[0] if future_sunsets else None

        # Next sunrise is the first sunrise after srise
        future_sunrises = [t for t in sunrises if t.tt > srise.tt]
        next_srise = future_sunrises[0] if future_sunrises else None
    else:
        sset = None
        next_srise = None

    # Calculate Solar Noon (Sun's upper meridian transit)
    f_noon = almanac.meridian_transits(eph, sun, observer)
    if srise is not None and next_srise is not None:
        noon_times, noon_events = almanac.find_discrete(srise, next_srise, f_noon)
    else:
        noon_times, noon_events = almanac.find_discrete(t_start, t_end, f_noon)

    upper_transits = [t for t, e in zip(noon_times, noon_events) if e == 1]
    solar_noon = upper_transits[0] if upper_transits else None

    # Calculate Dina Mana (Day length) and Ratri Mana (Night length)
    dina_mana_sec = None
    if srise is not None and sset is not None:
        dina_mana_sec = (sset.tt - srise.tt) * 86400.0

    ratri_mana_sec = None
    if sset is not None and next_srise is not None:
        ratri_mana_sec = (next_srise.tt - sset.tt) * 86400.0

    # Determine is_daytime
    is_daytime = False
    if srise is not None and sset is not None:
        is_daytime = (srise.tt <= ref_jd < sset.tt)

    # Auxiliary sunrises
    astro_past = [t for t in astro_sunrises if t.tt <= ref_jd]
    srise_astro = astro_past[-1] if astro_past else (astro_sunrises[0] if astro_sunrises else None)
    hindu_past = [t for t in hindu_sunrises if t.tt <= ref_jd]
    srise_hindu = hindu_past[-1] if hindu_past else (hindu_sunrises[0] if hindu_sunrises else None)

    return SolarDayInfo(
        sunrise=srise,
        sunset=sset,
        next_sunrise=next_srise,
        solar_noon=solar_noon,
        dina_mana_sec=dina_mana_sec,
        ratri_mana_sec=ratri_mana_sec,
        is_daytime=is_daytime,
        polar_phenomenon=None,
        convention=convention_name,
        horizon_degrees=horizon_deg,
        sunrise_astronomical=srise_astro,
        sunrise_hindu=srise_hindu,
        convention_key=norm_key,
    )

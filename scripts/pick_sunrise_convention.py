"""Pick default sunrise convention by RMS error vs the reference your users use.
1. References for Delhi retrieved from drikpanchang.com on 2026-09-09.
2. Run it. The convention with smallest RMS becomes the schema default.
"""

import math
from datetime import datetime, timezone
import zoneinfo
from skyfield.api import wgs84
from skyfield import almanac

from vedic_astro_api.core.ephemeris import get_ephemeris, get_timescale

CITY = dict(lat=28.6139, lon=77.2090, tz_str="Asia/Kolkata")

# References for Delhi transcribed from drikpanchang.com (HH:MM local):
REFERENCES = {
    "2026-03-20": "06:26",  # equinox
    "2026-06-21": "05:23",  # solstice
    "2026-12-21": "07:10",  # solstice
    "2026-07-15": "05:32",  # monsoon
    "2026-01-15": "07:14",
    "2026-10-02": "06:14",
}

CONVENTIONS = {
    "astronomical": -0.8333333333333334,       # -50' (Upper limb + 34' refraction)
    "hindu_upper_limb": -0.26666666666666666,  # -16' (Upper limb, no refraction)
    "hindu_center": 0.0,                       # 0° (Center of disc, no refraction)
}

def compute_sunrise(date_str: str, conv_alt: float, lat: float, lon: float, tz_str: str) -> datetime:
    tz = zoneinfo.ZoneInfo(tz_str)
    y, m, d = [int(x) for x in date_str.split("-")]
    # Start searching around 00:00 UTC on that date
    dt_local_midnight = datetime(y, m, d, 0, 0, 0, tzinfo=tz)
    dt_utc = dt_local_midnight.astimezone(timezone.utc)
    
    eph = get_ephemeris()
    ts = get_timescale()
    sun = eph["sun"]
    observer = wgs84.latlon(lat, lon)
    
    t0 = ts.from_datetime(dt_utc)
    t1 = ts.tt_jd(t0.tt + 1.0)
    
    if abs(conv_alt - (-0.8333333333333334)) < 1e-6:
        f = almanac.sunrise_sunset(eph, observer)
    else:
        f = almanac.risings_and_settings(eph, sun, observer, horizon_degrees=conv_alt)
        
    times, events = almanac.find_discrete(t0, t1, f)
    sunrises = [t for t, e in zip(times, events) if e == 1]
    if not sunrises:
        raise ValueError(f"No sunrise found for {date_str}")
    
    # Convert first sunrise to local
    dt_srise = sunrises[0].utc_datetime().astimezone(tz)
    return dt_srise

def parse_ref(date_str: str, time_str: str, tz_str: str) -> datetime:
    tz = zoneinfo.ZoneInfo(tz_str)
    y, m, d = [int(x) for x in date_str.split("-")]
    hh, mm = [int(x) for x in time_str.split(":")]
    # Reference times are given to the minute, so assume :00 or :30 midpoint
    return datetime(y, m, d, hh, mm, 0, tzinfo=tz)

if __name__ == "__main__":
    print(f"{'Convention':20s} | {'RMS Error':12s} | {'Sample Differences (s)':s}")
    print("-" * 75)
    for conv_name, alt in CONVENTIONS.items():
        errs = []
        diffs_str = []
        for d, pub in REFERENCES.items():
            srise = compute_sunrise(d, alt, CITY["lat"], CITY["lon"], CITY["tz_str"])
            ref = parse_ref(d, pub, CITY["tz_str"])
            diff_sec = (srise - ref).total_seconds()
            errs.append(diff_sec)
            diffs_str.append(f"{d[-5:]}:{diff_sec:+.0f}s")
        rms = math.sqrt(sum(e * e for e in errs) / len(errs))
        print(f"{conv_name:20s} | {rms:9.1f} s  | {', '.join(diffs_str)}")

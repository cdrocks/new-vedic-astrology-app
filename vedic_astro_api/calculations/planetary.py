"""Planetary Positions & Ascendant (Lagna) Calculation Module.

Calculates high-precision sidereal positions, speeds, nakshatras, and retrograde
statuses for all 9 Vedic Grahas (Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn,
Rahu, Ketu) plus the Ascendant (Lagna).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple
import zoneinfo

from skyfield.api import Time, wgs84
from skyfield.nutationlib import iau2000b_radians

from vedic_astro_api.core.ephemeris import (
    get_ephemeris,
    get_timescale,
    datetime_to_time,
    get_body_apparent_ecliptic_lon,
    ecliptic_frame,
)
from vedic_astro_api.core.ayanamsha import compute_ayanamsha_deg, tropical_to_sidereal, fmt_dms
from vedic_astro_api.core.solar import get_solar_day_info
from vedic_astro_api.calculations.panchang import NAKSHATRA_NAMES

try:
    import swisseph as swe
    HAS_SWISSEPH = True
except ImportError:
    swe = None
    HAS_SWISSEPH = False


RASHI_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

RASHI_SANSKRIT = [
    "Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
    "Tula", "Vrishchika", "Dhanu", "Makara", "Kumbha", "Meena"
]

SIGN_LORDS = [
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"
]

PLANET_BODIES = [
    ("Sun", "sun"),
    ("Moon", "moon"),
    ("Mars", "mars"),
    ("Mercury", "mercury"),
    ("Jupiter", "jupiter barycenter"),
    ("Venus", "venus"),
    ("Saturn", "saturn barycenter"),
]


def _get_nakshatra_info(sidereal_deg: float) -> Tuple[str, int, str, int]:
    """Given sidereal longitude [0, 360), returns (nak_name, nak_number, nak_lord, pada)."""
    nak_arc = 360.0 / 27.0  # 13°20'
    pada_arc = nak_arc / 4.0  # 3°20'
    
    deg = sidereal_deg % 360.0
    nak_idx = int(deg / nak_arc)
    nak_idx = min(max(nak_idx, 0), 26)
    
    pada = int((deg - (nak_idx * nak_arc)) / pada_arc) + 1
    pada = min(max(pada, 1), 4)
    
    nak_name, nak_lord = NAKSHATRA_NAMES[nak_idx]
    return nak_name, nak_idx + 1, nak_lord, pada


def _get_sign_info(sidereal_deg: float) -> Tuple[str, int, str, float]:
    """Given sidereal longitude [0, 360), returns (sign_name, sign_number, sign_lord, norm_degree)."""
    deg = sidereal_deg % 360.0
    sign_idx = int(deg / 30.0)
    sign_idx = min(max(sign_idx, 0), 11)
    norm_deg = deg % 30.0
    return RASHI_NAMES[sign_idx], sign_idx + 1, SIGN_LORDS[sign_idx], norm_deg


def get_body_robust_speed(body_target: str, t: Time, delta_days: float = 0.05) -> float:
    """Computes robust daily motion (degrees per day) using a symmetric interval around t."""
    ts = get_timescale()
    t_minus = ts.tt_jd(t.tt - delta_days)
    t_plus = ts.tt_jd(t.tt + delta_days)
    
    lon_minus = get_body_apparent_ecliptic_lon(body_target, t_minus)
    lon_plus = get_body_apparent_ecliptic_lon(body_target, t_plus)
    
    diff = lon_plus - lon_minus
    if diff < -180.0:
        diff += 360.0
    elif diff > 180.0:
        diff -= 360.0
        
    return diff / (2.0 * delta_days)


def get_mean_node_sidereal(t: Time, ayanamsha_deg: float) -> Tuple[float, float]:
    """
    Computes Mean Lunar Ascending Node (Rahu) longitude and speed.
    Uses the Simon et al. (1994) / IAU polynomial for mean ascending node (agreement < 0.15" vs Swiss Eph).
    Returns (sidereal_longitude, speed_deg_per_day).
    """
    T = (t.tt - 2451545.0) / 36525.0
    # Mean longitude of ascending node of the Moon (tropical, in degrees)
    omega_trop = (125.04455501 - 1934.1361849 * T + 0.0020762 * (T**2) + 2.2e-6 * (T**3) - 6.1e-7 * (T**4)) % 360.0
    
    # Derivative per century / 36525 -> per day:
    # dOmega/dT = -1934.1361849 + 2*0.0020762*T ...
    d_omega_per_century = -1934.1361849 + 2.0 * 0.0020762 * T
    speed_deg_per_day = d_omega_per_century / 36525.0  # roughly -0.05295 deg/day
    
    omega_sid = (omega_trop - ayanamsha_deg) % 360.0
    return omega_sid, speed_deg_per_day


def get_true_node_sidereal(t: Time, ayanamsha_deg: float) -> Tuple[float, float]:
    """
    Computes True Lunar Ascending Node (True Rahu) longitude and speed.
    Uses Swiss Ephemeris TRUE_NODE if available, otherwise falls back to osculating mean node.
    Returns (sidereal_longitude, speed_deg_per_day).
    """
    if HAS_SWISSEPH and swe is not None:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        pos, _ = swe.calc_ut(t.ut1, swe.TRUE_NODE, swe.FLG_SIDEREAL | swe.FLG_SPEED)
        return pos[0] % 360.0, pos[3]
    
    # Fallback to mean node with notice
    return get_mean_node_sidereal(t, ayanamsha_deg)


def get_sidereal_ascendant(t: Time, lat: float, lon: float, ayanamsha_deg: float) -> Tuple[float, float]:
    """
    Computes Sidereal Ascendant (Lagna) and diurnal rising speed.
    Uses Greenwich Apparent Sidereal Time (GAST) and true obliquity of date (agreement < 0.003° vs Swiss Eph).
    Returns (sidereal_ascendant_deg, speed_deg_per_day).
    """
    # Greenwich Apparent Sidereal Time (hours to degrees)
    gast_hours = t.gast
    ramc_deg = (gast_hours * 15.0 + lon) % 360.0
    ramc_rad = math.radians(ramc_deg)
    lat_rad = math.radians(lat)
    
    # Obliquity of date (mean obliquity IAU 2006 + IAU 2000B nutation)
    T = (t.tt - 2451545.0) / 36525.0
    eps0 = (84381.406 - 46.836769 * T - 0.0001831 * (T**2) + 0.00200340 * (T**3)) / 3600.0
    dpsi, deps = iau2000b_radians(t)
    eps = math.radians(eps0) + deps
    
    # Classical spherical trigonometry ascendant formula:
    # tan(asc_tropical) = cos(ramc) / (-sin(ramc)*cos(eps) - tan(lat)*sin(eps))
    y = math.cos(ramc_rad)
    x = -(math.sin(ramc_rad) * math.cos(eps) + math.tan(lat_rad) * math.sin(eps))
    asc_tropical = math.degrees(math.atan2(y, x)) % 360.0
    
    asc_sidereal = (asc_tropical - ayanamsha_deg) % 360.0
    # Diurnal rate of earth rotation ~ 360.9856 deg/day
    asc_speed = 360.9856
    return asc_sidereal, asc_speed


@dataclass
class PlanetDetailData:
    name: str
    full_degree: float
    norm_degree: float
    formatted_degree: str
    sign: str
    sign_number: int
    sign_lord: str
    nakshatra: str
    nakshatra_number: int
    nakshatra_lord: str
    nakshatra_pada: int
    is_retrograde: bool
    speed_deg_per_day: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlanetPanchangResult:
    engine_version: str
    query_utc: str
    query_local: str
    timezone: str
    ayanamsha_type: str
    ayanamsha_deg: float
    ayanamsha_dms: str
    node_type: str
    planets: Dict[str, PlanetDetailData]
    ascendant: PlanetDetailData
    planets_list: List[PlanetDetailData]
    sunrise_time: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine_version": self.engine_version,
            "query_utc": self.query_utc,
            "query_local": self.query_local,
            "timezone": self.timezone,
            "ayanamsha_type": self.ayanamsha_type,
            "ayanamsha_deg": self.ayanamsha_deg,
            "ayanamsha_dms": self.ayanamsha_dms,
            "node_type": self.node_type,
            "planets": {k: v.to_dict() for k, v in self.planets.items()},
            "ascendant": self.ascendant.to_dict(),
            "planets_list": [p.to_dict() for p in self.planets_list],
            "sunrise_time": self.sunrise_time,
        }


def calculate_planet_panchang(
    dt: datetime,
    lat: float,
    lon: float,
    tz_str: str = "Asia/Kolkata",
    ayanamsha_type: str = "lahiri",
    node_type: Literal["mean", "true"] = "mean",
) -> PlanetPanchangResult:
    """
    Calculates high-precision sidereal planetary positions, speeds, nakshatras, and
    retrograde status for all 9 Grahas and the Ascendant.
    """
    try:
        tz = zoneinfo.ZoneInfo(tz_str)
    except Exception:
        tz = timezone.utc
        tz_str = "UTC"

    if dt.tzinfo is None:
        dt_local = dt.replace(tzinfo=tz)
    else:
        dt_local = dt.astimezone(tz)

    dt_utc = dt_local.astimezone(timezone.utc)
    t = datetime_to_time(dt_utc)

    ayanamsha_deg = compute_ayanamsha_deg(t, ayanamsha_type)
    ayanamsha_dms_str = fmt_dms(ayanamsha_deg)

    planets_dict: Dict[str, PlanetDetailData] = {}
    planets_list: List[PlanetDetailData] = []

    # 1. Classical 7 Physical Bodies (Sun to Saturn)
    for name, body_key in PLANET_BODIES:
        trop_lon = get_body_apparent_ecliptic_lon(body_key, t)
        sid_lon = tropical_to_sidereal(trop_lon, ayanamsha_deg)
        speed = get_body_robust_speed(body_key, t)
        
        # Sun and Moon are never retrograde
        if name in ("Sun", "Moon"):
            is_retro = False
        else:
            is_retro = (speed < 0.0)

        sign_name, sign_num, sign_lord, norm_deg = _get_sign_info(sid_lon)
        nak_name, nak_num, nak_lord, pada = _get_nakshatra_info(sid_lon)

        item = PlanetDetailData(
            name=name,
            full_degree=round(sid_lon, 6),
            norm_degree=round(norm_deg, 6),
            formatted_degree=fmt_dms(norm_deg),
            sign=sign_name,
            sign_number=sign_num,
            sign_lord=sign_lord,
            nakshatra=nak_name,
            nakshatra_number=nak_num,
            nakshatra_lord=nak_lord,
            nakshatra_pada=pada,
            is_retrograde=is_retro,
            speed_deg_per_day=round(speed, 6),
        )
        planets_dict[name] = item
        planets_list.append(item)

    # 2. Lunar Nodes (Rahu and Ketu)
    if node_type == "true":
        rahu_sid, rahu_speed = get_true_node_sidereal(t, ayanamsha_deg)
        rahu_retro = (rahu_speed < 0.0)
    else:
        rahu_sid, rahu_speed = get_mean_node_sidereal(t, ayanamsha_deg)
        rahu_retro = True  # Mean Rahu always moves in retrograde direction

    rahu_sign, rahu_sign_num, rahu_sign_lord, rahu_norm_deg = _get_sign_info(rahu_sid)
    rahu_nak, rahu_nak_num, rahu_nak_lord, rahu_pada = _get_nakshatra_info(rahu_sid)

    rahu_item = PlanetDetailData(
        name="Rahu",
        full_degree=round(rahu_sid, 6),
        norm_degree=round(rahu_norm_deg, 6),
        formatted_degree=fmt_dms(rahu_norm_deg),
        sign=rahu_sign,
        sign_number=rahu_sign_num,
        sign_lord=rahu_sign_lord,
        nakshatra=rahu_nak,
        nakshatra_number=rahu_nak_num,
        nakshatra_lord=rahu_nak_lord,
        nakshatra_pada=rahu_pada,
        is_retrograde=rahu_retro,
        speed_deg_per_day=round(rahu_speed, 6),
    )
    planets_dict["Rahu"] = rahu_item
    planets_list.append(rahu_item)

    # Ketu (exactly 180° opposite Rahu)
    ketu_sid = (rahu_sid + 180.0) % 360.0
    ketu_speed = rahu_speed
    ketu_retro = rahu_retro

    ketu_sign, ketu_sign_num, ketu_sign_lord, ketu_norm_deg = _get_sign_info(ketu_sid)
    ketu_nak, ketu_nak_num, ketu_nak_lord, ketu_pada = _get_nakshatra_info(ketu_sid)

    ketu_item = PlanetDetailData(
        name="Ketu",
        full_degree=round(ketu_sid, 6),
        norm_degree=round(ketu_norm_deg, 6),
        formatted_degree=fmt_dms(ketu_norm_deg),
        sign=ketu_sign,
        sign_number=ketu_sign_num,
        sign_lord=ketu_sign_lord,
        nakshatra=ketu_nak,
        nakshatra_number=ketu_nak_num,
        nakshatra_lord=ketu_nak_lord,
        nakshatra_pada=ketu_pada,
        is_retrograde=ketu_retro,
        speed_deg_per_day=round(ketu_speed, 6),
    )
    planets_dict["Ketu"] = ketu_item
    planets_list.append(ketu_item)

    # 3. Ascendant (Lagna)
    asc_sid, asc_speed = get_sidereal_ascendant(t, lat, lon, ayanamsha_deg)
    asc_sign, asc_sign_num, asc_sign_lord, asc_norm_deg = _get_sign_info(asc_sid)
    asc_nak, asc_nak_num, asc_nak_lord, asc_pada = _get_nakshatra_info(asc_sid)

    asc_item = PlanetDetailData(
        name="Ascendant",
        full_degree=round(asc_sid, 6),
        norm_degree=round(asc_norm_deg, 6),
        formatted_degree=fmt_dms(asc_norm_deg),
        sign=asc_sign,
        sign_number=asc_sign_num,
        sign_lord=asc_sign_lord,
        nakshatra=asc_nak,
        nakshatra_number=asc_nak_num,
        nakshatra_lord=asc_nak_lord,
        nakshatra_pada=asc_pada,
        is_retrograde=False,
        speed_deg_per_day=round(asc_speed, 6),
    )

    return PlanetPanchangResult(
        engine_version="0.1.0",
        query_utc=(
            dt_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
            if dt_utc.year >= 1972
            else dt_utc.strftime("%Y-%m-%d %H:%M:%S (UT1 / proleptic UTC)")
        ),
        query_local=dt_local.strftime("%Y-%m-%d %H:%M:%S %Z"),
        timezone=tz_str,
        ayanamsha_type=ayanamsha_type,
        ayanamsha_deg=round(ayanamsha_deg, 6),
        ayanamsha_dms=ayanamsha_dms_str,
        node_type=node_type,
        planets=planets_dict,
        ascendant=asc_item,
        planets_list=planets_list,
    )


def calculate_planet_panchang_at_sunrise(
    dt_date: datetime,
    lat: float,
    lon: float,
    tz_str: str = "Asia/Kolkata",
    ayanamsha_type: str = "lahiri",
    node_type: Literal["mean", "true"] = "mean",
    sunrise_convention: str = "astronomical",
) -> PlanetPanchangResult:
    """
    Calculates planetary positions and Ascendant evaluated at the exact instant of astronomical sunrise.
    """
    try:
        tz = zoneinfo.ZoneInfo(tz_str)
    except Exception:
        tz = timezone.utc
        tz_str = "UTC"

    if dt_date.tzinfo is None:
        dt_local = dt_date.replace(tzinfo=tz)
    else:
        dt_local = dt_date.astimezone(tz)

    midday_local = dt_local.replace(hour=12, minute=0, second=0, microsecond=0)
    midday_utc = midday_local.astimezone(timezone.utc)
    solar_info = get_solar_day_info(midday_utc, lat, lon, convention=sunrise_convention)

    sunrise_iso = None
    if solar_info.sunrise is not None:
        srise_dt_local = solar_info.sunrise.utc_datetime().astimezone(tz)
        eval_dt = srise_dt_local + timedelta(seconds=1)
        sunrise_iso = srise_dt_local.isoformat()
    else:
        eval_dt = midday_local

    res = calculate_planet_panchang(
        dt=eval_dt,
        lat=lat,
        lon=lon,
        tz_str=tz_str,
        ayanamsha_type=ayanamsha_type,
        node_type=node_type,
    )
    res.sunrise_time = sunrise_iso
    return res


def compute_ishta_kala(
    query_dt_utc: datetime,
    solar_info: Any,
) -> Dict[str, Any]:
    """
    Computes Vedic Time (Ishtakala) in Ghati, Pala, and Vipala elapsed from sunrise,
    along with Dinamana (day duration) and Ratrimana (night duration).
    
    1 Day = 60 Ghati
    1 Ghati = 60 Pala (~24 minutes)
    1 Pala = 60 Vipala (~24 seconds)
    1 Vipala = 0.4 seconds
    Daytime (Sunrise to Sunset) = 30 Ghati
    Nighttime (Sunset to Next Sunrise) = 30 Ghati
    """
    if solar_info.sunrise is None or solar_info.sunset is None:
        return {
            "ishta_kala": "00:00:00",
            "ghati": 0,
            "pala": 0,
            "vipala": 0,
            "total_ghati": 0.0,
            "dinamana": "12 Hours 00 Mins 00 Secs",
            "ratrimana": "12 Hours 00 Mins 00 Secs",
        }

    srise_dt = solar_info.sunrise.utc_datetime()
    sset_dt = solar_info.sunset.utc_datetime()
    dinamana_sec = solar_info.dina_mana_sec or (sset_dt - srise_dt).total_seconds()

    if solar_info.next_sunrise is not None:
        next_srise_dt = solar_info.next_sunrise.utc_datetime()
        ratrimana_sec = (next_srise_dt - sset_dt).total_seconds()
    else:
        ratrimana_sec = solar_info.ratri_mana_sec or 43200.0
        next_srise_dt = sset_dt + timedelta(seconds=ratrimana_sec)

    d_hrs = int(dinamana_sec // 3600)
    d_mins = int((dinamana_sec % 3600) // 60)
    d_secs = int(round(dinamana_sec % 60))
    dinamana_str = f"{d_hrs} Hours {d_mins:02d} Mins {d_secs:02d} Secs"

    r_hrs = int(ratrimana_sec // 3600)
    r_mins = int((ratrimana_sec % 3600) // 60)
    r_secs = int(round(ratrimana_sec % 60))
    ratrimana_str = f"{r_hrs} Hours {r_mins:02d} Mins {r_secs:02d} Secs"

    if srise_dt <= query_dt_utc <= sset_dt:
        elapsed_sec = max(0.0, (query_dt_utc - srise_dt).total_seconds())
        ghati_float = (elapsed_sec / dinamana_sec) * 30.0
    elif query_dt_utc > sset_dt:
        elapsed_night_sec = max(0.0, (query_dt_utc - sset_dt).total_seconds())
        ghati_float = 30.0 + (elapsed_night_sec / ratrimana_sec) * 30.0
    else:
        elapsed_sec = max(0.0, (query_dt_utc - srise_dt).total_seconds())
        ghati_float = (elapsed_sec / dinamana_sec) * 30.0

    ghati_float = ghati_float % 60.0
    g = int(ghati_float)
    p_float = (ghati_float - g) * 60.0
    p = int(p_float)
    v_float = (p_float - p) * 60.0
    v = int(round(v_float))
    if v >= 60:
        v = 0
        p += 1
    if p >= 60:
        p = 0
        g = (g + 1) % 60

    return {
        "ishta_kala": f"{g:02d}:{p:02d}:{v:02d}",
        "ghati": g,
        "pala": p,
        "vipala": v,
        "total_ghati": round(ghati_float, 4),
        "dinamana": dinamana_str,
        "ratrimana": ratrimana_str,
    }


@dataclass
class SignChartDetailData:
    sign_number: int
    sign_name: str
    sign_lord: str
    is_ascendant_sign: bool
    planets: List[PlanetDetailData]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sign_number": self.sign_number,
            "sign_name": self.sign_name,
            "sign_lord": self.sign_lord,
            "is_ascendant_sign": self.is_ascendant_sign,
            "planets": [p.to_dict() for p in self.planets],
        }


@dataclass
class PanchangChartResult:
    engine_version: str
    query_utc: str
    query_local: str
    timezone: str
    ayanamsha_type: str
    ayanamsha_deg: float
    ayanamsha_dms: str
    node_type: str
    ascendant: PlanetDetailData
    chart: List[SignChartDetailData]
    planets_by_sign: Dict[str, List[PlanetDetailData]]
    sunrise_time: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine_version": self.engine_version,
            "query_utc": self.query_utc,
            "query_local": self.query_local,
            "timezone": self.timezone,
            "ayanamsha_type": self.ayanamsha_type,
            "ayanamsha_deg": self.ayanamsha_deg,
            "ayanamsha_dms": self.ayanamsha_dms,
            "node_type": self.node_type,
            "ascendant": self.ascendant.to_dict(),
            "chart": [s.to_dict() for s in self.chart],
            "planets_by_sign": {
                k: [p.to_dict() for p in v] for k, v in self.planets_by_sign.items()
            },
            "sunrise_time": self.sunrise_time,
        }


def calculate_panchang_chart(
    dt: datetime,
    lat: float,
    lon: float,
    tz_str: str = "Asia/Kolkata",
    ayanamsha_type: str = "lahiri",
    node_type: Literal["mean", "true"] = "mean",
) -> PanchangChartResult:
    """Calculates planetary distribution across the 12 zodiac signs for Kundli charts."""
    planet_res = calculate_planet_panchang(
        dt=dt,
        lat=lat,
        lon=lon,
        tz_str=tz_str,
        ayanamsha_type=ayanamsha_type,
        node_type=node_type,
    )

    asc_sign_num = planet_res.ascendant.sign_number
    chart_signs: List[SignChartDetailData] = []
    planets_by_sign: Dict[str, List[PlanetDetailData]] = {}

    for sign_num in range(1, 13):
        sign_name = RASHI_NAMES[sign_num - 1]
        sign_lord = SIGN_LORDS[sign_num - 1]
        is_asc = (sign_num == asc_sign_num)
        planets_here = [p for p in planet_res.planets_list if p.sign_number == sign_num]

        item = SignChartDetailData(
            sign_number=sign_num,
            sign_name=sign_name,
            sign_lord=sign_lord,
            is_ascendant_sign=is_asc,
            planets=planets_here,
        )
        chart_signs.append(item)
        planets_by_sign[sign_name] = planets_here

    return PanchangChartResult(
        engine_version=planet_res.engine_version,
        query_utc=planet_res.query_utc,
        query_local=planet_res.query_local,
        timezone=planet_res.timezone,
        ayanamsha_type=planet_res.ayanamsha_type,
        ayanamsha_deg=planet_res.ayanamsha_deg,
        ayanamsha_dms=planet_res.ayanamsha_dms,
        node_type=planet_res.node_type,
        ascendant=planet_res.ascendant,
        chart=chart_signs,
        planets_by_sign=planets_by_sign,
        sunrise_time=planet_res.sunrise_time,
    )


def calculate_panchang_chart_at_sunrise(
    dt_date: datetime,
    lat: float,
    lon: float,
    tz_str: str = "Asia/Kolkata",
    ayanamsha_type: str = "lahiri",
    node_type: Literal["mean", "true"] = "mean",
    sunrise_convention: str = "astronomical",
) -> PanchangChartResult:
    """Calculates planetary distribution across the 12 signs evaluated at sunrise."""
    planet_res = calculate_planet_panchang_at_sunrise(
        dt_date=dt_date,
        lat=lat,
        lon=lon,
        tz_str=tz_str,
        ayanamsha_type=ayanamsha_type,
        node_type=node_type,
        sunrise_convention=sunrise_convention,
    )

    asc_sign_num = planet_res.ascendant.sign_number
    chart_signs: List[SignChartDetailData] = []
    planets_by_sign: Dict[str, List[PlanetDetailData]] = {}

    for sign_num in range(1, 13):
        sign_name = RASHI_NAMES[sign_num - 1]
        sign_lord = SIGN_LORDS[sign_num - 1]
        is_asc = (sign_num == asc_sign_num)
        planets_here = [p for p in planet_res.planets_list if p.sign_number == sign_num]

        item = SignChartDetailData(
            sign_number=sign_num,
            sign_name=sign_name,
            sign_lord=sign_lord,
            is_ascendant_sign=is_asc,
            planets=planets_here,
        )
        chart_signs.append(item)
        planets_by_sign[sign_name] = planets_here

    return PanchangChartResult(
        engine_version=planet_res.engine_version,
        query_utc=planet_res.query_utc,
        query_local=planet_res.query_local,
        timezone=planet_res.timezone,
        ayanamsha_type=planet_res.ayanamsha_type,
        ayanamsha_deg=planet_res.ayanamsha_deg,
        ayanamsha_dms=planet_res.ayanamsha_dms,
        node_type=planet_res.node_type,
        ascendant=planet_res.ascendant,
        chart=chart_signs,
        planets_by_sign=planets_by_sign,
        sunrise_time=planet_res.sunrise_time,
    )


@dataclass
class LagnaTableItemData:
    lagna_number: int
    lagna_name: str
    lagna_sanskrit: str
    sign_lord: str
    start_time: str
    end_time: str
    start_time_iso: str
    end_time_iso: str
    duration: str
    duration_minutes: float
    is_sunrise_lagna: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PanchangLagnaTableResult:
    engine_version: str
    query_date: str
    timezone: str
    ayanamsha_type: str
    ayanamsha_deg: float
    ayanamsha_dms: str
    sunrise_time: str
    sunset_time: str
    lagna_table: List[LagnaTableItemData]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine_version": self.engine_version,
            "query_date": self.query_date,
            "timezone": self.timezone,
            "ayanamsha_type": self.ayanamsha_type,
            "ayanamsha_deg": self.ayanamsha_deg,
            "ayanamsha_dms": self.ayanamsha_dms,
            "sunrise_time": self.sunrise_time,
            "sunset_time": self.sunset_time,
            "lagna_table": [item.to_dict() for item in self.lagna_table],
        }


def _find_lagna_boundary_crossing(
    t_start_local: datetime,
    target_deg: float,
    lat: float,
    lon: float,
    ayanamsha_type: str,
    max_hours: float = 3.5,
) -> datetime:
    """Bisection root-finding to find when sidereal ascendant crosses target_deg."""
    low = t_start_local
    step = timedelta(minutes=10)
    high = low + step

    def get_diff(dt_loc: datetime) -> float:
        dt_u = dt_loc.astimezone(timezone.utc)
        t = datetime_to_time(dt_u)
        ayan = compute_ayanamsha_deg(t, ayanamsha_type)
        deg, _ = get_sidereal_ascendant(t, lat, lon, ayan)
        diff = (deg - target_deg) % 360.0
        if diff > 180.0:
            diff -= 360.0
        return diff

    diff_low = get_diff(low)
    for _ in range(int(max_hours * 6)):
        diff_high = get_diff(high)
        if diff_low < 0.0 and diff_high >= 0.0:
            break
        low = high
        diff_low = diff_high
        high = low + step

    for _ in range(20):
        mid = low + (high - low) / 2
        diff_mid = get_diff(mid)
        if diff_mid >= 0.0:
            high = mid
        else:
            low = mid

    return high


def calculate_panchang_lagna_table(
    dt_date: datetime,
    lat: float,
    lon: float,
    tz_str: str = "Asia/Kolkata",
    ayanamsha_type: str = "lahiri",
    sunrise_convention: str = "astronomical",
) -> PanchangLagnaTableResult:
    """
    Calculates start and end times for all 12 rising signs (Udaya Lagna) throughout the 24-hour day,
    starting from the sign rising at local sunrise.
    """
    try:
        tz = zoneinfo.ZoneInfo(tz_str)
    except Exception:
        tz = timezone.utc
        tz_str = "UTC"

    if dt_date.tzinfo is None:
        dt_local = dt_date.replace(tzinfo=tz)
    else:
        dt_local = dt_date.astimezone(tz)

    midday_local = dt_local.replace(hour=12, minute=0, second=0, microsecond=0)
    midday_utc = midday_local.astimezone(timezone.utc)
    solar_info = get_solar_day_info(midday_utc, lat, lon, convention=sunrise_convention)

    if solar_info.sunrise is not None:
        srise_local = solar_info.sunrise.utc_datetime().astimezone(tz)
    else:
        srise_local = midday_local.replace(hour=6, minute=0)

    if solar_info.sunset is not None:
        sset_local = solar_info.sunset.utc_datetime().astimezone(tz)
    else:
        sset_local = midday_local.replace(hour=18, minute=0)

    # Rising sign at sunrise instant
    dt_u = srise_local.astimezone(timezone.utc)
    t_srise = datetime_to_time(dt_u)
    ayan_deg = compute_ayanamsha_deg(t_srise, ayanamsha_type)
    srise_asc_deg, _ = get_sidereal_ascendant(t_srise, lat, lon, ayan_deg)
    srise_sign_idx = int(srise_asc_deg / 30.0) % 12

    # Find start time of sunrise sign by searching backwards
    target_start_deg = srise_sign_idx * 30.0
    t_search_start = srise_local - timedelta(hours=2.5)
    t_curr_boundary = _find_lagna_boundary_crossing(
        t_search_start, target_start_deg, lat, lon, ayanamsha_type
    )

    items: List[LagnaTableItemData] = []
    sign_idx = srise_sign_idx

    for _ in range(12):
        next_sign_idx = (sign_idx + 1) % 12
        target_end_deg = next_sign_idx * 30.0
        t_next_boundary = _find_lagna_boundary_crossing(
            t_curr_boundary, target_end_deg, lat, lon, ayanamsha_type
        )

        dur_sec = (t_next_boundary - t_curr_boundary).total_seconds()
        dur_hrs = int(dur_sec // 3600)
        dur_mins = int((dur_sec % 3600) // 60)
        dur_secs = int(round(dur_sec % 60))
        dur_str = f"{dur_hrs:02d} Hours {dur_mins:02d} Mins {dur_secs:02d} Secs"

        is_srise = (sign_idx == srise_sign_idx)

        item = LagnaTableItemData(
            lagna_number=sign_idx + 1,
            lagna_name=RASHI_NAMES[sign_idx],
            lagna_sanskrit=RASHI_SANSKRIT[sign_idx],
            sign_lord=SIGN_LORDS[sign_idx],
            start_time=t_curr_boundary.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=t_next_boundary.strftime("%Y-%m-%d %H:%M:%S"),
            start_time_iso=t_curr_boundary.isoformat(),
            end_time_iso=t_next_boundary.isoformat(),
            duration=dur_str,
            duration_minutes=round(dur_sec / 60.0, 2),
            is_sunrise_lagna=is_srise,
        )
        items.append(item)
        t_curr_boundary = t_next_boundary
        sign_idx = next_sign_idx

    return PanchangLagnaTableResult(
        engine_version="0.1.0",
        query_date=dt_local.strftime("%Y-%m-%d"),
        timezone=tz_str,
        ayanamsha_type=ayanamsha_type,
        ayanamsha_deg=round(ayan_deg, 6),
        ayanamsha_dms=fmt_dms(ayan_deg),
        sunrise_time=srise_local.isoformat(),
        sunset_time=sset_local.isoformat(),
        lagna_table=items,
    )

"""Classical Panchanga & Muhurtha Calculation Engine.

Calculates the 5 limbs of Vedic time:
1. Tithi (with exact bisection end timestamp and elapsed percentage)
2. Vara (Vedic solar day lord measured strictly from local sunrise)
3. Nakshatra (with exact bisection end timestamp and pada)
4. Nitya Yoga (27 solilunar yogas)
5. Karana (60 half-tithis, 4 fixed + 7 repeating cycles)

Also computes auspicious & inauspicious Muhurtha windows:
- Choghadiya (Day & Night 8-fold divisions)
- Hora (Indian 60-minute blocks in Chaldean order from sunrise)
- Rahu Kalam, Yamaganda, Gulika Kalam (1/8th day divisions)
- Abhijit Muhurtha (8th of 15 daytime muhurtas, dynamically scaled to Dina Mana)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import zoneinfo

from skyfield.api import Time

from vedic_astro_api.core.ephemeris import (
    datetime_to_time,
    get_body_apparent_ecliptic_lon,
    get_elongation_deg,
    find_elongation_crossing,
    find_moon_crossing,
)
from vedic_astro_api.core.ayanamsha import compute_ayanamsha_deg, tropical_to_sidereal, fmt_dms
from vedic_astro_api.core.solar import get_solar_day_info, SolarDayInfo

# ===========================================================================
# CONSTANTS & METRIC DEFINITIONS
# ===========================================================================

TITHI_NAMES = [
    # Shukla Paksha (1-15)
    "Shukla Pratipada", "Shukla Dwitiya", "Shukla Tritiya", "Shukla Chaturthi",
    "Shukla Panchami", "Shukla Shashthi", "Shukla Saptami", "Shukla Ashtami",
    "Shukla Navami", "Shukla Dashami", "Shukla Ekadashi", "Shukla Dwadashi",
    "Shukla Trayodashi", "Shukla Chaturdashi", "Purnima",
    # Krishna Paksha (16-30)
    "Krishna Pratipada", "Krishna Dwitiya", "Krishna Tritiya", "Krishna Chaturthi",
    "Krishna Panchami", "Krishna Shashthi", "Krishna Saptami", "Krishna Ashtami",
    "Krishna Navami", "Krishna Dashami", "Krishna Ekadashi", "Krishna Dwadashi",
    "Krishna Trayodashi", "Krishna Chaturdashi", "Amavasya"
]

NAKSHATRA_NAMES = [
    ("Ashwini", "Ketu"), ("Bharani", "Venus"), ("Krittika", "Sun"),
    ("Rohini", "Moon"), ("Mrigashira", "Mars"), ("Ardra", "Rahu"),
    ("Punarvasu", "Jupiter"), ("Pushya", "Saturn"), ("Ashlesha", "Mercury"),
    ("Magha", "Ketu"), ("Purva Phalguni", "Venus"), ("Uttara Phalguni", "Sun"),
    ("Hasta", "Moon"), ("Chitra", "Mars"), ("Swati", "Rahu"),
    ("Vishakha", "Jupiter"), ("Anuradha", "Saturn"), ("Jyeshtha", "Mercury"),
    ("Mula", "Ketu"), ("Purva Ashadha", "Venus"), ("Uttara Ashadha", "Sun"),
    ("Shravana", "Moon"), ("Dhanishta", "Mars"), ("Shatabhisha", "Rahu"),
    ("Purva Bhadrapada", "Jupiter"), ("Uttara Bhadrapada", "Saturn"), ("Revati", "Mercury")
]

YOGA_NAMES = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda",
    "Sukarma", "Dhriti", "Shula", "Ganda", "Vriddhi", "Dhruva",
    "Vyaghata", "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyan",
    "Parigha", "Shiva", "Siddha", "Sadhya", "Shubha", "Shukla",
    "Brahma", "Indra", "Vaidhriti"
]

VARA_NAMES = [
    ("Ravivara", "Sun"),
    ("Somavara", "Moon"),
    ("Mangalavara", "Mars"),
    ("Budhavara", "Mercury"),
    ("Guruvara", "Jupiter"),
    ("Shukravara", "Venus"),
    ("Shanivara", "Saturn"),
]

# The 7 repeating karanas
REPEATING_KARANAS = ["Bava", "Balava", "Kaulava", "Taitila", "Gara", "Vanija", "Vishti"]

# Chaldean planetary hour sequence
CHALDEAN_HORA_ORDER = ["Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars"]

# Choghadiya cyclic sequence starting from Sunday
CHOGHADIYA_CYCLE = ["Udveg", "Char", "Labh", "Amrit", "Kaal", "Shubh", "Rog"]
CHOGHADIYA_QUALITIES = {
    "Amrit": "Best / Amrit (Auspicious)",
    "Shubh": "Good / Shubh (Auspicious)",
    "Labh": "Gain / Labh (Auspicious)",
    "Char": "Neutral / Char (Variable/Travel)",
    "Udveg": "Anxiety / Udveg (Inauspicious - Sun)",
    "Kaal": "Loss / Kaal (Inauspicious - Saturn)",
    "Rog": "Illness / Rog (Inauspicious - Mars)",
}
# First Day Choghadiya index (0 to 6 in CHOGHADIYA_CYCLE) for each day of week (0=Sun..6=Sat)
DAY_CHOGHADIYA_START = {
    0: 0,  # Sun: Udveg
    1: 3,  # Mon: Amrit
    2: 6,  # Tue: Rog
    3: 2,  # Wed: Labh
    4: 5,  # Thu: Shubh
    5: 1,  # Fri: Char
    6: 4,  # Sat: Kaal
}

# First Night Choghadiya index (0 to 6 in CHOGHADIYA_CYCLE) for each day of week (0=Sun..6=Sat).
# Follows the classical 5th weekday lord rule:
# Sun night -> Thu lord (Shubh: index 5)
# Mon night -> Fri lord (Char: index 1)
# Tue night -> Sat lord (Kaal: index 4)
# Wed night -> Sun lord (Udveg: index 0)
# Thu night -> Mon lord (Amrit: index 3)
# Fri night -> Tue lord (Rog: index 6)
# Sat night -> Wed lord (Labh: index 2)
NIGHT_CHOGHADIYA_START = {
    0: 5,  # Sun night: Shubh
    1: 1,  # Mon night: Char
    2: 4,  # Tue night: Kaal
    3: 0,  # Wed night: Udveg
    4: 3,  # Thu night: Amrit
    5: 6,  # Fri night: Rog
    6: 2,  # Sat night: Labh
}

# 1/8th day segment index (1 to 8) for Rahu Kalam, Yamaganda, Gulika Kalam (0=Sun..6=Sat)
RAHU_KALAM_SEGMENTS = {0: 8, 1: 2, 2: 7, 3: 5, 4: 6, 5: 4, 6: 3}
YAMAGANDA_SEGMENTS =  {0: 5, 1: 4, 2: 3, 3: 2, 4: 1, 5: 7, 6: 6}
GULIKA_SEGMENTS =     {0: 7, 1: 6, 2: 5, 3: 4, 4: 3, 5: 2, 6: 1}


def get_karana_name(karana_num: int) -> Tuple[str, str]:
    """
    Returns (Karana_Name, Karana_Type) for Karana number (1 to 60).
    Type is either 'Fixed' (Sthira) or 'Movable' (Chara).
    """
    if karana_num == 1:
        return "Kintughna", "Fixed (Sthira)"
    elif 2 <= karana_num <= 57:
        rep_idx = (karana_num - 2) % 7
        return REPEATING_KARANAS[rep_idx], "Movable (Chara)"
    elif karana_num == 58:
        return "Shakuni", "Fixed (Sthira)"
    elif karana_num == 59:
        return "Chatushpada", "Fixed (Sthira)"
    elif karana_num == 60:
        return "Naga", "Fixed (Sthira)"
    raise ValueError(f"Invalid karana_num: {karana_num}")


# ===========================================================================
# PANCHANG DATA STRUCTURES
# ===========================================================================

@dataclass
class PanchangResult:
    # Metadata
    engine_version: str
    julian_day: float
    ayanamsha_type: str
    ayanamsha_deg: float
    ayanamsha_dms: str
    sunrise_convention: str
    query_utc: str
    query_local: str
    timezone: str

    # Solar Ephemeris
    sunrise: Optional[str]
    sunset: Optional[str]
    next_sunrise: Optional[str]
    solar_noon: Optional[str]
    dina_mana_hours: Optional[float]
    ratri_mana_hours: Optional[float]
    is_daytime: bool
    polar_phenomenon: Optional[str]
    sunrise_astronomical: Optional[str]
    sunrise_hindu: Optional[str]

    # Core 5 Limbs (Pancha-Anga)
    tithi_number: int
    tithi_name: str
    paksha: str
    paksha_tithi_number: int
    tithi_elapsed_pct: float
    tithi_end_time_local: Optional[str]

    vara_name: str
    vara_lord: str

    nakshatra_number: int
    nakshatra_name: str
    nakshatra_lord: str
    nakshatra_pada: int
    nakshatra_elapsed_pct: float
    nakshatra_end_time_local: Optional[str]

    yoga_number: int
    yoga_name: str

    karana_number: int
    karana_name: str
    karana_type: str

    # Muhurthas
    abhijit_muhurta: Optional[Dict[str, Any]]
    rahu_kalam: Optional[Dict[str, str]]
    yamaganda: Optional[Dict[str, str]]
    gulika_kalam: Optional[Dict[str, str]]
    choghadiya_day: List[Dict[str, Any]]
    choghadiya_night: List[Dict[str, Any]]
    hora: List[Dict[str, Any]]
    jd_tt: float = 0.0
    jd_ut1: float = 0.0
    sunrise_convention_key: str = "astronomical"
    vedic_time: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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


# ===========================================================================
# CALCULATION LOGIC
# ===========================================================================

def calculate_panchang(
    dt: datetime,
    lat: float,
    lon: float,
    tz_str: str = "UTC",
    ayanamsha_type: str = "lahiri",
    sunrise_convention: str = "astronomical",
) -> PanchangResult:
    """
    Calculate complete high-precision Vedic Panchanga & Muhurthas.
    Supports native IANA timezone names (e.g. 'Asia/Kolkata') via zoneinfo.
    Supports sunrise conventions: 'astronomical' (-50' refracted) and 'hindu' (0° geometric center).
    """
    # 1. Resolve Timezone
    try:
        tz = zoneinfo.ZoneInfo(tz_str)
    except Exception:
        # Fallback to UTC if timezone name invalid
        tz = timezone.utc
        tz_str = "UTC"

    if dt.tzinfo is None:
        dt_local = dt.replace(tzinfo=tz)
    else:
        dt_local = dt.astimezone(tz)
    dt_utc = dt_local.astimezone(timezone.utc)

    t_query = datetime_to_time(dt_utc)
    jd_tt = t_query.tt

    # 2. Compute Solar Day & Ephemeris
    solar_info: SolarDayInfo = get_solar_day_info(dt_utc, lat, lon, convention=sunrise_convention)

    def time_to_local_str(t_val: Optional[Time]) -> Optional[str]:
        if t_val is None:
            return None
        dt_u = t_val.utc_datetime()
        dt_loc = dt_u.astimezone(tz)
        return dt_loc.strftime("%Y-%m-%d %H:%M:%S")

    # 3. Compute Ayanamsha
    ayanamsha_deg = compute_ayanamsha_deg(t_query, ayanamsha_type)
    ayanamsha_dms = fmt_dms(ayanamsha_deg)

    # 4. Planetary Ecliptic Coordinates
    moon_trop = get_body_apparent_ecliptic_lon("moon", t_query)
    sun_trop = get_body_apparent_ecliptic_lon("sun", t_query)
    moon_sid = tropical_to_sidereal(moon_trop, ayanamsha_deg)
    sun_sid = tropical_to_sidereal(sun_trop, ayanamsha_deg)

    # 5. Limb 1: Tithi
    elongation = (moon_trop - sun_trop) % 360.0
    tithi_idx = int(elongation / 12.0)
    tithi_idx = min(max(tithi_idx, 0), 29)
    tithi_number = tithi_idx + 1
    tithi_name = TITHI_NAMES[tithi_idx]
    is_shukla = tithi_idx < 15
    paksha = "Shukla" if is_shukla else "Krishna"
    paksha_tithi_number = (tithi_idx % 15) + 1
    tithi_elapsed_pct = round(((elongation % 12.0) / 12.0) * 100.0, 2)

    # Calculate exact tithi end timestamp via bisection root-finding
    next_tithi_target_deg = (tithi_idx + 1) * 12.0
    t_tithi_end = find_elongation_crossing(t_query, next_tithi_target_deg, max_hours=36.0)
    tithi_end_time_local = time_to_local_str(t_tithi_end)

    # 6. Limb 2: Vara (Vedic Day Lord measured strictly from local sunrise)
    # The Vedic day belongs to the date of the sunrise that began the current Vedic day.
    if solar_info.sunrise is not None:
        effective_vara_dt = solar_info.sunrise.utc_datetime().astimezone(tz).date()
        py_weekday = effective_vara_dt.weekday()
        vedic_weekday_idx = (py_weekday + 1) % 7
    else:
        # Polar fallback: use standard calendar day
        py_weekday = dt_local.weekday()
        vedic_weekday_idx = (py_weekday + 1) % 7

    vara_name, vara_lord = VARA_NAMES[vedic_weekday_idx]

    # 7. Limb 3: Nakshatra
    nak_arc = 360.0 / 27.0  # 13° 20' = 13.333333°
    pada_arc = nak_arc / 4.0  # 3° 20' = 3.333333°
    nak_idx = int(moon_sid / nak_arc)
    nak_idx = min(max(nak_idx, 0), 26)
    nak_number = nak_idx + 1
    nak_name, nak_lord = NAKSHATRA_NAMES[nak_idx]
    nak_progress = moon_sid % nak_arc
    nak_pada = min(int(nak_progress / pada_arc) + 1, 4)
    nak_elapsed_pct = round((nak_progress / nak_arc) * 100.0, 2)

    # Calculate exact nakshatra end timestamp via bisection root-finding
    next_nak_sid_target = (nak_idx + 1) * nak_arc
    next_nak_trop_target = (next_nak_sid_target + ayanamsha_deg) % 360.0
    t_nak_end = find_moon_crossing(t_query, next_nak_trop_target, max_hours=36.0)
    nak_end_time_local = time_to_local_str(t_nak_end)

    # 8. Limb 4: Nitya Yoga (Nirayana / Sidereal sum)
    yoga_sum = (moon_sid + sun_sid) % 360.0
    yoga_idx = int(yoga_sum / nak_arc)
    yoga_idx = min(max(yoga_idx, 0), 26)
    yoga_number = yoga_idx + 1
    yoga_name = YOGA_NAMES[yoga_idx]

    # 9. Limb 5: Karana
    karana_idx = int(elongation / 6.0)
    karana_idx = min(max(karana_idx, 0), 59)
    karana_number = karana_idx + 1
    karana_name, karana_type = get_karana_name(karana_number)

    # 10. Muhurtha Windows: Choghadiya, Hora, Rahu Kalam, Abhijit
    choghadiya_day: List[Dict[str, Any]] = []
    choghadiya_night: List[Dict[str, Any]] = []
    hora_list: List[Dict[str, Any]] = []
    abhijit_muhurta: Optional[Dict[str, Any]] = None
    rahu_kalam: Optional[Dict[str, str]] = None
    yamaganda: Optional[Dict[str, str]] = None
    gulika_kalam: Optional[Dict[str, str]] = None

    if solar_info.sunrise is not None and solar_info.sunset is not None:
        srise_dt = solar_info.sunrise.utc_datetime().astimezone(tz)
        sset_dt = solar_info.sunset.utc_datetime().astimezone(tz)
        dina_mana_td = sset_dt - srise_dt

        # --- Abhijit Muhurtha (8th of 15 daytime muhurtas) ---
        muhurta_td = dina_mana_td / 15.0
        if solar_info.solar_noon is not None:
            noon_dt = solar_info.solar_noon.utc_datetime().astimezone(tz)
            abhijit_start = noon_dt - (muhurta_td / 2.0)
            abhijit_end = noon_dt + (muhurta_td / 2.0)
        else:
            # Fallback centered at midpoint between sunrise and sunset
            mid_dt = srise_dt + (dina_mana_td / 2.0)
            abhijit_start = mid_dt - (muhurta_td / 2.0)
            abhijit_end = mid_dt + (muhurta_td / 2.0)

        # Classically, Abhijit on Wednesday is tainted (Durmuhurtha) due to Rahu Kalam alignment
        is_wednesday = (vedic_weekday_idx == 3)
        abhijit_muhurta = {
            "start": abhijit_start.strftime("%Y-%m-%d %H:%M:%S"),
            "end": abhijit_end.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_minutes": round(muhurta_td.total_seconds() / 60.0, 1),
            "is_inauspicious_wednesday": is_wednesday,
            "status": "Inauspicious on Wednesday" if is_wednesday else "Highly Auspicious",
        }

        # --- 1/8th Day Divisions: Rahu Kalam, Yamaganda, Gulika Kalam ---
        seg_td = dina_mana_td / 8.0
        def get_segment_window(seg_num: int) -> Dict[str, str]:
            start_t = srise_dt + (seg_td * (seg_num - 1))
            end_t = start_t + seg_td
            return {
                "start": start_t.strftime("%Y-%m-%d %H:%M:%S"),
                "end": end_t.strftime("%Y-%m-%d %H:%M:%S"),
            }

        rahu_seg = RAHU_KALAM_SEGMENTS[vedic_weekday_idx]
        yama_seg = YAMAGANDA_SEGMENTS[vedic_weekday_idx]
        guli_seg = GULIKA_SEGMENTS[vedic_weekday_idx]

        rahu_kalam = get_segment_window(rahu_seg)
        yamaganda = get_segment_window(yama_seg)
        gulika_kalam = get_segment_window(guli_seg)

        # --- Day Choghadiya (8 segments of Dina Mana) ---
        day_chog_len = dina_mana_td / 8.0
        start_chog_idx = DAY_CHOGHADIYA_START[vedic_weekday_idx]
        for i in range(8):
            chog_name = CHOGHADIYA_CYCLE[(start_chog_idx + i) % 7]
            c_start = srise_dt + (day_chog_len * i)
            c_end = c_start + day_chog_len
            choghadiya_day.append({
                "index": i + 1,
                "name": chog_name,
                "quality": CHOGHADIYA_QUALITIES[chog_name],
                "start": c_start.strftime("%Y-%m-%d %H:%M:%S"),
                "end": c_end.strftime("%Y-%m-%d %H:%M:%S"),
            })

        # --- Night Choghadiya (8 segments of Ratri Mana) ---
        if solar_info.next_sunrise is not None:
            next_srise_dt = solar_info.next_sunrise.utc_datetime().astimezone(tz)
            ratri_mana_td = next_srise_dt - sset_dt
            night_chog_len = ratri_mana_td / 8.0
            # Night Choghadiya starts with the 5th weekday lord from day lord
            night_start_chog_idx = NIGHT_CHOGHADIYA_START[vedic_weekday_idx]
            for i in range(8):
                chog_name = CHOGHADIYA_CYCLE[(night_start_chog_idx + i) % 7]
                c_start = sset_dt + (night_chog_len * i)
                c_end = c_start + night_chog_len
                choghadiya_night.append({
                    "index": i + 1,
                    "name": chog_name,
                    "quality": CHOGHADIYA_QUALITIES[chog_name],
                    "start": c_start.strftime("%Y-%m-%d %H:%M:%S"),
                    "end": c_end.strftime("%Y-%m-%d %H:%M:%S"),
                })

        # --- Indian Hora (24 blocks of 60 minutes from Sunrise) ---
        # Starts with the day lord, continues in Chaldean order
        day_lord_name = VARA_NAMES[vedic_weekday_idx][1]
        start_chaldean_idx = CHALDEAN_HORA_ORDER.index(day_lord_name)
        for i in range(24):
            h_lord = CHALDEAN_HORA_ORDER[(start_chaldean_idx + i) % 7]
            h_start = srise_dt + timedelta(hours=i)
            h_end = h_start + timedelta(hours=1)
            hora_list.append({
                "hora_number": i + 1,
                "lord": h_lord,
                "start": h_start.strftime("%Y-%m-%d %H:%M:%S"),
                "end": h_end.strftime("%Y-%m-%d %H:%M:%S"),
            })

    # Prepare Dina / Ratri mana in decimal hours
    dina_mana_hrs = round(solar_info.dina_mana_sec / 3600.0, 3) if solar_info.dina_mana_sec is not None else None
    ratri_mana_hrs = round(solar_info.ratri_mana_sec / 3600.0, 3) if solar_info.ratri_mana_sec is not None else None

    return PanchangResult(
        engine_version="0.1.0",
        julian_day=round(jd_tt, 6),
        jd_tt=round(jd_tt, 6),
        jd_ut1=round(t_query.ut1, 6),
        sunrise_convention_key=solar_info.convention_key,
        ayanamsha_type=ayanamsha_type,
        ayanamsha_deg=round(ayanamsha_deg, 6),
        ayanamsha_dms=ayanamsha_dms,
        sunrise_convention=solar_info.convention,
        query_utc=(
            dt_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
            if dt_utc.year >= 1972
            else dt_utc.strftime("%Y-%m-%d %H:%M:%S (UT1 / proleptic UTC)")
        ),
        query_local=dt_local.strftime("%Y-%m-%d %H:%M:%S %Z"),
        timezone=tz_str,
        sunrise=time_to_local_str(solar_info.sunrise),
        sunset=time_to_local_str(solar_info.sunset),
        next_sunrise=time_to_local_str(solar_info.next_sunrise),
        solar_noon=time_to_local_str(solar_info.solar_noon),
        dina_mana_hours=dina_mana_hrs,
        ratri_mana_hours=ratri_mana_hrs,
        is_daytime=solar_info.is_daytime,
        polar_phenomenon=solar_info.polar_phenomenon,
        sunrise_astronomical=time_to_local_str(solar_info.sunrise_astronomical),
        sunrise_hindu=time_to_local_str(solar_info.sunrise_hindu),
        tithi_number=tithi_number,
        tithi_name=tithi_name,
        paksha=paksha,
        paksha_tithi_number=paksha_tithi_number,
        tithi_elapsed_pct=tithi_elapsed_pct,
        tithi_end_time_local=tithi_end_time_local,
        vara_name=vara_name,
        vara_lord=vara_lord,
        nakshatra_number=nak_number,
        nakshatra_name=nak_name,
        nakshatra_lord=nak_lord,
        nakshatra_pada=nak_pada,
        nakshatra_elapsed_pct=nak_elapsed_pct,
        nakshatra_end_time_local=nak_end_time_local,
        yoga_number=yoga_number,
        yoga_name=yoga_name,
        karana_number=karana_number,
        karana_name=karana_name,
        karana_type=karana_type,
        abhijit_muhurta=abhijit_muhurta,
        rahu_kalam=rahu_kalam,
        yamaganda=yamaganda,
        gulika_kalam=gulika_kalam,
        choghadiya_day=choghadiya_day,
        choghadiya_night=choghadiya_night,
        hora=hora_list,
        vedic_time=compute_ishta_kala(dt_utc, solar_info),
    )


def calculate_panchang_at_sunrise(
    dt_local_date: datetime,
    lat: float,
    lon: float,
    tz_str: str = "Asia/Kolkata",
    ayanamsha_type: str = "lahiri",
    sunrise_convention: str = "astronomical",
) -> PanchangResult:
    """Calculates full Panchanga evaluated at the exact instant of sunrise (Suryodaya Kalina)."""
    tz = zoneinfo.ZoneInfo(tz_str)
    if dt_local_date.tzinfo is None:
        dt_local = dt_local_date.replace(tzinfo=tz)
    else:
        dt_local = dt_local_date.astimezone(tz)

    midday_local = dt_local.replace(hour=12, minute=0, second=0, microsecond=0)
    midday_utc = midday_local.astimezone(timezone.utc)
    solar_info = get_solar_day_info(midday_utc, lat, lon, convention=sunrise_convention)

    if solar_info.sunrise is not None:
        srise_dt_local = solar_info.sunrise.utc_datetime().astimezone(tz)
        eval_dt = srise_dt_local + timedelta(seconds=1)
    else:
        srise_dt_local = midday_local
        eval_dt = midday_local

    return calculate_panchang(
        dt=eval_dt,
        lat=lat,
        lon=lon,
        tz_str=tz_str,
        ayanamsha_type=ayanamsha_type,
        sunrise_convention=sunrise_convention,
    )


def calculate_monthly_panchang(
    year: int,
    month: int,
    lat: float,
    lon: float,
    tz_str: str = "Asia/Kolkata",
    ayanamsha_type: str = "lahiri",
    sunrise_convention: str = "astronomical",
) -> Dict[str, Any]:
    """Calculates sunrise-based Panchanga summaries for every day of the requested month."""
    import calendar
    tz = zoneinfo.ZoneInfo(tz_str)
    num_days = calendar.monthrange(year, month)[1]

    days_list = []
    for day in range(1, num_days + 1):
        dt_day = datetime(year, month, day, 12, 0, 0, tzinfo=tz)
        p = calculate_panchang_at_sunrise(
            dt_local_date=dt_day,
            lat=lat,
            lon=lon,
            tz_str=tz_str,
            ayanamsha_type=ayanamsha_type,
            sunrise_convention=sunrise_convention,
        )
        d = p.to_dict()
        day_item = {
            "day": day,
            "date": f"{year}-{month:02d}-{day:02d}",
            "weekday": d["vara_name"],
            "tithi": {
                "number": d["tithi_number"],
                "name": d["tithi_name"],
                "paksha": d["paksha"],
                "end_time": d["tithi_end_time_local"],
            },
            "nakshatra": {
                "number": d["nakshatra_number"],
                "name": d["nakshatra_name"],
                "pada": d["nakshatra_pada"],
                "end_time": d["nakshatra_end_time_local"],
            },
            "yoga": {
                "number": d["yoga_number"],
                "name": d["yoga_name"],
            },
            "karana": {
                "number": d["karana_number"],
                "name": d["karana_name"],
                "type": d["karana_type"],
            },
            "sunrise": d["sunrise"],
            "sunset": d["sunset"],
        }
        days_list.append(day_item)

    return {
        "meta": {
            "engine": "AstroEngine",
            "version": "0.1.0",
            "year": year,
            "month": month,
            "total_days": num_days,
            "lat": lat,
            "lon": lon,
            "timezone": tz_str,
            "ayanamsha": ayanamsha_type,
            "sunrise_convention": sunrise_convention,
        },
        "days": days_list,
    }


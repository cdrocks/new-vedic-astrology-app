from datetime import datetime, timedelta
from typing import Any
import swisseph as swe

# ==========================================
# BASIC CONSTANTS FOR D1 CHART
# ==========================================
RASHI_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

PLANETS = {
    swe.SUN: 'Sun', swe.MOON: 'Moon', swe.MERCURY: 'Mercury',
    swe.VENUS: 'Venus', swe.MARS: 'Mars', swe.JUPITER: 'Jupiter',
    swe.SATURN: 'Saturn', swe.TRUE_NODE: 'Rahu'
}

DIGNITIES = {
    "Sun":     {"exalted": "Aries",     "debilitated": "Libra",      "moolatrikona": ("Leo", 0.0, 20.0),         "own": ["Leo"]},
    "Moon":    {"exalted": "Taurus",    "debilitated": "Scorpio",    "moolatrikona": ("Taurus", 3.0, 30.0),      "own": ["Cancer"]},
    "Mars":    {"exalted": "Capricorn", "debilitated": "Cancer",     "moolatrikona": ("Aries", 0.0, 12.0),       "own": ["Aries", "Scorpio"]},
    "Mercury": {"exalted": "Virgo",     "debilitated": "Pisces",     "moolatrikona": ("Virgo", 15.0, 20.0),      "own": ["Gemini", "Virgo"]},
    "Jupiter": {"exalted": "Cancer",    "debilitated": "Capricorn",  "moolatrikona": ("Sagittarius", 0.0, 10.0), "own": ["Sagittarius", "Pisces"]},
    "Venus":   {"exalted": "Pisces",    "debilitated": "Virgo",      "moolatrikona": ("Libra", 0.0, 15.0),       "own": ["Taurus", "Libra"]},
    "Saturn":  {"exalted": "Libra",     "debilitated": "Aries",      "moolatrikona": ("Aquarius", 0.0, 20.0),    "own": ["Capricorn", "Aquarius"]}
}


def get_dignity(planet_name, sign, deg_in_sign=None):
    if planet_name not in DIGNITIES:
        return None
    d = DIGNITIES[planet_name]

    # If degree in sign is provided, use precise BPHS Ch. 3 boundaries
    if deg_in_sign is not None:
        deg = float(deg_in_sign)
        # Special case: Mercury in Virgo (0-15 Exalted, 15-20 Moolatrikona, 20-30 Own)
        if planet_name == "Mercury" and sign == "Virgo":
            if deg <= 15.0:
                return "Exalted"
            elif deg <= 20.0:
                return "Moolatrikona"
            else:
                return "Own Sign"

        # Special case: Moon in Taurus (0-3 Exalted, 3-30 Moolatrikona)
        if planet_name == "Moon" and sign == "Taurus":
            if deg <= 3.0:
                return "Exalted"
            else:
                return "Moolatrikona"

        # Moolatrikona check for other planets
        mt_sign, mt_start, mt_end = d["moolatrikona"]
        if mt_start is not None and mt_end is not None and sign == mt_sign and float(mt_start) <= deg <= float(mt_end):
            return "Moolatrikona"

    # Standard sign-level dignity (used when deg is not provided or falls outside MT)
    if sign == d["exalted"]:
        return "Exalted"
    elif sign == d["debilitated"]:
        return "Debilitated"
    elif sign in d["own"]:
        return "Own Sign"
    return None


def fmt_dms(deg, precision=1, max_deg=None):
    """
    Roll-over-safe degree formatting to DD°MM'SS.s" (or DD°MM'SS").
    Prevents 59.999" rounding up to 60.0" without incrementing minutes/degrees.
    """
    deg_val = deg % 360.0 if max_deg == 360 else (deg % 30.0 if max_deg == 30 else deg)
    total_sec = round(deg_val * 3600.0, precision)
    d = int(total_sec // 3600)
    m = int((total_sec % 3600) // 60)
    s = round(total_sec % 60, precision)
    if s >= 60.0:
        s -= 60.0
        m += 1
    if m >= 60:
        m -= 60
        d += 1
    if max_deg is not None and d >= max_deg:
        d = d % max_deg
    if precision == 0:
        return f"{d:02d}°{m:02d}'{int(round(s)):02d}\""
    return f"{d:02d}°{m:02d}'{s:04.{precision}f}\""


def get_house_from_sign_idx(ref_sign_idx, planet_sign_idx):
    return (planet_sign_idx - ref_sign_idx) % 12 + 1


# ==========================================
# COMBUSTION (ASTANGATA) ENGINE — SURYA SIDDHANTA & BPHS
# ==========================================
COMBUSTION_LIMITS = {
    "Moon":    {"direct": 12.0, "rx": 12.0},
    "Mars":    {"direct": 17.0, "rx": 17.0},
    "Mercury": {"direct": 14.0, "rx": 12.0},
    "Jupiter": {"direct": 11.0, "rx": 11.0},
    "Venus":   {"direct": 10.0, "rx": 8.0},
    "Saturn":  {"direct": 15.0, "rx": 15.0},
}


def get_combustion_status(planet_name, data):
    planet_name = str(planet_name).strip()
    clean_data = {str(k).strip(): v for k, v in data.items()}

    if planet_name in ["Sun", "Rahu", "Ketu", "Ascendant"]:
        return None
    if "Sun" not in clean_data or planet_name not in clean_data:
        return None

    sun_d = clean_data["Sun"]["degree_total"]
    p_d = clean_data[planet_name]["degree_total"]
    distance = abs(sun_d - p_d)
    if distance > 180.0:
        distance = 360.0 - distance

    is_rx = clean_data[planet_name].get("status") == "Rx"
    limits = COMBUSTION_LIMITS.get(planet_name)
    if not limits:
        return None

    limit = limits["rx"] if is_rx else limits["direct"]
    if distance <= limit:
        return "Combust"
    return None


VEDIC_FLAGS = swe.FLG_SIDEREAL | swe.FLG_SPEED


def build_d1_raw(jd, lat, lon, flags=None):
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = VEDIC_FLAGS if flags is None else (flags | VEDIC_FLAGS)
    chart_data: dict[str, dict[str, Any]] = {}

    # Ascendant (using geographic latitude directly per classical Parashari / JHora standard)
    _, ascmc = swe.houses_ex(jd, lat, lon, b'W', flags)
    asc_deg = ascmc[0]
    asc_sign_idx = int(asc_deg / 30) % 12
    asc_sign = RASHI_NAMES[asc_sign_idx]
    nak_name, nak_lord, pada = get_nakshatra(asc_deg % 360)
    chart_data["Ascendant"] = {
        "sign": asc_sign,
        "house": 1,
        "house_provisional": 1,
        "degree_total": asc_deg % 360,
        "degree_in_sign": asc_deg % 30,
        "sign_idx": asc_sign_idx,
        "status": "N/A",
        "dignity": None,
        "nakshatra": nak_name,
        "nakshatra_lord": nak_lord,
        "pada": pada,
    }

    # Planets
    for planet_id, planet_name in PLANETS.items():
        pos, _ = swe.calc_ut(jd, planet_id, flags)
        deg_total = pos[0] % 360
        speed = pos[3]
        status = "Rx" if speed < 0 and planet_id not in [swe.SUN, swe.MOON] else "Dir"
        if planet_id == swe.TRUE_NODE:
            status = "Rx"
        sign_idx = int(deg_total / 30) % 12
        nak_name, nak_lord, pada = get_nakshatra(deg_total)

        house_num = get_house_from_sign_idx(asc_sign_idx, sign_idx)
        chart_data[planet_name] = {
            "sign": RASHI_NAMES[sign_idx],
            "house": house_num,
            "house_provisional": house_num,
            "degree_total": deg_total,
            "degree_in_sign": deg_total % 30,
            "sign_idx": sign_idx,
            "status": status,
            "dignity": get_dignity(planet_name, RASHI_NAMES[sign_idx], deg_total % 30),
            "nakshatra": nak_name,
            "nakshatra_lord": nak_lord,
            "pada": pada,
        }

    # Ketu (always opposite Rahu)
    rahu_deg = float(chart_data["Rahu"]["degree_total"])
    ketu_deg = (rahu_deg + 180) % 360
    ketu_sign_idx = int(ketu_deg / 30) % 12
    nak_name, nak_lord, pada = get_nakshatra(ketu_deg)
    ketu_house = get_house_from_sign_idx(asc_sign_idx, ketu_sign_idx)
    chart_data["Ketu"] = {
        "sign": RASHI_NAMES[ketu_sign_idx],
        "house": ketu_house,
        "house_provisional": ketu_house,
        "degree_total": ketu_deg,
        "degree_in_sign": ketu_deg % 30,
        "sign_idx": ketu_sign_idx,
        "status": "Rx",
        "dignity": None,
        "nakshatra": nak_name,
        "nakshatra_lord": nak_lord,
        "pada": pada,
    }

    # Graha Yuddha detection (Classical Parashari: Tara Grahas, exact same zodiac sign, within 1°)
    yuddha_planets = ["Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    for key in chart_data:
        chart_data[key]["graha_yuddha"] = None

    for i in range(len(yuddha_planets)):
        for j in range(i + 1, len(yuddha_planets)):
            p1 = yuddha_planets[i]
            p2 = yuddha_planets[j]
            if p1 in chart_data and p2 in chart_data:
                # Must be in the exact same zodiac sign (Ekastha)
                if chart_data[p1]["sign_idx"] == chart_data[p2]["sign_idx"]:
                    deg1 = float(chart_data[p1]["degree_in_sign"])
                    deg2 = float(chart_data[p2]["degree_in_sign"])
                    diff = abs(deg1 - deg2)
                    if diff <= 1.0:
                        # Classical BPHS rule: Venus is inherently victorious due to supreme brilliance;
                        # otherwise, planet with higher degree / northern position is victor (Vijayi).
                        if "Venus" in [p1, p2]:
                            winner = "Venus"
                            loser = p2 if p1 == "Venus" else p1
                        elif deg1 > deg2:
                            winner, loser = p1, p2
                        else:
                            winner, loser = p2, p1

                        chart_data[winner]["graha_yuddha"] = {
                            "opponent": loser,
                            "status": "Victor (Yuddha Vijayi)",
                            "orb_diff": round(diff, 2)
                        }
                        chart_data[loser]["graha_yuddha"] = {
                            "opponent": winner,
                            "status": "Defeated (Yuddha Parajita)",
                            "orb_diff": round(diff, 2)
                        }

    # Attach combustion status to all chart bodies
    for p in chart_data:
        chart_data[p]["combustion"] = get_combustion_status(p, chart_data)

    return chart_data


def build_d9_crosscheck(chart_data):
    """
    Add D9 Navamsa sign, D9 dignity, and Vargottama flag to each body.
    Does not modify the original chart_data; returns a new dict.
    """
    def get_navamsa_sign_idx(deg_total):
        sign = int(deg_total / 30) % 12
        deg_in_sign = deg_total % 30
        nav_num = int(deg_in_sign / (10.0 / 3.0))  # 0..8
        if sign % 3 == 0:      # Moveable
            return (sign + nav_num) % 12
        elif sign % 3 == 1:    # Fixed
            return (sign + 8 + nav_num) % 12
        else:                  # Dual
            return (sign + 4 + nav_num) % 12

    enriched = {}
    for body, data in chart_data.items():
        new_data = dict(data)  # copy original fields
        d9_idx = get_navamsa_sign_idx(data["degree_total"])
        d9_sign = RASHI_NAMES[d9_idx]
        new_data["d9_sign"] = d9_sign
        new_data["d9_sign_idx"] = d9_idx
        if body == "Ascendant":
            new_data["d9_dignity"] = None
        else:
            new_data["d9_dignity"] = get_dignity(body, d9_sign)
        new_data["vargottama"] = (data["sign_idx"] == d9_idx)
        enriched[body] = new_data
    return enriched


def build_bhava_chalit(chart_data):
    """
    Whole-sign houses are the single house system across the application.
    Returns a new dict with house_final set to the whole-sign house.
    """
    asc_sign_idx = chart_data["Ascendant"]["sign_idx"]

    enriched = {}
    for body, data in chart_data.items():
        house_num = data.get("house", get_house_from_sign_idx(asc_sign_idx, data["sign_idx"]))
        new_data = dict(data)
        new_data["house"] = house_num
        new_data["house_final"] = house_num
        enriched[body] = new_data

    return enriched


def assemble_locked_chart(bhava_chart):
    """
    Build the single LockedChart object using whole-sign houses.
    After this, no function should read raw chart_data directly.
    """
    asc_sign_idx = bhava_chart["Ascendant"]["sign_idx"]
    locked = {}
    for body, data in bhava_chart.items():
        d = dict(data)
        d.pop("house_provisional", None)
        house_num = d.get("house_final", d.get("house", get_house_from_sign_idx(asc_sign_idx, d["sign_idx"])))
        d["house"] = house_num
        d["house_final"] = house_num
        locked[body] = d

    # Combustion status for non-luminary bodies
    for body in list(locked.keys()):
        if body in ["Sun", "Rahu", "Ketu", "Ascendant"]:
            locked[body]["combustion"] = None
            continue
        locked[body]["combustion"] = get_combustion_status(body, locked)

    # Recompute aspects using whole-sign house
    aspects = {}
    for body, data in locked.items():
        if body == "Ascendant":
            continue
        current_house = data["house"]
        asp = [((current_house + 7 - 2) % 12 + 1)]
        if body == "Mars":
            asp.extend([
                ((current_house + 4 - 2) % 12 + 1),
                ((current_house + 8 - 2) % 12 + 1)
            ])
        elif body == "Jupiter":
            asp.extend([
                ((current_house + 5 - 2) % 12 + 1),
                ((current_house + 9 - 2) % 12 + 1)
            ])
        elif body == "Saturn":
            asp.extend([
                ((current_house + 3 - 2) % 12 + 1),
                ((current_house + 10 - 2) % 12 + 1)
            ])

        seen = set()
        unique = []
        for h in asp:
            if h not in seen:
                seen.add(h)
                unique.append(h)
        unique.sort()
        aspects[body] = unique

    locked["_aspects"] = aspects
    return locked


def compute_ashtakavarga(locked_chart):
    """
    Compute Ashtakavarga from LockedChart.
    Hard-validates SAV total and BAV planet totals.
    """
    rashi_positions = {
        "Ascendant": locked_chart["Ascendant"]["sign_idx"] + 1,
        "Sun":       locked_chart["Sun"]["sign_idx"] + 1,
        "Moon":      locked_chart["Moon"]["sign_idx"] + 1,
        "Mars":      locked_chart["Mars"]["sign_idx"] + 1,
        "Mercury":   locked_chart["Mercury"]["sign_idx"] + 1,
        "Jupiter":   locked_chart["Jupiter"]["sign_idx"] + 1,
        "Venus":     locked_chart["Venus"]["sign_idx"] + 1,
        "Saturn":    locked_chart["Saturn"]["sign_idx"] + 1,
    }

    result = calculate_ashtakavarga(rashi_positions)

    ok, total = validate_sav_invariant(result)
    if not ok:
        raise ValueError(
            f"Ashtakavarga validation failed: SAV total {total} != 337 "
            f"or planet BAV totals do not match expected values."
        )

    return result


# NAKSHATRA & PADA HELPER
# ==========================================
NAKSHATRAS = [
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

def get_nakshatra(deg_total):
    """Return (nakshatra_name, nakshatra_lord, pada) for a sidereal longitude."""
    nak_len = 360.0 / 27.0
    pada_len = nak_len / 4.0
    idx = int(deg_total / nak_len)
    idx = min(idx, 26)
    pos_in_nak = deg_total % nak_len
    pada = int(pos_in_nak / pada_len) + 1
    pada = min(pada, 4)
    return NAKSHATRAS[idx][0], NAKSHATRAS[idx][1], pada


def calculate_vimshottari_dasha(moon_degree, birth_dt, target_dt, days_per_year=365.2425, year_type=None):
    """
    Returns a dict with current MD/AD/PD, their mathematically derived date ranges,
    next periods, and remaining days so the AI never invents timing.
    Supports both Solar (365.2425 days/year) and traditional Savana (360.0 days/year) modes.
    """
    if year_type == "savana":
        days_per_year = 360.0

    DASHA_SEQ = [
        ("Ketu", 7), ("Venus", 20), ("Sun", 6), ("Moon", 10),
        ("Mars", 7), ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17)
    ]
    nak_len = 360.0 / 27.0
    nak_num = int(moon_degree / nak_len)
    lord_idx = nak_num % 9

    fraction_passed = (moon_degree % nak_len) / nak_len
    fraction_left = 1.0 - fraction_passed
    first_lord, first_years = DASHA_SEQ[lord_idx]
    balance_years = fraction_left * first_years

    days_passed = (target_dt - birth_dt).total_seconds() / 86400.0
    years_passed = days_passed / days_per_year

    # --- Locate Current Mahadasha ---
    md_idx = lord_idx
    elapsed_before_birth = first_years - balance_years

    if years_passed < balance_years:
        current_md = first_lord
        md_duration = first_years
        nominal_md_start_dt = birth_dt - timedelta(days=elapsed_before_birth * days_per_year)
        md_end_dt = birth_dt + timedelta(days=balance_years * days_per_year)
        md_start_dt = nominal_md_start_dt
        years_into_md = elapsed_before_birth + years_passed
    else:
        accumulated = balance_years
        md_idx = (lord_idx + 1) % 9
        for _ in range(20):  # covers 240+ years
            md_name, md_duration_full = DASHA_SEQ[md_idx]
            if accumulated + md_duration_full > years_passed:
                current_md = md_name
                md_duration = md_duration_full
                md_start_dt = birth_dt + timedelta(days=accumulated * days_per_year)
                md_end_dt = birth_dt + timedelta(days=(accumulated + md_duration_full) * days_per_year)
                nominal_md_start_dt = md_start_dt
                years_into_md = years_passed - accumulated
                break
            accumulated += md_duration_full
            md_idx = (md_idx + 1) % 9
        else:
            current_md = DASHA_SEQ[md_idx][0]
            md_duration = DASHA_SEQ[md_idx][1]
            md_start_dt = birth_dt + timedelta(days=accumulated * days_per_year)
            md_end_dt = birth_dt + timedelta(days=(accumulated + md_duration) * days_per_year)
            nominal_md_start_dt = md_start_dt
            years_into_md = 0.0

    # --- Locate Current Antardasha ---
    ad_accumulated = 0.0
    current_ad = None
    ad_start_in_md = 0.0
    ad_end_in_md = 0.0
    active_ad_idx = md_idx

    for i in range(9):
        curr_ad_idx = (md_idx + i) % 9
        ad_name, ad_years_total = DASHA_SEQ[curr_ad_idx]
        ad_duration = (md_duration * ad_years_total) / 120.0
        ad_end = ad_accumulated + ad_duration
        if ad_end > years_into_md:
            current_ad = ad_name
            ad_start_in_md = ad_accumulated
            ad_end_in_md = ad_end
            active_ad_idx = curr_ad_idx
            break
        ad_accumulated += ad_duration
    else:
        current_ad = DASHA_SEQ[active_ad_idx][0]
        ad_start_in_md = ad_accumulated
        ad_end_in_md = ad_accumulated + (md_duration * DASHA_SEQ[active_ad_idx][1]) / 120.0

    # --- Derive wall-clock dates ---
    ad_start_dt = nominal_md_start_dt + timedelta(days=ad_start_in_md * days_per_year)
    ad_end_dt = nominal_md_start_dt + timedelta(days=ad_end_in_md * days_per_year)

    # --- Next periods ---
    next_md_idx = (md_idx + 1) % 9
    next_md = DASHA_SEQ[next_md_idx][0]

    if ad_end_in_md >= md_duration - 1e-9:
        next_ad = next_md
    else:
        next_ad_idx = (active_ad_idx + 1) % 9
        next_ad = DASHA_SEQ[next_ad_idx][0]

    # --- Locate Current Pratyantardasha (Sub-Sub Period) ---
    total_ad_days = max(1.0, (ad_end_dt - ad_start_dt).total_seconds() / 86400.0)
    reordered_pd_seq = [DASHA_SEQ[(active_ad_idx + i) % 9] for i in range(9)]

    current_pd = None
    pd_start_dt = ad_start_dt
    pd_end_dt = ad_end_dt

    pd_pointer = ad_start_dt
    for pd_planet, pd_years in reordered_pd_seq:
        pd_days = total_ad_days * (pd_years / 120.0)
        next_pd_pointer = pd_pointer + timedelta(days=pd_days)
        if pd_pointer <= target_dt < next_pd_pointer:
            current_pd = pd_planet
            pd_start_dt = pd_pointer
            pd_end_dt = next_pd_pointer
            break
        pd_pointer = next_pd_pointer
    else:
        current_pd = reordered_pd_seq[-1][0]
        pd_start_dt = pd_pointer
        pd_end_dt = ad_end_dt

    def fmt(dt):
        return dt.strftime("%d %b %Y")

    return {
        "md": current_md,
        "ad": current_ad,
        "pd": current_pd,
        "current_pd": current_pd,
        "md_start": fmt(md_start_dt),
        "md_end": fmt(md_end_dt),
        "md_start_dt": md_start_dt,
        "md_end_dt": md_end_dt,
        "md_remaining_days": max(0, int((md_end_dt - target_dt).days)),
        "ad_start": fmt(ad_start_dt),
        "ad_end": fmt(ad_end_dt),
        "ad_start_dt": ad_start_dt,
        "ad_end_dt": ad_end_dt,
        "ad_remaining_days": max(0, int((ad_end_dt - target_dt).days)),
        "pd_start": fmt(pd_start_dt),
        "pd_end": fmt(pd_end_dt),
        "pd_start_dt": pd_start_dt,
        "pd_end_dt": pd_end_dt,
        "pd_remaining_days": max(0, int((pd_end_dt - target_dt).days)),
        "md_next": next_md,
        "ad_next": next_ad,
    }


# Adaptive Step Sizes for 100-Year High-Performance Astronomical Scans
TRANSIT_STEP_SIZES = {
    swe.MOON: 0.25,        # 6 hours
    swe.SUN: 1.0,          # 1 day
    swe.MERCURY: 0.5,      # 12 hours
    swe.VENUS: 0.5,        # 12 hours
    swe.MARS: 1.0,         # 1 day
    swe.JUPITER: 3.0,      # 3 days
    swe.SATURN: 5.0,       # 5 days
    swe.TRUE_NODE: 3.0,    # 3 days (Rahu)
}


def find_next_ingress(jd_start, planet_id, flags=None, start_dt_utc=None, rashi_names=RASHI_NAMES, target_sign_idx=None, max_years=100):
    """
    Returns (new_sign_name, date_string, datetime_obj) for the next sign change
    calculated with sub-second astronomical precision using adaptive planetary stepping
    and binary root-finding. Capable of scanning 100+ years in milliseconds.
    """
    flags = VEDIC_FLAGS if flags is None else (flags | VEDIC_FLAGS)
    pos, _ = swe.calc_ut(jd_start, planet_id, flags)
    start_sign = int(pos[0] % 360 / 30)

    step = TRANSIT_STEP_SIZES.get(planet_id, 1.0)
    max_days = int(max_years * 365.25)
    total_steps = int(max_days / step)

    jd_low, jd_high = None, None
    target_sign = None
    jd_curr = jd_start
    prev_sign = start_sign

    for _ in range(total_steps):
        jd_next = jd_curr + step
        pos_next, _ = swe.calc_ut(jd_next, planet_id, flags)
        sign_next = int(pos_next[0] % 360 / 30)

        if target_sign_idx is not None:
            if sign_next == target_sign_idx and prev_sign != target_sign_idx:
                jd_low, jd_high = jd_curr, jd_next
                target_sign = target_sign_idx
                break
        else:
            if sign_next != start_sign:
                jd_low, jd_high = jd_curr, jd_next
                target_sign = sign_next
                break

        prev_sign = sign_next
        jd_curr = jd_next

    if jd_low is None or target_sign is None:
        return None, None, None

    # Binary search (bisection) down to sub-second precision (18 iterations = ~0.3 sec)
    for _ in range(18):
        jd_mid = (jd_low + jd_high) / 2.0
        pos_mid, _ = swe.calc_ut(jd_mid, planet_id, flags)
        sign_mid = int(pos_mid[0] % 360 / 30)
        if target_sign_idx is not None:
            if sign_mid != target_sign_idx:
                jd_low = jd_mid
            else:
                jd_high = jd_mid
        else:
            if sign_mid == start_sign:
                jd_low = jd_mid
            else:
                jd_high = jd_mid

    exact_jd = (jd_low + jd_high) / 2.0
    days_exact = exact_jd - jd_start
    if start_dt_utc:
        ingress_dt = start_dt_utc + timedelta(days=days_exact)
        ingress_str = ingress_dt.strftime("%d %b %Y")
    else:
        ingress_dt = None
        ingress_str = f"+{days_exact:.1f} days"

    return rashi_names[target_sign], ingress_str, ingress_dt


def find_next_station(jd_start, planet_id, flags=None, start_dt_utc=None, max_years=100):
    """
    Returns (station_type, date_string, datetime_obj) for the next retrograde/direct station
    calculated with sub-second astronomical precision using adaptive stepping and binary root-finding.
    Capable of scanning 100+ years in milliseconds.
    """
    flags = VEDIC_FLAGS if flags is None else (flags | VEDIC_FLAGS)
    pos, _ = swe.calc_ut(jd_start, planet_id, flags)
    prev_speed = pos[3]

    step = 5.0 if planet_id in [swe.JUPITER, swe.SATURN] else 1.0
    max_days = int(max_years * 365.25)
    total_steps = int(max_days / step)

    jd_low, jd_high = None, None
    st_type = None
    jd_curr = jd_start

    for _ in range(total_steps):
        jd_next = jd_curr + step
        pos_next, _ = swe.calc_ut(jd_next, planet_id, flags)
        speed = pos_next[3]

        if prev_speed != 0 and (prev_speed * speed < 0):
            jd_low = jd_curr, jd_next
            st_type = "Retrograde" if speed < 0 else "Direct"
            break

        prev_speed = speed
        jd_curr = jd_next

    if jd_low is None:
        return None, None, None

    jd_low_val, jd_high_val = jd_low[0], jd_low[1]

    # Binary search (bisection) to find exact moment speed crosses zero (18 iterations)
    for _ in range(18):
        jd_mid = (jd_low_val + jd_high_val) / 2.0
        pos_mid, _ = swe.calc_ut(jd_mid, planet_id, flags)
        speed_mid = pos_mid[3]
        if (speed_mid < 0) == (prev_speed < 0):
            jd_low_val = jd_mid
        else:
            jd_high_val = jd_mid

    exact_jd = (jd_low_val + jd_high_val) / 2.0
    days_exact = exact_jd - jd_start
    if start_dt_utc:
        station_dt = start_dt_utc + timedelta(days=days_exact)
        station_str = station_dt.strftime("%d %b %Y")
    else:
        station_dt = None
        station_str = f"+{days_exact:.1f} days"

    return st_type, station_str, station_dt


def detect_yogas(chart_data, asc_sign_idx):
    """
    Comprehensive classical Vedic Yoga detection suite covering:
    1. Maha Raja Yogas (Pancha Mahapurusha, Dharma-Karmadhipati, Kendra-Trikona)
    2. Dhana & Lakshmi Yogas (Wealth & material prosperity)
    3. Parivartana Yogas (Mutual house exchanges: Maha, Dainya, Khala)
    4. Vipareeta Raja Yogas (Harsha, Sarala, Vimala)
    5. Vidya & Jnana Yogas (Saraswati, Budhaditya, Amala)
    6. Lunar & Solar Yogas (Gajakesari, Adhi, Sunapha, Anapha, Durudhura, Ubhayachari)
    7. Neecha Bhanga Raja Yogas (Cancellation of debilitation)
    """
    yogas = []
    clean_chart = {str(k).strip(): v for k, v in chart_data.items()}

    def house_of(p):
        p_clean = str(p).strip()
        return clean_chart[p_clean]["house"]

    SIGN_LORDS = {
        "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
        "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
        "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
        "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"
    }

    RASHI = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
             "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

    def lord_of_house(house_num):
        sign_idx = (asc_sign_idx + house_num - 1) % 12
        return SIGN_LORDS[RASHI[sign_idx]]

    KENDRAS = [1, 4, 7, 10]
    TRIKONAS = [1, 5, 9]
    DUSTHANAS = [6, 8, 12]
    UPACHAYAS = [3, 6, 10, 11]

    hlords = {h: lord_of_house(h) for h in range(1, 13)}

    # ----------------------------------------------------
    # 1. PANCHA MAHAPURUSHA YOGAS (BPHS Ch. 75)
    # ----------------------------------------------------
    mahapurusha = {
        "Mars": ("Ruchaka", "Courage, physical vitality, command, strategic leadership, and victory over adversaries."),
        "Mercury": ("Bhadra", "Sharp intellect, eloquence, trade mastery, scholarship, and executive administrative acumen."),
        "Jupiter": ("Hamsa", "Spiritual grace, profound wisdom, righteous wealth, high societal honor, and pure character."),
        "Venus": ("Malavya", "Refined luxury, artistic brilliance, magnetic charm, marital happiness, and material prosperity."),
        "Saturn": ("Sasa", "Relentless perseverance, command over organizations/masses, political endurance, and enduring authority.")
    }
    for planet, (yoga_name, promise) in mahapurusha.items():
        if planet in clean_chart:
            dignity = clean_chart[planet].get("dignity")
            h = house_of(planet)
            if h in KENDRAS and dignity in ["Exalted", "Own Sign", "Moolatrikona"]:
                yogas.append({
                    "name": f"{yoga_name} Yoga (Pancha Mahapurusha)",
                    "category": "Maha Raja Yoga",
                    "planets": [planet],
                    "desc": f"{planet} is {dignity} in Kendra House {h}. Grants {promise}",
                    "classical_ref": "Brihat Parasara Hora Sastra Ch. 75"
                })

    # ----------------------------------------------------
    # 2. DHARMA-KARMADHIPATI & MAJOR RAJA YOGAS (BPHS Ch. 34-35)
    # ----------------------------------------------------
    lord9 = hlords[9]
    lord10 = hlords[10]
    if lord9 in clean_chart and lord10 in clean_chart:
        if house_of(lord9) == house_of(lord10):
            yogas.append({
                "name": "Dharma-Karmadhipati Raja Yoga",
                "category": "Maha Raja Yoga",
                "planets": list(set([lord9, lord10])),
                "desc": f"9th Lord of Dharma ({lord9}) and 10th Lord of Karma ({lord10}) conjoin in House {house_of(lord9)}, forming the supreme classical Raja Yoga for life purpose, executive authority, and renowned accomplishments.",
                "classical_ref": "Brihat Parasara Hora Sastra Ch. 34"
            })
        elif house_of(lord9) == 10 and house_of(lord10) == 9:
            yogas.append({
                "name": "Dharma-Karmadhipati Maha Parivartana Raja Yoga",
                "category": "Maha Raja Yoga",
                "planets": list(set([lord9, lord10])),
                "desc": f"9th Lord ({lord9}) and 10th Lord ({lord10}) exchange houses (Parivartana), creating an unbreakable nexus of ethical authority and lifetime rise.",
                "classical_ref": "Brihat Parasara Hora Sastra Ch. 34"
            })

    seen_raja = set()
    for kh in KENDRAS:
        for th in TRIKONAS:
            kl = hlords[kh]
            tl = hlords[th]
            if kl != tl and kl in clean_chart and tl in clean_chart:
                if house_of(kl) == house_of(tl):
                    pair = tuple(sorted([kl, tl]))
                    if pair not in seen_raja and not (kl in [lord9, lord10] and tl in [lord9, lord10] and house_of(kl) == house_of(tl)):
                        seen_raja.add(pair)
                        yogas.append({
                            "name": f"Kendra-Trikona Raja Yoga (H{kh}-H{th})",
                            "category": "Raja Yoga",
                            "planets": list(pair),
                            "desc": f"{kl} (Lord of Kendra H{kh}) and {tl} (Lord of Trikona H{th}) conjoin in House {house_of(kl)}, generating power, social elevation, and professional success.",
                            "classical_ref": "Brihat Parasara Hora Sastra Ch. 34"
                        })

    # ----------------------------------------------------
    # 3. GAJAKESARI & LUNAR YOGAS (BPHS Ch. 12-14)
    # ----------------------------------------------------
    if "Jupiter" in clean_chart and "Moon" in clean_chart:
        moon_sign = clean_chart["Moon"]["sign_idx"]
        jup_sign = clean_chart["Jupiter"]["sign_idx"]
        rel_house = (jup_sign - moon_sign) % 12 + 1
        if rel_house in KENDRAS:
            yogas.append({
                "name": "Gajakesari Yoga",
                "category": "Maha Raja Yoga",
                "planets": ["Jupiter", "Moon"],
                "desc": f"Jupiter is in Kendra (House {rel_house}) from natal Moon. Grants majestic intellect, lasting reputation, royal favor, virtuous prosperity, and protection from disgrace.",
                "classical_ref": "Brihat Parasara Hora Sastra Ch. 12"
            })

    if "Moon" in clean_chart and "Mars" in clean_chart:
        if house_of("Moon") == house_of("Mars"):
            yogas.append({
                "name": "Chandra-Mangala Yoga",
                "category": "Dhana Yoga",
                "planets": ["Moon", "Mars"],
                "desc": "Moon and Mars conjoin, creating dynamic financial drive, enterprise, tangible wealth creation, and resource accumulation.",
                "classical_ref": "Saravali Ch. 15"
            })

    if "Moon" in clean_chart:
        m_house = house_of("Moon")
        p_in_2nd_moon = [p for p in clean_chart if p not in ["Moon", "Sun", "Rahu", "Ketu", "Ascendant"] and house_of(p) == (m_house % 12 + 1)]
        p_in_12th_moon = [p for p in clean_chart if p not in ["Moon", "Sun", "Rahu", "Ketu", "Ascendant"] and house_of(p) == ((m_house - 2) % 12 + 1)]

        if p_in_2nd_moon and p_in_12th_moon:
            yogas.append({
                "name": "Durudhura Yoga",
                "category": "Chandra Yoga",
                "planets": ["Moon"] + p_in_2nd_moon + p_in_12th_moon,
                "desc": f"Planets occupy both 2nd ({', '.join(p_in_2nd_moon)}) and 12th ({', '.join(p_in_12th_moon)}) from Moon, blessing the native with generous wealth, abundant comforts, vehicles, and enduring stability.",
                "classical_ref": "Brihat Parasara Hora Sastra Ch. 13"
            })
        elif p_in_2nd_moon:
            yogas.append({
                "name": "Sunapha Yoga",
                "category": "Chandra Yoga",
                "planets": ["Moon"] + p_in_2nd_moon,
                "desc": f"{', '.join(p_in_2nd_moon)} in 2nd from Moon grants self-earned fortune, intellectual sharpness, and steady prosperity.",
                "classical_ref": "Brihat Parasara Hora Sastra Ch. 13"
            })
        elif p_in_12th_moon:
            yogas.append({
                "name": "Anapha Yoga",
                "category": "Chandra Yoga",
                "planets": ["Moon"] + p_in_12th_moon,
                "desc": f"{', '.join(p_in_12th_moon)} in 12th from Moon grants magnetic personality, self-control, eloquence, and freedom from disease.",
                "classical_ref": "Brihat Parasara Hora Sastra Ch. 13"
            })
        else:
            kendra_planets = [p for p in clean_chart if p not in ["Rahu", "Ketu", "Ascendant"] and house_of(p) in KENDRAS]
            if kendra_planets:
                yogas.append({
                    "name": "Kemadruma Bhanga (Isolation Cancelled)",
                    "category": "Arishta Bhanga Yoga",
                    "planets": ["Moon"] + kendra_planets[:2],
                    "desc": "Moon has no planets in adjacent houses, but the Kemadruma dosha is cancelled because planets occupy Kendra houses, converting early struggle into mature independence and self-reliance.",
                    "classical_ref": "Brihat Parasara Hora Sastra Ch. 13"
                })

    if "Moon" in clean_chart:
        m_house = house_of("Moon")
        adhi_houses = [(m_house + 4) % 12 + 1, (m_house + 5) % 12 + 1, (m_house + 6) % 12 + 1]
        benefics = ["Jupiter", "Venus", "Mercury"]
        adhi_planets = [p for p in benefics if p in clean_chart and house_of(p) in adhi_houses]
        if len(adhi_planets) >= 2:
            yogas.append({
                "name": "Chandradhi Yoga (Adhi Yoga)",
                "category": "Maha Raja Yoga",
                "planets": adhi_planets,
                "desc": f"Natural benefics ({', '.join(adhi_planets)}) occupy 6th/7th/8th from Moon, forming the classical Adhi Yoga indicating ministerial rank, executive leadership, command, and refined comforts.",
                "classical_ref": "Brihat Parasara Hora Sastra Ch. 35"
            })

    # ----------------------------------------------------
    # 4. PARIVARTANA YOGAS (Mutual House Exchanges - BPHS Ch. 36)
    # ----------------------------------------------------
    seen_exchanges = set()
    for h1 in range(1, 13):
        for h2 in range(h1 + 1, 13):
            l1, l2 = hlords[h1], hlords[h2]
            if l1 != l2 and l1 in clean_chart and l2 in clean_chart:
                if house_of(l1) == h2 and house_of(l2) == h1:
                    pair = tuple(sorted([h1, h2]))
                    if pair not in seen_exchanges:
                        seen_exchanges.add(pair)
                        if h1 in DUSTHANAS or h2 in DUSTHANAS:
                            ytype = "Dainya Parivartana Yoga"
                            ycat = "Parivartana Yoga"
                            ydesc = f"Mutual exchange between Lords of House {h1} ({l1}) and House {h2} ({l2}) involving a Dusthana. Indicates powerful resilience, overcoming hardship, and deep karmic transformations."
                        elif h1 == 3 or h2 == 3:
                            ytype = "Khala Parivartana Yoga"
                            ycat = "Parivartana Yoga"
                            ydesc = f"Mutual exchange between 3rd Lord and House {h2 if h1 == 3 else h1} Lord, indicating fluctuating fortunes mastered through exceptional courage and personal initiative."
                        else:
                            ytype = "Maha Parivartana Yoga"
                            ycat = "Maha Raja Yoga"
                            ydesc = f"Mutual exchange between auspicious Houses {h1} ({l1}) and {h2} ({l2}), multiplying the power and prosperity of both life sectors permanently."

                        yogas.append({
                            "name": f"{ytype} (H{h1} ⇄ H{h2})",
                            "category": ycat,
                            "planets": [l1, l2],
                            "desc": ydesc,
                            "classical_ref": "Brihat Parasara Hora Sastra Ch. 36"
                        })

    # ----------------------------------------------------
    # 5. DHANA YOGAS (Wealth & Lakshmi Yogas)
    # ----------------------------------------------------
    lord1, lord2, lord11 = hlords[1], hlords[2], hlords[11]

    if lord2 in clean_chart and lord11 in clean_chart and lord2 != lord11:
        if house_of(lord2) == house_of(lord11):
            yogas.append({
                "name": "Maha Dhana Yoga (H2 & H11 Interlink)",
                "category": "Dhana Yoga",
                "planets": list(set([lord2, lord11])),
                "desc": f"2nd Lord of Wealth ({lord2}) and 11th Lord of Gains ({lord11}) conjoin in House {house_of(lord2)}, generating extraordinary wealth accumulation and financial multiplying power.",
                "classical_ref": "Brihat Parasara Hora Sastra Ch. 41"
            })

    if lord1 in clean_chart and lord2 in clean_chart and lord1 != lord2:
        if house_of(lord1) == house_of(lord2):
            yogas.append({
                "name": "Dhana Yoga (H1 & H2 Conjunction)",
                "category": "Dhana Yoga",
                "planets": list(set([lord1, lord2])),
                "desc": f"Lagna Lord ({lord1}) and 2nd Lord ({lord2}) conjoin in House {house_of(lord1)}, ensuring personal capacity to generate and preserve wealth.",
                "classical_ref": "Brihat Parasara Hora Sastra Ch. 41"
            })

    if lord9 in clean_chart:
        d9_status = clean_chart[lord9].get("dignity")
        if house_of(lord9) in (KENDRAS + TRIKONAS) and d9_status in ["Exalted", "Own Sign", "Moolatrikona"]:
            yogas.append({
                "name": "Lakshmi Yoga",
                "category": "Dhana Yoga",
                "planets": [lord9, lord1],
                "desc": f"9th Lord ({lord9}) is {d9_status} in auspicious House {house_of(lord9)}, forming classical Lakshmi Yoga. Bestows wealth, nobility, high moral character, and divine fortune.",
                "classical_ref": "Phaladeepika Ch. 6"
            })

    benefics = ["Jupiter", "Venus", "Mercury"]
    benefics_in_upachaya = [p for p in benefics if p in clean_chart and house_of(p) in UPACHAYAS]
    if len(benefics_in_upachaya) >= 2:
        yogas.append({
            "name": "Vasumathi Yoga",
            "category": "Dhana Yoga",
            "planets": benefics_in_upachaya,
            "desc": f"Benefics ({', '.join(benefics_in_upachaya)}) occupy Upachaya growth houses, granting self-generated prosperity, enterprise, and financial independence.",
            "classical_ref": "Brihat Parasara Hora Sastra Ch. 41"
        })

    # ----------------------------------------------------
    # 6. VIPAREETA RAJA YOGAS (Uttara Kalamrita / Phaladeepika Ch. 6)
    # ----------------------------------------------------
    lord6 = hlords[6]
    if lord6 in clean_chart and house_of(lord6) in DUSTHANAS:
        yogas.append({
            "name": "Harsha Vipareeta Raja Yoga",
            "category": "Vipareeta Raja Yoga",
            "planets": [lord6],
            "desc": f"6th Lord ({lord6}) is placed in Dusthana House {house_of(lord6)}. Bestows happiness, robust immunity, invincibility against enemies/litigation, and freedom from debts.",
            "classical_ref": "Phaladeepika Ch. 6"
        })

    lord8 = hlords[8]
    if lord8 in clean_chart and house_of(lord8) in DUSTHANAS:
        yogas.append({
            "name": "Sarala Vipareeta Raja Yoga",
            "category": "Vipareeta Raja Yoga",
            "planets": [lord8],
            "desc": f"8th Lord ({lord8}) is placed in Dusthana House {house_of(lord8)}. Grants longevity, fearless resolve, victory in difficult crises, and sudden windfalls.",
            "classical_ref": "Phaladeepika Ch. 6"
        })

    lord12 = hlords[12]
    if lord12 in clean_chart and house_of(lord12) in DUSTHANAS:
        yogas.append({
            "name": "Vimala Vipareeta Raja Yoga",
            "category": "Vipareeta Raja Yoga",
            "planets": [lord12],
            "desc": f"12th Lord ({lord12}) is placed in Dusthana House {house_of(lord12)}. Bestows noble expenditures, spiritual independence, accumulation of wealth, and honorable reputation.",
            "classical_ref": "Phaladeepika Ch. 6"
        })

    # ----------------------------------------------------
    # 7. VIDYA, JNANA & SOLAR YOGAS
    # ----------------------------------------------------
    if "Sun" in clean_chart and "Mercury" in clean_chart:
        if house_of("Sun") == house_of("Mercury"):
            dist = abs(clean_chart["Sun"]["degree_total"] - clean_chart["Mercury"]["degree_total"])
            combust_note = " (Highly potent & clear intellect)" if dist > 4.0 else " (Combustion softens expression; sharp analytical capability)"
            yogas.append({
                "name": "Budhaditya Yoga",
                "category": "Vidya & Jnana Yoga",
                "planets": ["Sun", "Mercury"],
                "desc": f"Sun and Mercury conjoin in House {house_of('Sun')}{combust_note}, bestowing sharp analytical intellect, communication mastery, and professional respect.",
                "classical_ref": "Brihat Parasara Hora Sastra Ch. 35"
            })

    saraswati_planets = [p for p in ["Jupiter", "Venus", "Mercury"] if p in clean_chart and house_of(p) in (KENDRAS + TRIKONAS + [2])]
    if len(saraswati_planets) == 3:
        yogas.append({
            "name": "Saraswati Yoga",
            "category": "Vidya & Jnana Yoga",
            "planets": ["Jupiter", "Venus", "Mercury"],
            "desc": "All three natural benefics (Jupiter, Venus, Mercury) occupy Kendra/Trikona/2nd houses. Grants literary excellence, artistic or technical mastery, profound wisdom, and societal fame.",
            "classical_ref": "Phaladeepika Ch. 6"
        })

    for ref_name, ref_h in [("Lagna", 1), ("Moon", house_of("Moon") if "Moon" in clean_chart else None)]:
        if ref_h is not None:
            h10 = (ref_h + 8) % 12 + 1
            h10_benefics = [p for p in ["Jupiter", "Venus", "Mercury"] if p in clean_chart and house_of(p) == h10]
            if h10_benefics:
                yogas.append({
                    "name": f"Amala Yoga (from {ref_name})",
                    "category": "Raja Yoga",
                    "planets": h10_benefics,
                    "desc": f"Pure benefic ({', '.join(h10_benefics)}) occupies 10th house from {ref_name}. Bestows unblemished professional reputation, ethical success, and lasting social goodwill.",
                    "classical_ref": "Phaladeepika Ch. 6"
                })

    if "Sun" in clean_chart:
        s_house = house_of("Sun")
        p_in_2nd_sun = [p for p in clean_chart if p not in ["Sun", "Rahu", "Ketu", "Ascendant"] and house_of(p) == (s_house % 12 + 1)]
        p_in_12th_sun = [p for p in clean_chart if p not in ["Sun", "Rahu", "Ketu", "Ascendant"] and house_of(p) == ((s_house - 2) % 12 + 1)]

        if p_in_2nd_sun and p_in_12th_sun:
            yogas.append({
                "name": "Ubhayachari Yoga",
                "category": "Surya Yoga",
                "planets": ["Sun"] + p_in_2nd_sun + p_in_12th_sun,
                "desc": f"Planets flank the Sun in both 2nd ({', '.join(p_in_2nd_sun)}) and 12th ({', '.join(p_in_12th_sun)}), conferring well-balanced personality, eloquence, leadership, and prosperity.",
                "classical_ref": "Brihat Parasara Hora Sastra Ch. 14"
            })
        elif p_in_2nd_sun:
            yogas.append({
                "name": "Vesi Yoga",
                "category": "Surya Yoga",
                "planets": ["Sun"] + p_in_2nd_sun,
                "desc": f"{', '.join(p_in_2nd_sun)} in 2nd from Sun grants steady determination, eloquence, and influential connections.",
                "classical_ref": "Brihat Parasara Hora Sastra Ch. 14"
            })
        elif p_in_12th_sun:
            yogas.append({
                "name": "Vosi Yoga",
                "category": "Surya Yoga",
                "planets": ["Sun"] + p_in_12th_sun,
                "desc": f"{', '.join(p_in_12th_sun)} in 12th from Sun grants charitable nature, sharp insight, and philosophical perspective.",
                "classical_ref": "Brihat Parasara Hora Sastra Ch. 14"
            })

    # ----------------------------------------------------
    # 8. NEECHA BHANGA RAJA YOGA (Phaladeepika Ch. 6)
    # ----------------------------------------------------
    for p in clean_chart:
        if p == "Ascendant":
            continue
        if clean_chart[p].get("dignity") == "Debilitated":
            deb_sign = clean_chart[p]["sign"]
            deb_lord = SIGN_LORDS[deb_sign]
            cancelled_by_lagna = deb_lord in clean_chart and house_of(deb_lord) in KENDRAS
            cancelled_by_moon = (
                deb_lord in clean_chart and "Moon" in clean_chart and
                (clean_chart[deb_lord]["house"] - clean_chart["Moon"]["house"]) % 12 + 1 in KENDRAS
            )
            if cancelled_by_lagna or cancelled_by_moon:
                src = "Lagna" if cancelled_by_lagna else "Moon"
                yogas.append({
                    "name": f"Neecha Bhanga Raja Yoga ({p})",
                    "category": "Maha Raja Yoga",
                    "planets": [p, deb_lord],
                    "desc": f"{p}'s debilitation is cancelled because its dispositor {deb_lord} is in Kendra from {src}. Converts initial vulnerability into extraordinary eventual mastery and late-career triumph.",
                    "classical_ref": "Phaladeepika Ch. 6"
                })

    CATEGORY_PRIORITY = {
        "Maha Raja Yoga": 1,
        "Raja Yoga": 2,
        "Dhana Yoga": 3,
        "Parivartana Yoga": 4,
        "Vipareeta Raja Yoga": 5,
        "Vidya & Jnana Yoga": 6,
        "Chandra Yoga": 7,
        "Surya Yoga": 8,
        "Arishta Bhanga Yoga": 9,
    }

    unique = {}
    for y in yogas:
        key = y["name"]
        if key not in unique:
            unique[key] = y

    final = sorted(unique.values(), key=lambda x: CATEGORY_PRIORITY.get(x.get("category", ""), 99))
    return final


def check_yoga_activation(yogas, dasha_data):
    """
    Evaluates current, upcoming, and dormant activation of classical yogas
    based on the active 3-tier Vimshottari Dasha periods (MD, AD, PD).
    """
    activation_report = []
    md = str(dasha_data.get("md", "")).strip()
    ad = str(dasha_data.get("ad", "")).strip()
    pd = str(dasha_data.get("current_pd", "")).strip()
    md_next = str(dasha_data.get("md_next", "")).strip()
    ad_next = str(dasha_data.get("ad_next", "")).strip()

    for y in yogas:
        involved = [str(p).strip() for p in y["planets"]]
        active_now = False
        status_label = ""
        timing_note = ""

        if md in involved and ad in involved:
            active_now = True
            status_label = "FULLY ACTIVE"
            timing_note = f"Both Mahadasha ({md}) and Antardasha ({ad}) rule this yoga right now until {dasha_data['ad_end']}."
        elif md in involved:
            active_now = True
            status_label = "ACTIVE (MD)"
            timing_note = f"{md} Mahadasha is fueling this yoga until {dasha_data['md_end']}."
        elif ad in involved:
            active_now = True
            status_label = "ACTIVE (AD)"
            timing_note = f"{ad} Antardasha activates this yoga until {dasha_data['ad_end']}."
        elif pd in involved:
            active_now = True
            status_label = "ACTIVE (PD)"
            timing_note = f"{pd} Pratyantardasha triggers this yoga until {dasha_data.get('pd_end', '')}."
        elif ad_next in involved:
            status_label = "UPCOMING (NEXT AD)"
            timing_note = f"Activates next in {ad_next} Antardasha starting {dasha_data['ad_end']}."
        elif md_next in involved:
            status_label = "UPCOMING (NEXT MD)"
            timing_note = f"Activates in {md_next} Mahadasha starting {dasha_data['md_end']}."
        else:
            status_label = "DORMANT"
            timing_note = f"Awaits Dasha of {', '.join(involved)}."

        activation_report.append({
            "name": y["name"],
            "category": y.get("category", "Classical Yoga"),
            "planets": y["planets"],
            "desc": y["desc"],
            "classical_ref": y.get("classical_ref", "Classical Texts"),
            "active": active_now,
            "status_label": status_label,
            "timing": timing_note
        })

    return activation_report


# ==========================================
# PANCHADHA MAITRI (5-FOLD PLANETARY FRIENDSHIP)
# ==========================================
def calculate_panchadha_maitri(natal_signs, natal_houses):
    """
    Calculate Panchadha Maitri using Sign Indices for host identification
    and House Positions for temporary distance tracking.
    """
    clean_signs = {str(k).strip(): v for k, v in natal_signs.items()}
    clean_houses = {str(k).strip(): v for k, v in natal_houses.items()}

    SIGN_LORDS = {
        0: "Mars",    1: "Venus",   2: "Mercury", 3: "Moon",
        4: "Sun",     5: "Mercury", 6: "Venus",   7: "Mars",
        8: "Jupiter", 9: "Saturn",  10: "Saturn", 11: "Jupiter"
    }

    NATURAL_FRIENDS = {
        "Sun": ["Moon", "Mars", "Jupiter"],
        "Moon": ["Sun", "Mercury"],
        "Mars": ["Sun", "Moon", "Jupiter"],
        "Mercury": ["Sun", "Venus"],
        "Jupiter": ["Sun", "Moon", "Mars"],
        "Venus": ["Mercury", "Saturn"],
        "Saturn": ["Mercury", "Venus"]
    }

    NATURAL_ENEMIES = {
        "Sun": ["Venus", "Saturn"],
        "Moon": [],
        "Mars": ["Mercury"],
        "Mercury": ["Moon"],
        "Jupiter": ["Mercury", "Venus"],
        "Venus": ["Sun", "Moon"],
        "Saturn": ["Sun", "Moon", "Mars"]
    }

    COMPOUND_LABELS = {
        2: "Great Friend", 1: "Friend", 0: "Neutral",
        -1: "Enemy", -2: "Bitter Enemy"
    }

    result = {}

    for planet, sign_idx in clean_signs.items():
        host_planet = SIGN_LORDS[sign_idx]

        # Own Sign check: a planet is its own dispositor
        if host_planet == planet:
            result[planet] = {
                "Host": host_planet,
                "Natural_Status": "Self",
                "Temporary_Status": "Self",
                "Final_Relationship": "Own Sign"
            }
            continue

        # Calculate Natural Relationship Score
        if host_planet in NATURAL_FRIENDS.get(planet, []):
            natural_score = 1
        elif host_planet in NATURAL_ENEMIES.get(planet, []):
            natural_score = -1
        else:
            natural_score = 0

        # Calculate Temporary Relationship based on actual House Distance
        current_planet_house = clean_houses[planet]
        host_planet_house = clean_houses[host_planet]

        house_count = (host_planet_house - current_planet_house) % 12 + 1

        if house_count in {2, 3, 4, 10, 11, 12}:
            temporary_score = 1
        else:
            temporary_score = -1

        compound_score = natural_score + temporary_score

        result[planet] = {
            "Host": host_planet,
            "Natural_Status": "Friend" if natural_score == 1 else "Enemy" if natural_score == -1 else "Neutral",
            "Temporary_Status": "Friend" if temporary_score == 1 else "Enemy",
            "Final_Relationship": COMPOUND_LABELS[compound_score]
        }

    return result


# ==========================================
# COMBUSTION HELPER (Classical Surya Siddhanta & BPHS Limits)
# ==========================================
COMBUSTION_LIMITS = {
    "Moon":    {"direct": 12.0, "rx": 12.0},
    "Mars":    {"direct": 17.0, "rx": 17.0},
    "Mercury": {"direct": 14.0, "rx": 12.0},
    "Jupiter": {"direct": 11.0, "rx": 11.0},
    "Venus":   {"direct": 10.0, "rx": 8.0},
    "Saturn":  {"direct": 15.0, "rx": 15.0},
}


def get_combustion_status(planet_name, data):
    planet_name = str(planet_name).strip()
    clean_data = {str(k).strip(): v for k, v in data.items()}

    if planet_name in ["Sun", "Rahu", "Ketu", "Ascendant"]:
        return None
    if "Sun" not in clean_data or planet_name not in clean_data:
        return None

    sun_d = clean_data["Sun"]["degree_total"]
    p_d = clean_data[planet_name]["degree_total"]
    distance = abs(sun_d - p_d)
    if distance > 180.0:
        distance = 360.0 - distance

    is_rx = clean_data[planet_name].get("status") == "Rx"
    limits = COMBUSTION_LIMITS.get(planet_name)
    if not limits:
        return None

    limit = limits["rx"] if is_rx else limits["direct"]
    if distance <= limit:
        return "Combust"
    return None


# =============================================================================
# ASHTAKAVARGA ENGINE — Complete Parashari Implementation
# =============================================================================
RASHI_LORDS = {
    0: "Mars",      # Aries
    1: "Venus",     # Taurus
    2: "Mercury",   # Gemini
    3: "Moon",      # Cancer
    4: "Sun",       # Leo
    5: "Mercury",   # Virgo
    6: "Venus",     # Libra
    7: "Mars",      # Scorpio
    8: "Jupiter",   # Sagittarius
    9: "Saturn",    # Capricorn
    10: "Saturn",   # Aquarius
    11: "Jupiter",  # Pisces
}

ASHTAKAVARGA_PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]

EXPECTED_BAV_TOTALS = {
    "Sun": 48,
    "Moon": 49,
    "Mars": 39,
    "Mercury": 54,
    "Jupiter": 56,
    "Venus": 52,
    "Saturn": 39,
}

ASHTAKAVARGA_RULES = {
    "Sun": {
        "Sun": [1, 2, 4, 7, 8, 9, 10, 11],
        "Moon": [3, 6, 10, 11],
        "Mars": [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [5, 6, 9, 11],
        "Venus": [6, 7, 12],
        "Saturn": [1, 2, 4, 7, 8, 9, 10, 11],
        "Ascendant": [3, 4, 6, 10, 11, 12],
    },
    "Moon": {
        "Sun": [3, 6, 7, 8, 10, 11],
        "Moon": [1, 3, 6, 7, 10, 11],
        "Mars": [2, 3, 5, 6, 9, 10, 11],
        "Mercury": [1, 3, 4, 5, 7, 8, 10, 11],
        "Jupiter": [1, 4, 7, 8, 10, 11, 12],
        "Venus": [3, 4, 5, 7, 9, 10, 11],
        "Saturn": [3, 5, 6, 11],
        "Ascendant": [3, 6, 10, 11],
    },
    "Mars": {
        "Sun": [3, 5, 6, 10, 11],
        "Moon": [3, 6, 11],
        "Mars": [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [3, 5, 6, 11],
        "Jupiter": [6, 10, 11, 12],
        "Venus": [6, 8, 11, 12],
        "Saturn": [1, 4, 7, 8, 9, 10, 11],
        "Ascendant": [1, 3, 6, 10, 11],
    },
    "Mercury": {
        "Sun": [5, 6, 9, 11, 12],
        "Moon": [2, 4, 6, 8, 10, 11],
        "Mars": [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [1, 3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [6, 8, 11, 12],
        "Venus": [1, 2, 3, 4, 5, 8, 9, 11],
        "Saturn": [1, 2, 4, 7, 8, 9, 10, 11],
        "Ascendant": [1, 2, 4, 6, 8, 10, 11],
    },
    "Jupiter": {
        "Sun": [1, 2, 3, 4, 7, 8, 9, 10, 11],
        "Moon": [2, 5, 7, 9, 11],
        "Mars": [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [1, 2, 4, 5, 6, 9, 10, 11],
        "Jupiter": [1, 2, 3, 4, 7, 8, 10, 11],
        "Venus": [2, 5, 6, 9, 10, 11],
        "Saturn": [3, 5, 6, 12],
        "Ascendant": [1, 2, 4, 5, 6, 7, 9, 10, 11],
    },
    "Venus": {
        "Sun": [8, 11, 12],
        "Moon": [1, 2, 3, 4, 5, 8, 9, 11, 12],
        "Mars": [3, 5, 6, 9, 11, 12],
        "Mercury": [3, 5, 6, 9, 11],
        "Jupiter": [5, 8, 9, 10, 11],
        "Venus": [1, 2, 3, 4, 5, 8, 9, 10, 11],
        "Saturn": [3, 4, 5, 7, 9, 10, 11],
        "Ascendant": [1, 2, 3, 4, 5, 8, 9, 11],
    },
    "Saturn": {
        "Sun": [1, 2, 4, 7, 8, 10, 11],
        "Moon": [3, 6, 11],
        "Mars": [3, 5, 6, 10, 11, 12],
        "Mercury": [6, 8, 9, 10, 11, 12],
        "Jupiter": [5, 6, 11, 12],
        "Venus": [6, 11, 12],
        "Saturn": [3, 5, 6, 11],
        "Ascendant": [1, 3, 4, 6, 10, 11],
    },
}

def calculate_ashtakavarga(rashi_positions):
    """
    Calculate Bhinnashtakavarga (BAV) and Sarvashtakavarga (SAV).
    """
    # Clean input keys to handle any accidental leading/trailing spaces
    clean_positions = {str(k).strip(): v for k, v in rashi_positions.items()}

    planets = [p.strip() for p in ASHTAKAVARGA_PLANETS]
    required = ["Ascendant"] + planets
    for key in required:
        if key not in clean_positions:
            raise ValueError(f"Missing required rashi position: {key}")
        if not 1 <= clean_positions[key] <= 12:
            raise ValueError(f"{key} rashi position must be 1-12, got {clean_positions[key]}")

    source_bodies = ["Ascendant"] + planets

    bav = {
        planet: {rashi: 0 for rashi in range(1, 13)}
        for planet in planets
    }

    clean_rules = {
        subj.strip(): {src.strip(): list(offsets) for src, offsets in src_dict.items()}
        for subj, src_dict in ASHTAKAVARGA_RULES.items()
    }

    for subject in planets:
        for source in source_bodies:
            source_rashi = clean_positions[source]
            source_idx = source_rashi - 1
            for offset in clean_rules[subject][source]:
                target_idx = (source_idx + (offset - 1)) % 12
                target_rashi = target_idx + 1
                bav[subject][target_rashi] += 1

    sav = {rashi: 0 for rashi in range(1, 13)}
    for rashi in range(1, 13):
        sav[rashi] = sum(bav[planet][rashi] for planet in planets)

    planet_totals = {
        planet: sum(bav[planet].values())
        for planet in planets
    }

    return {
        "Bhinnashtakavarga": bav,
        "Sarvashtakavarga": sav,
        "Planet_Totals": planet_totals,
        "House_Totals": dict(sav),
    }


def validate_sav_invariant(result):
    """
    Validates that:
    1. The total of all 12 SAV values equals 337 for standard Parashari tables.
    2. Each planet's BAV total matches its expected Parashari total.
    Returns (is_valid, grand_total).
    """
    sav = result.get("Sarvashtakavarga", {})
    total = sum(sav.values())

    if total != 337:
        return False, total

    planet_totals = result.get("Planet_Totals", {})
    if not planet_totals and "Bhinnashtakavarga" in result:
        bav = result["Bhinnashtakavarga"]
        planet_totals = {p: sum(bav[p].values()) for p in bav}

    clean_totals = {str(k).strip(): v for k, v in planet_totals.items()}

    for planet, expected in EXPECTED_BAV_TOTALS.items():
        if clean_totals.get(planet) != expected:
            return False, total

    return True, total


# ==========================================
# FUNCTIONAL HOUSE LORDS (WHOLE SIGN SYSTEM)
# ==========================================
def map_functional_lords(asc_sign_idx):
    """
    Map the functional house lords for key life domains using the Whole Sign House System.
    """
    SIGN_LORDS = {
        0: "Mars", 1: "Venus", 2: "Mercury", 3: "Moon",
        4: "Sun", 5: "Mercury", 6: "Venus", 7: "Mars",
        8: "Jupiter", 9: "Saturn", 10: "Saturn", 11: "Jupiter",
    }

    def lord_of_house(house_num):
        sign_idx = (asc_sign_idx + house_num - 1) % 12
        return SIGN_LORDS[sign_idx]

    return {
        "Lagna_Lord": lord_of_house(1),
        "Wealth_Lord": lord_of_house(2),
        "Job_Lord": lord_of_house(6),
        "Relationship_Lord": lord_of_house(7),
        "Chronic_Health_Lord": lord_of_house(8),
        "Career_Lord": lord_of_house(10),
        "Gains_Lord": lord_of_house(11),
    }


# ==========================================
# PRATYANTARDASHA (3-TIER DASHA ENGINE)
# ==========================================
def calculate_pratyantardasha(md_name, ad_name, ad_start_date, ad_end_date, target_date=None):
    """
    Calculate the active Pratyantardasha (sub-sub-period) within a given Antardasha window.
    """
    DASHA_SEQUENCE = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
    DASHA_YEARS = {
        "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10,
        "Mars": 7, "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17
    }

    if target_date is None:
        target_date = datetime.utcnow()

    md_name = str(md_name).strip()
    ad_name = str(ad_name).strip()

    if md_name not in DASHA_SEQUENCE:
        raise ValueError(f"Invalid Mahadasha planet: {md_name}")
    if ad_name not in DASHA_SEQUENCE:
        raise ValueError(f"Invalid Antardasha planet: {ad_name}")

    total_ad_days = (ad_end_date - ad_start_date).total_seconds() / 86400.0

    if total_ad_days <= 0:
        raise ValueError("Antardasha end date must be after start date.")

    ad_idx = DASHA_SEQUENCE.index(ad_name)
    reordered_sequence = DASHA_SEQUENCE[ad_idx:] + DASHA_SEQUENCE[:ad_idx]

    current_pointer = ad_start_date

    for planet in reordered_sequence:
        pd_factor = DASHA_YEARS[planet] / 120.0
        pd_days = total_ad_days * pd_factor
        pd_end = current_pointer + timedelta(days=pd_days)

        if current_pointer <= target_date < pd_end:
            return {
                "current_pd": planet,
                "pd_start": current_pointer.strftime("%d %b %Y"),
                "pd_end": pd_end.strftime("%d %b %Y"),
                "pd_start_dt": current_pointer,
                "pd_end_dt": pd_end,
            }

        current_pointer = pd_end

    return {
        "current_pd": reordered_sequence[-1],
        "pd_start": current_pointer.strftime("%d %b %Y"),
        "pd_end": ad_end_date.strftime("%d %b %Y"),
        "pd_start_dt": current_pointer,
        "pd_end_dt": ad_end_date,
    }


# ============================================================================
# MOON, MIND & CHANDRA LAGNA ENGINE (RE-EXPORTED FROM MOON PACKAGE)
# ============================================================================
from moon import (
    TITHI_NAMES,
    TARA_BALA_TYPES,
    CLASSICAL_MOON_GOCHAR_AUSPICIOUS,
    calculate_moon_details,
    get_chandra_lagna_data,
    calculate_moon_gochar,
    format_chandra_lagna_for_prompt,
    format_moon_gochar_for_prompt,
)


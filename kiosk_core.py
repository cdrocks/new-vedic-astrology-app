"""
Kiosk Core Engine: Executes chart calculations, Swiss Ephemeris math, and AI interpretation
for live event kiosks without touching or modifying the original app.py.
"""

import os
import pytz
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
import swisseph as swe
from geopy.geocoders import ArcGIS, Nominatim
from timezonefinder import TimezoneFinder
from openai import OpenAI

from engine import (
    get_nakshatra,
    calculate_vimshottari_dasha,
    find_next_ingress,
    find_next_station,
    detect_yogas,
    check_yoga_activation,
    calculate_panchadha_maitri,
    calculate_ashtakavarga,
    validate_sav_invariant,
    map_functional_lords,
    calculate_pratyantardasha,
    get_combustion_status
)
from moon import (
    calculate_moon_details,
    get_chandra_lagna_data,
    calculate_moon_gochar,
    format_chandra_lagna_for_prompt,
    format_moon_gochar_for_prompt
)
from bhava_bala import (
    compute_bhava_bala,
    format_bhava_bala,
    format_bhava_bala_indicative,
    strength_from_shadbala,
    shadbala_percent,
    CLASSICAL_MINIMUMS,
    validate_bhava_bala
)
from prompts import WORKFLOWS, classify_workflow, get_workflow_template

# Initialize Geocoder and TimezoneFinder
tf = TimezoneFinder()

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
    "Sun":     {"exalted": "Aries",     "debilitated": "Libra",      "own": ["Leo"]},
    "Moon":    {"exalted": "Taurus",    "debilitated": "Scorpio",    "own": ["Cancer"]},
    "Mars":    {"exalted": "Capricorn", "debilitated": "Cancer",     "own": ["Aries", "Scorpio"]},
    "Mercury": {"exalted": "Virgo",     "debilitated": "Pisces",     "own": ["Gemini", "Virgo"]},
    "Jupiter": {"exalted": "Cancer",    "debilitated": "Capricorn",  "own": ["Sagittarius", "Pisces"]},
    "Venus":   {"exalted": "Pisces",    "debilitated": "Virgo",      "own": ["Taurus", "Libra"]},
    "Saturn":  {"exalted": "Libra",     "debilitated": "Aries",      "own": ["Capricorn", "Aquarius"]}
}

def get_dignity(planet_name: str, sign: str) -> Optional[str]:
    if planet_name not in DIGNITIES:
        return None
    d = DIGNITIES[planet_name]
    if sign == d["exalted"]: return "Exalted"
    elif sign == d["debilitated"]: return "Debilitated"
    elif sign in d["own"]: return "Own Sign"
    return None

def get_house_from_sign_idx(ref_sign_idx: int, planet_sign_idx: int) -> int:
    return (planet_sign_idx - ref_sign_idx) % 12 + 1

def get_navamsa_sign_idx(deg_total: float) -> int:
    sign = int(deg_total / 30)
    deg_in_sign = deg_total % 30
    nav_num = int(deg_in_sign / (10.0 / 3.0))
    if sign % 3 == 0:
        return (sign + nav_num) % 12
    elif sign % 3 == 1:
        return (sign + 8 + nav_num) % 12
    else:
        return (sign + 4 + nav_num) % 12

def get_location_data(city_name: str) -> Optional[Tuple[float, float, str]]:
    """Resolve city to (lat, lon, timezone_str)."""
    try:
        geolocator = ArcGIS(timeout=7.0)
        loc = geolocator.geocode(city_name)
        if loc and hasattr(loc, "latitude") and hasattr(loc, "longitude"):
            lat = float(loc.latitude)
            lng = float(loc.longitude)
            tz_name = tf.timezone_at(lng=lng, lat=lat)
            if tz_name:
                return (lat, lng, tz_name)
    except Exception:
        pass

    try:
        geolocator = Nominatim(user_agent="vedic-kiosk/1.0", timeout=7.0)
        loc = geolocator.geocode(city_name)
        if loc and hasattr(loc, "latitude") and hasattr(loc, "longitude"):
            lat = float(loc.latitude)
            lng = float(loc.longitude)
            tz_name = tf.timezone_at(lng=lng, lat=lat)
            if tz_name:
                return (lat, lng, tz_name)
    except Exception:
        pass

    return None

def _get_api_key() -> str:
    """Retrieve API key from env or .streamlit/secrets.toml"""
    key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
        if os.path.exists(secrets_path):
            try:
                with open(secrets_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if "DEEPSEEK_API_KEY" in line and "=" in line:
                            key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception:
                pass
    return key or ""

def compute_kiosk_reading(
    name: str,
    dob_str: str,  # "YYYY-MM-DD"
    time_str: str, # "HH:MM"
    city: str,
    country: str,
    user_question: str,
    topic: str = ""
) -> Dict[str, Any]:
    """
    Computes full Vedic chart math and generates tailored AI interpretation.
    """
    api_key = _get_api_key()
    if not api_key:
        raise ValueError("API Key not found. Please set DEEPSEEK_API_KEY in environment or secrets.")

    # Geolocation
    query_loc = f"{city}, {country}" if country else city
    loc_data = get_location_data(query_loc)
    if not loc_data:
        raise ValueError(f"Could not locate '{query_loc}'. Please check city name spelling.")

    lat, lon, tz_name = loc_data
    tz = pytz.timezone(tz_name)
    
    dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
    tob = datetime.strptime(time_str, "%H:%M").time()
    
    local_naive = datetime.combine(dob, tob)
    try:
        local_dt = tz.localize(local_naive, is_dst=None)
    except pytz.exceptions.NonExistentTimeError:
        local_dt = tz.localize(local_naive + pytz.timedelta(hours=1))
    except pytz.exceptions.AmbiguousTimeError:
        local_dt = tz.localize(local_naive, is_dst=False)

    utc_dt = local_dt.astimezone(pytz.UTC)
    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day,
                    utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0)

    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED

    # 1. Ascendant
    chart_data: Dict[str, Dict[str, Any]] = {}
    _, ascmc = swe.houses_ex(jd, lat, lon, b'W', flags)
    asc_deg = ascmc[0]
    asc_sign_idx = int(asc_deg / 30) % 12
    asc_sign = RASHI_NAMES[asc_sign_idx]
    nak_name, nak_lord, pada = get_nakshatra(asc_deg % 360)

    chart_data["Ascendant"] = {
        "sign": asc_sign,
        "house": 1,
        "degree_total": asc_deg % 360,
        "degree_in_sign": asc_deg % 30,
        "sign_idx": asc_sign_idx,
        "nakshatra": nak_name,
        "nakshatra_lord": nak_lord,
        "pada": pada
    }

    # 2. Planetary positions
    for planet_id, planet_name in PLANETS.items():
        pos, _ = swe.calc_ut(jd, planet_id, flags)
        deg_total = pos[0] % 360
        speed = pos[3]
        status = "Rx" if speed < 0 and planet_id not in [swe.SUN, swe.MOON] else "Dir"
        if planet_id == swe.TRUE_NODE:
            status = "Rx"
        sign_idx = int(deg_total / 30) % 12
        p_nak_name, p_nak_lord, p_pada = get_nakshatra(deg_total)

        chart_data[planet_name] = {
            "sign": RASHI_NAMES[sign_idx],
            "house": get_house_from_sign_idx(asc_sign_idx, sign_idx),
            "degree_total": deg_total,
            "degree_in_sign": deg_total % 30,
            "sign_idx": sign_idx,
            "speed": speed,
            "status": status,
            "dignity": get_dignity(planet_name, RASHI_NAMES[sign_idx]),
            "nakshatra": p_nak_name,
            "nakshatra_lord": p_nak_lord,
            "pada": p_pada
        }

    # Ketu
    rahu_deg = chart_data["Rahu"]["degree_total"]
    ketu_deg = (rahu_deg + 180) % 360
    ketu_sign_idx = int(ketu_deg / 30) % 12
    k_nak, k_lord, k_pada = get_nakshatra(ketu_deg)
    chart_data["Ketu"] = {
        "sign": RASHI_NAMES[ketu_sign_idx],
        "house": get_house_from_sign_idx(asc_sign_idx, ketu_sign_idx),
        "degree_total": ketu_deg,
        "degree_in_sign": ketu_deg % 30,
        "sign_idx": ketu_sign_idx,
        "status": "Rx",
        "dignity": None,
        "nakshatra": k_nak,
        "nakshatra_lord": k_lord,
        "pada": k_pada
    }

    # 3. Navamsa (D9) Chart & Vargottama Planets
    d9_chart_data = {}
    vargottama_planets = []
    for p_name, p_data in chart_data.items():
        d9_idx = get_navamsa_sign_idx(p_data["degree_total"])
        d9_chart_data[p_name] = {
            "sign": RASHI_NAMES[d9_idx],
            "sign_idx": d9_idx,
            "dignity": get_dignity(p_name, RASHI_NAMES[d9_idx])
        }
        if p_data["sign_idx"] == d9_idx:
            vargottama_planets.append(p_name)

    d9_string = "### NAVAMSA (D9) CHART\n"
    d9_string += f"Ascendant: {d9_chart_data['Ascendant']['sign']}\n"
    for p_name in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]:
        if p_name in d9_chart_data:
            dign = d9_chart_data[p_name].get("dignity")
            dign_tag = f" ({dign})" if dign else ""
            d9_string += f"{p_name}: {d9_chart_data[p_name]['sign']}{dign_tag}\n"

    if vargottama_planets:
        d9_string += f"\nVargottama Planets (D1 = D9): {', '.join(vargottama_planets)}\n"
    else:
        d9_string += "\nNo Vargottama planets.\n"

    # 4. Panchadha Maitri (5-fold Relationship)
    natal_signs_for_maitri = {
        "Sun": int(chart_data["Sun"]["sign_idx"]),
        "Moon": int(chart_data["Moon"]["sign_idx"]),
        "Mars": int(chart_data["Mars"]["sign_idx"]),
        "Mercury": int(chart_data["Mercury"]["sign_idx"]),
        "Jupiter": int(chart_data["Jupiter"]["sign_idx"]),
        "Venus": int(chart_data["Venus"]["sign_idx"]),
        "Saturn": int(chart_data["Saturn"]["sign_idx"])
    }
    natal_houses_for_maitri = {
        "Sun": int(chart_data["Sun"]["house"]),
        "Moon": int(chart_data["Moon"]["house"]),
        "Mars": int(chart_data["Mars"]["house"]),
        "Mercury": int(chart_data["Mercury"]["house"]),
        "Jupiter": int(chart_data["Jupiter"]["house"]),
        "Venus": int(chart_data["Venus"]["house"]),
        "Saturn": int(chart_data["Saturn"]["house"])
    }
    panchadha_data = calculate_panchadha_maitri(natal_signs_for_maitri, natal_houses_for_maitri)
    panchadha_string = "### PANCHADHA MAITRI (5-FOLD PLANETARY FRIENDSHIP)\n"
    for p_name, p_data in panchadha_data.items():
        if p_data.get("Final_Relationship") in ["Own Sign", "Own House"]:
            panchadha_string += (
                f"{p_name} in House {natal_houses_for_maitri[p_name]} "
                f"→ Host: {p_data.get('Host', '')} (Own Sign / Sva-kshetra) | Final: Own Sign\n"
            )
        else:
            panchadha_string += (
                f"{p_name} in House {natal_houses_for_maitri[p_name]} "
                f"→ Host: {p_data.get('Host', '')} | "
                f"Natural: {p_data.get('Natural_Status', '')} | "
                f"Temporary: {p_data.get('Temporary_Status', '')} | "
                f"Final: {p_data.get('Final_Relationship', 'Neutral')}\n"
            )

    # 5. Ashtakavarga & Bhava Bala
    natal_positions_for_av = {
        "Ascendant": int(asc_sign_idx) + 1,
        "Sun": int(chart_data["Sun"]["sign_idx"]) + 1,
        "Moon": int(chart_data["Moon"]["sign_idx"]) + 1,
        "Mars": int(chart_data["Mars"]["sign_idx"]) + 1,
        "Mercury": int(chart_data["Mercury"]["sign_idx"]) + 1,
        "Jupiter": int(chart_data["Jupiter"]["sign_idx"]) + 1,
        "Venus": int(chart_data["Venus"]["sign_idx"]) + 1,
        "Saturn": int(chart_data["Saturn"]["sign_idx"]) + 1,
    }
    ashtakavarga_data = calculate_ashtakavarga(natal_positions_for_av)
    sav = ashtakavarga_data.get("SAV", {})

    ashtakavarga_string = "### SAMUDAYA ASHTAKAVARGA (SAV)\n"
    for h in range(1, 13):
        r_idx = (asc_sign_idx + h - 1) % 12
        pts = sav.get(r_idx + 1, 28)
        label = "Strong" if pts >= 28 else ("Average" if pts >= 25 else "Low")
        ashtakavarga_string += f"House {h} ({RASHI_NAMES[r_idx]}): {pts} points [{label}]\n"

    bb_data = compute_bhava_bala(chart_data, jd, lat, lon, flags)

    strength_string = "### PLANETARY STRENGTH (SHADBALA)\n"
    for planet in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        if planet in chart_data:
            sb = bb_data["planets_shadbala"][planet]
            pct = shadbala_percent(sb["total"], planet)
            chart_data[planet]["strength"] = strength_from_shadbala(sb["total"], planet)
            chart_data[planet]["shadbala_pct"] = pct
            strength_string += f"- **{planet}**: {pct:.0f}% of requirement ({strength_from_shadbala(sb['total'], planet)})\n"

    bhava_bala_string = format_bhava_bala_indicative(bb_data)

    # 6. Functional Lords
    functional_lords = map_functional_lords(asc_sign_idx)
    functional_lords_string = "### FUNCTIONAL NATURE OF PLANETS\n"
    for cat, p_list in functional_lords.items():
        functional_lords_string += f"- {cat}: {', '.join(p_list) if p_list else 'None'}\n"

    # 7. Planetary Aspects (Drishti)
    def get_target_house(current_house, aspect_offset):
        return (current_house + aspect_offset - 2) % 12 + 1

    aspects_string = "### NATAL PLANETARY ASPECTS\n"
    for p, pdata in chart_data.items():
        if p == "Ascendant":
            continue
        current_house = pdata["house"]
        aspects = [get_target_house(current_house, 7)]
        if p == "Mars":
            aspects.extend([get_target_house(current_house, 4), get_target_house(current_house, 8)])
        elif p == "Jupiter":
            aspects.extend([get_target_house(current_house, 5), get_target_house(current_house, 9)])
        elif p == "Saturn":
            aspects.extend([get_target_house(current_house, 3), get_target_house(current_house, 10)])

        seen = set()
        unique_aspects = []
        for a in aspects:
            if a not in seen:
                seen.add(a)
                unique_aspects.append(a)
        unique_aspects.sort()
        if unique_aspects:
            aspects_string += f"{p} (in H{current_house}) aspects Houses: {', '.join(map(str, unique_aspects))}\n"

    # 8. Chara Karakas
    karaka_planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    sorted_karakas = sorted(
        karaka_planets,
        key=lambda p: chart_data[p]["degree_in_sign"],
        reverse=True
    )
    atmakaraka = sorted_karakas[0]

    karaka_labels = [
        "Atmakaraka (AK)", "Amatyakaraka (AmK)", "Bhratrikaraka (BK)",
        "Matrikaraka (MK)", "Putrakaraka (PK)", "Gnatikaraka (GK)", "Darakaraka (DK)"
    ]
    karaka_string = "### CHARA KARAKAS\n"
    for i, planet in enumerate(sorted_karakas):
        karaka_string += f"{karaka_labels[i]}: {planet} ({chart_data[planet]['degree_in_sign']:.2f}°)\n"

    # 9. Vimshottari Dasha & Dynamic Target Date
    import re
    moon_deg = chart_data["Moon"]["degree_total"]
    real_now = datetime.now(pytz.UTC)
    now_utc = real_now

    # Check if question specifies a future year (e.g. 2027, 2028)
    year_match = re.search(r'\b(20\d{2})\b', user_question)
    if year_match:
        target_year = int(year_match.group(1))
        if target_year >= real_now.year:
            try:
                now_utc = real_now.replace(year=target_year)
            except ValueError:
                now_utc = real_now.replace(year=target_year, day=28)

    dasha_data = calculate_vimshottari_dasha(moon_deg, utc_dt, now_utc)

    current_mahadasha = dasha_data.get("md", "")
    current_antardasha = dasha_data.get("ad", "")
    current_pd = dasha_data.get("current_pd", "")

    moon_nak, moon_nak_lord, moon_pada = get_nakshatra(chart_data["Moon"]["degree_total"])
    dasha_string = (
        f"### VIMSHOTTARI DASHA TIMELINE (CALCULATED FROM NATAL MOON)\n"
        f"Natal Moon Nakshatra: {moon_nak} (Lord: {moon_nak_lord}), Pada {moon_pada}\n"
        f"Current Mahadasha (Main Period): {current_mahadasha}\n"
        f"  - Began: {dasha_data.get('md_start')} | Ends: {dasha_data.get('md_end')}\n"
        f"Current Antardasha (Sub Period): {current_antardasha}\n"
        f"  - Began: {dasha_data.get('ad_start')} | Ends: {dasha_data.get('ad_end')}\n"
        f"Current Pratyantardasha: {current_pd}\n"
        f"  - Began: {dasha_data.get('pd_start')} | Ends: {dasha_data.get('pd_end')}\n"
        f"Next Mahadasha: {dasha_data.get('md_next')} (begins {dasha_data.get('md_end')})\n"
        f"Next Antardasha: {dasha_data.get('ad_next')} (begins {dasha_data.get('ad_end')})\n"
    )

    # 10. Moon Details & Chandra Lagna
    moon_details = calculate_moon_details(moon_deg, chart_data["Sun"]["degree_total"])
    moon_sign_idx = chart_data["Moon"]["sign_idx"]
    chandra_lagna_data = get_chandra_lagna_data(chart_data, moon_sign_idx)
    chandra_lagna_string = format_chandra_lagna_for_prompt(chandra_lagna_data, moon_details)

    # 11. Live Planetary Transits (Gochar)
    jd_now = swe.julday(
        now_utc.year, now_utc.month, now_utc.day,
        now_utc.hour + now_utc.minute / 60.0 + now_utc.second / 3600.0
    )
    gochar_string = "### LIVE PLANETARY TRANSITS (GOCHAR)\n"
    transit_dict = {}
    for p_id, p_name in PLANETS.items():
        pos_now, _ = swe.calc_ut(jd_now, p_id, flags)
        deg_now = pos_now[0] % 360
        sign_now_idx = int(deg_now / 30) % 12
        rx_tag = " (Rx)" if (p_name == "Rahu" or (p_name not in ["Sun", "Moon"] and pos_now[3] < 0)) else ""
        t_status = "Rx" if rx_tag else "Dir"

        transit_dict[p_name] = {
            "sign": RASHI_NAMES[sign_now_idx],
            "sign_idx": sign_now_idx,
            "degree_total": deg_now,
            "degree_in_sign": deg_now % 30,
            "status": t_status
        }
        h_asc = (sign_now_idx - asc_sign_idx) % 12 + 1
        h_moon = (sign_now_idx - moon_sign_idx) % 12 + 1
        rashi_key = sign_now_idx + 1
        t_sav = sav.get(rashi_key, 28)
        sav_label = "Strong" if t_sav >= 28 else ("Average" if t_sav >= 25 else "Low")
        gochar_string += (
            f"{p_name}{rx_tag}: {RASHI_NAMES[sign_now_idx]} ({deg_now % 30:.2f}°) [SAV: {t_sav} ({sav_label})] — "
            f"House {h_asc} from Lagna, House {h_moon} from Moon\n"
        )

    # Ketu transit
    rahu_now_deg = transit_dict["Rahu"]["degree_total"]
    ketu_now_deg = (rahu_now_deg + 180) % 360
    ketu_t_sign_idx = int(ketu_now_deg / 30) % 12
    transit_dict["Ketu"] = {
        "sign": RASHI_NAMES[ketu_t_sign_idx],
        "sign_idx": ketu_t_sign_idx,
        "degree_total": ketu_now_deg,
        "degree_in_sign": ketu_now_deg % 30,
        "status": "Rx"
    }
    ketu_h_asc = (ketu_t_sign_idx - asc_sign_idx) % 12 + 1
    ketu_h_moon = (ketu_t_sign_idx - moon_sign_idx) % 12 + 1
    ketu_sav = sav.get(ketu_t_sign_idx + 1, 28)
    ketu_sav_label = "Strong" if ketu_sav >= 28 else ("Average" if ketu_sav >= 25 else "Low")
    gochar_string += (
        f"Ketu (Rx): {RASHI_NAMES[ketu_t_sign_idx]} ({ketu_now_deg % 30:.2f}°) [SAV: {ketu_sav} ({ketu_sav_label})] — "
        f"House {ketu_h_asc} from Lagna, House {ketu_h_moon} from Moon\n"
    )

    # Ingress and stations
    transit_events = []
    for p_name, p_id in [("Jupiter", swe.JUPITER), ("Saturn", swe.SATURN), ("Rahu", swe.TRUE_NODE)]:
        n_sign, n_date, _ = find_next_ingress(jd_now, p_id, flags, now_utc, RASHI_NAMES)
        if n_sign and n_date:
            transit_events.append(f"{p_name} enters {n_sign}: {n_date}")
        if p_name not in ["Rahu", "Ketu"]:
            st_type, st_date, _ = find_next_station(jd_now, p_id, flags, now_utc)
            if st_type and st_date:
                transit_events.append(f"{p_name} goes {st_type}: {st_date}")
    if transit_events:
        gochar_string += "\n### UPCOMING VERIFIED TRANSIT EVENTS\n" + "\n".join(transit_events) + "\n"

    # 12. Dedicated Moon Gochar (Sade Sati & Psychological Weather)
    today_moon_deg = float(transit_dict["Moon"]["degree_total"]) if "Moon" in transit_dict else None
    natal_moon_nak_idx = int(moon_details["nakshatra_idx"])
    moon_gochar_data = calculate_moon_gochar(
        chart_data,
        transit_dict,
        moon_sign_idx,
        natal_moon_nak_idx,
        today_moon_deg=today_moon_deg,
        sav=sav
    )
    moon_gochar_string = format_moon_gochar_for_prompt(moon_gochar_data)

    # 13. Detect Yogas & Check Dasha Activation
    detected_yogas = detect_yogas(chart_data, asc_sign_idx)
    yoga_activation = check_yoga_activation(detected_yogas, dasha_data)

    yoga_string = "### TOP YOGAS & DASHA ACTIVATION\n"
    if not yoga_activation:
        yoga_string += "No major classical yogas detected in this chart.\n"
    else:
        for i, y in enumerate(yoga_activation, 1):
            status_icon = "🟢 Active" if y["active"] else "⚪ Inactive"
            p_list = y.get("planets", [])
            p_str = ", ".join(str(p_item) for p_item in p_list) if isinstance(p_list, list) else str(p_list)
            yoga_string += (
                f"\n{i}. {y['name']} [{y['category']}] — {status_icon}\n"
                f"   Planets: {p_str} | Reference: {y['classical_ref']}\n"
                f"   Life Promise: {y['desc']}\n"
                f"   Activation Status: {y['timing']}\n"
            )

    # 14. Natal Placements (D1 Chart String)
    chart_string = (
        f"Ascendant: {chart_data['Ascendant']['sign']} "
        f"({chart_data['Ascendant']['degree_in_sign']:.2f}°) "
        f"[{chart_data['Ascendant']['nakshatra']} Pada {chart_data['Ascendant']['pada']}]\n"
    )
    for p, pdata in chart_data.items():
        if p == "Ascendant":
            continue
        combust_tag = " (Combust)" if pdata.get("combustion") else ""
        rx_tag = " (Retrograde)" if pdata.get('status') == 'Rx' else ""
        dignity_label = pdata.get("dignity")
        dignity_tag = f" ({dignity_label})" if dignity_label else ""
        nak_tag = f" — {pdata['nakshatra']} Pada {pdata['pada']}"
        chart_string += (
            f"{p}: {pdata['sign']} ({pdata['degree_in_sign']:.2f}°) "
            f"in House {pdata['house']}{nak_tag}{rx_tag}{combust_tag}{dignity_tag}\n"
        )

    # Workflows classification
    workflow_key = classify_workflow(user_question)
    current_date = now_utc.strftime("%d %B %Y")

    # Safe placeholder replacement across the workflow template
    replacements = {
        "{chart_string}": chart_string,
        "{aspects_string}": aspects_string,
        "{d9_string}": d9_string,
        "{panchadha_string}": panchadha_string,
        "{strength_string}": strength_string,
        "{ashtakavarga_string}": ashtakavarga_string,
        "{functional_lords_string}": functional_lords_string,
        "{dasha_string}": dasha_string,
        "{chandra_lagna_string}": chandra_lagna_string,
        "{moon_gochar_string}": moon_gochar_string,
        "{gochar_string}": gochar_string,
        "{yoga_string}": yoga_string,
        "{karaka_string}": karaka_string,
        "{current_date}": current_date,
    }

    system_prompt = get_workflow_template(workflow_key)
    for placeholder, value in replacements.items():
        system_prompt = system_prompt.replace(placeholder, value)

    # ====================================================================
    #  CONSUMER INSIGHT, TOPIC DIVERSITY & TIMING INDEPENDENCE DIRECTIVE
    # ====================================================================
    system_prompt += (
        "\n\n### CONSUMER INSIGHT, TOPIC DIVERSITY & TIMING INDEPENDENCE DIRECTIVE ###\n"
        "1. DIRECT ANSWER IN FIRST SENTENCE: Answer the user's specific question immediately, clearly, and concisely in the very first sentence.\n"
        "2. TIMING INDEPENDENCE (CRITICAL ANTI-REPETITION RULE): Each life area operates on its OWN unique planetary clock and transits. NEVER postpone everything to the next Antardasha change (e.g. late 2026 / Jupiter Antardasha) as a generic answer for every question! Provide specific, independent windows (e.g. next 1–3 months, 3–6 months, seasonal shifts) based strictly on the planetary rulers of the asked topic.\n"
        "3. ZERO BOILERPLATE WARNINGS / NO SADE SATI OBSESSION: Do NOT repeat the same generic warnings about 'heavy responsibility', 'mental pressure', 'laying bricks', or 'emotional strain' across multiple topics. If the user asks about Wealth, focus 100% on financial strategy, income streams, and capital retention. If they ask about Career, focus 100% on professional status, authority, and skill leverage.\n"
        "4. ZERO ASTROLOGICAL JARGON: NEVER recite raw chart coordinates, house numbers, or technical Sanskrit terms without seamless translation into everyday human language.\n"
    )

    system_prompt += "\n\n### HOUSE SUPPORT INDICATORS (BHAVA BALA)\n" + bhava_bala_string

    user_prompt = f"The native asks: <question>{user_question}</question>"

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.65,
        presence_penalty=0.25,
        frequency_penalty=0.2,
        max_tokens=1800
    )

    reading_text = response.choices[0].message.content or ""

    from nakshatra_archetypes import get_nakshatra_archetype
    moon_nak = chart_data["Moon"]["nakshatra"]
    nak_archetype = get_nakshatra_archetype(moon_nak)

    return {
        "name": name,
        "ascendant": asc_sign,
        "moon_sign": chart_data["Moon"]["sign"],
        "sun_sign": chart_data["Sun"]["sign"],
        "nakshatra": moon_nak,
        "archetype_title": nak_archetype["title"],
        "life_focus": nak_archetype["life_focus"],
        "atmakaraka": atmakaraka,
        "current_dasha": f"{current_mahadasha} - {current_antardasha}" if current_antardasha else current_mahadasha,
        "reading": reading_text,
        "workflow": workflow_key,
        "timestamp": datetime.now().isoformat()
    }

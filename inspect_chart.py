#!/usr/bin/env python3
"""
Vedic Astrology Chart Inspector (CLI)
=====================================
Instantly computes and displays the full mathematical Vedic birth chart
directly in your terminal for private client consultations.
Zero reliance on Streamlit, zero LLM cost, instant calculation.
"""

import sys
import os
import argparse
from datetime import datetime, timedelta
import pytz
import swisseph as swe
from geopy.geocoders import ArcGIS
from timezonefinder import TimezoneFinder

# Ensure workspace root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import (
    get_nakshatra,
    calculate_vimshottari_dasha,
    detect_yogas,
    check_yoga_activation,
    calculate_panchadha_maitri,
    calculate_ashtakavarga,
    map_functional_lords,
    calculate_pratyantardasha,
    get_combustion_status,
    COMBUSTION_LIMITS,
    get_house_from_sign_idx
)
from moon import (
    calculate_moon_details,
    calculate_moon_gochar
)
from bhava_bala import (
    compute_bhava_bala,
    strength_from_shadbala,
    CLASSICAL_MINIMUMS
)
from nakshatra_archetypes import get_nakshatra_archetype
from doshas import calculate_doshas

RASHI_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

SIGN_LORDS = {
    0: "Mars", 1: "Venus", 2: "Mercury", 3: "Moon",
    4: "Sun", 5: "Mercury", 6: "Venus", 7: "Mars",
    8: "Jupiter", 9: "Saturn", 10: "Saturn", 11: "Jupiter"
}

PLANETS = {
    swe.SUN: "Sun",
    swe.MOON: "Moon",
    swe.MARS: "Mars",
    swe.MERCURY: "Mercury",
    swe.JUPITER: "Jupiter",
    swe.VENUS: "Venus",
    swe.SATURN: "Saturn",
    swe.TRUE_NODE: "Rahu"
}

DIGNITIES = {
    "Sun": {"exalted": "Aries", "debilitated": "Libra", "own": ["Leo"]},
    "Moon": {"exalted": "Taurus", "debilitated": "Scorpio", "own": ["Cancer"]},
    "Mars": {"exalted": "Capricorn", "debilitated": "Cancer", "own": ["Aries", "Scorpio"]},
    "Mercury": {"exalted": "Virgo", "debilitated": "Pisces", "own": ["Gemini", "Virgo"]},
    "Jupiter": {"exalted": "Cancer", "debilitated": "Capricorn", "own": ["Sagittarius", "Pisces"]},
    "Venus": {"exalted": "Pisces", "debilitated": "Virgo", "own": ["Taurus", "Libra"]},
    "Saturn": {"exalted": "Libra", "debilitated": "Aries", "own": ["Capricorn", "Aquarius"]},
    "Rahu": {"exalted": "Taurus", "debilitated": "Scorpio", "own": ["Aquarius"]},
    "Ketu": {"exalted": "Scorpio", "debilitated": "Taurus", "own": ["Scorpio"]}
}

def get_dignity(planet: str, sign: str) -> str:
    rules = DIGNITIES.get(planet, {})
    if sign == rules.get("exalted"):
        return "Exalted"
    if sign == rules.get("debilitated"):
        return "Debilitated"
    if sign in rules.get("own", []):
        return "Own Sign"
    return "Neutral"

def get_house_from_sign_idx(asc_sign_idx: int, sign_idx: int) -> int:
    return (sign_idx - asc_sign_idx) % 12 + 1

def get_navamsa_sign_idx(deg_total: float) -> int:
    sign_idx = int(deg_total / 30) % 12
    pada_in_sign = int((deg_total % 30) / (30.0 / 9.0)) % 9
    element = sign_idx % 4
    if element == 0:
        start = 0
    elif element == 1:
        start = 9
    elif element == 2:
        start = 6
    else:
        start = 3
    return (start + pada_in_sign) % 12

def get_lagna_functional_profile(asc_sign_idx: int):
    YOGAKARAKAS = {
        1: "Saturn (Lord of 9th & 10th)",
        3: "Mars (Lord of 5th & 10th)",
        4: "Mars (Lord of 4th & 9th)",
        6: "Saturn (Lord of 4th & 5th)",
        9: "Venus (Lord of 5th & 10th)",
        10: "Venus (Lord of 4th & 9th)",
    }
    SIGN_LORDS = {
        0: "Mars", 1: "Venus", 2: "Mercury", 3: "Moon",
        4: "Sun", 5: "Mercury", 6: "Venus", 7: "Mars",
        8: "Jupiter", 9: "Saturn", 10: "Saturn", 11: "Jupiter"
    }
    def lord(h):
        return SIGN_LORDS[(asc_sign_idx + h - 1) % 12]
        
    lagna_lord = lord(1)
    trikona_lords = [f"{lord(h)} (L{h})" for h in [1, 5, 9]]
    dusthana_lords = [f"{lord(h)} (L{h})" for h in [6, 8, 12]]
    maraka_lords = [f"{lord(h)} (L{h})" for h in [2, 7]]
    
    if asc_sign_idx in [0, 3, 6, 9]:
        badhaka_house = 11
    elif asc_sign_idx in [1, 4, 7, 10]:
        badhaka_house = 9
    else:
        badhaka_house = 7
    badhaka_lord = lord(badhaka_house)
    
    return {
        "lagna_lord": lagna_lord,
        "yogakaraka": YOGAKARAKAS.get(asc_sign_idx, "None"),
        "functional_benefics": ", ".join(dict.fromkeys(trikona_lords)),
        "functional_malefics": ", ".join(dict.fromkeys(dusthana_lords)),
        "marakas": ", ".join(dict.fromkeys(maraka_lords)),
        "badhaka": f"House {badhaka_house} ({badhaka_lord})"
    }

def compute_aspects_and_special(chart_data: dict, asc_sign_idx: int):
    aspects = {}
    SEVEN_PLUS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
    
    house_occupants = {h: [] for h in range(1, 13)}
    for p in SEVEN_PLUS:
        h = chart_data[p]["house"]
        p_name = f"{p} (Rx)" if chart_data[p].get("status") == "Rx" else p
        house_occupants[h].append(p_name)
        
    for p in SEVEN_PLUS:
        h = chart_data[p]["house"]
        aspected_houses = []
        aspected_houses.append((h + 6 - 1) % 12 + 1)
        if p == "Mars":
            aspected_houses.append((h + 3 - 1) % 12 + 1)
            aspected_houses.append((h + 7 - 1) % 12 + 1)
        elif p == "Jupiter":
            aspected_houses.append((h + 4 - 1) % 12 + 1)
            aspected_houses.append((h + 8 - 1) % 12 + 1)
        elif p == "Saturn":
            aspected_houses.append((h + 2 - 1) % 12 + 1)
            aspected_houses.append((h + 9 - 1) % 12 + 1)
        elif p in ["Rahu", "Ketu"]:
            aspected_houses.append((h + 4 - 1) % 12 + 1)
            aspected_houses.append((h + 8 - 1) % 12 + 1)
            
        aspected_houses = sorted(list(set(aspected_houses)))
        targets = []
        for ah in aspected_houses:
            for occ in house_occupants[ah]:
                targets.append(f"{occ} (H{ah})")
                
        aspects[p] = {
            "houses": aspected_houses,
            "targets": targets
        }
        
    mars_h_lagna = chart_data["Mars"]["house"]
    mars_h_moon = (chart_data["Mars"]["sign_idx"] - chart_data["Moon"]["sign_idx"]) % 12 + 1
    is_manglik_lagna = mars_h_lagna in [1, 4, 7, 8, 12]
    is_manglik_moon = mars_h_moon in [1, 4, 7, 8, 12]
    
    gandanta = []
    for p in ["Ascendant", "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        sign_idx = chart_data[p]["sign_idx"]
        deg_in_sign = chart_data[p]["degree_in_sign"]
        if sign_idx in [3, 7, 11] and deg_in_sign >= 26.666:
            gandanta.append(f"{p} ({RASHI_NAMES[sign_idx]} {deg_in_sign:.2f}° — Water Junction)")
        elif sign_idx in [0, 4, 8] and deg_in_sign <= 3.333:
            gandanta.append(f"{p} ({RASHI_NAMES[sign_idx]} {deg_in_sign:.2f}° — Fire Junction)")
            
    return {
        "aspects": aspects,
        "is_manglik_lagna": is_manglik_lagna,
        "mars_h_lagna": mars_h_lagna,
        "is_manglik_moon": is_manglik_moon,
        "mars_h_moon": mars_h_moon,
        "gandanta": gandanta
    }

def compute_antardasha_sequence(moon_deg: float, birth_dt: datetime, target_dt: datetime):
    DASHA_SEQ = [
        ("Ketu", 7), ("Venus", 20), ("Sun", 6), ("Moon", 10),
        ("Mars", 7), ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17)
    ]
    days_per_year = 365.2425
    nak_len = 360.0 / 27.0
    lord_idx = int(moon_deg / nak_len) % 9
    fraction_passed = (moon_deg % nak_len) / nak_len
    first_lord, first_years = DASHA_SEQ[lord_idx]
    balance_years = (1.0 - fraction_passed) * first_years
    elapsed_before_birth = first_years - balance_years
    
    days_passed = (target_dt - birth_dt).total_seconds() / 86400.0
    years_passed = days_passed / days_per_year
    
    if years_passed < balance_years:
        current_md = first_lord
        md_idx = lord_idx
        md_duration = first_years
        nominal_md_start_dt = birth_dt - timedelta(days=elapsed_before_birth * days_per_year)
        md_end_dt = birth_dt + timedelta(days=balance_years * days_per_year)
        md_start_dt = nominal_md_start_dt
        years_into_md = elapsed_before_birth + years_passed
    else:
        accumulated = balance_years
        md_idx = (lord_idx + 1) % 9
        for _ in range(20):
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
            
    ad_sequence = []
    ad_accum = 0.0
    for i in range(9):
        curr_ad_idx = (md_idx + i) % 9
        ad_name, ad_years_nom = DASHA_SEQ[curr_ad_idx]
        ad_dur_years = (md_duration * ad_years_nom) / 120.0
        ad_s_dt = nominal_md_start_dt + timedelta(days=ad_accum * days_per_year)
        ad_e_dt = nominal_md_start_dt + timedelta(days=(ad_accum + ad_dur_years) * days_per_year)
        
        is_active = (ad_s_dt <= target_dt < ad_e_dt)
        is_past = (ad_e_dt <= target_dt)
        
        ad_sequence.append({
            "planet": ad_name,
            "start": ad_s_dt.strftime("%d %b %Y"),
            "end": ad_e_dt.strftime("%d %b %Y"),
            "duration_years": round(ad_dur_years, 2),
            "is_active": is_active,
            "is_past": is_past,
            "days_left": max(0, int((ad_e_dt - target_dt).days)) if is_active else 0
        })
        ad_accum += ad_dur_years
        
    return {
        "md_name": current_md,
        "md_start": md_start_dt.strftime("%d %b %Y"),
        "md_end": md_end_dt.strftime("%d %b %Y"),
        "md_days_left": max(0, int((md_end_dt - target_dt).days)),
        "ad_sequence": ad_sequence
    }

def parse_birth_time(time_str: str):
    clean = time_str.strip().upper().replace(".", "")
    formats = [
        "%H:%M",
        "%I:%M %p",
        "%I:%M%p",
        "%H:%M:%S",
        "%I:%M:%S %p",
        "%I:%M:%S%p"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(clean, fmt).time()
        except ValueError:
            pass
    raise ValueError(
        f"Invalid time format '{time_str}'.\n"
        "  • For 5 minutes after midnight: use '00:05' or '12:05 AM'\n"
        "  • For 5 minutes after noon:     use '12:05' or '12:05 PM'"
    )

def parse_birth_date(dob_str: str):
    clean = dob_str.strip()
    formats = [
        "%Y-%m-%d",    # 1994-06-15
        "%d/%m/%Y",    # 15/06/1994
        "%d-%m-%Y",    # 15-06-1994
        "%d.%m.%Y",    # 15.06.1994
        "%d %b %Y",    # 15 Jun 1994
        "%d %B %Y",    # 15 June 1994
        "%B %d %Y",    # June 15 1994
        "%B %d, %Y",   # June 15, 1994
        "%b %d %Y",    # Jun 15 1994
        "%b %d, %Y",   # Jun 15, 1994
        "%Y/%m/%d",    # 1994/06/15
        "%m/%d/%Y",    # 06/15/1994
    ]
    for fmt in formats:
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            pass
    raise ValueError(
        f"Invalid date format '{dob_str}'.\n"
        "  Accepted examples: 15/06/1994, 15-06-1994, 1994-06-15, or 15 June 1994"
    )

def calculate_chart(name: str, dob_str: str, time_str: str, city: str, country: str = "India"):
    query = f"{city}, {country}" if country else city
    geolocator = ArcGIS(user_agent="vedic_inspector")
    loc = geolocator.geocode(query, timeout=10)
    if not loc:
        raise ValueError(f"Could not find coordinates for location '{query}'")

    lat, lon = loc.latitude, loc.longitude
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lon) or "Asia/Kolkata"
    tz = pytz.timezone(tz_name)

    dob = parse_birth_date(dob_str)
    tob = parse_birth_time(time_str)
    local_naive = datetime.combine(dob, tob)
    try:
        local_dt = tz.localize(local_naive, is_dst=None)
    except Exception:
        local_dt = tz.localize(local_naive, is_dst=False)
    utc_dt = local_dt.astimezone(pytz.UTC)

    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day,
                    utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0)

    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED

    # Ascendant
    _, ascmc = swe.houses_ex(jd, lat, lon, b'W', flags)
    asc_deg = ascmc[0]
    asc_sign_idx = int(asc_deg / 30) % 12
    asc_sign = RASHI_NAMES[asc_sign_idx]
    nak_name, nak_lord, pada = get_nakshatra(asc_deg % 360)

    chart_data = {
        "Ascendant": {
            "sign": asc_sign,
            "house": 1,
            "degree_total": asc_deg % 360,
            "degree_in_sign": asc_deg % 30,
            "sign_idx": asc_sign_idx,
            "nakshatra": nak_name,
            "nakshatra_lord": nak_lord,
            "pada": pada,
            "status": "Dir",
            "dignity": "-"
        }
    }

    # Planetary positions
    for planet_id, planet_name in PLANETS.items():
        pos, _ = swe.calc_ut(jd, planet_id, flags)
        deg_total = pos[0] % 360
        speed = pos[3]
        status = "Rx" if speed < 0 and planet_id not in [swe.SUN, swe.MOON] else "Dir"
        if planet_id == swe.TRUE_NODE:
            status = "Rx"
        sign_idx = int(deg_total / 30) % 12
        p_nak, p_lord, p_pada = get_nakshatra(deg_total)

        chart_data[planet_name] = {
            "sign": RASHI_NAMES[sign_idx],
            "house": get_house_from_sign_idx(asc_sign_idx, sign_idx),
            "degree_total": deg_total,
            "degree_in_sign": deg_total % 30,
            "sign_idx": sign_idx,
            "speed": speed,
            "status": status,
            "dignity": get_dignity(planet_name, RASHI_NAMES[sign_idx]),
            "nakshatra": p_nak,
            "nakshatra_lord": p_lord,
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
        "dignity": "-",
        "nakshatra": k_nak,
        "nakshatra_lord": k_lord,
        "pada": k_pada
    }

    # Natal Combustion check (Astangata)
    sun_natal_deg = chart_data["Sun"]["degree_total"]
    for p in ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        dist = abs(sun_natal_deg - chart_data[p]["degree_total"])
        if dist > 180.0:
            dist = 360.0 - dist
        chart_data[p]["sun_dist"] = dist
        is_comb = (get_combustion_status(p, chart_data) == "Combust")
        chart_data[p]["combustion"] = is_comb
        limits = COMBUSTION_LIMITS.get(p, {})
        chart_data[p]["comb_limit"] = limits.get("rx") if chart_data[p]["status"] == "Rx" else limits.get("direct")

    # Navamsa & Vargottama
    d9_asc_idx = get_navamsa_sign_idx(chart_data["Ascendant"]["degree_total"])
    d9_data = {}
    vargottama = []
    for p, pdata in chart_data.items():
        d9_idx = get_navamsa_sign_idx(pdata["degree_total"])
        d9_h = ((d9_idx - d9_asc_idx) % 12) + 1
        d9_data[p] = {
            "sign": RASHI_NAMES[d9_idx],
            "sign_idx": d9_idx,
            "house": d9_h,
            "dignity": get_dignity(p, RASHI_NAMES[d9_idx])
        }
        if p != "Ascendant" and pdata["sign_idx"] == d9_idx:
            vargottama.append(p)

    # Karakas
    karaka_planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    sorted_karakas = sorted(karaka_planets, key=lambda p: chart_data[p]["degree_in_sign"], reverse=True)
    labels = ["Atmakaraka (AK)", "Amatyakaraka (AmK)", "Bhratrikaraka (BK)",
              "Matrikaraka (MK)", "Putrakaraka (PK)", "Gnatikaraka (GK)", "Darakaraka (DK)"]
    karakas = {labels[i]: sorted_karakas[i] for i in range(len(sorted_karakas))}

    # Ashtakavarga & Bhava Bala
    av_input = {p: chart_data[p]["sign_idx"] + 1 for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]}
    av_input["Ascendant"] = asc_sign_idx + 1
    ashtakavarga = calculate_ashtakavarga(av_input)
    sav = ashtakavarga.get("SAV", {})

    bb_data = compute_bhava_bala(chart_data, jd, lat, lon, flags)

    # Dashas
    moon_deg = chart_data["Moon"]["degree_total"]
    now_utc = datetime.now(pytz.UTC)
    dasha_data = calculate_vimshottari_dasha(moon_deg, utc_dt, now_utc)
    current_mahadasha = dasha_data.get("md", "")
    current_antardasha = dasha_data.get("ad", "")
    current_pd = dasha_data.get("current_pd", "")

    # Yogas
    detected_yogas = detect_yogas(chart_data, asc_sign_idx)
    yoga_activation = check_yoga_activation(detected_yogas, dasha_data)

    # Moon Details & Deity
    sun_deg = chart_data["Sun"]["degree_total"]
    moon_details = calculate_moon_details(chart_data["Moon"]["degree_total"], sun_deg)
    nak_deity = get_nakshatra_archetype(chart_data["Moon"]["nakshatra"])

    # Live Planetary Transits (Gochar - Today)
    jd_now = swe.julday(
        now_utc.year, now_utc.month, now_utc.day,
        now_utc.hour + now_utc.minute / 60.0 + now_utc.second / 3600.0
    )
    transit_data = {}
    for planet_id, planet_name in PLANETS.items():
        pos_now, _ = swe.calc_ut(jd_now, planet_id, flags)
        deg_now = pos_now[0] % 360
        speed_now = pos_now[3]
        status_now = "Rx" if speed_now < 0 and planet_id not in [swe.SUN, swe.MOON] else "Dir"
        if planet_id == swe.TRUE_NODE:
            status_now = "Rx"
        sign_now_idx = int(deg_now / 30) % 12
        nak_now, lord_now, pada_now = get_nakshatra(deg_now)

        h_asc = get_house_from_sign_idx(asc_sign_idx, sign_now_idx)
        h_moon = get_house_from_sign_idx(chart_data["Moon"]["sign_idx"], sign_now_idx)
        sav_pts = sav.get(sign_now_idx + 1, 28)

        transit_data[planet_name] = {
            "sign": RASHI_NAMES[sign_now_idx],
            "sign_idx": sign_now_idx,
            "degree_total": deg_now,
            "degree_in_sign": deg_now % 30,
            "speed": speed_now,
            "status": status_now,
            "dignity": get_dignity(planet_name, RASHI_NAMES[sign_now_idx]),
            "nakshatra": nak_now,
            "nakshatra_lord": lord_now,
            "pada": pada_now,
            "house_from_asc": h_asc,
            "house_from_moon": h_moon,
            "sav": sav_pts
        }

    # Transit Ketu
    rahu_t_deg = transit_data["Rahu"]["degree_total"]
    ketu_t_deg = (rahu_t_deg + 180) % 360
    ketu_t_sign_idx = int(ketu_t_deg / 30) % 12
    k_nak_now, k_lord_now, k_pada_now = get_nakshatra(ketu_t_deg)
    transit_data["Ketu"] = {
        "sign": RASHI_NAMES[ketu_t_sign_idx],
        "sign_idx": ketu_t_sign_idx,
        "degree_total": ketu_t_deg,
        "degree_in_sign": ketu_t_deg % 30,
        "speed": -1.0,
        "status": "Rx",
        "dignity": "-",
        "nakshatra": k_nak_now,
        "nakshatra_lord": k_lord_now,
        "pada": k_pada_now,
        "house_from_asc": get_house_from_sign_idx(asc_sign_idx, ketu_t_sign_idx),
        "house_from_moon": get_house_from_sign_idx(chart_data["Moon"]["sign_idx"], ketu_t_sign_idx),
        "sav": sav.get(ketu_t_sign_idx + 1, 28)
    }

    # Check Transit Combustion against Live Transit Sun
    sun_t_deg = transit_data["Sun"]["degree_total"]
    for p in ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        dist = abs(sun_t_deg - transit_data[p]["degree_total"])
        if dist > 180.0:
            dist = 360.0 - dist
        transit_data[p]["sun_dist"] = dist
        is_comb = (get_combustion_status(p, transit_data) == "Combust")
        transit_data[p]["combustion"] = is_comb
        limits = COMBUSTION_LIMITS.get(p, {})
        transit_data[p]["comb_limit"] = limits.get("rx") if transit_data[p]["status"] == "Rx" else limits.get("direct")

    # Lagna Functional Profile
    lagna_profile = get_lagna_functional_profile(asc_sign_idx)

    # Parashari Aspects & Manglik & Gandanta
    aspects_info = compute_aspects_and_special(chart_data, asc_sign_idx)

    # 9-Antardasha Sequence roadmap
    dasha_roadmap = compute_antardasha_sequence(moon_deg, utc_dt, now_utc)

    # Shani Gochar & Sade Sati
    moon_nak_len = 360.0 / 27.0
    natal_moon_nak_idx = min(int((chart_data["Moon"]["degree_total"] % 360.0) / moon_nak_len), 26)
    moon_gochar = calculate_moon_gochar(
        chart_data=chart_data,
        transit_data=transit_data,
        moon_sign_idx=chart_data["Moon"]["sign_idx"],
        natal_moon_nak_idx=natal_moon_nak_idx,
        today_moon_deg=transit_data["Moon"]["degree_total"],
        sav=sav
    )

    # Master Vedic Doshas (Kaal Sarp, Manglik, Pitra)
    doshas_data = calculate_doshas(chart_data, birth_dt=utc_dt)

    return {
        "name": name,
        "dob": dob.strftime("%d %B %Y (%Y-%m-%d)"),
        "time": f"{tob.strftime('%H:%M')} (24-hr) / {tob.strftime('%I:%M %p').lstrip('0')}",
        "city": loc.address,
        "lat": lat,
        "lon": lon,
        "tz": tz_name,
        "chart_data": chart_data,
        "d9_data": d9_data,
        "vargottama": vargottama,
        "karakas": karakas,
        "sav": sav,
        "bb_data": bb_data,
        "current_mahadasha": current_mahadasha,
        "current_antardasha": current_antardasha,
        "current_pd": current_pd,
        "dasha_data": dasha_data,
        "dasha_roadmap": dasha_roadmap,
        "lagna_profile": lagna_profile,
        "aspects_info": aspects_info,
        "doshas_data": doshas_data,
        "moon_gochar": moon_gochar,
        "yogas": yoga_activation,
        "moon_details": moon_details,
        "nak_deity": nak_deity,
        "transit_data": transit_data,
        "transit_date": now_utc.strftime("%d %B %Y, %H:%M UTC")
    }

def format_chart_report(c: dict) -> str:
    lines = []
    def p(text=""):
        lines.append(text)

    cd = c["chart_data"]
    asc = cd["Ascendant"]
    moon = cd["Moon"]
    sun = cd["Sun"]
    lp = c["lagna_profile"]
    dd = c["dasha_data"]
    rm = c["dasha_roadmap"]
    asp = c["aspects_info"]
    mg = c["moon_gochar"]
    bb = c["bb_data"]
    shad = bb.get("planets_shadbala", {})

    p("=" * 90)
    p(f" ✨ VEDIC ASTROLOGY PRIVATE CONSULTATION REPORT: {c['name'].upper()} ✨ ")
    p("=" * 90)
    p(f" Birth Date   : {c['dob']} | Time: {c['time']}")
    p(f" Location     : {c['city']}")
    p(f" Coordinates  : {c['lat']:.4f}°, {c['lon']:.4f}° | Timezone: {c['tz']}")
    p("-" * 90)
    p(f" 🕉️  Ascendant (Lagna) : {asc['sign']} ({asc['degree_in_sign']:.2f}°) — {asc['nakshatra']} (Pada {asc['pada']})")
    p(f" 🌙 Moon Sign (Rasi)   : {moon['sign']} ({moon['degree_in_sign']:.2f}°) — {moon['nakshatra']} (Pada {moon['pada']})")
    p(f" ☀️  Sun Sign           : {sun['sign']} ({sun['degree_in_sign']:.2f}°) — {sun['nakshatra']} (Pada {sun['pada']})")
    p(f" ⚡ Janma Deity Archetype: {c['nak_deity']['deity']} ({c['nak_deity'].get('title', '')})")
    p(f" 👑 Atmakaraka (Soul)  : {c['karakas'].get('Atmakaraka (AK)', 'Sun')} | Amatyakaraka: {c['karakas'].get('Amatyakaraka (AmK)', 'Mercury')}")
    p("-" * 90)
    p(" 🏛️  LAGNA FUNCTIONAL PROFILE (PARASHARI):")
    p(f"   • Lagna Lord         : {lp['lagna_lord']}")
    p(f"   • Yogakaraka Planet  : {lp['yogakaraka']}")
    p(f"   • Functional Benefics: {lp['functional_benefics']}")
    p(f"   • Functional Malefics: {lp['functional_malefics']}")
    p(f"   • Maraka Lords       : {lp['marakas']}")
    p(f"   • Badhaka Point      : {lp['badhaka']}")
    p("-" * 90)
    p(" ⏳ ACTIVE VIMSHOTTARI DASHA CYCLE:")
    p(f"   • Mahadasha : {dd.get('md')} (Ends: {dd.get('md_end')} | {dd.get('md_remaining_days', 0):,} days remaining)")
    p(f"   • Antardasha: {dd.get('ad')} (Ends: {dd.get('ad_end')} | {dd.get('ad_remaining_days', 0):,} days remaining)")
    p(f"   • Pratyantar: {dd.get('current_pd')} (Ends: {dd.get('pd_end')} | {dd.get('pd_remaining_days', 0):,} days remaining)")
    p(f"   • Next Shift: {dd.get('ad_next')} Antardasha begins {dd.get('ad_end')}")
    p("-" * 90)

    # [1] D1 Natal Planetary Positions
    p("\n[1] D1 NATAL PLANETARY POSITIONS (Rasi Chart)")
    p("-" * 90)
    p(f"{'Planet':<14} | {'Sign':<12} | {'House':<5} | {'Degree':<8} | {'Nakshatra':<14} | {'Dignity':<11} | {'Combustion':<14}")
    p("-" * 90)
    for planet_name in ["Ascendant", "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]:
        pdata = cd[planet_name]
        rx = pdata.get("status", "Dir")
        display_name = f"{planet_name} (Rx)" if rx == "Rx" and planet_name not in ["Ascendant", "Sun"] else planet_name

        if planet_name in ["Ascendant", "Sun", "Rahu", "Ketu"]:
            comb_str = "-"
        elif pdata.get("combustion"):
            comb_str = f"🔥 COMBUST ({pdata['sun_dist']:.1f}°)"
        else:
            comb_str = f"Safe ({pdata.get('sun_dist', 0.0):.1f}°)"

        p(f"{display_name:<14} | {pdata['sign']:<12} | H{pdata['house']:<4} | {pdata['degree_in_sign']:>5.2f}°  | {pdata['nakshatra'][:11]+' P'+str(pdata['pada']):<14} | {pdata.get('dignity','-'):<11} | {comb_str:<14}")
    p("-" * 90)

    # Natal Alerts
    natal_comb = [f"{p} ({cd[p]['sun_dist']:.1f}° from Sun < {cd[p]['comb_limit']}°)" for p in ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"] if cd[p].get("combustion")]
    natal_rx = [f"{p} (Rx in {cd[p]['sign']}, House {cd[p]['house']})" for p in ["Mars", "Mercury", "Jupiter", "Venus", "Saturn"] if cd[p].get("status") == "Rx"]
    warring = bb.get("warring_pairs", [])

    if natal_comb:
        p(f"🔥 Natal Combust (Astangata) : {', '.join(natal_comb)}")
    else:
        p("✨ Natal Combust (Astangata) : None (All planetary rays unobstructed)")

    if natal_rx:
        p(f"🔄 Natal Retrograde (Vakra)  : {', '.join(natal_rx)} [High Chesta Bala]")
    else:
        p("✨ Natal Retrograde (Vakra)  : None (All true planets moving direct)")

    v_str = ", ".join(c["vargottama"]) if c["vargottama"] else "None"
    p(f"🌟 Vargottama (D1 = D9)      : {v_str}")

    if asp["gandanta"]:
        p(f"⚠️  Gandanta Points Detected  : {', '.join(asp['gandanta'])}")
    else:
        p("✨ Gandanta Check            : None (No planets at water-fire junctions)")

    if warring:
        war_str = ", ".join([f"{w[0]} vs {w[1]} ({w[2]}° separation)" for w in warring])
        p(f"⚔️  Graha Yuddha (War)        : {war_str}")
    else:
        p("✨ Graha Yuddha (War)        : None (No planets locked within 1°)")

    # [2] D9 Navamsa Table (Matching D1 Structure)
    p("\n[2] D9 NAVAMSA PLANETARY POSITIONS (Navamsa Chart — Marriage, Dharma & Soul Potential)")
    p("-" * 90)
    p(f"{'Planet':<14} | {'D9 Sign':<14} | {'D9 House':<9} | {'D9 Dignity':<14} | {'Vargottama (D1=D9)':<18}")
    p("-" * 90)
    d9_planets = ["Ascendant", "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
    d9_house_map = {h: [] for h in range(1, 13)}
    for pl in d9_planets:
        d9_pinfo = c["d9_data"].get(pl, {})
        d9_sign = d9_pinfo.get("sign", "-")
        d9_h = f"H{d9_pinfo.get('house', 1)}"
        d9_dig = d9_pinfo.get("dignity", "-")
        is_vg = "🌟 Vargottama" if pl in c["vargottama"] else "-"
        p_disp = f"{pl} (Rx)" if (pl in cd and cd[pl].get("status") == "Rx") else pl
        p(f"{p_disp:<14} | {d9_sign:<14} | {d9_h:<9} | {d9_dig:<14} | {is_vg:<18}")
        if pl != "Ascendant":
            d9_house_map[d9_pinfo.get("house", 1)].append(p_disp)
    p("-" * 90)
    d9_asc_sidx = c["d9_data"]["Ascendant"]["sign_idx"]
    d9_h7_sidx = (d9_asc_sidx + 6) % 12
    d9_h7_sign = RASHI_NAMES[d9_h7_sidx]
    d9_h7_lord = SIGN_LORDS[d9_h7_sidx]
    h1_occ = ", ".join(d9_house_map[1]) if d9_house_map[1] else "Empty"
    h7_occ = ", ".join(d9_house_map[7]) if d9_house_map[7] else "Empty"
    h12_occ = ", ".join(d9_house_map[12]) if d9_house_map[12] else "Empty"
    p(f"💍 D9 Marriage Axis  : Lagna H1 ({c['d9_data']['Ascendant']['sign']}) ⇄ 7th House H7 ({d9_h7_sign}, Lord: {d9_h7_lord})")
    p(f"   • Planets in D9 Lagna (H1)      : {h1_occ}")
    p(f"   • Planets in D9 7th House (H7)  : {h7_occ}")
    if h12_occ != "Empty":
        p(f"   • Planets in D9 12th House (H12): {h12_occ}")

    # [3] Jaimini Karakas
    p("\n[3] JAIMINI 7 CHARA KARAKAS (Soul Agenda)")
    p("-" * 90)
    for k_title, k_planet in c["karakas"].items():
        p(f"  {k_title:<24} : {k_planet:<9} ({cd[k_planet]['degree_in_sign']:.2f}° in {cd[k_planet]['sign']})")

    # [4] 7 Planetary Shadbala Strengths & Rank
    p("\n[4] 7 PLANETARY SHADBALA STRENGTHS (Parashari Power Ranking)")
    p("-" * 90)
    p(f"{'Rank':<5} | {'Planet':<14} | {'Rupas':<7} | {'Virupas':<9} | {'Req Min':<9} | {'% of Req':<9} | {'Strength Status':<18}")
    p("-" * 90)
    sorted_shad = sorted(shad.items(), key=lambda x: x[1]["rupas"], reverse=True)
    for rank, (p_name, sdata) in enumerate(sorted_shad, start=1):
        rx = cd[p_name].get("status", "Dir")
        p_disp = f"{p_name} (Rx)" if rx == "Rx" else p_name
        pct = sdata["pct_of_required"]
        if pct >= 125.0:
            status_tag = "🔥 Very Strong"
        elif pct >= 100.0:
            status_tag = "✅ Strong"
        elif pct >= 85.0:
            status_tag = "⚠️ Moderate"
        else:
            status_tag = "❌ Deficit"
        p(f"#{rank:<4} | {p_disp:<14} | {sdata['rupas']:>5.2f}  | {sdata['total']:>7.1f}   | {sdata['required_min']:>7.0f}   | {pct:>6.1f}%  | {status_tag:<18}")
    p("-" * 90)
    if sorted_shad:
        p(f"👑 Chart Anchor / Strongest Planet : {sorted_shad[0][0]} ({sorted_shad[0][1]['pct_of_required']:.1f}%)")
        p(f"⚠️ Most Challenged Planet in Bala  : {sorted_shad[-1][0]} ({sorted_shad[-1][1]['pct_of_required']:.1f}%)")

    # [5] Parashari Aspects & Manglik
    p("\n[5] PARASHARI DRISHTIS (ASPECTS) & MANGLIK ANALYSIS")
    p("-" * 90)
    for p_name in ["Mars", "Jupiter", "Saturn", "Rahu", "Ketu"]:
        ainfo = asp["aspects"][p_name]
        h_str = ", ".join([f"H{h}" for h in ainfo["houses"]])
        t_str = ", ".join(ainfo["targets"]) if ainfo["targets"] else "None (Open Houses)"
        p(f"  • {p_name:<7} Aspects Houses: {h_str:<15} | Targets: {t_str}")
    p("-" * 90)
    # Master Dosha Analysis
    doshas = c.get("doshas_data", {})
    m_data = doshas.get("manglik", {})
    ks_data = doshas.get("kalsarpa", {})
    p_data = doshas.get("pitra_dosha", {})

    p("  💍 Kuja Dosha (Manglik) Check:")
    p(f"     • Severity Score : {m_data.get('severity_score', 0)}/100 [{m_data.get('severity', 'None')}]")
    p(f"     • From Lagna     : {'YES (H' + str(m_data.get('mars_positions', {}).get('house_from_lagna')) + ')' if m_data.get('reference_afflictions', {}).get('lagna') else 'No'}")
    p(f"     • From Moon      : {'YES (H' + str(m_data.get('mars_positions', {}).get('house_from_moon')) + ')' if m_data.get('reference_afflictions', {}).get('moon') else 'No'}")
    p(f"     • From Venus     : {'YES (H' + str(m_data.get('mars_positions', {}).get('house_from_venus')) + ')' if m_data.get('reference_afflictions', {}).get('venus') else 'No'}")
    if m_data.get("cancellations"):
        for cancel in m_data["cancellations"]:
            p(f"     • Cancellation   : {cancel}")
    if m_data.get("mitigations"):
        for mit in m_data["mitigations"]:
            p(f"     • Mitigation     : {mit}")

    p("\n  🐍 Kaal Sarp Dosha Check:")
    if ks_data.get("is_present"):
        p(f"     • Status         : PRESENT [{ks_data.get('classification')}]")
        p(f"     • Nodal Type     : {ks_data.get('type_name')} (Rahu H{ks_data.get('rahu_house')}, Ketu H{ks_data.get('ketu_house')})")
        p(f"     • Direction      : {ks_data.get('direction')}")
        if ks_data.get("escaped_planet"):
            p(f"     • Note           : Modern Anshik (escaped: {ks_data['escaped_planet']})")
    else:
        p("     • Status         : NONE (Planets dispersed across nodal axis)")

    p("\n  🌿 Pitra Dosha (Ancestral Debt) Check:")
    if p_data.get("is_present"):
        p(f"     • Status         : PRESENT [{p_data.get('severity')}] — Score: {p_data.get('severity_score')}/100")
        for aff in p_data.get("affliction_factors", []):
            p(f"     • Affliction     : {aff}")
    else:
        p(f"     • Status         : NONE [Score: {p_data.get('severity_score', 0)}/100]")

    # [6] House Power
    p("\n[6] HOUSE POWER (BHAVA BALA & SAMUDAYA ASHTAKAVARGA)")
    p("-" * 90)
    p(f"{'House':<6} | {'Sign':<12} | {'Lord':<9} | {'SAV Points':<12} | {'Bhava Bala Strength':<25}")
    p("-" * 90)
    bb_houses = bb.get("houses", {})
    asc_idx = cd["Ascendant"]["sign_idx"]
    for h in range(1, 13):
        r_idx = (asc_idx + h - 1) % 12
        r_name = RASHI_NAMES[r_idx]
        sav_pts = c["sav"].get(r_idx + 1, 28)
        h_data = bb_houses.get(h, {})
        h_lord = h_data.get("lord", "-")
        rupas = h_data.get("rupas", 0.0)
        strength = h_data.get("strength", "Medium")
        sav_tag = "Strong" if sav_pts >= 28 else ("Average" if sav_pts >= 25 else "Weak")
        p(f"H{h:<5} | {r_name:<12} | {h_lord:<9} | {sav_pts:>2} pts ({sav_tag:<7}) | {rupas:>5.2f} Rupas [{strength}]")

    # [7] Dasha Roadmap
    p(f"\n[7] VIMSHOTTARI DASHA ROADMAP (Mahadasha: {rm['md_name']})")
    p("-" * 90)
    p(f"Active Cycle : {dd.get('md')} MD -> {dd.get('ad')} AD -> {dd.get('current_pd')} PD")
    p(f"{'Sub-Period (AD)':<18} | {'Start Date':<13} | {'End Date':<13} | {'Duration':<10} | {'Status'}")
    p("-" * 90)
    for ad in rm["ad_sequence"]:
        dur_str = f"{ad['duration_years']:.2f} yrs"
        if ad["is_active"]:
            status_str = f"🟢 ACTIVE NOW ({ad['days_left']} days left)"
        elif ad["is_past"]:
            status_str = "Completed"
        else:
            status_str = "Upcoming"
        p(f"{ad['planet']+' Antardasha':<18} | {ad['start']:<13} | {ad['end']:<13} | {dur_str:<10} | {status_str}")

    # [8] Yogas
    p("\n[8] ACTIVE CLASSICAL YOGAS")
    p("-" * 90)
    active_yogas = [y for y in c["yogas"] if y.get("active")]
    if active_yogas:
        for y in active_yogas:
            planets_str = ", ".join(y.get("planets", [])) if isinstance(y.get("planets"), list) else str(y.get("planets"))
            p(f"  🟢 {y['name']} ({y['category']})")
            p(f"     Planets: {planets_str} | Life Promise: {y['desc']}")
            p(f"     Timing: {y['timing']}")
    else:
        p("  No major active Raja/Dhana yogas in the current Dasha cycle.")

    # [9] Live Transits & Sade Sati
    p(f"\n[9] TODAY'S LIVE TRANSITS (GOCHAR) & SADE SATI REPORT — {c.get('transit_date', 'LIVE')}")
    p("-" * 90)
    p(" 🪐 SHANI GOCHAR & SADE SATI REPORT:")
    p(f"    • Phase  : {mg['shani_phase']}")
    p(f"    • Insight: {mg['shani_desc']}")
    p(" 🌟 GURU GOCHAR (JUPITER FROM MOON):")
    p(f"    • Phase  : {mg['guru_status']}")
    p(f"    • Insight: {mg['guru_desc']}")
    if mg.get("tara_bala"):
        tb = mg["tara_bala"]
        p(f" 🌙 DAILY MOON TARA BALA: {tb.get('tara_name')} ({tb.get('transit_moon_nakshatra')}) — {tb.get('tara_desc')}")
    p("-" * 90)
    p(f"{'Planet':<14} | {'Transiting':<12} | {'Deg':<8} | {'H(Lagna)':<8} | {'H(Moon)':<8} | {'SAV Pts':<10} | {'Combustion':<14}")
    p("-" * 90)
    td = c["transit_data"]
    for p_name in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]:
        tp = td[p_name]
        rx = tp.get("status", "Dir")
        display_name = f"{p_name} (Rx)" if rx == "Rx" and p_name not in ["Sun", "Moon"] else p_name

        if p_name in ["Sun", "Rahu", "Ketu"]:
            comb_str = "-"
        elif tp.get("combustion"):
            comb_str = f"🔥 COMBUST ({tp['sun_dist']:.1f}°)"
        else:
            comb_str = f"Safe ({tp.get('sun_dist', 0.0):.1f}°)"

        sav_label = "Str" if tp['sav'] >= 28 else ("Avg" if tp['sav'] >= 25 else "Low")
        sav_display = f"{tp['sav']} ({sav_label})"
        p(f"{display_name:<14} | {tp['sign']:<12} | {tp['degree_in_sign']:>5.2f}°  | H{tp['house_from_asc']:<7} | H{tp['house_from_moon']:<7} | {sav_display:<10} | {comb_str:<14}")

    p("-" * 90)
    t_comb = [f"{p} ({td[p]['sun_dist']:.1f}° from Sun < {td[p]['comb_limit']}°)" for p in ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"] if td[p].get("combustion")]
    t_rx = [f"{p} (Rx in {td[p]['sign']})" for p in ["Mars", "Mercury", "Jupiter", "Venus", "Saturn"] if td[p].get("status") == "Rx"]

    if t_comb:
        p(f"🔥 Live Transit Combust Alert: {', '.join(t_comb)} are currently COMBUST in the sky!")
    else:
        p("✨ Live Transit Combustion   : None (All visible transit planets free from combustion)")

    if t_rx:
        p(f"🔄 Live Transit Retrograde   : {', '.join(t_rx)} are currently RETROGRADE in the sky!")
    else:
        p("✨ Live Transit Retrograde   : None (Only Rahu/Ketu in natural retrograde)")

    if mg.get("transit_on_natal_conjunctions"):
        p("⚡ Transit-on-Natal Conjunctions:")
        for c_str in mg["transit_on_natal_conjunctions"]:
            p(f"    • {c_str}")

    p("=" * 90 + "\n")
    return "\n".join(lines)

def print_chart_summary(c: dict) -> str:
    report = format_chart_report(c)
    print(report)
    return report

def save_report_to_file(chart: dict, report_text: str):
    clean_name = "".join(ch for ch in chart["name"] if ch.isalnum() or ch in (" ", "_")).strip().replace(" ", "_")
    folder = "client_readings"
    os.makedirs(folder, exist_ok=True)
    dob_slug = chart["dob"].split(" ")[-1].replace("(", "").replace(")", "")
    filename = os.path.join(folder, f"{clean_name}_{dob_slug}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"💾 Report saved successfully to: {filename}\n")

def parse_quick_paste(text: str):
    text = text.strip()
    if not text:
        return None
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) > 1:
        data = {}
        for l in lines:
            for sep in [":", "-"]:
                if sep in l:
                    k, v = l.split(sep, 1)
                    k_clean = k.strip().lower()
                    v_clean = v.strip()
                    if any(x in k_clean for x in ["name", "client"]):
                        data["name"] = v_clean
                    elif any(x in k_clean for x in ["dob", "date", "birth date"]):
                        data["dob"] = v_clean
                    elif any(x in k_clean for x in ["time", "tob"]):
                        data["time"] = v_clean
                    elif any(x in k_clean for x in ["city", "place", "location"]):
                        data["city"] = v_clean
                    break
        if "dob" in data and "time" in data and "city" in data:
            return data.get("name", "Client"), data["dob"], data["time"], data["city"], "India"

    for d in [",", "|"]:
        if text.count(d) >= 3:
            parts = [p.strip() for p in text.split(d)]
            if len(parts) >= 4:
                return parts[0], parts[1], parts[2], parts[3], (parts[4] if len(parts) > 4 else "India")
    return None

def run_single_chart(name: str, dob: str, tob: str, city: str, country: str):
    try:
        print("\n⚙️  Calculating Swiss Ephemeris chart & divisional positions...")
        chart = calculate_chart(name, dob, tob, city, country)
        report = print_chart_summary(chart)
        save_opt = input("💾 Save this client report to file? [y/N]: ").strip().lower()
        if save_opt in ["y", "yes"]:
            save_report_to_file(chart, report)
    except Exception as e:
        print(f"\n❌ Error: {e}\n")

def main():
    parser = argparse.ArgumentParser(description="Vedic Astrology Private Chart Inspector")
    parser.add_argument("--name", default="Client", help="Client Name")
    parser.add_argument("--dob", help="Date of birth (e.g. 15/06/1994 or 1994-06-15)")
    parser.add_argument("--time", help="Time of birth (e.g. '12:05 PM' or '00:05')")
    parser.add_argument("--city", help="City of birth")
    parser.add_argument("--country", default="India", help="Country of birth (default: India)")

    args = parser.parse_args()

    # If flags were provided in command line, run once and exit
    if args.dob and args.time and args.city:
        run_single_chart(args.name, args.dob, args.time, args.city, args.country)
        return

    # Interactive Consultation Loop
    print("\n" + "=" * 76)
    print("        ✨ VEDIC ASTROLOGY PRIVATE CONSULTATION ENGINE ✨")
    print("=" * 76)

    while True:
        print("\n📌 OPTIONS:")
        print("  • Paste all in 1 line: Name, DOB, Time, City (e.g. Rahul, 15/06/1994, 12:05 PM, Mumbai)")
        print("  • OR press [Enter] to fill step-by-step")
        print("  • Type 'q' to exit")
        print("-" * 76)
        
        try:
            entry = input("Paste details OR press Enter for step-by-step: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting session. Namaste!")
            break

        if entry.lower() in ["q", "exit", "quit"]:
            print("Session ended. Namaste!")
            break

        parsed = parse_quick_paste(entry)
        if parsed:
            name, dob, tob, city, country = parsed
            print(f"\n✅ Recognized: {name} | DOB: {dob} | Time: {tob} | City: {city}")
        else:
            try:
                name = input("  1. Client Name           : ").strip() or "Client"
                dob = input("  2. Date of Birth         : ").strip()
                tob = input("  3. Time of Birth         : ").strip()
                city = input("  4. City of Birth         : ").strip()
                country = input("  5. Country [default India]: ").strip() or "India"
            except (KeyboardInterrupt, EOFError):
                print("\nExiting session. Namaste!")
                break

        if not dob or not tob or not city:
            print("⚠️  Missing required details (DOB, Time, and City are needed). Please try again.")
            continue

        run_single_chart(name, dob, tob, city, country)

        try:
            nxt = input("Press [Enter] to inspect another chart (or 'q' to quit): ").strip()
            if nxt.lower() in ["q", "exit", "quit"]:
                print("Session ended. Namaste!")
                break
        except (KeyboardInterrupt, EOFError):
            print("\nExiting session. Namaste!")
            break

if __name__ == "__main__":
    main()

from datetime import datetime, timedelta
import swisseph as swe

# ==========================================
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


def calculate_vimshottari_dasha(moon_degree, birth_dt, target_dt):
    """
    Returns a dict with current MD/AD, their mathematically derived date ranges,
    next periods, and remaining days so the AI never invents timing.
    """
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

    days_per_year = 365.2425
    days_passed = (target_dt - birth_dt).total_seconds() / 86400.0
    years_passed = days_passed / days_per_year

    # --- Locate Current Mahadasha ---
    md_idx = lord_idx

    if years_passed < balance_years:
        current_md = first_lord
        md_start_years = 0.0
        md_end_years = balance_years
        years_into_md = years_passed
        md_duration = balance_years          # FIXED: first period is balance only
    else:
        accumulated = balance_years
        md_idx = (lord_idx + 1) % 9
        for _ in range(20):  # covers 240+ years
            md_name, md_duration_full = DASHA_SEQ[md_idx]
            if accumulated + md_duration_full > years_passed:
                current_md = md_name
                md_start_years = accumulated
                md_end_years = accumulated + md_duration_full
                years_into_md = years_passed - accumulated
                md_duration = md_duration_full
                break
            accumulated += md_duration_full
            md_idx = (md_idx + 1) % 9
        else:
            current_md = DASHA_SEQ[md_idx][0]
            md_start_years = accumulated
            md_end_years = accumulated + DASHA_SEQ[md_idx][1]
            years_into_md = 0.0
            md_duration = DASHA_SEQ[md_idx][1]

    # --- Locate Current Antardasha ---
    ad_idx = md_idx
    ad_accumulated = 0.0
    current_ad = None
    ad_start_in_md = 0.0
    ad_end_in_md = 0.0

    for _ in range(20):
        ad_name, ad_years_total = DASHA_SEQ[ad_idx]
        ad_duration = (md_duration * ad_years_total) / 120.0
        if ad_accumulated + ad_duration > years_into_md:
            current_ad = ad_name
            ad_start_in_md = ad_accumulated
            ad_end_in_md = ad_accumulated + ad_duration
            break
        ad_accumulated += ad_duration
        ad_idx = (ad_idx + 1) % 9
    else:
        current_ad = DASHA_SEQ[ad_idx][0]
        ad_start_in_md = ad_accumulated
        ad_end_in_md = ad_accumulated + (md_duration * DASHA_SEQ[ad_idx][1]) / 120.0

    # --- Derive wall-clock dates ---
    md_start_dt = birth_dt + timedelta(days=md_start_years * days_per_year)
    md_end_dt = birth_dt + timedelta(days=md_end_years * days_per_year)
    ad_start_dt = md_start_dt + timedelta(days=ad_start_in_md * days_per_year)
    ad_end_dt = md_start_dt + timedelta(days=ad_end_in_md * days_per_year)

    # --- Next periods ---
    next_md_idx = (md_idx + 1) % 9
    next_md = DASHA_SEQ[next_md_idx][0]

    if ad_end_in_md >= md_duration - 1e-9:
        next_ad = next_md
    else:
        next_ad_idx = (ad_idx + 1) % 9
        next_ad = DASHA_SEQ[next_ad_idx][0]

    def fmt(dt):
        return dt.strftime("%d %b %Y")

    return {
        "md": current_md,
        "ad": current_ad,
        "md_start": fmt(md_start_dt),
        "md_end": fmt(md_end_dt),
        "md_remaining_days": max(0, int((md_end_dt - target_dt).days)),
        "ad_start": fmt(ad_start_dt),
        "ad_end": fmt(ad_end_dt),
        "ad_remaining_days": max(0, int((ad_end_dt - target_dt).days)),
        "md_next": next_md,
        "ad_next": next_ad,
    }


def find_next_ingress(jd_start, planet_id, flags, start_dt_utc, rashi_names, max_days=365 * 5):
    """Returns (new_sign_name, date_string, datetime_obj) for next sign change."""
    pos, _ = swe.calc_ut(jd_start, planet_id, flags)
    start_sign = int(pos[0] % 360 / 30)

    for day_offset in range(1, max_days + 1):
        jd_test = jd_start + day_offset
        pos_test, _ = swe.calc_ut(jd_test, planet_id, flags)
        test_sign = int(pos_test[0] % 360 / 30)
        if test_sign != start_sign:
            ingress_dt = start_dt_utc + timedelta(days=day_offset)
            return rashi_names[test_sign], ingress_dt.strftime("%d %b %Y"), ingress_dt
    return None, None, None


def find_next_station(jd_start, planet_id, flags, start_dt_utc, max_days=365 * 3):
    """
    Returns (station_type, date_string, datetime_obj).
    station_type = 'Retrograde' or 'Direct'
    """
    pos, _ = swe.calc_ut(jd_start, planet_id, flags)
    prev_speed = pos[3]

    for day_offset in range(1, max_days + 1):
        jd_test = jd_start + day_offset
        pos_test, _ = swe.calc_ut(jd_test, planet_id, flags)
        speed = pos_test[3]

        if prev_speed != 0 and (prev_speed * speed < 0):
            station_dt = start_dt_utc + timedelta(days=day_offset)
            st_type = "Retrograde" if speed < 0 else "Direct"
            return st_type, station_dt.strftime("%d %b %Y"), station_dt

        prev_speed = speed

    return None, None, None


def detect_yogas(chart_data, asc_sign_idx):
    yogas = []

    def house_of(p):
        return chart_data[p]["house"]

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

    # 1. Pancha Mahapurusha
    mahapurusha = {
        "Mars": "Ruchaka", "Mercury": "Bhadra", "Jupiter": "Hamsa",
        "Venus": "Malavya", "Saturn": "Sasa"
    }
    for planet, yoga_name in mahapurusha.items():
        if planet in chart_data:
            dignity = chart_data[planet].get("dignity")
            if house_of(planet) in KENDRAS and dignity in ["Exalted", "Own Sign"]:
                strength = 95 if dignity == "Exalted" else 85
                yogas.append({
                    "name": f"{yoga_name} Yoga (Pancha Mahapurusha)",
                    "strength": strength,
                    "planets": [planet],
                    "desc": f"{planet} is {dignity} in a Kendra (House {house_of(planet)}), forming this powerful Mahapurusha yoga. Grants leadership, fame, and strong character."
                })

    # 2. Gajakesari
    if "Jupiter" in chart_data and "Moon" in chart_data:
        moon_sign = chart_data["Moon"]["sign_idx"]
        jup_sign = chart_data["Jupiter"]["sign_idx"]
        rel_house = (jup_sign - moon_sign) % 12 + 1
        if rel_house in KENDRAS:
            yogas.append({
                "name": "Gajakesari Yoga",
                "strength": 80,
                "planets": ["Jupiter", "Moon"],
                "desc": "Jupiter is in a Kendra from the Moon. Grants intelligence, respect, wealth, and good reputation."
            })

    # 3. Budhaditya
    if "Sun" in chart_data and "Mercury" in chart_data:
        if house_of("Sun") == house_of("Mercury"):
            yogas.append({
                "name": "Budhaditya Yoga",
                "strength": 70,
                "planets": ["Sun", "Mercury"],
                "desc": "Sun and Mercury conjoin, granting intelligence, communication skills, and analytical ability."
            })

    # 4. Dhana Yoga
    lord2 = lord_of_house(2)
    lord11 = lord_of_house(11)
    if lord2 in chart_data and lord11 in chart_data:
        if house_of(lord2) == house_of(lord11):
            yogas.append({
                "name": "Dhana Yoga",
                "strength": 75,
                "planets": list(set([lord2, lord11])),
                "desc": "Lords of wealth houses (2nd & 11th) connect, indicating strong financial potential."
            })

    # 5. Raja Yoga (Kendra-Trikona conjunction)
    kendra_lords = set(lord_of_house(h) for h in KENDRAS)
    trikona_lords = set(lord_of_house(h) for h in TRIKONAS)
    raja_pairs = []
    for kl in kendra_lords:
        for tl in trikona_lords:
            if kl != tl and kl in chart_data and tl in chart_data:
                if house_of(kl) == house_of(tl):
                    pair = tuple(sorted([kl, tl]))
                    if pair not in raja_pairs:
                        raja_pairs.append(pair)
                        yogas.append({
                            "name": "Raja Yoga",
                            "strength": 88,
                            "planets": list(pair),
                            "desc": f"{kl} (Kendra lord) and {tl} (Trikona lord) connect, forming a power/success yoga indicating authority and rise in status."
                        })

    # 6. Neecha Bhanga
    for p in chart_data:
        if p == "Ascendant":
            continue
        if chart_data[p].get("dignity") == "Debilitated":
            deb_sign = chart_data[p]["sign"]
            deb_lord = SIGN_LORDS[deb_sign]
            if deb_lord in chart_data and house_of(deb_lord) in KENDRAS:
                yogas.append({
                    "name": "Neecha Bhanga Raja Yoga",
                    "strength": 78,
                    "planets": [p, deb_lord],
                    "desc": f"{p}'s debilitation is cancelled (Neecha Bhanga), turning weakness into eventual strength and success after struggle."
                })

    # 7. Chandra-Mangal
    if "Moon" in chart_data and "Mars" in chart_data:
        if house_of("Moon") == house_of("Mars"):
            yogas.append({
                "name": "Chandra-Mangal Yoga",
                "strength": 65,
                "planets": ["Moon", "Mars"],
                "desc": "Moon and Mars conjoin, indicating financial acumen and earning ability through effort."
            })

    # 8. Vipareeta
    dusthanas = [6, 8, 12]
    for h in dusthanas:
        dl = lord_of_house(h)
        if dl in chart_data and house_of(dl) in dusthanas:
            yogas.append({
                "name": "Vipareeta Raja Yoga",
                "strength": 60,
                "planets": [dl],
                "desc": f"Lord of {h}th house placed in another dusthana, granting unexpected success through adversity."
            })

    unique = {}
    for y in yogas:
        key = y["name"] + ",".join(sorted(y["planets"]))
        if key not in unique or y["strength"] > unique[key]["strength"]:
            unique[key] = y

    final = sorted(unique.values(), key=lambda x: x["strength"], reverse=True)
    return final[:6]


def check_yoga_activation(yogas, dasha_data):
    activation_report = []
    md = dasha_data["md"]
    ad = dasha_data["ad"]

    for y in yogas:
        involved = y["planets"]
        active_now = False
        timing_note = ""

        if md in involved and ad in involved:
            active_now = True
            timing_note = f"FULLY ACTIVE — both {md} (MD) and {ad} (AD) rule this yoga right now (until {dasha_data['ad_end']})."
        elif md in involved:
            active_now = True
            timing_note = f"ACTIVE — {md} Mahadasha is fueling this yoga (until {dasha_data['md_end']})."
        elif ad in involved:
            active_now = True
            timing_note = f"PARTIALLY ACTIVE — {ad} Antardasha triggers this yoga (until {dasha_data['ad_end']})."
        else:
            if dasha_data["md_next"] in involved:
                timing_note = f"UPCOMING — activates in {dasha_data['md_next']} Mahadasha (begins {dasha_data['md_end']})."
            elif dasha_data["ad_next"] in involved:
                timing_note = f"UPCOMING — activates in {dasha_data['ad_next']} Antardasha (begins {dasha_data['ad_end']})."
            else:
                timing_note = "DORMANT — none of its planets rule the current or immediate-next periods."

        activation_report.append({
            "name": y["name"],
            "strength": y["strength"],
            "planets": y["planets"],
            "desc": y["desc"],
            "active": active_now,
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

    for planet, sign_idx in natal_signs.items():
        host_planet = SIGN_LORDS[sign_idx]

        # Calculate Natural Relationship Score
        if host_planet == planet:
            natural_score = 0
        elif host_planet in NATURAL_FRIENDS[planet]:
            natural_score = 1
        elif host_planet in NATURAL_ENEMIES[planet]:
            natural_score = -1
        else:
            natural_score = 0

        # Calculate Temporary Relationship based on actual House Distance
        current_planet_house = natal_houses[planet]
        host_planet_house = natal_houses[host_planet]

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
# COMBUSTION HELPER
# ==========================================
COMBUSTION_LIMITS = {
    "Moon": 12, "Mars": 8, "Mercury": 12,
    "Jupiter": 11, "Venus": 8, "Saturn": 15
}

def get_combustion_status(planet_name, data):
    if planet_name in ["Sun", "Rahu", "Ketu", "Ascendant"]:
        return None
    sun_d = data["Sun"]["degree_total"]
    p_d = data[planet_name]["degree_total"]
    distance = abs(sun_d - p_d)
    if distance > 180:
        distance = 360 - distance
    limit = COMBUSTION_LIMITS.get(planet_name, 15)
    if data[planet_name].get("status") == "Rx":
        limit -= 2
    if distance > limit:
        return None
    ratio = distance / limit
    if ratio <= 0.25:   return "Severe"
    elif ratio <= 0.50: return "Strong"
    elif ratio <= 0.75: return "Moderate"
    else:               return "Mild"


# ==========================================
# SIMPLIFIED PLANETARY STRENGTH (Strong / Medium / Weak)
# ==========================================
def calculate_planetary_strength(planet_name, chart_data, panchadha_data, sav_data):
    """
    Returns only the label: 'Strong', 'Medium', or 'Weak'
    """
    pdata = chart_data[planet_name]
    p_maitri = panchadha_data.get(planet_name, {})
    # SAV is keyed by rashi (1-12), so use the natal sign index, not the house.
    planet_sign = pdata["sign_idx"] + 1   # 0-based sign index -> 1-12 rashi key
    sav_score = sav_data.get(planet_sign, 20)

    score = 50  # baseline

    # 1. Dignity
    dignity = pdata.get("dignity")
    if dignity == "Exalted":
        score += 25
    elif dignity == "Own Sign":
        score += 15
    elif dignity == "Debilitated":
        score -= 20

    # 2. Combustion
    combustion = get_combustion_status(planet_name, chart_data)
    if combustion:
        if combustion == "Severe":
            score -= 25
        elif combustion == "Strong":
            score -= 18
        elif combustion == "Moderate":
            score -= 10
        elif combustion == "Mild":
            score -= 5

    # 3. Retrograde
    if pdata.get("status") == "Rx" and planet_name not in ["Rahu", "Ketu"]:
        score -= 5

    # 4. Panchadha Maitri
    final_relation = p_maitri.get("Final_Relationship", "Neutral")
    if final_relation == "Great Friend":
        score += 15
    elif final_relation == "Friend":
        score += 8
    elif final_relation == "Enemy":
        score -= 10
    elif final_relation == "Bitter Enemy":
        score -= 18

    # 5. SAV House Strength
    if sav_score >= 30:
        score += 15
    elif sav_score >= 25:
        score += 8
    elif sav_score <= 14:
        score -= 15
    elif sav_score <= 19:
        score -= 8

    score = max(0, min(100, score))

    if score >= 70:
        return "Strong"
    elif score >= 40:
        return "Medium"
    else:
        return "Weak"


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

ASHTAKAVARGA_RULES = {
    "Sun": {
        "Sun": [1, 2, 4, 7, 8, 9, 10, 11],
        "Moon": [3, 6, 10, 11],
        "Mars": [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [5, 6, 9, 11, 12],
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
        "Sun": [5, 6, 11, 12],
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
    required = ["Ascendant"] + ASHTAKAVARGA_PLANETS
    for key in required:
        if key not in rashi_positions:
            raise ValueError(f"Missing required rashi position: {key}")
        if not 1 <= rashi_positions[key] <= 12:
            raise ValueError(f"{key} rashi position must be 1-12, got {rashi_positions[key]}")

    source_bodies = ["Ascendant"] + ASHTAKAVARGA_PLANETS

    bav = {
        planet: {rashi: 0 for rashi in range(1, 13)}
        for planet in ASHTAKAVARGA_PLANETS
    }

    for subject in ASHTAKAVARGA_PLANETS:
        for source in source_bodies:
            source_rashi = rashi_positions[source]
            source_idx = source_rashi - 1
            for offset in ASHTAKAVARGA_RULES[subject][source]:
                target_idx = (source_idx + (offset - 1)) % 12
                target_rashi = target_idx + 1
                bav[subject][target_rashi] += 1

    sav = {rashi: 0 for rashi in range(1, 13)}
    for rashi in range(1, 13):
        sav[rashi] = sum(bav[planet][rashi] for planet in ASHTAKAVARGA_PLANETS)

    planet_totals = {
        planet: sum(bav[planet].values())
        for planet in ASHTAKAVARGA_PLANETS
    }

    return {
        "Bhinnashtakavarga": bav,
        "Sarvashtakavarga": sav,
        "Planet_Totals": planet_totals,
        "House_Totals": dict(sav),
    }


def validate_sav_invariant(result):
    """The total of all 12 SAV values must equal 333 for standard Parashara tables."""
    total = sum(result["Sarvashtakavarga"].values())
    return total == 333, total


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

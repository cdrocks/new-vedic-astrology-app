"""Moon, Mind & Chandra Lagna Engine (Mood & Mental State Architecture).

This module contains the full Moon-centered calculation suite:
1. Moon Details (Nakshatra, Pada, Arc-minute advancement, Boundary alerts, Paksha & Tithi)
2. Chandra Lagna (12 Houses of Mind/Emotion, resident planets, house lords)
3. Psychological Yogas & Temperament (Visha, Chandra-Mangala, Gajakesari, Grahan, Kemadruma, Sunapha, Anapha, Durudhara)
4. Moon Gochar (Shani Sade Sati/Kantaka/Ashtama/Upachaya cycles, Guru Gochar, Transit-on-Natal conjunctions, Tara Bala, Phaladeepika transit matrix)
5. Structured prompt formatting for LLM consultation workflows
"""

from __future__ import annotations

from typing import Any

RASHI_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

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

TITHI_NAMES = [
    "Shukla Pratipada (1)", "Shukla Dwitiya (2)", "Shukla Tritiya (3)", "Shukla Chaturthi (4)",
    "Shukla Panchami (5)", "Shukla Shashthi (6)", "Shukla Saptami (7)", "Shukla Ashtami (8)",
    "Shukla Navami (9)", "Shukla Dashami (10)", "Shukla Ekadashi (11)", "Shukla Dwadashi (12)",
    "Shukla Trayodashi (13)", "Shukla Chaturdashi (14)", "Purnima (15 - Full Moon)",
    "Krishna Pratipada (1)", "Krishna Dwitiya (2)", "Krishna Tritiya (3)", "Krishna Chaturthi (4)",
    "Krishna Panchami (5)", "Krishna Shashthi (6)", "Krishna Saptami (7)", "Krishna Ashtami (8)",
    "Krishna Navami (9)", "Krishna Dashami (10)", "Krishna Ekadashi (11)", "Krishna Dwadashi (12)",
    "Krishna Trayodashi (13)", "Krishna Chaturdashi (14)", "Amavasya (30 - New Moon)"
]

TARA_BALA_TYPES = [
    ("Janma", "Birth/Self — Neutral/Moderate mental baseline"),
    ("Sampat", "Wealth/Prosperity — Highly Auspicious & positive mental flow"),
    ("Vipat", "Obstacles/Distractions — Challenging & requires mental patience"),
    ("Kshema", "Security/Well-being — Highly Auspicious, peaceful & protective"),
    ("Pratyak", "Opposition/Hurdles — Obstinate or conflicting mental state"),
    ("Sadhana", "Achievement/Fulfillment — Peak Auspicious, goal-oriented drive"),
    ("Naidhana", "Vulnerability/Crisis — Demanding, introspective & cautious"),
    ("Mitra", "Friend/Alliance — Auspicious, cooperative & harmonious"),
    ("Parama Mitra", "Supreme Ally — Auspicious, deeply supportive & empowering")
]

CLASSICAL_MOON_GOCHAR_AUSPICIOUS: dict[str, list[int]] = {
    "Sun":     [3, 6, 10, 11],
    "Moon":    [1, 3, 6, 7, 10, 11],
    "Mars":    [3, 6, 11],
    "Mercury": [2, 4, 6, 8, 10, 11],
    "Jupiter": [2, 5, 7, 9, 11],
    "Venus":   [1, 2, 3, 4, 5, 8, 9, 11, 12],
    "Saturn":  [3, 6, 11],
    "Rahu":    [3, 6, 10, 11],
    "Ketu":    [3, 6, 10, 11]
}


def calculate_moon_details(moon_deg: float, sun_deg: float | None = None) -> dict[str, Any]:
    """Calculates Moon sign, advancement, nakshatra, pada, boundary distance, paksha, and tithi."""
    L = float(moon_deg) % 360.0
    M = L * 60.0
    R = int(L / 30.0) % 12
    sign_name = RASHI_NAMES[R]

    adv_deg = L - (R * 30.0)
    d_int = int(adv_deg)
    m_int = int(round((adv_deg - d_int) * 60))
    if m_int >= 60:
        m_int -= 60
        d_int += 1
    advancement_str = f"{d_int}° {m_int:02d}'"

    nak_len = 360.0 / 27.0
    nak_idx = min(int(L / nak_len), 26)
    nak_name, nak_lord = NAKSHATRAS[nak_idx]

    rem_min = M % 800.0
    pada = min(int(rem_min / 200.0) + 1, 4)
    dist_pada_min = min(rem_min % 200.0, 200.0 - (rem_min % 200.0))
    dist_pada_deg = dist_pada_min / 60.0

    paksha_info: dict[str, Any] = {}
    if sun_deg is not None:
        diff = (L - (float(sun_deg) % 360.0)) % 360.0
        tithi_idx = min(int(diff / 12.0), 29)
        tithi_name = TITHI_NAMES[tithi_idx]
        is_shukla = diff < 180.0
        paksha_str = "Shukla Paksha (Waxing / High Mental Vitality)" if is_shukla else "Krishna Paksha (Waning / Deep Internal Reflection)"
        paksha_info = {
            "paksha": "Shukla" if is_shukla else "Krishna",
            "paksha_desc": paksha_str,
            "tithi_num": tithi_idx + 1,
            "tithi_name": tithi_name,
            "sun_moon_angle": diff
        }

    return {
        "sign_idx": R,
        "sign_name": sign_name,
        "degree_total": L,
        "degree_in_sign": adv_deg,
        "advancement": advancement_str,
        "nakshatra": nak_name,
        "nakshatra_lord": nak_lord,
        "nakshatra_idx": nak_idx,
        "pada": pada,
        "pada_boundary_dist_deg": dist_pada_deg,
        "is_near_boundary": dist_pada_deg < 0.5,
        **paksha_info
    }


def get_chandra_lagna_data(chart_data: dict[str, dict[str, Any]], moon_sign_idx: int) -> dict[str, Any]:
    """
    Constructs Chandra Lagna (Moon Chart) with all 12 houses relative to Moon,
    resident natal planets, and psychological temperament / Moon conjunction yogas.
    """
    house_planets: dict[int, list[str]] = {h: [] for h in range(1, 13)}
    planets_with_moon: list[str] = []

    for p_name, p_data in chart_data.items():
        if p_name == "Ascendant":
            continue
        p_sign_idx = int(p_data["sign_idx"])
        h_moon = (p_sign_idx - moon_sign_idx) % 12 + 1
        label = p_name
        if p_data.get("status") == "Rx":
            label += " (Rx)"
        if p_data.get("combustion"):
            label += " (Combust)"
        house_planets[h_moon].append(label)

        if h_moon == 1 and p_name != "Moon":
            planets_with_moon.append(p_name)

    # Mental temperament & Chandra Yogas
    psychological_yogas: list[str] = []
    if "Saturn" in planets_with_moon:
        psychological_yogas.append("Moon-Saturn Conjunction (Visha / Punaphoo Yoga): Deep caution, intense emotional resilience, prone to over-seriousness and self-critical introspection under stress.")
    if "Mars" in planets_with_moon:
        psychological_yogas.append("Chandra-Mangala Yoga: High emotional drive, fiery ambition, commercial aggression, quick temper but immense determination.")
    if "Jupiter" in planets_with_moon:
        psychological_yogas.append("Gajakesari Yoga (Lagna/Moon Core): Philosophical poise, noble mental disposition, emotional optimism, natural wisdom.")
    if "Rahu" in planets_with_moon:
        psychological_yogas.append("Chandra-Rahu Grahan Influence: Hyper-active imagination, unorthodox desires, prone to overthinking, psychological restlessness, visionary thinking.")
    if "Ketu" in planets_with_moon:
        psychological_yogas.append("Chandra-Ketu Grahan Influence: Deeply intuitive, emotionally detached, spiritual depth, feeling misunderstood, analytical isolation.")
    if "Mercury" in planets_with_moon:
        psychological_yogas.append("Buddhi-Manas Yoga (Moon-Mercury): Sharp intellect, communicative agility, curious mindset, analytical processing of feelings.")
    if "Sun" in planets_with_moon:
        psychological_yogas.append("Amavasya Conjunction (Sun-Moon): Intense internal focus, strong individual willpower, introverted emotional processing.")
    if "Venus" in planets_with_moon:
        psychological_yogas.append("Shukra-Chandra Yoga: Creative sensibility, aesthetic refinement, desire for harmony, gentleness in expression.")

    # Kemadruma / Sunapha / Anapha checks
    planets_h2 = [p for p in house_planets[2] if not any(k in p for k in ["Rahu", "Ketu", "Sun"])]
    planets_h12 = [p for p in house_planets[12] if not any(k in p for k in ["Rahu", "Ketu", "Sun"])]
    if not planets_h2 and not planets_h12:
        psychological_yogas.append("Kemadruma Disposition (Isolated Moon): Independent emotional processing, self-reliant mindset, needs conscious external support networks.")
    elif planets_h2 and planets_h12:
        psychological_yogas.append(f"Durudhara Yoga: Flanked by support on both sides (H2: {', '.join(planets_h2)}, H12: {', '.join(planets_h12)}), providing balanced emotional stability.")
    elif planets_h2:
        psychological_yogas.append(f"Sunapha Yoga: Planets in 2nd from Moon ({', '.join(planets_h2)}) providing forward-looking financial and emotional drive.")
    elif planets_h12:
        psychological_yogas.append(f"Anapha Yoga: Planets in 12th from Moon ({', '.join(planets_h12)}) providing magnetic charisma, discipline, and self-restraint.")

    houses_summary: dict[int, dict[str, Any]] = {}
    sign_lords_list = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]
    for h in range(1, 13):
        sign_i = (moon_sign_idx + h - 1) % 12
        houses_summary[h] = {
            "house": h,
            "sign_idx": sign_i,
            "sign_name": RASHI_NAMES[sign_i],
            "sign_lord": sign_lords_list[sign_i],
            "planets": house_planets[h]
        }

    return {
        "moon_sign_idx": moon_sign_idx,
        "moon_sign_name": RASHI_NAMES[moon_sign_idx],
        "houses": houses_summary,
        "planets_with_moon": planets_with_moon,
        "psychological_yogas": psychological_yogas
    }


def calculate_moon_gochar(
    chart_data: dict[str, dict[str, Any]],
    transit_data: dict[str, dict[str, Any]],
    moon_sign_idx: int,
    natal_moon_nak_idx: int,
    today_moon_deg: float | None = None,
    sav: dict[int, int] | None = None
) -> dict[str, Any]:
    """
    Calculates comprehensive Moon Gochar:
    1. Saturn Shani Cycle (Sade Sati, Ardhashtama, Ashtama, Upachaya)
    2. Jupiter Guru Gochara
    3. Classical Phaladeepika Auspiciousness Matrix for all 9 transiting grahas
    4. Active Transit-on-Natal Conjunctions
    5. Daily Transit Moon Mood & Tara Bala
    """
    sav = sav or {}

    # 1. Shani Gochar (Saturn relative to Moon)
    saturn_transit = transit_data.get("Saturn", {})
    saturn_sign_idx = int(saturn_transit.get("sign_idx", 0))
    saturn_h_moon = (saturn_sign_idx - moon_sign_idx) % 12 + 1

    shani_phase = "Neutral Shani Transit"
    shani_desc = f"Saturn transits House {saturn_h_moon} from Moon in {RASHI_NAMES[saturn_sign_idx]}."
    if saturn_h_moon == 12:
        shani_phase = "Sade Sati Phase 1 (Rising / Vyaya Shani)"
        shani_desc = "Saturn transiting 12th from Moon: Mental restructuring, letting go of outdated commitments, fatigue, preparation for new cycle."
    elif saturn_h_moon == 1:
        shani_phase = "Sade Sati Phase 2 (Peak / Janma Shani)"
        shani_desc = "Saturn transiting Natal Moon (Janma Rashi): Peak psychological responsibility, heavy endurance test, forging inner maturity."
    elif saturn_h_moon == 2:
        shani_phase = "Sade Sati Phase 3 (Setting / Dhana Shani)"
        shani_desc = "Saturn transiting 2nd from Moon: Practical consolidation, family responsibilities, financial discipline, grounding."
    elif saturn_h_moon == 4:
        shani_phase = "Ardhashtama Shani (Kantaka Shani / 4th from Moon)"
        shani_desc = "Saturn in 4th from Moon: Disruption of domestic peace, mental unrest, career relocation, pressure on inner comfort."
    elif saturn_h_moon == 8:
        shani_phase = "Ashtama Shani (8th from Moon)"
        shani_desc = "Saturn in 8th from Moon: Deep psychological transformation, overcoming systemic roadblocks, confronting vulnerabilities."
    elif saturn_h_moon in [3, 6, 11]:
        shani_phase = f"Upachaya Shani (Favorable - House {saturn_h_moon} from Moon)"
        shani_desc = f"Saturn in House {saturn_h_moon} from Moon: Classical victory house! High mental stamina, defeat of competition, steady progress."

    # 2. Guru Gochar (Jupiter relative to Moon)
    jupiter_transit = transit_data.get("Jupiter", {})
    jupiter_sign_idx = int(jupiter_transit.get("sign_idx", 0))
    jupiter_h_moon = (jupiter_sign_idx - moon_sign_idx) % 12 + 1
    guru_favorable = jupiter_h_moon in [2, 5, 7, 9, 11]
    guru_status = "Favorable (Guru Gochara Blessings)" if guru_favorable else "Internalizing / Demanding Effort"
    guru_desc = f"Jupiter transiting House {jupiter_h_moon} from Moon ({guru_status}): " + (
        "Expands optimism, clears confusion, confers intellectual poise and luck."
        if guru_favorable else
        "Promotes internal wisdom, self-reliance, and patient effort."
    )

    # 3. Transits Matrix from Moon
    transit_items: list[dict[str, Any]] = []
    conjunctions: list[str] = []

    # Map natal planets by sign
    natal_by_sign: dict[int, list[str]] = {s: [] for s in range(12)}
    for p_name, p_data in chart_data.items():
        if p_name == "Ascendant":
            continue
        natal_by_sign[int(p_data["sign_idx"])].append(p_name)

    for p_name in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]:
        if p_name not in transit_data:
            continue
        t_data = transit_data[p_name]
        t_sign_idx = int(t_data["sign_idx"])
        t_deg = float(t_data.get("degree_in_sign", 0.0))
        t_status = t_data.get("status", "Dir")
        h_moon = (t_sign_idx - moon_sign_idx) % 12 + 1

        is_favorable = h_moon in CLASSICAL_MOON_GOCHAR_AUSPICIOUS.get(p_name, [])
        fav_label = "Favorable" if is_favorable else "Challenging"

        rashi_num = t_sign_idx + 1
        sav_val = sav.get(rashi_num, 28)
        sav_tag = f"SAV: {sav_val}"

        rx_tag = " (Rx)" if t_status == "Rx" else ""

        transit_items.append({
            "planet": p_name,
            "sign": RASHI_NAMES[t_sign_idx],
            "sign_idx": t_sign_idx,
            "house_from_moon": h_moon,
            "degree_in_sign": t_deg,
            "status": t_status,
            "classical_rating": fav_label,
            "sav": sav_val,
            "summary_line": f"- Transiting {p_name}{rx_tag} in {RASHI_NAMES[t_sign_idx]} (House {h_moon} from Moon) — [{fav_label} | {sav_tag}]"
        })

        # Check conjunction with natal planets
        natal_here = natal_by_sign.get(t_sign_idx, [])
        if natal_here:
            conj_str = f"Transit {p_name}{rx_tag} in {RASHI_NAMES[t_sign_idx]} conjuncts Natal {', '.join(natal_here)} (House {h_moon} from Moon)"
            conjunctions.append(conj_str)

    # 4. Today's Transit Moon & Tara Bala
    tara_bala_info: dict[str, Any] = {}
    if today_moon_deg is not None:
        nak_len = 360.0 / 27.0
        t_nak_idx = min(int((float(today_moon_deg) % 360.0) / nak_len), 26)
        t_nak_name, t_nak_lord = NAKSHATRAS[t_nak_idx]
        tara_step = (t_nak_idx - natal_moon_nak_idx) % 9
        tara_name, tara_desc = TARA_BALA_TYPES[tara_step]
        tara_bala_info = {
            "transit_moon_nakshatra": t_nak_name,
            "transit_moon_nakshatra_lord": t_nak_lord,
            "tara_step": tara_step + 1,
            "tara_name": tara_name,
            "tara_desc": tara_desc
        }

    return {
        "shani_phase": shani_phase,
        "shani_desc": shani_desc,
        "shani_house_from_moon": saturn_h_moon,
        "guru_status": guru_status,
        "guru_desc": guru_desc,
        "guru_house_from_moon": jupiter_h_moon,
        "transits": transit_items,
        "transit_on_natal_conjunctions": conjunctions,
        "tara_bala": tara_bala_info
    }


def format_chandra_lagna_for_prompt(c_data: dict[str, Any], moon_details: dict[str, Any]) -> str:
    """Formats Chandra Lagna and Natal Mental Framework for LLM prompt."""
    out = []
    out.append(f"Natal Moon: {moon_details.get('sign_name', '')} ({moon_details.get('advancement', '')}) | Nakshatra: {moon_details.get('nakshatra', '')} (Pada {moon_details.get('pada', '')}, Lord: {moon_details.get('nakshatra_lord', '')})")
    if "paksha_desc" in moon_details:
        out.append(f"Paksha & Tithi: {moon_details['paksha_desc']} | Tithi: {moon_details.get('tithi_name', '')}")
    if moon_details.get("is_near_boundary"):
        out.append(f"⚠️ Moon is within {float(moon_details.get('pada_boundary_dist_deg', 0.0))*60.0:.1f}' of a Pada boundary.")

    out.append("\nPsychological Disposition & Mental Temperament (Chandra Yogas):")
    yogas = c_data.get("psychological_yogas", [])
    if yogas:
        for y in yogas:
            out.append(f"- {y}")
    else:
        out.append("- Balanced emotional foundation; no severe afflictions or isolation on Natal Moon.")

    out.append("\nChandra Lagna (12 Houses of Mind, Emotion & Internal Drive):")
    houses = c_data.get("houses", {})
    for h in range(1, 13):
        h_info = houses[h]
        planets_str = ", ".join(h_info["planets"]) if h_info["planets"] else "Empty"
        out.append(f"- House {h:2d} ({h_info['sign_name']}): {planets_str}")
    return "\n".join(out)


def format_moon_gochar_for_prompt(mg_data: dict[str, Any]) -> str:
    """Formats Moon Gochar, Shani Cycle, and Daily Micro-Mood for LLM prompt."""
    out = []
    out.append("### 1. Saturn Shani Gochar (Psychological Responsibility & Long-term Maturity):")
    out.append(f"- Status: **{mg_data.get('shani_phase', '')}**")
    out.append(f"- Impact: {mg_data.get('shani_desc', '')}")

    out.append("\n### 2. Jupiter Guru Gochar (Mental Optimism, Higher Wisdom & Luck):")
    out.append(f"- Status: **{mg_data.get('guru_status', '')}** (House {mg_data.get('guru_house_from_moon', '')} from Moon)")
    out.append(f"- Impact: {mg_data.get('guru_desc', '')}")

    conjs = mg_data.get("transit_on_natal_conjunctions", [])
    if conjs:
        out.append("\n### 3. Active Transit-on-Natal Conjunctions (Psychological Hotspots):")
        for c in conjs:
            out.append(f"- {c}")

    tb = mg_data.get("tara_bala", {})
    if tb:
        out.append("\n### 4. Today's Transit Moon & Tara Bala (Daily Micro-Mood Trigger):")
        out.append(f"- Today's Transit Moon Nakshatra: {tb.get('transit_moon_nakshatra', '')} ({tb.get('tara_name', '')} Tara — {tb.get('tara_desc', '')})")

    out.append("\n### 5. Classical Gochara Matrix from Moon (Phaladeepika Auspiciousness):")
    for t in mg_data.get("transits", []):
        out.append(t["summary_line"])

    return "\n".join(out)

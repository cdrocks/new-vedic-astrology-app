"""
Kiosk Core Engine: Executes chart calculations, Swiss Ephemeris math, and AI interpretation
for live event kiosks without touching or modifying the original app.py.
"""

import os
import re
import logging
import pytz
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)
import swisseph as swe
from geopy.geocoders import ArcGIS, Nominatim
from timezonefinder import TimezoneFinder
from openai import OpenAI
try:
    import anthropic
except ImportError:
    anthropic = None

def _load_dotenv_if_present():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_dotenv_if_present()

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
from doshas import calculate_doshas, format_doshas_for_prompt

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

def _get_api_credentials() -> Tuple[str, str]:
    """Retrieve (provider, api_key) from env or secrets."""
    # 1. Anthropic Claude (preferred)
    ant_key = os.getenv("ANTHROPIC_API_KEY")
    if not ant_key:
        secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
        if os.path.exists(secrets_path):
            try:
                with open(secrets_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if "ANTHROPIC_API_KEY" in line and "=" in line:
                            ant_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception:
                pass
    if ant_key and anthropic is not None:
        return "anthropic", ant_key

    # 2. DeepSeek (fallback)
    deep_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not deep_key:
        secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
        if os.path.exists(secrets_path):
            try:
                with open(secrets_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if "DEEPSEEK_API_KEY" in line and "=" in line:
                            deep_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception:
                pass
    if deep_key:
        return "deepseek", deep_key

    return "", ""

def _get_api_key() -> str:
    """Backwards compatibility helper."""
    _, key = _get_api_credentials()
    return key

YOGA_USER_MEANINGS = {
    "gajakesari": "Wisdom, lasting public respect, and natural protection from setbacks.",
    "budhaditya": "Sharp analytical intellect, executive communication, and commercial acumen.",
    "kendra-trikona": "Leadership authority, rapid professional rise, and executive leverage.",
    "dharma-karmadhipati": "Fulfilling life purpose, commanding career status, and ethical success.",
    "maha dhana": "Major wealth multiplication, diverse profit streams, and strong capital growth.",
    "dhana yoga": "Steady financial resilience, earning power, and wealth preservation.",
    "lakshmi": "Abundant prosperity, graceful fortune, and enduring material comfort.",
    "vasumathi": "Self-earned financial independence and compounding prosperity over time.",
    "chandra-mangala": "Dynamic enterprise instinct, commercial drive, and active wealth creation.",
    "ruchaka": "Bold courage, physical stamina, command, and decisive victory in competition.",
    "bhadra": "Sharp business intellect, trade mastery, and executive administrative acumen.",
    "hamsa": "Profound wisdom, spiritual dignity, sound judgment, and honorable acclaim.",
    "malavya": "Refined lifestyle, artistic brilliance, magnetic charm, and material comfort.",
    "sasa": "Relentless stamina, organizational command, and long-term authority.",
    "amala": "Spotless professional reputation, ethical rise, and lasting social goodwill.",
    "saraswati": "Creative mastery, deep learning, eloquence, and intellectual acclaim.",
    "harsha": "Invincibility against obstacles, robust vitality, and triumph over adversaries.",
    "sarala": "Fearless crisis resolution, breakthrough windfalls, and victory under pressure.",
    "vimala": "Financial resilience, noble character, and honorable independence.",
    "neecha bhanga": "Turning early limitations into exceptional late-career mastery.",
    "adhi": "Executive command, high social status, and natural leadership leverage.",
    "chandradhi": "Executive command, high social status, and natural leadership leverage.",
    "maha parivartana": "Mutual synergy between key life areas, multiplying success and rise.",
    "dainya parivartana": "Deep resilience that transforms hardships into breakthroughs.",
    "khala parivartana": "Bold personal initiative that masters fluctuating circumstances.",
    "durudhura": "Balanced fortune, generous comforts, vehicles, and enduring stability.",
    "sunapha": "Self-earned prosperity, mental agility, and steady life rise.",
    "anapha": "Magnetic poise, self-command, eloquence, and robust vitality.",
    "ubhayachari": "Balanced confidence, persuasive speech, and dependable career drive.",
    "vesi": "Articulate expression, steady determination, and influential connections.",
    "vosi": "Sharp insight, charitable standing, and wise philosophical outlook.",
    "kemadruma bhanga": "Overcoming early isolation to develop strong self-reliance."
}

def clean_yoga_title(name: str) -> str:
    """Removes technical astrological coordinates and brackets for user-friendly display."""
    if not name:
        return ""
    # Strip trailing technical qualifiers like (Adhi Yoga), (H1-H9), (Pancha Mahapurusha), etc.
    cleaned = re.sub(r'\s*\((?:Adhi Yoga|Isolation Cancelled|H\d+|Pancha Mahapurusha|H\d+.*?|from Lagna|from Moon|Mars|Sun|Moon|Jupiter|Venus|Saturn|Mercury)\)', '', name).strip()
    return cleaned or name

def get_yoga_user_meaning(name: str, desc: str = "") -> str:
    """Returns a concise 5-10 word real-world meaning of what the yoga brings to the native in practice."""
    name_lower = (name or "").lower()
    for key, meaning in YOGA_USER_MEANINGS.items():
        if key in name_lower:
            return meaning
    # Fallback: extract clean promise from desc if present
    if desc:
        m = re.search(r'(?:Grants|Bestows|Indicates|Conferring|Converts)\s+(.*)', desc, re.IGNORECASE)
# ==============================================================================
# BANNED TROPES & SAFETY PATTERNS
# ==============================================================================
BANNED_SUPERSTITION_PATTERNS = [
    r'\b(temple|mandir|puja|pooja|dal|lentil|masoor|donate|donation|cows?|crows?|birds?|copper|gemstone|ruby|emerald|sapphire|pearl|coral|hessonite|cat\'s\s+eye|rudraksha|yantra|totka|remedy|remedies)\b'
]
BANNED_WELLNESS_PATTERNS = [
    r'\b(splash(?:ing)?\s+(?:cold\s+)?water|8\s+glasses|eight\s+glasses|morning\s+sunlight|15\s+minutes\s+of\s+sunlight|deep\s+breath(?:ing|s)?|digital\s+detox|calming\s+music|warm\s+bath)\b'
]
BANNED_CODE_PATTERNS = [
    r'(\(Rx\)|\[COMBUST\]|\bShadbala\b|\bBhava\s+Bala\b|\bSAV\b|\bBAV\b|\bbindus\b|\bMahadasha\b|\bAntardasha\b|\bPratyantardasha\b|\bMD/AD/PD\b)'
]

SIGN_LORDS_DICT = {
    0: "Mars", 1: "Venus", 2: "Mercury", 3: "Moon", 4: "Sun", 5: "Mercury",
    6: "Venus", 7: "Mars", 8: "Jupiter", 9: "Saturn", 10: "Saturn", 11: "Jupiter"
}

def compute_astrological_verdicts(
    chart_data: Dict[str, Any],
    bb_data: Dict[str, Any],
    sav: Dict[int, int],
    bav: Dict[str, Dict[int, int]],
    transit_dict: Dict[str, Any],
    dasha_data: Dict[str, Any],
    moon_details: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Python pre-computes concrete machine VERDICTS (STRONG / WEAK / MODERATE / ACUTE FRICTION)
    for every metric so the LLM never has to interpret or guess raw numbers.
    """
    verdicts = {}

    # 1. Planetary Shadbala Verdicts
    planets_shadbala = bb_data.get("planets_shadbala", {})
    sb_verdicts = {}
    for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        if p in planets_shadbala:
            sb = planets_shadbala[p]
            pct = shadbala_percent(sb["total"], p)
            if pct >= 110:
                v_label = "STRONG (High natural rebound & stamina)"
            elif pct >= 85:
                v_label = "MODERATE (Consistent, steady baseline)"
            else:
                v_label = "WEAK (Low reserve, vulnerable to acute exhaustion, requires pacing)"
            sb_verdicts[p] = {"pct": pct, "verdict": v_label}
    verdicts["shadbala"] = sb_verdicts

    # 2. Bhava Bala House Rank Verdicts (1 to 12)
    houses_bb = bb_data.get("houses", {})
    scores = {h: houses_bb[h]["adhipati"] + houses_bb[h]["dig"] for h in houses_bb}
    order = sorted(scores, key=lambda h: (-scores[h], h))
    rank_map = {h: i + 1 for i, h in enumerate(order)}

    house_verdicts = {}
    for h in range(1, 13):
        r = rank_map.get(h, 6)
        rupas = houses_bb.get(h, {}).get("rupas", 6.0)
        if r <= 4:
            hv = "STRONG (Highly protected house, robust structural buffer)"
        elif r <= 8:
            hv = "MODERATE (Neutral support, reflects daily routines)"
        else:
            hv = "WEAK / HIGH STRESS (Vulnerable house, high friction zone, sensitive to transit pressure)"
        house_verdicts[h] = {"rank": r, "rupas": rupas, "verdict": hv}
    verdicts["houses"] = house_verdicts

    # 3. SAV (Samudaya Ashtakavarga) Verdicts
    asc_sign_idx = int(chart_data["Ascendant"]["sign_idx"])
    sav_verdicts = {}
    for h in range(1, 13):
        r_idx = (asc_sign_idx + h - 1) % 12
        pts = sav.get(r_idx + 1, 28)
        if pts >= 28:
            sv = "STRONG BUFFER (High resilience to transit pressure)"
        elif pts >= 25:
            sv = "MODERATE BUFFER (Average resilience)"
        else:
            sv = "LOW BUFFER (Transit pressure causes high friction & fatigue)"
        sav_verdicts[h] = {"points": pts, "verdict": sv}
    verdicts["sav"] = sav_verdicts

    # 4. Transiting Planet BAV Bindus & Friction Verdicts
    transit_bav_verdicts = {}
    for p_name in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]:
        if p_name in transit_dict:
            tp = transit_dict[p_name]
            t_sign_idx = tp["sign_idx"]
            rashi_key = t_sign_idx + 1
            bindus = bav.get(p_name, {}).get(rashi_key, 4)
            if bindus >= 5:
                bv = "HIGH TRANSIT SUPPORT (Smooth forward flow, planet delivers strength)"
            elif bindus == 4:
                bv = "MODERATE TRANSIT SUPPORT (Balanced)"
            else:
                bv = "ACUTE TRANSIT FRICTION (Low energy buffer, high metabolic/muscular drag)"
            transit_bav_verdicts[p_name] = {"bindus": bindus, "verdict": bv}
    verdicts["transit_bav"] = transit_bav_verdicts

    # 5. Mercury Combustion Verdict
    sun_deg = chart_data["Sun"]["degree_total"]
    merc_deg = chart_data["Mercury"]["degree_total"]
    diff = abs((merc_deg - sun_deg + 180) % 360 - 180)
    if diff < 3.0:
        cv = "SEVERE COMBUSTION (High cognitive over-stimulation, nervous fatigue, mental scattering)"
    elif diff < 8.0:
        cv = "MODERATE COMBUSTION (Active mind, restlessness under tight deadlines)"
    else:
        cv = "CLEAR / NON-COMBUST (Steady nervous system, clear mental adaptability)"
    verdicts["mercury_combustion"] = {"distance_deg": round(diff, 2), "verdict": cv}

    return verdicts


def build_topic_factsheet(
    workflow_key: str,
    chart_data: Dict[str, Any],
    verdicts: Dict[str, Any],
    dasha_data: Dict[str, Any],
    transit_dict: Dict[str, Any],
    asc_sign_idx: int,
    moon_sign_idx: int
) -> str:
    """
    Compiles the domain-specific pre-computed machine-verdict factsheet for ANY workflow.
    Pre-labels all numbers with verdicts (STRONG / WEAK / MODERATE / ACUTE FRICTION).
    """
    sb = verdicts.get("shadbala", {})
    hv = verdicts.get("houses", {})
    sav_v = verdicts.get("sav", {})
    tb_v = verdicts.get("transit_bav", {})
    mc_v = verdicts.get("mercury_combustion", {})

    DOMAIN_CONFIGS = {
        "career": {
            "title": "CAREER, VOCATION & PROFESSIONAL MOMENTUM",
            "primary_houses": [10, 6, 11, 2, 1],
            "key_planets": ["Sun", "Saturn", "Jupiter", "Mercury"],
            "timing_focus": "Immediate windows (next 1–3 months) & mid-term milestones (3–8 months)"
        },
        "generic_career": {
            "title": "CAREER DIRECTION, VOCATION & ACADEMIC STREAM",
            "primary_houses": [10, 1, 5, 9, 6],
            "key_planets": ["Mercury", "Jupiter", "Sun", "Saturn"],
            "timing_focus": "Medium-to-long term foundation and directional positioning"
        },
        "wealth": {
            "title": "WEALTH, FINANCES & ASSET ACCUMULATION",
            "primary_houses": [2, 11, 5, 9, 12],
            "key_planets": ["Jupiter", "Venus", "Mercury", "Saturn"],
            "timing_focus": "Cashflow velocity, savings retention buffers, and investment compounding"
        },
        "relationships": {
            "title": "RELATIONSHIPS, LOVE & EMOTIONAL HARMONY",
            "primary_houses": [7, 5, 2, 8, 12],
            "key_planets": ["Venus", "Moon", "Jupiter", "Mars"],
            "timing_focus": "Current emotional weather, communication rhythms, and relationship chemistry"
        },
        "marriage": {
            "title": "MARRIAGE, SPOUSE & LONG-TERM MATRIMONY",
            "primary_houses": [7, 2, 8, 4, 12],
            "key_planets": ["Venus", "Jupiter", "Mars", "Saturn"],
            "timing_focus": "Commitment readiness, matrimonial timing windows, and partnership stability"
        },
        "health": {
            "title": "HEALTH, VITALITY & METABOLIC PACING",
            "primary_houses": [1, 6, 8],
            "key_planets": ["Sun", "Mars", "Moon", "Mercury"],
            "timing_focus": "Strict 90-day vitality and recovery window (Pratyantardasha)"
        },
        "luck": {
            "title": "LUCK, FORTUNE & BHAGYA EXPANSION",
            "primary_houses": [9, 5, 1, 11],
            "key_planets": ["Jupiter", "Sun", "Venus"],
            "timing_focus": "Active grace windows, mentorship leverage, and karmic timing"
        },
        "children": {
            "title": "CHILDREN, PROGENY & FAMILY EXPANSION",
            "primary_houses": [5, 9, 2, 11],
            "key_planets": ["Jupiter", "Venus", "Moon"],
            "timing_focus": "Family expansion windows, parental guidance, and creative progeny"
        },
        "foreign": {
            "title": "FOREIGN TRAVEL, RELOCATION & GLOBAL OPPORTUNITY",
            "primary_houses": [12, 9, 3, 4],
            "key_planets": ["Rahu", "Jupiter", "Moon", "Saturn"],
            "timing_focus": "Relocation milestones, visa/travel cycles, and cross-border expansion"
        },
        "legal": {
            "title": "LEGAL MATTERS, DISPUTES & RESOLUTION",
            "primary_houses": [6, 8, 10, 11],
            "key_planets": ["Mars", "Saturn", "Jupiter"],
            "timing_focus": "Dispute navigation, negotiation leverage, and settlement timing"
        },
        "predictor_2027": {
            "title": "YEAR AHEAD / 4-QUARTER MILESTONE BLUEPRINT",
            "primary_houses": [1, 10, 11, 9, 7, 2, 6],
            "key_planets": ["Jupiter", "Saturn", "Rahu", "Sun"],
            "timing_focus": "Quarterly progression: Q1 (Jan-Mar), Q2 (Apr-Jun), Q3 (Jul-Sep), Q4 (Oct-Dec)"
        }
    }
    cfg = DOMAIN_CONFIGS.get(workflow_key, {
        "title": f"{workflow_key.upper().replace('_', ' ')} & STRATEGIC GUIDANCE",
        "primary_houses": [1, 10, 11, 9, 7, 2, 6],
        "key_planets": ["Sun", "Moon", "Jupiter", "Saturn"],
        "timing_focus": "Current planetary periods and live transit cycles"
    })

    pd_name = dasha_data.get("current_pd", "Active Sub-period")
    ad_name = dasha_data.get("ad", "Active Sub-period")
    md_name = dasha_data.get("md", "Active Mahadasha")
    pd_start = dasha_data.get("pd_start", "Current")
    pd_end = dasha_data.get("pd_end", "Next 90 Days")
    ad_start = dasha_data.get("ad_start", "")
    ad_end = dasha_data.get("ad_end", "")

    lines = [f"### {cfg['title']} (PRE-COMPUTED MACHINE VERDICTS)\n"]

    # Timing header
    if workflow_key == "health":
        lines.extend([
            "[TIME HORIZON: STRICT 90-DAY WINDOW]",
            f"- Active Cosmic Window: {pd_name} (Pratyantardasha) within {ad_name} (Antardasha)",
            f"- Timing Boundaries: {pd_start} to {pd_end}",
            "- MANDATORY TIMING RULE: Anchor all health guidance strictly within this 90-day window. NEVER reference distant years (like 2031).\n"
        ])
    else:
        lines.extend([
            "[TIME HORIZON & DASHA TIMELINE]",
            f"- Running Dasha: {md_name} Mahadasha → {ad_name} Antardasha → {pd_name} Pratyantardasha",
            f"- Antardasha Window: {ad_start} to {ad_end} | Pratyantardasha Window: {pd_start} to {pd_end}",
            f"- Focus Horizons: {cfg['timing_focus']}\n"
        ])

    # Section 1: Domain Foundation & House Capacities
    lines.append("[1. DOMAIN FOUNDATION & HOUSE CAPACITIES (BHAVA BALA & SAV VERDICTS)]")
    for h in cfg["primary_houses"]:
        h_info = hv.get(h, {})
        h_sav = sav_v.get(h, {})
        r_idx = (asc_sign_idx + h - 1) % 12
        h_lord = SIGN_LORDS_DICT.get(r_idx, "Unknown")
        lord_sb = sb.get(h_lord, {})
        lines.append(
            f"- House {h} (Lord: {h_lord} - {lord_sb.get('pct', 100)}% {lord_sb.get('verdict', 'MODERATE')}): "
            f"Bhava Bala Rank {h_info.get('rank', 6)}/12 — VERDICT: {h_info.get('verdict', 'MODERATE')} | "
            f"SAV: {h_sav.get('points', 28)} pts — VERDICT: {h_sav.get('verdict', 'MODERATE BUFFER')}"
        )
    lines.append("")

    # Section 2: Key Planetary Engines
    lines.append("[2. KEY PLANETARY ENGINES (SHADBALA VERDICTS)]")
    for p_name in cfg["key_planets"]:
        p_sb = sb.get(p_name, {})
        lines.append(f"- {p_name}: {p_sb.get('pct', 100)}% of required Shadbala — VERDICT: {p_sb.get('verdict', 'MODERATE')}")
    lines.append("")

    # Section 3: Active Transit Weather
    lines.append("[3. ACTIVE TRANSIT WEATHER (WITH BAV BINDUS & VERDICTS)]")
    target_houses = set(cfg["primary_houses"])
    transit_lines = []
    for p_name in ["Jupiter", "Saturn", "Rahu", "Mars", "Sun", "Mercury", "Venus"]:
        if p_name in transit_dict:
            tp = transit_dict[p_name]
            t_sign_idx = tp["sign_idx"]
            h_asc = (t_sign_idx - asc_sign_idx) % 12 + 1
            h_moon = (t_sign_idx - moon_sign_idx) % 12 + 1
            if h_asc in target_houses or h_moon in target_houses or p_name in ["Jupiter", "Saturn", "Rahu"]:
                b_info = tb_v.get(p_name, {})
                pts = b_info.get("bindus", 4)
                v_text = b_info.get("verdict", "MODERATE")
                rx_str = " (Rx)" if tp.get("status") == "Rx" else ""
                transit_lines.append(
                    f"- {p_name}{rx_str} in House {h_asc} from Lagna / House {h_moon} from Moon: "
                    f"Individual BAV = {pts}/8 — VERDICT: {v_text}"
                )
    if not transit_lines:
        transit_lines.append("- Transit weather is balanced across active domain houses.")
    lines.append("\n".join(transit_lines) + "\n")

    # Section 4: Cognitive & Emotional Weather
    lines.append("[4. COGNITIVE & EMOTIONAL WEATHER]")
    lines.append(f"- Mercury Combustion Distance: {mc_v.get('distance_deg', 10.0)}° from Sun — VERDICT: {mc_v.get('verdict', 'CLEAR')}")

    return "\n".join(lines)


def build_health_factsheet(
    chart_data: Dict[str, Any],
    verdicts: Dict[str, Any],
    dasha_data: Dict[str, Any],
    transit_dict: Dict[str, Any],
    asc_sign_idx: int,
    moon_sign_idx: int
) -> str:
    """Wrapper ensuring 100% backwards compatibility with health-specific callers."""
    return build_topic_factsheet("health", chart_data, verdicts, dasha_data, transit_dict, asc_sign_idx, moon_sign_idx)


def validate_and_sanitize_reading(raw_text: str, workflow_key: str = "general") -> Tuple[bool, str, str, str]:
    """
    Deterministic validator:
    1. Extracts <data_audit> and <reading>.
    2. Enforces word count limits (strictly under 240 words for standard, up to 300 for predictor_2027).
    3. Scans for banned superstitions, lazy wellness clichés, and raw astrological jargon.
    Returns: (is_valid, error_reason, reading_text, audit_text)
    """
    if not raw_text:
        return False, "Response was empty.", "", ""

    audit_match = re.search(r'<data_audit>(.*?)</data_audit>', raw_text, re.DOTALL | re.IGNORECASE)
    audit_text = audit_match.group(1).strip() if audit_match else ""

    # Check for unclosed <reading> tag (indicates truncation before finish)
    if re.search(r'<reading>', raw_text, re.IGNORECASE) and not re.search(r'</reading>', raw_text, re.IGNORECASE):
        return False, "Reading was cut off or truncated before completion (unclosed <reading> tag).", "", audit_text

    reading_match = re.search(r'<reading>(.*?)</reading>', raw_text, re.DOTALL | re.IGNORECASE)
    if reading_match:
        reading_text = reading_match.group(1).strip()
    else:
        # If <data_audit> was present but <reading> tags missing, take text following </data_audit>
        if audit_match:
            parts = re.split(r'</data_audit>', raw_text, flags=re.IGNORECASE)
            reading_text = parts[-1].strip() if len(parts) > 1 else raw_text.strip()
        else:
            reading_text = raw_text.strip()

    # Clean residual markup
    reading_text = re.sub(r'</?(?:data_audit|reading)>', '', reading_text, flags=re.IGNORECASE).strip()

    word_count = len(reading_text.split())
    max_words = 315 if workflow_key == "predictor_2027" else 250
    min_words = 60

    # 1. Check banned superstitions
    for pat in BANNED_SUPERSTITION_PATTERNS:
        m = re.search(pat, reading_text, re.IGNORECASE)
        if m:
            return False, f"Contains banned superstitious/remedial term: '{m.group(0)}'", reading_text, audit_text

    # 2. Check banned lazy wellness clichés
    for pat in BANNED_WELLNESS_PATTERNS:
        m = re.search(pat, reading_text, re.IGNORECASE)
        if m:
            return False, f"Contains banned generic wellness cliché: '{m.group(0)}'", reading_text, audit_text

    # 3. Check raw astrological code leaks
    for pat in BANNED_CODE_PATTERNS:
        m = re.search(pat, reading_text, re.IGNORECASE)
        if m:
            return False, f"Contains un-translated astrological jargon or code marker: '{m.group(0)}'", reading_text, audit_text

    # 4. Length checks
    if word_count > max_words:
        return False, f"Length limit exceeded: {word_count} words (strict limit is {max_words - 10} words)", reading_text, audit_text

    if word_count < min_words:
        return False, f"Reading truncated or too short: {word_count} words", reading_text, audit_text

    # 5. Terminal punctuation check (catch sentences cut off mid-word)
    if reading_text and reading_text[-1] not in '.!?"\')':
        return False, f"Reading appears truncated mid-sentence (ends with '{reading_text[-15:]}').", reading_text, audit_text

    return True, "", reading_text, audit_text


def generate_deterministic_fallback_reading(
    chart_data: Dict[str, Any],
    verdicts: Dict[str, Any],
    workflow_key: str = "general",
    user_question: str = ""
) -> str:
    """
    Fallback safety net: Emits a polished, chart-grounded, professional reading based on Python's machine verdicts.
    Guarantees the kiosk never crashes, never freezes, and never outputs banned phrases across any workflow.
    """
    sb = verdicts.get("shadbala", {})
    hv = verdicts.get("houses", {})
    sun_sb = sb.get("Sun", {}).get("pct", 100)
    jup_sb = sb.get("Jupiter", {}).get("pct", 100)
    sat_sb = sb.get("Saturn", {}).get("pct", 100)
    ven_sb = sb.get("Venus", {}).get("pct", 100)
    h10 = hv.get(10, {})
    h2 = hv.get(2, {})
    h7 = hv.get(7, {})
    lagna_h = hv.get(1, {})

    if workflow_key == "health":
        vitality_phrase = "operates with steady natural stamina" if sun_sb >= 100 else "calls for deliberate physical pacing"
        recovery_phrase = "rebounds smoothly with consistent daily discipline" if lagna_h.get("rank", 6) <= 6 else "requires conscious protection against sudden overexertion"
        p1 = (
            f"Over the coming 90 days, your vitality {vitality_phrase} while your overall physical recovery {recovery_phrase}. "
            f"Your constitutional foundation provides reliable underlying resilience, meaning your stamina holds up well during focused efforts "
            f"provided you avoid sudden spikes of chronic exhaustion. Rather than pushing through fatigue, aligning your daily rhythms with "
            f"predictable work-rest intervals ensures sustained productivity without depleting your physical reserves."
        )
        p2 = (
            f"To protect your mental clarity and metabolic equilibrium right now, prioritize consistent meal timing and defend a non-negotiable "
            f"evening wind-down window. Structure demanding cognitive workloads into dedicated morning focus blocks, and avoid multitasking "
            f"across late evening hours. Treating deliberate rest intervals as an essential component of your daily routine keeps your vitality "
            f"at peak performance throughout this 90-day phase."
        )
        return f"{p1}\n\n{p2}"

    elif workflow_key in ["career", "generic_career"]:
        authority_phrase = "operates with strong authority and upward leverage" if h10.get("rank", 6) <= 6 else "calls for strategic consolidation and disciplined execution"
        discipline_phrase = "rewards structured responsibility and proven capability" if sat_sb >= 100 else "demands deliberate patience when navigating team dynamics"
        p1 = (
            f"Over the coming 3 to 6 months, your professional momentum {authority_phrase}, anchored by your foundational career baseline. "
            f"Current planetary weather {discipline_phrase}, indicating that demonstrating dependable competence and solving high-impact problems "
            f"will open more doors than forcing premature transitions. Your underlying drive remains capable of handling increased responsibility "
            f"provided you channel your energy into visible, measurable deliverables."
        )
        p2 = (
            f"To maximize your career trajectory and safeguard your professional reputation right now, focus on transparent stakeholder alignment "
            f"and avoid uncalculated confrontations across team boundaries. Verify all written commitments and contract details thoroughly before "
            f"making major directional moves. Maintaining consistent daily execution while steering clear of workplace friction ensures your authority "
            f"grows steadily throughout this cycle."
        )
        return f"{p1}\n\n{p2}"

    elif workflow_key == "wealth":
        wealth_phrase = "points to steady cash flow retention and compounding stability" if h2.get("rank", 6) <= 6 else "calls for disciplined liquidity management and budget guardrails"
        growth_phrase = "favors structured, long-term capital preservation" if jup_sb >= 100 else "advises against speculative acceleration or impulsive spending"
        p1 = (
            f"Over the coming months, your financial outlook {wealth_phrase}, supported by your underlying material foundation. "
            f"Your chart indicates reliable capacity for capital accumulation, meaning steady efforts compound effectively provided you avoid "
            f"unnecessary leaks in non-essential expenditures. This is a favorable phase for building financial security through methodical savings "
            f"rather than chasing high-risk windfalls."
        )
        p2 = (
            f"To protect your net worth and maintain healthy liquidity right now, establish clear spending limits and defend an emergency cash reserve. "
            f"Pace major acquisitions deliberately and resist the temptation to make speculative investments during emotionally volatile market cycles. "
            f"Focusing on debt reduction, capital retention, and methodical budgeting will ensure your financial resilience expands steadily across this window."
        )
        return f"{p1}\n\n{p2}"

    elif workflow_key in ["relationships", "marriage"]:
        rel_phrase = "centers on harmonious mutual understanding and shared alignment" if h7.get("rank", 6) <= 6 else "calls for conscious emotional patience and healthy communication boundaries"
        grace_phrase = "supports deeper emotional bonding when expectations are clearly voiced" if ven_sb >= 100 else "counsels against assuming feelings or letting silent grievances build"
        p1 = (
            f"Over the coming months, your relationship environment {rel_phrase}, supported by your underlying partnership foundation. "
            f"Planetary influences indicate that mutual respect and emotional connection grow steadily provided both partners communicate with "
            f"openness and vulnerability. This phase {grace_phrase}, making honest and mature dialogue your strongest tool for lasting harmony."
        )
        p2 = (
            f"To navigate interpersonal rhythms constructively right now, give each other space during high-pressure work weeks and address emerging "
            f"misunderstandings early before they escalate. Practice active listening rather than reacting defensively during sensitive discussions. "
            f"Prioritizing calm mutual appreciation and shared quality time will keep your connection grounded and resilient throughout this period."
        )
        return f"{p1}\n\n{p2}"

    else:
        p1 = (
            f"Over the coming months, your life momentum operates on a dependable foundation that supports steady progress when your efforts "
            f"are channeled into clear, singular priorities. Your chart reveals strong underlying resilience, indicating that you have the stamina "
            f"and focus to handle demanding circumstances as long as you pace yourself deliberately and avoid spreading your energy across too many "
            f"competing commitments simultaneously."
        )
        p2 = (
            f"To navigate this period with maximum effectiveness right now, establish structured daily habits and protect your focus against "
            f"unproductive distractions. Verify important details thoroughly before finalizing major life decisions, and approach new opportunities "
            f"with measured discernment. Maintaining consistent personal discipline and patience will ensure your long-term goals advance securely."
        )
        return f"{p1}\n\n{p2}"


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
    provider, api_key = _get_api_credentials()
    if not api_key:
        raise ValueError("API Key not found. Please set ANTHROPIC_API_KEY or DEEPSEEK_API_KEY in environment or secrets.")

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
    sav = ashtakavarga_data.get("Sarvashtakavarga") or ashtakavarga_data.get("SAV", {})
    bav = ashtakavarga_data.get("Bhinnashtakavarga", {})

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

    # Transit combustion check
    for p in ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        if p in transit_dict:
            transit_dict[p]["combustion"] = (get_combustion_status(p, transit_dict) == "Combust")

    gochar_string = "### LIVE PLANETARY TRANSITS (GOCHAR)\n"
    for p_name in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]:
        tp = transit_dict[p_name]
        sign_now_idx = tp["sign_idx"]
        deg_now = tp["degree_total"]
        rx_tag = " (Rx)" if tp["status"] == "Rx" else ""
        comb_tag = " [COMBUST]" if tp.get("combustion") else ""
        h_asc = (sign_now_idx - asc_sign_idx) % 12 + 1
        h_moon = (sign_now_idx - moon_sign_idx) % 12 + 1
        rashi_key = sign_now_idx + 1
        t_sav = sav.get(rashi_key, 28)
        p_bav = bav.get(p_name, {}).get(rashi_key, 4)
        sav_label = "Strong" if t_sav >= 28 else ("Average" if t_sav >= 25 else "Low")
        bav_label = "High Support" if p_bav >= 5 else ("Moderate" if p_bav == 4 else "Acute Friction")
        gochar_string += (
            f"{p_name}{rx_tag}{comb_tag}: {RASHI_NAMES[sign_now_idx]} ({deg_now % 30:.2f}°) "
            f"[SAV: {t_sav} ({sav_label}) | BAV: {p_bav}/8 ({bav_label})] — "
            f"House {h_asc} from Lagna, House {h_moon} from Moon\n"
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

    # Filter active auspicious yogas (ban negative yogas like Kemadruma, Daridra, Visha, Grahan, Shakata, Dainya)
    BANNED_YOGA_KEYWORDS = {"kemadruma", "daridra", "visha", "grahan", "shakata", "guru chandal", "dainya"}
    active_yogas_list = [
        {
            "name": clean_yoga_title(y["name"]),
            "original_name": y["name"],
            "meaning": get_yoga_user_meaning(y["name"], y.get("desc", "")),
            "category": y.get("category", "Auspicious Yoga"),
            "timing": y.get("timing", "Active in current life period"),
            "desc": y.get("desc", ""),
            "planets": y.get("planets", [])
        }
        for y in yoga_activation
        if y.get("active") and not any(b in y["name"].lower() for b in BANNED_YOGA_KEYWORDS)
    ]

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

    # 15. Vedic Doshas (Kaal Sarp, Manglik, Pitra)
    doshas_data = calculate_doshas(chart_data, birth_dt=utc_dt)
    doshas_string = format_doshas_for_prompt(doshas_data)

    # Pre-calculate machine verdicts across all metrics
    verdicts = compute_astrological_verdicts(
        chart_data=chart_data,
        bb_data=bb_data,
        sav=sav,
        bav=bav,
        transit_dict=transit_dict,
        dasha_data=dasha_data,
        moon_details=moon_details
    )

    # Workflows classification
    workflow_key = classify_workflow(user_question)
    current_date = now_utc.strftime("%d %B %Y")

    # Build domain-specific factsheet with machine verdicts
    topic_factsheet = build_topic_factsheet(
        workflow_key=workflow_key,
        chart_data=chart_data,
        verdicts=verdicts,
        dasha_data=dasha_data,
        transit_dict=transit_dict,
        asc_sign_idx=asc_sign_idx,
        moon_sign_idx=moon_sign_idx
    )

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
        "{doshas_string}": doshas_string,
        "{topic_factsheet}": topic_factsheet,
        "{health_factsheet}": topic_factsheet,
        "{current_date}": current_date,
    }

    # For Health: strictly clamp Dasha timeline to the immediate 90-day window
    if workflow_key == "health":
        dasha_string_health = (
            f"### ACTIVE 90-DAY VITALITY TIMELINE (PRATYANTARDASHA)\n"
            f"Current Antardasha: {current_antardasha} (Began: {dasha_data.get('ad_start')} | Ends: {dasha_data.get('ad_end')})\n"
            f"Active Pratyantardasha: {current_pd} (Began: {dasha_data.get('pd_start')} | Ends: {dasha_data.get('pd_end')})\n"
            f"Active 90-Day Vitality Window: {dasha_data.get('pd_start')} to {dasha_data.get('pd_end')}\n"
            f"NOTE: Focus 100% on this immediate 90-day window. Long-term multi-year cycles are suppressed for health pacing.\n"
        )
        replacements["{dasha_string}"] = dasha_string_health

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
        "5. STRICT BREVITY & CONCISENESS (NON-NEGOTIABLE ANTI-FATIGUE RULE): The user is reading this on a screen at an event kiosk. Sprawling essays cause immediate reading fatigue. Deliver maximum astrological clarity in the shortest, crispest possible form. For standard questions: EXACTLY 2 short, punchy paragraphs (approx 90–120 words each; strictly under 240 words total). For 4-quarter year ahead questions: exactly 1 crisp sentence for '✦ Where to Push' and 1 crisp sentence for '▲ Where to Steer with Care' per quarter (strictly under 300 words total). Zero filler, zero repetition, zero academic throat-clearing. Cut straight to actionable guidance.\n"
        "6. STRICT ZERO-TOLERANCE ON BANNED REMEDIES & TROPES: Absolute ban on temple visits, pujas, dal/food donations, cow/bird feeding, copper coins, gemstones, splashing water on the face, 8 glasses of water, 15 minutes of sunlight, or generic meditation. All advice must be practical cause-and-effect lifestyle/workload pacing directly tied to active transit friction.\n"
    )

    system_prompt += "\n\n### HOUSE SUPPORT INDICATORS (BHAVA BALA)\n" + bhava_bala_string

    user_prompt = f"The native asks: <question>{user_question}</question>"
    if active_yogas_list:
        active_names = ", ".join([y["name"] for y in active_yogas_list])
        user_prompt += f"\n\nACTIVE AUSPICIOUS YOGAS IN EFFECT: [{active_names}]. Explicitly name and weave the native's active yoga into the opening cosmic fuel / opportunity analysis as their primary engine of promise."
    if workflow_key == "predictor_2027":
        user_prompt += (
            "\n\nEXECUTION PROTOCOL (MANDATORY): "
            "1. Output <data_audit> completing the 4-task internal worksheet based on the pre-computed machine verdicts in {topic_factsheet}. "
            "2. Output <reading> delivering the structured 4-Quarter Milestone Blueprint (Q1, Q2, Q3, Q4) with exactly 1 crisp sentence for '✦ Where to Push' and 1 crisp sentence for '▲ Where to Steer with Care' for each quarter, as specified in the 2027 Milestone Blueprint. Total reading strictly under 300 words. "
            "Translate all astrological verdicts into natural, mature human advice. NEVER write technical terms like SAV, BAV, Shadbala, Bhava Bala, bindus, or dasha abbreviations inside <reading>."
        )
    elif workflow_key == "health":
        user_prompt += (
            "\n\nEXECUTION PROTOCOL (MANDATORY): "
            "1. Output <data_audit> completing all 4 tasks based on the pre-computed machine verdicts in {topic_factsheet}. "
            "2. Output <reading> with EXACTLY 2 punchy, jargon-free paragraphs (strictly under 240 words total). "
            "Translate all astrological verdicts into natural, mature human advice. NEVER write technical terms like SAV, BAV, Shadbala, Bhava Bala, bindus, or dasha abbreviations inside <reading>. "
            "3. Anchor strictly to the 90-day window. Zero mention of temples, dal donations, gemstones, or water splashing."
        )
    else:
        user_prompt += (
            "\n\nEXECUTION PROTOCOL (MANDATORY): "
            "1. Output <data_audit> completing all 4 tasks concisely (brief bullet lines, strictly under 200 words total) based on the pre-computed machine verdicts in {topic_factsheet}. "
            "2. Output <reading> with EXACTLY 2 punchy, jargon-free paragraphs (strictly under 240 words total). "
            "Translate all astrological verdicts into natural, mature human advice. NEVER write technical terms like SAV, BAV, Shadbala, Bhava Bala, bindus, or dasha abbreviations inside <reading>. "
            "3. Ground all timing in verified planetary windows (next 1–3 months, 3–8 months). Zero mention of superstitious rituals, donations, or generic wellness tropes."
        )

    # Internal LLM execution helper
    def _execute_llm_call(sys_p: str, usr_p: str) -> str:
        if provider == "anthropic":
            anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
            ant_client = anthropic.Anthropic(api_key=api_key)
            max_tok = 2200
            ant_kwargs = {
                "model": anthropic_model,
                "system": sys_p,
                "messages": [
                    {"role": "user", "content": usr_p}
                ],
                "max_tokens": max_tok
            }
            # Newer Anthropic models (e.g. claude-sonnet-5) deprecate the temperature parameter
            if "sonnet-5" not in anthropic_model and "opus-4" not in anthropic_model:
                ant_kwargs["temperature"] = 0.65
            else:
                ant_kwargs["thinking"] = {"type": "disabled"}
            resp = ant_client.messages.create(**ant_kwargs)
            return "".join([b.text for b in resp.content if getattr(b, "type", "") == "text" or (hasattr(b, "text") and not hasattr(b, "thinking"))]).strip() if resp.content else ""
        else:
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            max_tok = 2000
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": sys_p},
                    {"role": "user", "content": usr_p}
                ],
                temperature=0.65,
                presence_penalty=0.25,
                frequency_penalty=0.2,
                max_tokens=max_tok
            )
            return resp.choices[0].message.content or ""

    # Attempt 1
    raw_response = _execute_llm_call(system_prompt, user_prompt)
    is_valid, err_reason, clean_reading, audit_text = validate_and_sanitize_reading(raw_response, workflow_key)

    if not is_valid:
        logger.warning(f"Kiosk Reading Attempt 1 rejected ({err_reason}). Initiating Retry 1...")
        retry_prompt = (
            user_prompt +
            f"\n\nCRITICAL QUALITY REJECTION (PREVIOUS ATTEMPT FAILED): [{err_reason}]. "
            f"You MUST rewrite immediately respecting these non-negotiable rules: "
            f"1. You must complete <data_audit> first. "
            f"2. You must output <reading> with EXACTLY 2 short paragraphs strictly under 240 words. "
            f"3. ZERO superstitious remedies (no temples, no dal/food donations, no gemstones). "
            f"4. ZERO generic self-help clichés (no splashing water, no 8 glasses of water, no morning sunlight, no generic meditation). "
            f"5. ZERO raw astrological jargon or code leaks like (Rx) or [COMBUST]."
        )
        try:
            raw_response_2 = _execute_llm_call(system_prompt, retry_prompt)
            is_valid_2, err_reason_2, clean_reading_2, audit_text_2 = validate_and_sanitize_reading(raw_response_2, workflow_key)
            if is_valid_2:
                clean_reading = clean_reading_2
                audit_text = audit_text_2
                logger.info("Kiosk Reading Attempt 2 succeeded after retry.")
            else:
                logger.error(f"Kiosk Reading Attempt 2 failed: {err_reason_2}. Activating deterministic fallback reading.")
                clean_reading = generate_deterministic_fallback_reading(chart_data, verdicts, workflow_key, user_question)
                audit_text = f"Deterministic fallback activated. Errors: Attempt 1 ({err_reason}) | Attempt 2 ({err_reason_2})"
        except Exception as retry_exc:
            logger.exception(f"Exception during LLM retry: {retry_exc}. Using deterministic fallback.")
            clean_reading = generate_deterministic_fallback_reading(chart_data, verdicts, workflow_key, user_question)
            audit_text = f"Deterministic fallback activated due to retry exception: {retry_exc}"

    from nakshatra_archetypes import get_nakshatra_archetype
    moon_nak = chart_data["Moon"]["nakshatra"]
    nak_deity = get_nakshatra_archetype(moon_nak)

    return {
        "name": name,
        "ascendant": asc_sign,
        "moon_sign": chart_data["Moon"]["sign"],
        "sun_sign": chart_data["Sun"]["sign"],
        "nakshatra": moon_nak,
        "nakshatra_deity": nak_deity["deity"],
        "archetype_title": nak_deity["deity"],
        "life_focus": nak_deity["blessing_message"],
        "blessing_message": nak_deity["blessing_message"],
        "atmakaraka": atmakaraka,
        "current_dasha": f"{current_mahadasha} - {current_antardasha}" if current_antardasha else current_mahadasha,
        "doshas": doshas_data["summary"],
        "active_yogas": active_yogas_list,
        "reading": clean_reading,
        "data_audit": audit_text,
        "workflow": workflow_key,
        "timestamp": datetime.now().isoformat()
    }

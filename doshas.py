"""
doshas.py - Classical & Modern Vedic Astrological Dosha Calculation Suite
========================================================================

A modular, standalone engine providing mathematically rigorous and classical
evaluations for:
1. Kaal Sarp Dosha (Full, Anshik/Partial, Savya/Apsavya, 12 Nodal Types)
2. Manglik Dosha / Kuja Dosha (Lagna, Moon, Venus references, South Indian H2 option,
   classical BPHS cancellations, and planetary age maturity mitigations)
3. Pitra Dosha (Sun, 9th House, 9th Lord afflictions by Rahu, Ketu, and Saturn)

House System:
-------------
All calculations strictly adhere to the Whole-Sign (Rashi) House System,
consistent with classical Parashari principles.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ============================================================================
# CONSTANTS & LOOKUP MATRICES
# ============================================================================

# Version tracking for API consumers and caching deprecation
RUBRIC_VERSION = "2026.09-v2"

RASHI_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

# 7 Physical Grahas evaluated for Kaal Sarp hemming
PHYSICAL_PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]

# 12 Classical Kaal Sarp Types by Rahu's Whole-Sign House placement
KALSARPA_TYPES: Dict[int, Dict[str, Any]] = {
    1: {
        "name": "Anant",
        "rahu_house": 1,
        "ketu_house": 7,
        "significance": "Self, identity, health, marital delays, personal struggle and eventual spiritual awakening."
    },
    2: {
        "name": "Kulik",
        "rahu_house": 2,
        "ketu_house": 8,
        "significance": "Family wealth, speech, domestic friction, financial volatility, and unexpected expenditures."
    },
    3: {
        "name": "Vasuki",
        "rahu_house": 3,
        "ketu_house": 9,
        "significance": "Siblings, courage, self-initiative, strained relationship with father, and travel hurdles."
    },
    4: {
        "name": "Shankhapal",
        "rahu_house": 4,
        "ketu_house": 10,
        "significance": "Domestic peace, mother's health, real estate hurdles, mental restlessness, and career stress."
    },
    5: {
        "name": "Padma",
        "rahu_house": 5,
        "ketu_house": 11,
        "significance": "Education, intellect, childbearing delays, speculative risks, and creative blocks."
    },
    6: {
        "name": "Mahapadma",
        "rahu_house": 6,
        "ketu_house": 12,
        "significance": "Debts, litigation, hidden adversaries, digestive issues, followed by immense competitive victory."
    },
    7: {
        "name": "Takshak",
        "rahu_house": 7,
        "ketu_house": 1,
        "significance": "Marriage friction, business partnership volatility, delayed settling down, and strong public desires."
    },
    8: {
        "name": "Karkotak",
        "rahu_house": 8,
        "ketu_house": 2,
        "significance": "Sudden setbacks, inheritance disputes, hidden occult abilities, and volatile ancestral ties."
    },
    9: {
        "name": "Shankhachur",
        "rahu_house": 9,
        "ketu_house": 3,
        "significance": "Dharma, philosophical doubt, father's fortunes, luck arriving only through relentless self-effort."
    },
    10: {
        "name": "Ghatak",
        "rahu_house": 10,
        "ketu_house": 4,
        "significance": "Career turbulence, political / executive friction, public reputation swings, and parental burdens."
    },
    11: {
        "name": "Vishdhar",
        "rahu_house": 11,
        "ketu_house": 5,
        "significance": "Fluctuating cash flow, strained elder sibling ties, unfulfilled desires, and eye/memory strain."
    },
    12: {
        "name": "Sheshnag",
        "rahu_house": 12,
        "ketu_house": 6,
        "significance": "Subconscious anxiety, heavy expenditures, foreign relocation, isolation, and deep spiritual liberation."
    }
}

# Sign ownership map
SIGN_LORDS = {
    0: "Mars", 1: "Venus", 2: "Mercury", 3: "Moon",
    4: "Sun", 5: "Mercury", 6: "Venus", 7: "Mars",
    8: "Jupiter", 9: "Saturn", 10: "Saturn", 11: "Jupiter"
}

# Conjunction tolerance on the nodal axis (1.5 degrees)
NODE_CONJUNCT_ORB_DEG = 1.5


# ============================================================================
# CUSTOM EXCEPTIONS FOR ROBUST REST API CONSUMPTION
# ============================================================================

class DoshaCalculationError(Exception):
    """Base exception for dosha calculation failures."""
    pass


class MissingChartDataError(DoshaCalculationError):
    """Raised when required planetary or chart data is missing from chart_data."""
    pass


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _normalize_deg(deg: float) -> float:
    """Normalize angle to [0.0, 360.0)."""
    return float(deg) % 360.0


def _angular_dist(deg1: float, deg2: float) -> float:
    """Shortest angular distance between two points on the circle [0, 180]."""
    diff = abs(_normalize_deg(deg1) - _normalize_deg(deg2))
    return 360.0 - diff if diff > 180.0 else diff


def _get_house_from_sign_idx(ref_sign_idx: int, target_sign_idx: int) -> int:
    """Whole-Sign house calculation (1-indexed)."""
    return ((target_sign_idx - ref_sign_idx) % 12) + 1


def _extract_body_data(chart_data: Dict[str, Any], body_name: str) -> Dict[str, Any]:
    """Gracefully extracts body data from chart_data with typed custom error."""
    if body_name in chart_data:
        return chart_data[body_name]
    # Check case-insensitive match
    for k, v in chart_data.items():
        if k.strip().lower() == body_name.strip().lower():
            return v
    raise MissingChartDataError(f"Missing required planetary body '{body_name}' in chart_data.")


# ============================================================================
# 1. KAAL SARP DOSHA ENGINE
# ============================================================================

def check_kaalsarp_dosha(chart_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculates Kaal Sarp Dosha with strict classical fidelity and modern extensions.

    Classical Definition:
    ---------------------
    All 7 physical grahas (Sun through Saturn) must be hemmed inside the 180-degree
    arc between Rahu and Ketu.

    Mathematical Hemisphere Rule:
    -----------------------------
    For each planet longitude L_p, calculate delta from Rahu:
        delta = (L_p - L_Rahu) % 360
    - If 0 <= delta < 180: Planet is in the Rahu->Ketu arc (Arc 1).
    - If 180 <= delta < 360: Planet is in the Ketu->Rahu arc (Arc 2).

    Boundary / Orb Rule:
    --------------------
    If a planet is within NODE_CONJUNCT_ORB_DEG (1.5°) of either Rahu or Ketu,
    it is classified as conjunct the node and considered hemmed with the majority.

    Direction Rule (Savya vs Apsavya):
    ----------------------------------
    Since planetary longitude advances eastward (Aries -> Taurus -> ...):
    - When planets occupy the Ketu->Rahu arc, their natural eastward progression
      leads directly into the mouth of the serpent (Rahu). This is Savya (Udit) Kaal Sarp.
    - When planets occupy the Rahu->Ketu arc, their natural eastward progression
      leads towards the tail (Ketu). This is Apsavya (Anudit) Kaal Sarp.
    """
    rahu_data = _extract_body_data(chart_data, "Rahu")
    rahu_deg = _normalize_deg(rahu_data["degree_total"])

    # Resolve Ketu (prefer stored, fallback to exact opposite)
    if "Ketu" in chart_data:
        ketu_deg = _normalize_deg(chart_data["Ketu"]["degree_total"])
    else:
        ketu_deg = _normalize_deg(rahu_deg + 180.0)

    # Ascendant sign index for whole-sign house of Rahu
    asc_data = _extract_body_data(chart_data, "Ascendant")
    asc_sign_idx = int(asc_data["sign_idx"])
    rahu_sign_idx = int(rahu_data["sign_idx"])
    rahu_house = _get_house_from_sign_idx(asc_sign_idx, rahu_sign_idx)
    ketu_house = ((rahu_house + 6 - 1) % 12) + 1

    arc1_planets: List[str] = []  # Rahu -> Ketu (0 to 180)
    arc2_planets: List[str] = []  # Ketu -> Rahu (180 to 360)
    boundary_planets: List[Dict[str, Any]] = []

    planet_positions: Dict[str, Dict[str, Any]] = {}

    for p in PHYSICAL_PLANETS:
        p_data = _extract_body_data(chart_data, p)
        p_deg = _normalize_deg(p_data["degree_total"])

        dist_rahu = _angular_dist(p_deg, rahu_deg)
        dist_ketu = _angular_dist(p_deg, ketu_deg)

        is_conjunct_node = (dist_rahu <= NODE_CONJUNCT_ORB_DEG) or (dist_ketu <= NODE_CONJUNCT_ORB_DEG)
        nearest_node = "Rahu" if dist_rahu <= dist_ketu else "Ketu"
        node_dist = dist_rahu if nearest_node == "Rahu" else dist_ketu

        delta_from_rahu = (p_deg - rahu_deg) % 360.0

        if delta_from_rahu < 180.0:
            assigned_arc = "Rahu_to_Ketu"
            arc1_planets.append(p)
        else:
            assigned_arc = "Ketu_to_Rahu"
            arc2_planets.append(p)

        if is_conjunct_node:
            boundary_planets.append({
                "planet": p,
                "node": nearest_node,
                "orb_deg": round(node_dist, 2)
            })

        planet_positions[p] = {
            "degree_total": round(p_deg, 2),
            "sign": p_data.get("sign", RASHI_NAMES[int(p_deg // 30)]),
            "house": p_data.get("house", _get_house_from_sign_idx(asc_sign_idx, int(p_deg // 30))),
            "delta_from_rahu": round(delta_from_rahu, 2),
            "assigned_arc": assigned_arc,
            "is_conjunct_node": is_conjunct_node
        }

    # Count distribution
    c1 = len(arc1_planets)
    c2 = len(arc2_planets)

    # Resolve boundary edge case: if 6 planets are in one arc and the 7th is conjunct a node,
    # the 7th planet is held captive on the axis, creating full closure.
    escaped_planet: Optional[str] = None
    is_classical = False
    is_present = False
    classification = "None"
    direction = "None"
    direction_desc = ""

    if c1 == 7 or c2 == 7:
        is_present = True
        is_classical = True
        classification = "Full Kaal Sarp Dosha"
        occupied_arc = "Rahu_to_Ketu" if c1 == 7 else "Ketu_to_Rahu"
    elif c1 == 6 and c2 == 1:
        # Check if the single planet in Arc 2 is conjunct a node
        odd_planet = arc2_planets[0]
        if planet_positions[odd_planet]["is_conjunct_node"]:
            is_present = True
            is_classical = True
            classification = "Full Kaal Sarp Dosha (On-Axis Closure)"
            occupied_arc = "Rahu_to_Ketu"
        else:
            is_present = True
            is_classical = False
            escaped_planet = odd_planet
            classification = "Partial / Anshik Kaal Sarp (Modern Interpretation)"
            occupied_arc = "Rahu_to_Ketu"
    elif c2 == 6 and c1 == 1:
        # Check if the single planet in Arc 1 is conjunct a node
        odd_planet = arc1_planets[0]
        if planet_positions[odd_planet]["is_conjunct_node"]:
            is_present = True
            is_classical = True
            classification = "Full Kaal Sarp Dosha (On-Axis Closure)"
            occupied_arc = "Ketu_to_Rahu"
        else:
            is_present = True
            is_classical = False
            escaped_planet = odd_planet
            classification = "Partial / Anshik Kaal Sarp (Modern Interpretation)"
            occupied_arc = "Ketu_to_Rahu"
    else:
        is_present = False
        is_classical = False
        classification = "None"
        occupied_arc = "None"

    # Direction Determination
    if is_present:
        if occupied_arc == "Ketu_to_Rahu":
            direction = "Savya (Udit / Direct Progression to Rahu)"
            direction_desc = (
                "Planets are placed between Ketu and Rahu; as longitudes increase, "
                "planets advance directly towards the mouth of the dragon (Rahu). "
                "Considered more intense and externally transformative."
            )
        else:
            direction = "Apsavya (Anudit / Progression to Ketu)"
            direction_desc = (
                "Planets are placed between Rahu and Ketu; as longitudes increase, "
                "planets advance away from Rahu towards the tail (Ketu). "
                "Tends to drive internal introspection and spiritual resolution."
            )

    type_info = KALSARPA_TYPES.get(rahu_house, {
        "name": "Unknown",
        "rahu_house": rahu_house,
        "ketu_house": ketu_house,
        "significance": ""
    })

    remedies = []
    if is_present:
        remedies = [
            "Perform Mahamrityunjaya Mantra japa (108 times daily or 125,000 count).",
            "Offer milk and sacred water during Monday Rudrabhisheka to Lord Shiva.",
            "Nag Panchami puja or Rahu-Ketu Shanti at Trimbakeshwar / Kalahasti if severely afflicted.",
            "Avoid wearing dark blue or black gemstones (like Blue Sapphire/Hessonite) without expert guidance.",
            "Feed birds and stray dogs on Saturdays / Amavasya days."
        ]

    notes = []
    if not is_classical and is_present:
        notes.append(
            "Note on Partial/Anshik Kaal Sarp: Classical Jyotish texts require all 7 physical planets "
            "to be strictly enclosed between Rahu and Ketu. One planet escaping is a popular modern "
            "astrological extension."
        )
    if boundary_planets:
        p_names = ", ".join(f"{b['planet']} ({b['orb_deg']}° from {b['node']})" for b in boundary_planets)
        notes.append(f"Planets within {NODE_CONJUNCT_ORB_DEG}° orb of nodal axis: {p_names}.")

    return {
        "rubric_version": RUBRIC_VERSION,
        "is_present": is_present,
        "is_classical": is_classical,
        "classification": classification,
        "type_name": type_info["name"] if is_present else None,
        "rahu_house": rahu_house,
        "ketu_house": ketu_house,
        "direction": direction,
        "direction_desc": direction_desc,
        "escaped_planet": escaped_planet,
        "significance": type_info["significance"] if is_present else "All planets freely dispersed; nodal axis is unobstructed.",
        "boundary_planets": boundary_planets,
        "planet_positions": planet_positions,
        "remedies": remedies,
        "notes": notes
    }


# ============================================================================
# 2. COMPREHENSIVE MANGLIK (KUJA DOSHA) ENGINE
# ============================================================================

def check_manglik_dosha(
    chart_data: Dict[str, Any],
    birth_dt: Optional[datetime] = None,
    as_of: Optional[datetime] = None,
    age_years: Optional[float] = None,
    include_2nd_house: bool = False
) -> Dict[str, Any]:
    """
    Calculates Comprehensive Manglik Dosha (Kuja Dosha) across classical and traditional
    reference points with exact cancellation matrices and deterministic age mitigation.

    Reference Points Evaluated:
    ---------------------------
    1. From Ascendant (Lagna) - Classical Primary Parashari (BPHS Santhanam recension Ch. 81 / G.C. Sharma Ch. 80)
    2. From Moon (Chandra Lagna) - Classical Secondary Parashari
    3. From Venus (Shukra) - Traditional/Experiential Practice (Karaka for spouse/vitality)

    Afflicted Houses:
    -----------------
    Standard Classical: Houses [1, 4, 7, 8, 12]
    South Indian Tradition: Houses [1, 2, 4, 7, 8, 12] (enabled when include_2nd_house=True)

    Primary vs Supplementary Semantics:
    -----------------------------------
    - Primary Manglik: Mars afflicted from Lagna or Moon.
    - Venus Reference: Evaluated as supplementary karaka evidence. A Venus-only affliction
      does not set the top-level is_manglik flag to True unless confirmed from Lagna or Moon.
    - Cancellation Distinction: If Mars occupies a Kuja house but is fully cancelled,
      has_placement is True, is_cancelled is True, and is_manglik is False (score = 0).

    Deterministic Severity Scoring Rubric (0 to 100):
    --------------------------------------------------
    Base Affliction Points:
    - Mars in afflicted house from Lagna: +40 pts
    - Mars in afflicted house from Moon: +30 pts
    - Mars in afflicted house from Venus: +20 pts
    - South Indian H2 affliction (if active): +15 pts

    Classical Cancellations vs Mitigations:
    ---------------------------------------
    - Classical Root Cancellations (Zeroing):
      * Mars in Own Sign (Aries, Scorpio) or Exalted (Capricorn)
      * Classical House-Sign Exemptions (H2 Gem/Vir, H4 Ari/Sco, H7 Can/Cap, H8 Sag/Pis, H12 Tau/Lib)
      These classically nullify the affected reference contribution at the root (raw_score = 0,
      classically_cancelled = True).
    - Secondary Mitigations (Softening Deductions):
      * Jupiter Conjunction (H1) or Aspect (H5, H7, H9) on Mars: -30 pts
      * Moon Conjunct Mars (Chandra-Mangala Yoga): -15 pts
      * Native Age >= 28 Mitigation (Mars reaches natural planetary maturity): -20 pts
      If secondary mitigations reduce an uncancelled raw score to zero, mitigated_to_zero = True.
    - is_cancelled is True if either classically_cancelled or mitigated_to_zero is True.

    Clamping & Severity Bands:
    - Final Score = max(0, min(100, raw_score - deductions))
    - Severity Bands:
      * Score == 0: "None" (No dosha or fully cancelled)
      * Score 1 to 35: "Low"
      * Score 36 to 65: "Medium"
      * Score 66 to 100: "High"
    """
    mars_data = _extract_body_data(chart_data, "Mars")
    mars_sign_idx = int(mars_data["sign_idx"])
    mars_sign = mars_data.get("sign", RASHI_NAMES[mars_sign_idx])
    mars_deg_in_sign = float(mars_data.get("degree_in_sign", mars_data["degree_total"] % 30.0))

    asc_data = _extract_body_data(chart_data, "Ascendant")
    asc_sign_idx = int(asc_data["sign_idx"])

    moon_data = _extract_body_data(chart_data, "Moon")
    moon_sign_idx = int(moon_data["sign_idx"])

    venus_data = _extract_body_data(chart_data, "Venus")
    venus_sign_idx = int(venus_data["sign_idx"])

    jup_data = _extract_body_data(chart_data, "Jupiter")
    jup_sign_idx = int(jup_data["sign_idx"])

    # Calculate Mars house from each reference point
    mars_h_lagna = _get_house_from_sign_idx(asc_sign_idx, mars_sign_idx)
    mars_h_moon = _get_house_from_sign_idx(moon_sign_idx, mars_sign_idx)
    mars_h_venus = _get_house_from_sign_idx(venus_sign_idx, mars_sign_idx)

    check_houses = [1, 4, 7, 8, 12]
    if include_2nd_house:
        check_houses.append(2)

    afflicted_from_lagna = mars_h_lagna in check_houses
    afflicted_from_moon = mars_h_moon in check_houses
    afflicted_from_venus = mars_h_venus in check_houses

    # Base raw score calculation with classical zeroing cancellations
    raw_score = 0
    factors: List[str] = []
    cancellations: List[str] = []
    mitigations: List[str] = []

    # Helper: Check if a specific reference placement is classically cancelled (zeroed out)
    def check_placement_cancellation(h: int, sign: str) -> Tuple[bool, Optional[str]]:
        if sign in ["Aries", "Scorpio"]:
            return True, f"Mars in own sign ({sign}) classically nullifies Kuja Dosha (Ruchaka / Svastha dignity)."
        if sign == "Capricorn":
            return True, "Mars exalted in Capricorn (Uchcha Graha) classically nullifies Kuja Dosha."
        if h == 2 and sign in ["Gemini", "Virgo"]:
            return True, f"Mars in 2nd house in {sign} is classically exempt from Kuja Dosha (Mercury sign exemption)."
        if h == 4 and sign in ["Aries", "Scorpio"]:
            return True, f"Mars in 4th house in {sign} is classically exempt from Kuja Dosha (Mars sign exemption)."
        if h == 7 and sign in ["Cancer", "Capricorn"]:
            return True, f"Mars in 7th house in {sign} is classically exempt from Kuja Dosha."
        if h == 8 and sign in ["Sagittarius", "Pisces"]:
            return True, f"Mars in 8th house in {sign} is classically exempt from Kuja Dosha (Jupiter sign exemption)."
        if h == 12 and sign in ["Taurus", "Libra"]:
            return True, f"Mars in 12th house in {sign} is classically exempt from Kuja Dosha (Venus sign exemption)."
        return False, None

    if afflicted_from_lagna:
        is_canc, reason = check_placement_cancellation(mars_h_lagna, mars_sign)
        if is_canc:
            cancellations.append(f"From Lagna: {reason}")
        else:
            raw_score += 40
            factors.append(f"Mars in House {mars_h_lagna} from Lagna (Classical Parashari).")

    if afflicted_from_moon:
        is_canc, reason = check_placement_cancellation(mars_h_moon, mars_sign)
        if is_canc:
            cancellations.append(f"From Moon: {reason}")
        else:
            raw_score += 30
            factors.append(f"Mars in House {mars_h_moon} from Moon (Chandra Lagna).")

    if afflicted_from_venus:
        is_canc, reason = check_placement_cancellation(mars_h_venus, mars_sign)
        if is_canc:
            cancellations.append(f"From Venus: {reason}")
        else:
            raw_score += 20
            factors.append(f"Mars in House {mars_h_venus} from Venus (Traditional Marital Karaka Practice).")

    has_placement = (afflicted_from_lagna or afflicted_from_moon or afflicted_from_venus)
    is_primary_manglik = (afflicted_from_lagna or afflicted_from_moon)
    is_venus_only = (afflicted_from_venus and not is_primary_manglik)

    # Deterministic age calculation
    effective_age: Optional[float] = None
    if age_years is not None:
        effective_age = float(age_years)
    elif birth_dt is not None:
        ref_date = as_of if as_of is not None else (datetime.now(timezone.utc) if birth_dt.tzinfo else datetime.utcnow())
        effective_age = (ref_date - birth_dt).days / 365.2425

    # -------------------------------------------------------------
    # Secondary Softening Mitigations (Applied only to uncancelled score)
    # -------------------------------------------------------------
    deductions = 0
    if raw_score > 0:
        # 1. Jupiter Aspects or Conjunction
        # Jupiter casts full Parashari sign aspects on 1st (conjunction), 5th, 7th, 9th from itself
        rel_jup_to_mars = ((mars_sign_idx - jup_sign_idx) % 12) + 1
        if rel_jup_to_mars == 1:
            mitigations.append("Jupiter is conjunct Mars (Guru-Mangala Yoga), converting aggressive heat into righteous wisdom.")
            deductions += 30
        elif rel_jup_to_mars in [5, 7, 9]:
            mitigations.append(f"Jupiter casts full classical {rel_jup_to_mars}th aspect on Mars, calming affliction.")
            deductions += 30

        # 2. Moon Conjunction
        if mars_sign_idx == moon_sign_idx:
            mitigations.append("Moon is conjunct Mars, forming auspicious Chandra-Mangala Yoga which softens Kuja Dosha.")
            deductions += 15

        # 3. Native Age >= 28 Mitigation (Mars natural planetary maturity)
        if effective_age is not None and effective_age >= 28.0:
            mitigations.append(
                f"Native age ({effective_age:.1f} yrs) exceeds Mars planetary maturity age (28 yrs). "
                "Mars's volatile impulsiveness has naturally matured into emotional stability."
            )
            deductions += 20

    final_score = max(0, min(100, raw_score - deductions)) if has_placement else 0
    classically_cancelled = has_placement and (len(cancellations) > 0) and (raw_score == 0)
    mitigated_to_zero = has_placement and (raw_score > 0) and (final_score == 0)
    is_cancelled = classically_cancelled or mitigated_to_zero

    # Traditionally, Lagna/Moon set primary Manglik status; Venus alone does not declare native Manglik
    is_effective_manglik = is_primary_manglik and (final_score > 0)

    # Classify Severity Level
    if final_score == 0:
        severity = "None"
    elif final_score <= 35:
        severity = "Low"
    elif final_score <= 65:
        severity = "Medium"
    else:
        severity = "High"

    remedies = []
    if is_effective_manglik or (has_placement and not is_cancelled and severity != "None"):
        remedies = [
            "Worship Lord Hanuman or recite the Hanuman Chalisa daily.",
            "Offer red lentils (masoor dal) or copper items in charity on Tuesdays.",
            "Kumbh Vivah (or Ark/Vishnu Vivah) prior to marriage if both partners are non-matching.",
            "Recite the Mangal Beej Mantra: 'Om Kram Kreem Kroum Sah Bhaumaya Namah' (108 times).",
            "Cultivate transparent, calm communication during partnership negotiations."
        ]

    return {
        "rubric_version": RUBRIC_VERSION,
        "is_manglik": is_effective_manglik,
        "has_placement": has_placement,
        "is_primary_manglik": is_primary_manglik,
        "is_venus_only": is_venus_only,
        "is_cancelled": is_cancelled,
        "classically_cancelled": classically_cancelled,
        "mitigated_to_zero": mitigated_to_zero,
        "effective_age": round(effective_age, 2) if effective_age is not None else None,
        "severity": severity,
        "severity_score": final_score,
        "raw_score": raw_score,
        "mars_positions": {
            "sign": mars_sign,
            "degree_in_sign": round(mars_deg_in_sign, 2),
            "house_from_lagna": mars_h_lagna,
            "house_from_moon": mars_h_moon,
            "house_from_venus": mars_h_venus
        },
        "reference_afflictions": {
            "lagna": afflicted_from_lagna,
            "moon": afflicted_from_moon,
            "venus": afflicted_from_venus
        },
        "factors": factors,
        "cancellations": cancellations,
        "mitigations": mitigations,
        "remedies": remedies,
        "rules_applied": {
            "house_2_included": include_2nd_house,
            "venus_reference": "Traditional experiential practice (Spouse Karaka - supplementary)",
            "lagna_reference": "Brihat Parasara Hora Sastra (Santhanam recension, Ch. 81 'Stri Jatakadhyaya' / G.C. Sharma Ch. 80)"
        }
    }


# ============================================================================
# 3. PITRA DOSHA ENGINE
# ============================================================================

def check_pitra_dosha(chart_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculates Pitra Dosha (Ancestral Affliction / Debt to Forefathers)
    using classical Parashari full-sign aspects and nodal conjunctions.

    Diagnostic Pillars:
    -------------------
    1. Sun (Natural Karaka of Father, Atman, and Ancestors) afflicted by Rahu, Ketu, or Saturn.
    2. 9th House (Bhava of Father, Dharma, Ancestral Lineage) afflicted by Rahu, Ketu, or Saturn
       via occupation or full Parashari drishti.
    3. 9th Lord in Dusthanas (6, 8, 12) or afflicted by Rahu, Ketu, or Saturn (via conjunction or aspect).
    4. Sun placed in 8th or 12th house while afflicted.

    Deterministic Scoring Rubric (0 to 100):
    ----------------------------------------
    - Sun conjunct Rahu or Ketu (same sign): +35 pts base (Grahan Yoga)
      + 15 pts bonus if within tight conjunction orb (<= 10.0°) -> Total 50 pts
    - Sun aspected by Rahu or Ketu (5th, 7th, or 9th Parashari drishti): +20 pts
    - Sun conjunct Saturn (Father-Son mutual hostility): +20 pts
    - Sun aspected by Saturn (3rd, 7th, 10th drishti): +15 pts
    - 9th House occupied by Rahu: +30 pts (Classical Pitra Rin)
    - 9th House occupied by Ketu: +25 pts
    - 9th House aspected by Rahu or Ketu (5th, 7th, or 9th drishti): +20 pts
    - 9th House occupied by Saturn: +20 pts
    - 9th House aspected by Saturn (3rd, 7th, 10th drishti): +15 pts
    - 9th Lord in Dusthana (6, 8, 12): +20 pts
    - 9th Lord conjunct Rahu or Ketu: +20 pts
    - 9th Lord aspected by Rahu or Ketu (5th, 7th, 9th drishti): +15 pts
    - 9th Lord conjunct Saturn: +15 pts
    - 9th Lord aspected by Saturn (3rd, 7th, 10th drishti): +15 pts

    Dual-Aspect Compounding (Bhava + Bhava Lord Reinforcement):
    -----------------------------------------------------------
    When the 9th Lord resides in the 9th House, an incoming malefic aspect (from Rahu,
    Ketu, or Saturn) strikes both the Bhava (+20 pts) and the Bhava Lord (+15 pts)
    simultaneously from the same drishti (+35 pts total). Classically (BPHS, Phaladeepika),
    an affliction striking both the vessel (Bhava) and its protector (Bhava Lord) in the
    same sign creates a reinforced, compounding affliction rather than an accidental
    double-count. This intentional compounding is explicitly documented and labeled in
    the output.

    Clamping & Severity Bands (Intentional Asymmetry vs Manglik):
    - Final Score = max(0, min(100, score))
    - While Manglik requires score == 0 for "None", Pitra Dosha evaluates cumulative ancestral
      affliction requiring score >= 25 to manifest as an active debt.
      * Score < 25: "None" (Ancestral line clear; Pitra Dosha absent)
      * Score 25 to 45: "Low"
      * Score 46 to 70: "Medium"
      * Score 71 to 100: "High"
    """
    asc_data = _extract_body_data(chart_data, "Ascendant")
    asc_sign_idx = int(asc_data["sign_idx"])

    sun_data = _extract_body_data(chart_data, "Sun")
    sun_sign_idx = int(sun_data["sign_idx"])
    sun_deg = _normalize_deg(sun_data["degree_total"])
    sun_house = _get_house_from_sign_idx(asc_sign_idx, sun_sign_idx)

    rahu_data = _extract_body_data(chart_data, "Rahu")
    rahu_sign_idx = int(rahu_data["sign_idx"])
    rahu_deg = _normalize_deg(rahu_data["degree_total"])
    rahu_house = _get_house_from_sign_idx(asc_sign_idx, rahu_sign_idx)

    if "Ketu" in chart_data:
        ketu_data = chart_data["Ketu"]
        ketu_sign_idx = int(ketu_data["sign_idx"])
        ketu_deg = _normalize_deg(ketu_data["degree_total"])
    else:
        ketu_sign_idx = (rahu_sign_idx + 6) % 12
        ketu_deg = _normalize_deg(rahu_deg + 180.0)
    ketu_house = _get_house_from_sign_idx(asc_sign_idx, ketu_sign_idx)

    saturn_data = _extract_body_data(chart_data, "Saturn")
    saturn_sign_idx = int(saturn_data["sign_idx"])
    saturn_house = _get_house_from_sign_idx(asc_sign_idx, saturn_sign_idx)

    # 9th House and 9th Lord
    ninth_sign_idx = (asc_sign_idx + 8) % 12
    ninth_lord_name = SIGN_LORDS[ninth_sign_idx]
    ninth_lord_data = _extract_body_data(chart_data, ninth_lord_name)
    ninth_lord_sign_idx = int(ninth_lord_data["sign_idx"])
    ninth_lord_house = _get_house_from_sign_idx(asc_sign_idx, ninth_lord_sign_idx)

    # Helper: Check Parashari full-sign aspects
    def has_saturn_aspect(target_sign_idx: int) -> bool:
        """Saturn aspects 3rd, 7th, 10th from itself."""
        rel = ((target_sign_idx - saturn_sign_idx) % 12) + 1
        return rel in [3, 7, 10]

    def has_nodal_aspect(node_sign_idx: int, target_sign_idx: int) -> bool:
        """
        Rahu and Ketu cast full Parashari drishti on 5th, 7th (opposition),
        and 9th signs from themselves (per BPHS and Phaladeepika Ch. 25).
        """
        rel = ((target_sign_idx - node_sign_idx) % 12) + 1
        return rel in [5, 7, 9]

    afflictions: List[str] = []
    score = 0

    # 1. Sun afflicted by Rahu / Ketu
    if sun_sign_idx == rahu_sign_idx:
        orb = _angular_dist(sun_deg, rahu_deg)
        is_tight = (orb <= 10.0)
        pts = 35 + (15 if is_tight else 0)
        score += pts
        afflictions.append(
            f"Sun is conjunct Rahu in {RASHI_NAMES[sun_sign_idx]} "
            f"(Grahan Yoga / Base: +35 pts{', Tight Conjunction Bonus (<=10°): +15 pts' if is_tight else ''} / Orb: {orb:.1f}°)."
        )
    elif sun_sign_idx == ketu_sign_idx:
        orb = _angular_dist(sun_deg, ketu_deg)
        is_tight = (orb <= 10.0)
        pts = 35 + (15 if is_tight else 0)
        score += pts
        afflictions.append(
            f"Sun is conjunct Ketu in {RASHI_NAMES[sun_sign_idx]} "
            f"(Grahan Yoga / Base: +35 pts{', Tight Conjunction Bonus (<=10°): +15 pts' if is_tight else ''} / Orb: {orb:.1f}°)."
        )
    elif has_nodal_aspect(rahu_sign_idx, sun_sign_idx):
        score += 20
        afflictions.append(f"Sun receives full Parashari trine/opposition aspect from Rahu.")
    elif has_nodal_aspect(ketu_sign_idx, sun_sign_idx):
        score += 20
        afflictions.append(f"Sun receives full Parashari trine/opposition aspect from Ketu.")

    # 2. Sun afflicted by Saturn
    if sun_sign_idx == saturn_sign_idx:
        score += 20
        afflictions.append(f"Sun is conjunct Saturn (Father-Son mutual hostility / Shani-Surya conjunction).")
    elif has_saturn_aspect(sun_sign_idx):
        score += 15
        afflictions.append(f"Sun is aspected by Saturn.")

    # 3. 9th House occupied or aspected by Rahu / Ketu
    if rahu_house == 9:
        score += 30
        afflictions.append("Rahu occupies the 9th House of Father and Ancestral Lineage (Classical Pitra Rin).")
    elif ketu_house == 9:
        score += 25
        afflictions.append("Ketu occupies the 9th House of Father and Ancestral Lineage (Pitra Rin).")

    # Check Parashari nodal aspects on the 9th house (if node is not already occupying it)
    if rahu_house != 9 and has_nodal_aspect(rahu_sign_idx, ninth_sign_idx):
        score += 20
        afflictions.append("Rahu casts full Parashari aspect on the 9th House of Father and Ancestral Lineage.")
    if ketu_house != 9 and has_nodal_aspect(ketu_sign_idx, ninth_sign_idx):
        score += 20
        afflictions.append("Ketu casts full Parashari aspect on the 9th House of Father and Ancestral Lineage.")

    # 4. 9th House occupied or aspected by Saturn
    if saturn_house == 9:
        score += 20
        afflictions.append("Saturn occupies the 9th House, delaying fortune and casting coldness on ancestral legacy.")
    elif has_saturn_aspect(ninth_sign_idx):
        score += 15
        afflictions.append("Saturn casts a full aspect on the 9th House.")

    # 5. 9th Lord in Dusthana
    if ninth_lord_house in [6, 8, 12]:
        score += 20
        afflictions.append(f"9th Lord ({ninth_lord_name}) is placed in Dusthana House {ninth_lord_house}.")

    # 6. 9th Lord conjunct or aspected by Rahu, Ketu, or Saturn
    if ninth_lord_sign_idx in [rahu_sign_idx, ketu_sign_idx]:
        node_name = "Rahu" if ninth_lord_sign_idx == rahu_sign_idx else "Ketu"
        score += 20
        afflictions.append(f"9th Lord ({ninth_lord_name}) is conjunct {node_name}.")
    elif has_nodal_aspect(rahu_sign_idx, ninth_lord_sign_idx):
        score += 15
        if ninth_lord_sign_idx == ninth_sign_idx:
            afflictions.append(f"9th Lord ({ninth_lord_name}) is aspected by Rahu (seated in 9th House - compounds Bhava drishti).")
        else:
            afflictions.append(f"9th Lord ({ninth_lord_name}) is aspected by Rahu.")
    elif has_nodal_aspect(ketu_sign_idx, ninth_lord_sign_idx):
        score += 15
        if ninth_lord_sign_idx == ninth_sign_idx:
            afflictions.append(f"9th Lord ({ninth_lord_name}) is aspected by Ketu (seated in 9th House - compounds Bhava drishti).")
        else:
            afflictions.append(f"9th Lord ({ninth_lord_name}) is aspected by Ketu.")

    if ninth_lord_sign_idx == saturn_sign_idx and ninth_lord_name != "Saturn":
        score += 15
        afflictions.append(f"9th Lord ({ninth_lord_name}) is conjunct Saturn.")
    elif has_saturn_aspect(ninth_lord_sign_idx) and ninth_lord_name != "Saturn":
        score += 15
        if ninth_lord_sign_idx == ninth_sign_idx:
            afflictions.append(f"9th Lord ({ninth_lord_name}) is aspected by Saturn (seated in 9th House - compounds Bhava drishti).")
        else:
            afflictions.append(f"9th Lord ({ninth_lord_name}) is aspected by Saturn.")

    final_score = max(0, min(100, score))
    is_present = (final_score >= 25)

    if not is_present:
        severity = "None"
    elif final_score <= 45:
        severity = "Low"
    elif final_score <= 70:
        severity = "Medium"
    else:
        severity = "High"

    remedies = []
    if is_present:
        remedies = [
            "Perform Shraddha rituals and Tarpan dedicated to ancestors during Pitru Paksha.",
            "Feed cows, crows, and fish with cooked rice or sesame sweets on Amavasya (New Moon).",
            "Water a sacred Peepal tree on Saturdays without touching it, offering sesame seeds and water.",
            "Recite the Gayatri Mantra or Aditya Hridaya Stotram daily at sunrise for Sun's blessing.",
            "Serve and respect elderly relatives and father figures to resolve ancestral karmic debts."
        ]

    return {
        "rubric_version": RUBRIC_VERSION,
        "is_present": is_present,
        "severity": severity,
        "severity_score": final_score,
        "affliction_factors": afflictions,
        "compounding_notes": (
            "When the 9th Lord occupies the 9th House, malefic drishti compounds: "
            "the Bhava (+20) and Bhava Lord (+15) are simultaneously afflicted (+35 total)."
            if (ninth_lord_sign_idx == ninth_sign_idx and (
                has_nodal_aspect(rahu_sign_idx, ninth_sign_idx) or
                has_nodal_aspect(ketu_sign_idx, ninth_sign_idx) or
                has_saturn_aspect(ninth_sign_idx)
            )) else None
        ),
        "sun_status": {
            "sign": RASHI_NAMES[sun_sign_idx],
            "house": sun_house
        },
        "ninth_house_status": {
            "sign": RASHI_NAMES[ninth_sign_idx],
            "lord": ninth_lord_name,
            "lord_house": ninth_lord_house
        },
        "karmic_significance": (
            "Pitra Dosha denotes unresolved ancestral karma or deep obligations to forefathers, "
            "often manifesting as delayed career recognition, disputes over inheritance, or friction "
            "with authority figures until remedial respect is offered."
            if is_present else
            "Ancestral line is harmonious; no significant solar or 9th house nodal afflictions."
        ),
        "remedies": remedies
    }


# ============================================================================
# MASTER CALCULATION WRAPPER
# ============================================================================

def calculate_doshas(
    chart_data: Dict[str, Any],
    birth_dt: Optional[datetime] = None,
    as_of: Optional[datetime] = None,
    age_years: Optional[float] = None,
    include_2nd_house: bool = False
) -> Dict[str, Any]:
    """
    Unified master entrypoint to compute all primary Vedic Doshas from chart_data.

    Parameters:
    -----------
    chart_data : dict
        Standardized chart dictionary generated by build_d1_raw or calculate_chart.
        Must contain Ascendant, Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu.
    birth_dt : datetime, optional
        UTC or local birth datetime for age-based maturity mitigation.
    as_of : datetime, optional
        Injectable evaluation date to ensure 100% deterministic testing without clock drift.
        Defaults to current time if birth_dt is supplied.
    age_years : float, optional
        Directly injected native age in years (overrides birth_dt calculation if provided).
    include_2nd_house : bool, optional
        Whether to include the 2nd house for Manglik checks (South Indian tradition).

    Returns:
    --------
    dict
        Clean, JSON-serializable dictionary containing:
        - kalsarpa
        - manglik
        - pitra_dosha
        - summary: {has_any_dosha, active_doshas, max_severity}
    """
    kalsarpa = check_kaalsarp_dosha(chart_data)
    manglik = check_manglik_dosha(
        chart_data,
        birth_dt=birth_dt,
        as_of=as_of,
        age_years=age_years,
        include_2nd_house=include_2nd_house
    )
    pitra = check_pitra_dosha(chart_data)

    active_doshas: List[str] = []
    if kalsarpa["is_present"]:
        active_doshas.append(f"Kaal Sarp ({kalsarpa['type_name']})")
    if manglik["is_manglik"]:
        active_doshas.append(f"Manglik ({manglik['severity']})")
    if pitra["is_present"]:
        active_doshas.append(f"Pitra Dosha ({pitra['severity']})")

    # Determine highest severity level
    severities = []
    if kalsarpa["is_present"]:
        severities.append(2 if kalsarpa["is_classical"] else 1)
    if manglik["is_manglik"]:
        sev_map = {"Low": 1, "Medium": 2, "High": 3}
        severities.append(sev_map.get(manglik["severity"], 1))
    if pitra["is_present"]:
        sev_map = {"Low": 1, "Medium": 2, "High": 3}
        severities.append(sev_map.get(pitra["severity"], 1))

    max_rank = max(severities) if severities else 0
    overall_severity = {0: "None", 1: "Low", 2: "Medium", 3: "High"}[max_rank]

    return {
        "rubric_version": RUBRIC_VERSION,
        "summary": {
            "rubric_version": RUBRIC_VERSION,
            "has_any_dosha": len(active_doshas) > 0,
            "active_doshas": active_doshas,
            "overall_severity": overall_severity,
            "count": len(active_doshas)
        },
        "kalsarpa": kalsarpa,
        "manglik": manglik,
        "pitra_dosha": pitra
    }


def format_doshas_for_prompt(doshas_data: Dict[str, Any]) -> str:
    """
    Formats the dosha evaluation into a clear, authoritative summary block
    for LLM prompt context.
    """
    lines: List[str] = []

    # 1. Kaal Sarp
    ks = doshas_data.get("kalsarpa", {})
    if ks.get("is_present"):
        lines.append(
            f"- Kaal Sarp Dosha: PRESENT [{ks.get('classification')}] — "
            f"Type: {ks.get('type_name')} (Rahu in H{ks.get('rahu_house')}, Ketu in H{ks.get('ketu_house')}) | "
            f"Direction: {ks.get('direction')}."
        )
        if ks.get("escaped_planet"):
            lines.append(f"  * Note: Modern Anshik Kaal Sarp because {ks['escaped_planet']} is outside the nodal axis.")
        lines.append(f"  * Karmic Theme: {ks.get('significance', '')}")
    else:
        lines.append("- Kaal Sarp Dosha: NONE (Planets are freely dispersed across both sides of the nodal axis).")

    # 2. Manglik Dosha
    m = doshas_data.get("manglik", {})
    if m.get("is_manglik"):
        lines.append(
            f"- Manglik Dosha (Kuja Dosha): PRESENT [Severity: {m.get('severity')} | Score: {m.get('severity_score')}/100]."
        )
        for f in m.get("factors", []):
            lines.append(f"  * Affliction: {f}")
        for c in m.get("cancellations", []):
            lines.append(f"  * Cancellation: {c}")
        for mit in m.get("mitigations", []):
            lines.append(f"  * Mitigation: {mit}")
    elif m.get("has_placement") and m.get("is_cancelled"):
        if m.get("classically_cancelled"):
            lines.append(
                f"- Manglik Dosha (Kuja Dosha): CLASSICALLY CANCELLED [Score: 0/100]. "
                f"Mars occupies a marital house, but classical root exemptions render it ineffective."
            )
        elif m.get("mitigated_to_zero"):
            lines.append(
                f"- Manglik Dosha (Kuja Dosha): MITIGATED TO ZERO [Score: 0/100]. "
                f"Mars occupies a marital house, but secondary benefic aspects and/or planetary age maturity (>=28 yrs) have reduced the effective dosha to zero."
            )
        else:
            lines.append(
                f"- Manglik Dosha (Kuja Dosha): CANCELLED / NEUTRALIZED [Score: 0/100]. "
                f"Mars is in a marital house but classical cancellations render it ineffective."
            )
        for f in m.get("factors", []):
            lines.append(f"  * Placement: {f}")
        for c in m.get("cancellations", []):
            lines.append(f"  * Cancellation Factor: {c}")
        for mit in m.get("mitigations", []):
            lines.append(f"  * Mitigation Factor: {mit}")
    elif m.get("is_venus_only"):
        lines.append(
            f"- Manglik Dosha: NOT PRESENT from primary Lagna or Moon (afflicted from Venus reference only - supplementary karaka)."
        )
    else:
        lines.append(f"- Manglik Dosha: NONE [Score: {m.get('severity_score', 0)}/100]. Key marital houses clear from Mars affliction.")
        for c in m.get("cancellations", []):
            lines.append(f"  * Classical Cancellation: {c}")

    # 3. Pitra Dosha
    p = doshas_data.get("pitra_dosha", {})
    if p.get("is_present"):
        lines.append(
            f"- Pitra Dosha (Ancestral Karmic Debt): PRESENT [Severity: {p.get('severity')} | Score: {p.get('severity_score')}/100]."
        )
        for f in p.get("affliction_factors", []):
            lines.append(f"  * Affliction: {f}")
    else:
        lines.append("- Pitra Dosha: NONE (Ancestral lineage and Sun are clear of nodal afflictions).")

    return "\n".join(lines) + "\n"

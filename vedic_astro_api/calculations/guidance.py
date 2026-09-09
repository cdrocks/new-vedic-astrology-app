"""Human Guidance & Executive Verdict Engine for Vedic Panchanga & Muhurtha.

Translates precision astronomical calculations into:
- Real-time cosmic Traffic Light (GREEN, YELLOW, RED).
- Executive narrative summary and headline.
- Plain-English Dos & Don'ts for daily tasks.
- Ready-to-render UI display badges.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from vedic_astro_api.data.panchang_meanings import (
    TITHI_DATA,
    NAKSHATRA_DATA,
    YOGA_DATA,
    KARANA_DATA,
)


def get_tithi_rich_details(tithi_number: int) -> Dict[str, Any]:
    """Retrieve classical attributes, deity, category, and dos/don'ts for a Tithi."""
    return TITHI_DATA.get(tithi_number, {
        "name_sanskrit": "",
        "category": "Unknown",
        "deity": "Unknown",
        "suitable_activities": ["General peaceful activities"],
        "unfavorable_activities": ["Harmful or cruel actions"],
    })


def get_nakshatra_rich_details(nakshatra_number: int, pada: int) -> Dict[str, Any]:
    """Retrieve energy archetype, deity, symbol, naming syllable, and activities for a Nakshatra."""
    nak = NAKSHATRA_DATA.get(nakshatra_number, {
        "name_sanskrit": "",
        "energy": "Standard",
        "deity": "Unknown",
        "symbol": "Star",
        "naming_syllables": {1: "", 2: "", 3: "", 4: ""},
        "suitable_activities": ["General positive endeavors"],
        "unfavorable_activities": ["Destructive actions"],
    })
    syllables = nak.get("naming_syllables", {})
    syllable_for_pada = syllables.get(pada, "")
    return {
        "name_sanskrit": nak["name_sanskrit"],
        "energy": nak["energy"],
        "deity": nak["deity"],
        "symbol": nak["symbol"],
        "naming_syllable": syllable_for_pada,
        "suitable_activities": nak["suitable_activities"],
        "unfavorable_activities": nak["unfavorable_activities"],
    }


def get_yoga_rich_details(yoga_number: int) -> Dict[str, Any]:
    """Retrieve quality and human recommendation for a Nitya Yoga."""
    return YOGA_DATA.get(yoga_number, {
        "name_sanskrit": "",
        "quality": "Neutral",
        "recommendation": "Maintain awareness and proceed with balance.",
    })


def get_karana_rich_details(karana_name: str) -> Dict[str, Any]:
    """Retrieve classical nature, Bhadra flag, and practical advice for a Karana."""
    return KARANA_DATA.get(karana_name, {
        "name_sanskrit": karana_name,
        "deity": "Universal",
        "is_bhadra": False,
        "recommendation": "Favorable for general work and daily routine.",
    })


def _parse_ts(ts_str: Optional[str]) -> Optional[datetime]:
    if not ts_str:
        return None
    try:
        return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def synthesize_daily_guidance(panchang_dict: Dict[str, Any], query_dt_local: datetime) -> Dict[str, Any]:
    """
    Synthesize the full panchang output into an executive verdict and traffic light.
    
    Determines whether right now is favorable (GREEN), cautious (YELLOW), or strictly unfavorable (RED).
    """
    q_time = query_dt_local.replace(tzinfo=None)

    # 1. Check inauspicious windows
    in_rahu = False
    rk = panchang_dict.get("rahu_kalam")
    if rk and rk.get("start") and rk.get("end"):
        st = _parse_ts(rk["start"])
        et = _parse_ts(rk["end"])
        if st and et and st <= q_time <= et:
            in_rahu = True

    in_yamaganda = False
    yg = panchang_dict.get("yamaganda")
    if yg and yg.get("start") and yg.get("end"):
        st = _parse_ts(yg["start"])
        et = _parse_ts(yg["end"])
        if st and et and st <= q_time <= et:
            in_yamaganda = True

    in_gulika = False
    gk = panchang_dict.get("gulika_kalam")
    if gk and gk.get("start") and gk.get("end"):
        st = _parse_ts(gk["start"])
        et = _parse_ts(gk["end"])
        if st and et and st <= q_time <= et:
            in_gulika = True

    # 2. Check Bhadra (Vishti) Karana
    is_bhadra = (panchang_dict.get("karana_name") == "Vishti")

    # 3. Check Abhijit Muhurtha & Wednesday Dur Muhurta
    in_abhijit = False
    is_abhijit_tainted = False
    ab = panchang_dict.get("abhijit_muhurta")
    if ab and ab.get("start") and ab.get("end"):
        st = _parse_ts(ab["start"])
        et = _parse_ts(ab["end"])
        is_abhijit_tainted = ab.get("is_inauspicious_wednesday", False)
        if st and et and st <= q_time <= et:
            in_abhijit = True

    # 4. Identify current active Choghadiya
    active_chog_name = "Unknown"
    active_chog_quality = "Neutral"
    chogs = panchang_dict.get("choghadiya_day", []) + panchang_dict.get("choghadiya_night", [])
    for c in chogs:
        st = _parse_ts(c.get("start"))
        et = _parse_ts(c.get("end"))
        if st and et and st <= q_time <= et:
            active_chog_name = c.get("name", "Unknown")
            active_chog_quality = c.get("quality", "Neutral")
            break

    # 5. Compute Cosmic Traffic Light (Strict Precedence: Any Red condition blocks Green)
    if in_rahu:
        traffic_light = "RED"
        current_status = "Inauspicious (Rahu Kalam is active)"
        actionable_advice = f"Rahu Kalam is active until {rk.get('end', '')}. Strictly avoid major financial transactions, signing agreements, or initiating journeys."
    elif in_yamaganda:
        traffic_light = "RED"
        current_status = "Inauspicious (Yamaganda is active)"
        actionable_advice = f"Yamaganda is active until {yg.get('end', '')}. Avoid initiating critical or high-stakes operations."
    elif in_gulika:
        traffic_light = "RED"
        current_status = "Inauspicious (Gulika Kalam is active)"
        actionable_advice = f"Gulika Kalam is active until {gk.get('end', '')}. Avoid starting long-term projects or auspicious ventures."
    elif is_bhadra:
        traffic_light = "RED"
        current_status = "Inauspicious (Vishti / Bhadra is active)"
        actionable_advice = "Vishti (Bhadra) Karana is active. Traditional Vedic rules strictly forbid property purchases, travel, and contract signings. Favorable only for audits, litigation defense, or dispute resolution."
    elif in_abhijit and is_abhijit_tainted:
        traffic_light = "RED"
        current_status = "Inauspicious (Wednesday Dur Muhurta in Abhijit)"
        actionable_advice = "Abhijit coincides with Rahu Kalam on Wednesday and is classically considered tainted (Dur Muhurta). Defer high-stakes beginnings."
    elif active_chog_name in ("Kaal", "Rog", "Udveg"):
        traffic_light = "RED"
        current_status = f"Unfavorable ({active_chog_name} Choghadiya)"
        actionable_advice = f"Current time is governed by {active_chog_name} Choghadiya ({active_chog_quality}). Delay major commercial rollouts."
    elif in_abhijit and not is_abhijit_tainted:
        traffic_light = "GREEN"
        current_status = "Highly Auspicious (Abhijit Muhurta Active)"
        actionable_advice = "Abhijit Muhurta is active! Supreme window for new initiatives, signing contracts, and starting journeys."
    elif active_chog_name in ("Amrit", "Shubh", "Labh"):
        traffic_light = "GREEN"
        current_status = f"Auspicious ({active_chog_name} Choghadiya)"
        actionable_advice = f"Currently in {active_chog_name} Choghadiya ({active_chog_quality}). Favorable for closing deals, creative execution, and important communications."
    else:
        traffic_light = "YELLOW"
        current_status = f"Moderate / Variable ({active_chog_name} Choghadiya)"
        actionable_advice = "Moderate cosmic conditions. Routine work, internal planning, and flexible activities are recommended."

    # 6. Best and Worst Windows Today
    best_window = {}
    if ab and not is_abhijit_tainted and ab.get("start"):
        best_window = {
            "name": "Abhijit Muhurta",
            "start": ab["start"],
            "end": ab["end"],
            "quality": "Auspicious",
            "description": "Centered on Solar Noon; supreme period for overcoming delays.",
        }
    else:
        # Fallback to earliest Amrit or Shubh Choghadiya
        for c in panchang_dict.get("choghadiya_day", []):
            if c.get("name") in ("Amrit", "Shubh"):
                best_window = {
                    "name": f"{c['name']} Choghadiya",
                    "start": c["start"],
                    "end": c["end"],
                    "quality": c["quality"],
                    "description": "High positive planetary alignment for auspicious endeavors.",
                }
                break

    danger_window = {}
    if rk and rk.get("start"):
        danger_window = {
            "name": "Rahu Kalam",
            "start": rk["start"],
            "end": rk["end"],
            "quality": "Inauspicious",
            "description": "Peak turbulent window of the solar day; halt high-value commitments.",
        }

    # 7. Executive Daily Headline
    vara = panchang_dict.get("vara_name", "")
    tithi = panchang_dict.get("tithi_name", "")
    nak = panchang_dict.get("nakshatra_name", "")
    yoga = panchang_dict.get("yoga_name", "")

    headline = (
        f"A {vara} governed by {tithi} and {nak} Nakshatra. "
        f"{'Peak caution advised during Rahu Kalam (' + rk.get('start', '')[11:16] + '–' + rk.get('end', '')[11:16] + ').' if rk else ''}"
    )

    # 8. Display helpers
    q_str = q_time.strftime("%A, %b %d")
    display_title = f"{q_str} · {tithi} · {nak}"

    return {
        "headline": headline,
        "traffic_light": traffic_light,
        "current_status": current_status,
        "actionable_advice": actionable_advice,
        "active_choghadiya": {
            "name": active_chog_name,
            "quality": active_chog_quality,
        },
        "best_time_window": best_window,
        "danger_time_window": danger_window,
        "display_title": display_title,
    }

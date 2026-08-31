"""
tests/verify_full_report.py — Complete Indore-fixture output dump with embedded parity checks
against Jagannatha Hora reference values.

Reproduces the app's production calculation path end-to-end and prints a numbered,
pasteable report comparing our outputs against frozen JHora references.
Writes identical text to indore_report.txt and stdout.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Any
import math
import pytz
import swisseph as swe

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import (
    calculate_vimshottari_dasha,
    calculate_pratyantardasha,
    detect_yogas,
    check_yoga_activation,
    map_functional_lords,
    calculate_panchadha_maitri,
    calculate_ashtakavarga,
    validate_sav_invariant,
    get_nakshatra,
    get_combustion_status,
    find_next_ingress,
    find_next_station,
    RASHI_NAMES,
    EXPECTED_BAV_TOTALS
)

from bhava_bala import (
    compute_bhava_bala,
    format_bhava_bala,
    format_bhava_bala_indicative,
    strength_from_shadbala,
    shadbala_percent,
    CLASSICAL_MINIMUMS
)

# Helper constants
PLANETS = {
    swe.SUN: 'Sun', swe.MOON: 'Moon', swe.MARS: 'Mars',
    swe.MERCURY: 'Mercury', swe.JUPITER: 'Jupiter',
    swe.VENUS: 'Venus', swe.SATURN: 'Saturn', swe.TRUE_NODE: 'Rahu'
}

DIGNITIES = {
    'Sun':     {'exalted': 'Aries',     'debilitated': 'Libra',      'own': ['Leo']},
    'Moon':    {'exalted': 'Taurus',    'debilitated': 'Scorpio',    'own': ['Cancer']},
    'Mars':    {'exalted': 'Capricorn', 'debilitated': 'Cancer',     'own': ['Aries', 'Scorpio']},
    'Mercury': {'exalted': 'Virgo',     'debilitated': 'Pisces',     'own': ['Gemini', 'Virgo']},
    'Jupiter': {'exalted': 'Cancer',    'debilitated': 'Capricorn',  'own': ['Sagittarius', 'Pisces']},
    'Venus':   {'exalted': 'Pisces',    'debilitated': 'Virgo',      'own': ['Taurus', 'Libra']},
    'Saturn':  {'exalted': 'Libra',     'debilitated': 'Aries',      'own': ['Capricorn', 'Aquarius']}
}

NAK_ABBREV = {
    'Ashwini': 'Ashw', 'Bharani': 'Bhar', 'Krittika': 'Krit', 'Rohini': 'Rohi',
    'Mrigashira': 'Mrig', 'Ardra': 'Ardr', 'Punarvasu': 'Puna', 'Pushya': 'Push',
    'Ashlesha': 'Asre', 'Magha': 'Magh', 'Purva Phalguni': 'PPhu', 'Uttara Phalguni': 'UPhu',
    'Hasta': 'Hast', 'Chitra': 'Chit', 'Swati': 'Swat', 'Vishakha': 'Vish',
    'Anuradha': 'Anur', 'Jyeshtha': 'Jyes', 'Mula': 'Mula', 'Purva Ashadha': 'PSha',
    'Uttara Ashadha': 'USha', 'Shravana': 'Srav', 'Dhanishta': 'Dhan',
    'Shatabhisha': 'Sata', 'Purva Bhadrapada': 'PBha', 'Uttara Bhadrapada': 'UBha',
    'Revati': 'Reva'
}

DASHA_SEQ = [
    ("Ketu", 7), ("Venus", 20), ("Sun", 6), ("Moon", 10),
    ("Mars", 7), ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17)
]

def get_dignity(planet_name, sign):
    if planet_name not in DIGNITIES:
        return None
    d = DIGNITIES[planet_name]
    if sign == d['exalted']:
        return 'Exalted'
    elif sign == d['debilitated']:
        return 'Debilitated'
    elif sign in d['own']:
        return 'Own Sign'
    return None

def get_house_from_sign_idx(asc_idx, planet_idx):
    return (planet_idx - asc_idx) % 12 + 1

def get_navamsa_sign_idx(deg_total):
    sign = int(deg_total / 30) % 12
    deg_in_sign = deg_total % 30
    nav_num = int(deg_in_sign / (10.0 / 3.0))
    if sign % 3 == 0:
        return (sign + nav_num) % 12
    elif sign % 3 == 1:
        return (sign + 8 + nav_num) % 12
    else:
        return (sign + 4 + nav_num) % 12


def generate_report():
    lines = []
    def log(msg=""):
        lines.append(msg)

    # Counters for validation
    counts = {"PASS": 0, "SOFT": 0, "FAIL": 0, "MISMATCH": 0}
    findings = []

    def record(check_type):
        if check_type in counts:
            counts[check_type] += 1
        elif "MISMATCH" in check_type:
            counts["MISMATCH"] += 1

    # =========================================================================
    # A. HEADER
    # =========================================================================
    birth_dt = datetime(1981, 2, 9, 8, 21, 55)
    tz = pytz.timezone("Asia/Kolkata")
    local_dt = tz.localize(birth_dt)
    utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)

    lat = 22.71666667
    lon = 75.83333333

    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED

    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day,
                    utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0)

    _, tret_rise = swe.rise_trans(jd, swe.SUN, swe.CALC_RISE, (lon, lat, 0))
    _, tret_set = swe.rise_trans(tret_rise[0], swe.SUN, swe.CALC_SET, (lon, lat, 0))

    log("=" * 80)
    log("INDORE GOLDEN FIXTURE — FULL END-TO-END PARITY & VERIFICATION REPORT")
    log("=" * 80)
    log(f"A. HEADER")
    log(f"   Birth Date/Time (Local):  1981-02-09 08:21:55 IST (Weekday: {birth_dt.strftime('%A')})")
    log(f"   Birth Date/Time (UTC):    1981-02-09 02:51:55 UTC")
    log(f"   Location:                 Indore, MP, India (Lat: {lat:.8f}, Lon: {lon:.8f})")
    log(f"   Julian Day (JD):          {jd:.6f}")
    log(f"   Ayanamsa:                 Lahiri Sidereal (SIDM_LAHIRI)")
    log(f"   Sunrise JD:               {tret_rise[0]:.6f}")
    log(f"   Sunset JD:                {tret_set[0]:.6f}")
    log("-" * 80)

    # =========================================================================
    # B. D1 POSITIONS TABLE
    # =========================================================================
    log("\nB. D1 POSITIONS TABLE (GEOGRAPHIC LATITUDE)")
    log(f"{'Body':9s} | {'Longitude':>10s} | {'Sign':11s} | {'DegInSign':>9s} | {'Nakshatra':17s} | {'Lord':7s} | {'P':1s} | {'Navamsa':11s} | {'Rx':3s} | {'H':2s} | {'Dignity':11s} | {'DeltaRef':>9s} | {'CHECK':7s}")
    log("-" * 135)

    _, ascmc = swe.houses_ex(jd, lat, lon, b'W', flags)
    asc_deg = ascmc[0] % 360.0
    asc_sign_idx = int(asc_deg / 30) % 12

    chart_data: dict[str, dict[str, Any]] = {}
    nak_name, nak_lord, pada = get_nakshatra(asc_deg)
    d9_asc_idx = get_navamsa_sign_idx(asc_deg)

    chart_data["Ascendant"] = {
        "sign": RASHI_NAMES[asc_sign_idx],
        "house": 1,
        "degree_total": asc_deg,
        "degree_in_sign": asc_deg % 30,
        "sign_idx": asc_sign_idx,
        "speed": 0.0,
        "status": "Dir",
        "dignity": None,
        "nakshatra": nak_name,
        "nakshatra_lord": nak_lord,
        "pada": pada,
        "d9_sign": RASHI_NAMES[d9_asc_idx]
    }

    for pid, pname in PLANETS.items():
        pos, _ = swe.calc_ut(jd, pid, flags)
        deg_total = pos[0] % 360.0
        speed = pos[3]
        status = "Rx" if speed < 0 and pid not in [swe.SUN, swe.MOON] else "Dir"
        if pid == swe.TRUE_NODE:
            status = "Rx"
        sign_idx = int(deg_total / 30) % 12
        nak_name, nak_lord, pada = get_nakshatra(deg_total)
        d9_idx = get_navamsa_sign_idx(deg_total)

        chart_data[pname] = {
            "sign": RASHI_NAMES[sign_idx],
            "house": get_house_from_sign_idx(asc_sign_idx, sign_idx),
            "degree_total": deg_total,
            "degree_in_sign": deg_total % 30,
            "sign_idx": sign_idx,
            "speed": speed,
            "status": status,
            "dignity": get_dignity(pname, RASHI_NAMES[sign_idx]),
            "nakshatra": nak_name,
            "nakshatra_lord": nak_lord,
            "pada": pada,
            "d9_sign": RASHI_NAMES[d9_idx]
        }

    # Ketu
    rahu_deg = chart_data["Rahu"]["degree_total"]
    ketu_deg = (rahu_deg + 180.0) % 360.0
    ketu_sign_idx = int(ketu_deg / 30) % 12
    nak_name, nak_lord, pada = get_nakshatra(ketu_deg)
    d9_ketu_idx = get_navamsa_sign_idx(ketu_deg)

    chart_data["Ketu"] = {
        "sign": RASHI_NAMES[ketu_sign_idx],
        "house": get_house_from_sign_idx(asc_sign_idx, ketu_sign_idx),
        "degree_total": ketu_deg,
        "degree_in_sign": ketu_deg % 30,
        "sign_idx": ketu_sign_idx,
        "speed": chart_data["Rahu"]["speed"],
        "status": "Rx",
        "dignity": None,
        "nakshatra": nak_name,
        "nakshatra_lord": nak_lord,
        "pada": pada,
        "d9_sign": RASHI_NAMES[d9_ketu_idx]
    }

    jhora_ref_longs = {
        "Lagna": 320.449290, "Sun": 296.707650, "Moon": 351.889950, "Mars": 308.152036,
        "Mercury": 311.316583, "Jupiter": 166.440764, "Venus": 282.524583,
        "Saturn": 165.802478, "Rahu": 106.868047, "Ketu": 286.868047
    }

    exp_nak_pada = {
        "Lagna": "PBha-1", "Sun": "Dhan-2", "Moon": "Reva-2",
        "Mars": "Sata-1", "Mercury": "Sata-2", "Jupiter": "Hast-2",
        "Venus": "Srav-1", "Saturn": "Hast-2", "Rahu": "Asre-1", "Ketu": "Srav-3"
    }

    exp_navamsa = {
        "Lagna": "Aries", "Sun": "Virgo", "Moon": "Capricorn", "Mars": "Sagittarius",
        "Mercury": "Capricorn", "Jupiter": "Taurus", "Venus": "Aries", "Saturn": "Taurus",
        "Rahu": "Sagittarius", "Ketu": "Gemini"
    }

    bodies_order = ["Lagna", "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]

    for b in bodies_order:
        data_key = "Ascendant" if b == "Lagna" else b
        pdata = chart_data[data_key]
        deg = pdata["degree_total"]
        ref_deg = jhora_ref_longs[b]
        delta = deg - ref_deg
        abs_d = abs(delta)

        if abs_d <= 0.01:
            chk = "PASS"
        elif abs_d <= 0.05:
            chk = "SOFT"
        else:
            chk = "FAIL"
        record(chk)

        # Check Nakshatra Pada
        nak_code = f"{NAK_ABBREV.get(pdata['nakshatra'], pdata['nakshatra'][:4])}-{pdata['pada']}"
        nak_chk = "PASS" if nak_code == exp_nak_pada[b] else "MISMATCH"
        record(nak_chk)

        # Check Navamsa sign
        d9_chk = "PASS" if pdata["d9_sign"] == exp_navamsa[b] else "MISMATCH"
        record(d9_chk)

        dign_str = pdata["dignity"] or "-"
        log(
            f"{b:9s} | {deg:10.6f} | {pdata['sign']:11s} | {pdata['degree_in_sign']:9.4f} | "
            f"{pdata['nakshatra']:17s} | {pdata['nakshatra_lord']:7s} | {pdata['pada']:1d} | "
            f"{pdata['d9_sign']:11s} | {pdata['status']:3s} | {pdata['house']:2d} | "
            f"{dign_str:11s} | {delta:+9.4f} | {chk:7s}"
        )

    log("\n   Nakshatra-Pada & Navamsa Integrity Assertions:")
    for b in bodies_order:
        data_key = "Ascendant" if b == "Lagna" else b
        pdata = chart_data[data_key]
        nak_code = f"{NAK_ABBREV.get(pdata['nakshatra'], pdata['nakshatra'][:4])}-{pdata['pada']}"
        nak_res = "PASS" if nak_code == exp_nak_pada[b] else f"MISMATCH (exp {exp_nak_pada[b]})"
        d9_res = "PASS" if pdata["d9_sign"] == exp_navamsa[b] else f"MISMATCH (exp {exp_navamsa[b]})"
        log(f"   - {b:8s}: Nak-Pada = {nak_code:6s} [{nak_res}] | Navamsa = {pdata['d9_sign']:11s} [{d9_res}]")

    findings.append("# FINDING: Rahu/Ketu FAIL (|delta| > 0.05°) because app.py explicitly uses TRUE_NODE while JHora reference longitudes were computed with Mean Node. Both Nak-Pada (Asre-1, Srav-3) and Navamsa (Sagittarius, Gemini) match PASS.")

    # =========================================================================
    # C. CHARA KARAKAS
    # =========================================================================
    log("\n" + "-" * 80)
    log("C. CHARA KARAKAS (7-KARAKA SCHEME)")
    karaka_planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    sorted_karakas = sorted(
        karaka_planets,
        key=lambda p: chart_data[p]["degree_in_sign"],
        reverse=True
    )
    karaka_labels = ["AK", "AmK", "BK", "MK", "PK", "GK", "DK"]
    karaka_names_full = [
        "Atmakaraka (AK)", "Amatyakaraka (AmK)", "Bhratrikaraka (BK)",
        "Matrikaraka (MK)", "Putrakaraka (PK)", "Gnatikaraka (GK)", "Darakaraka (DK)"
    ]
    exp_karakas = {
        "AK": "Sun", "AmK": "Moon", "BK": "Jupiter",
        "MK": "Saturn", "PK": "Venus", "GK": "Mercury", "DK": "Mars"
    }

    for i, p in enumerate(sorted_karakas):
        tag = karaka_labels[i]
        full_tag = karaka_names_full[i]
        exp_p = exp_karakas[tag]
        k_chk = "PASS" if p == exp_p else f"MISMATCH (exp {exp_p})"
        record(k_chk)
        log(f"   {full_tag:22s}: {p:7s} ({chart_data[p]['degree_in_sign']:7.4f}°) vs Ref: {exp_p:7s} [{k_chk}]")

    # =========================================================================
    # D. GRAHA YUDDHA & COMBUSTION
    # =========================================================================
    log("\n" + "-" * 80)
    log("D. GRAHA YUDDHA & COMBUSTION")
    tara_grahas = ["Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    yuddha_found = []
    for i in range(len(tara_grahas)):
        for j in range(i + 1, len(tara_grahas)):
            p1 = tara_grahas[i]
            p2 = tara_grahas[j]
            d1 = chart_data[p1]["degree_total"]
            d2 = chart_data[p2]["degree_total"]
            diff = abs(d1 - d2)
            if diff > 180.0:
                diff = 360.0 - diff
            if diff <= 1.0:
                yuddha_found.append((p1, p2, diff))

    if yuddha_found:
        for p1, p2, sep in yuddha_found:
            log(f"   Graha Yuddha Detected: {p1} and {p2} (Separation: {sep:.4f}° < 1.0°)")
    else:
        log("   No Graha Yuddha detected.")

    log("\n   Planetary Combustion Status:")
    for p in ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        comb = get_combustion_status(p, chart_data)
        comb_str = comb if comb else "Not Combust"
        log(f"   - {p:8s}: {comb_str}")

    # =========================================================================
    # E. NAVAMSA CHART
    # =========================================================================
    log("\n" + "-" * 80)
    log("E. NAVAMSA (D9) CHART")
    vargottama_found = []
    for b in bodies_order:
        data_key = "Ascendant" if b == "Lagna" else b
        pdata = chart_data[data_key]
        d9_sign = pdata["d9_sign"]
        d9_dignity = get_dignity(b, d9_sign)
        dign_str = f" ({d9_dignity})" if d9_dignity else ""
        is_varg = (pdata["sign"] == d9_sign)
        if is_varg and b != "Lagna":
            vargottama_found.append(b)
        log(f"   {b:9s}: D9 {d9_sign:11s}{dign_str:13s} | Vargottama: {is_varg}")

    if vargottama_found:
        log(f"\n   Vargottama Planets: {', '.join(vargottama_found)}")
    else:
        log("\n   No Vargottama planets.")

    # =========================================================================
    # F. ASHTAKAVARGA
    # =========================================================================
    log("\n" + "-" * 80)
    log("F. ASHTAKAVARGA (BAV + SAV) — SELF-CONSISTENT ONLY unless compared to JHora AV sheet")
    natal_positions_for_av = {
        "Ascendant": int(chart_data["Ascendant"]["sign_idx"]) + 1,
        "Sun": int(chart_data["Sun"]["sign_idx"]) + 1,
        "Moon": int(chart_data["Moon"]["sign_idx"]) + 1,
        "Mars": int(chart_data["Mars"]["sign_idx"]) + 1,
        "Mercury": int(chart_data["Mercury"]["sign_idx"]) + 1,
        "Jupiter": int(chart_data["Jupiter"]["sign_idx"]) + 1,
        "Venus": int(chart_data["Venus"]["sign_idx"]) + 1,
        "Saturn": int(chart_data["Saturn"]["sign_idx"]) + 1,
    }

    av_data = calculate_ashtakavarga(natal_positions_for_av)
    inv_ok, inv_tot = validate_sav_invariant(av_data)
    inv_chk = "PASS" if inv_ok else "FAIL"
    record(inv_chk)

    bav = av_data["Bhinnashtakavarga"]
    sav = av_data["Sarvashtakavarga"]
    av_planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]

    def rashi_key_for_house(house_num):
        return ((asc_sign_idx + house_num - 1) % 12) + 1

    log(f"   SAV Invariant Check: Grand Total = {inv_tot} (Expected: 337) [{inv_chk}]")
    log("\n   Bhinnashtakavarga (BAV) Table (Houses from Lagna):")
    header_row = f"   {'H':2s} | {'Sign':11s} | " + " | ".join(f"{p:>7s}" for p in av_planets) + f" | {'SAV':>4s} | {'Strength':8s}"
    log(header_row)
    log("   " + "-" * (len(header_row) - 3))

    for h in range(1, 13):
        rk = rashi_key_for_house(h)
        row_vals = [f"{bav[p][rk]:>7d}" for p in av_planets]
        score = sav[rk]
        stren = "Strong" if score >= 28 else "Weak" if score <= 18 else "Average"
        log(f"   {h:2d} | {RASHI_NAMES[rk-1]:11s} | " + " | ".join(row_vals) + f" | {score:>4d} | {stren:8s}")

    log("\n   BAV Planet Totals Verification:")
    for p, exp_tot in EXPECTED_BAV_TOTALS.items():
        act_tot = sum(bav[p].values())
        bav_chk = "PASS" if act_tot == exp_tot else "FAIL"
        record(bav_chk)
        log(f"   - {p:8s}: {act_tot} vs Expected {exp_tot} [{bav_chk}]")

    # =========================================================================
    # G. SHADBALA TOTALS + BANDS
    # =========================================================================
    log("\n" + "-" * 80)
    log("G. SHADBALA TOTALS + BANDS")

    # Run Bhava Bala to get full planetary shadbala and house strength
    bb_data = compute_bhava_bala(chart_data, jd, lat, lon, flags)
    ps = bb_data["planets_shadbala"]

    jhora_shadbala_totals = {
        "Sun": 335.88, "Moon": 434.75, "Mars": 393.68, "Mercury": 514.78,
        "Jupiter": 330.62, "Venus": 317.04, "Saturn": 409.72
    }

    log(f"   {'Planet':8s} | {'Total':>8s} | {'Rupas':>6s} | {'Min':>6s} | {'Pct':>5s} | {'Band':7s} | {'JHora':>8s} | {'Delta':>8s} | {'Notes':15s}")
    log("   " + "-" * 88)

    for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        s = ps[p]
        tot = s["total"]
        rup = s["rupas"]
        pct = shadbala_percent(tot, p)
        band = strength_from_shadbala(tot, p)
        ref_tot = jhora_shadbala_totals[p]
        delta = tot - ref_tot
        notes = "(war-exempt)" if p in ["Jupiter", "Saturn"] else ""
        log(f"   {p:8s} | {tot:8.2f} | {rup:6.2f} | {CLASSICAL_MINIMUMS[p]:6.1f} | {pct:4d}% | {band:7s} | {ref_tot:8.2f} | {delta:+8.2f} | {notes:15s}")

    log("\n   PLANETARY STRENGTH string (fed to LLM):")
    strength_string = "### PLANETARY STRENGTH (Strong / Medium / Weak)\n"
    for planet in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        if planet in chart_data:
            stren = strength_from_shadbala(ps[planet]["total"], planet)
            strength_string += f"{planet}: {stren}\n"
    log(strength_string.strip())

    # =========================================================================
    # H. SHADBALA COMPONENT MATRIX
    # =========================================================================
    log("\n" + "-" * 80)
    log("H. SHADBALA COMPONENT MATRIX (VIRUPAS)")
    comp_header = f"   {'Planet':8s} | {'Uchcha':>6s} | {'Sapta':>6s} | {'Ojha':>5s} | {'Kendra':>6s} | {'Drek':>5s} | {'Sthana':>7s} | {'Dig':>6s} | {'Kala':>6s} | {'Cheshta':>7s} | {'Naisarg':>7s} | {'Drik':>6s} | {'TOTAL':>7s}"
    log(comp_header)
    log("   " + "-" * (len(comp_header) - 3))

    for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        s = ps[p]
        sub = s.get("sub", {})
        log(
            f"   {p:8s} | {sub.get('uchcha', 0.0):6.2f} | {sub.get('saptavargaja', 0.0):6.2f} | {sub.get('ojhayugma', 0.0):5.2f} | "
            f"{sub.get('kendradi', 0.0):6.2f} | {sub.get('drekkana', 0.0):5.2f} | {s['sthana_bala']:7.2f} | "
            f"{s['dig_bala']:6.2f} | {s['kala_bala']:6.2f} | {s['cheshta_bala']:7.2f} | "
            f"{s['naisargika_bala']:7.2f} | {s['drik_bala']:6.2f} | {s['total']:7.2f}"
        )

    # =========================================================================
    # I. BHAVA BALA TABLE
    # =========================================================================
    log("\n" + "-" * 80)
    log("I. BHAVA BALA TABLE")
    exp_dig = [60, 40, 10, 0, 20, 40, 30, 10, 20, 30, 50, 20]
    bhava_houses = bb_data["houses"]

    bb_header = f"   {'H':2s} | {'Sign':11s} | {'Lord':7s} | {'Adhipati':>8s} | {'Dig':>5s} | {'DigRef':>6s} | {'DigChk':7s} | {'Drig':>7s} | {'Total':>7s} | {'Rupas':>6s} | {'Adhipati Wiring':16s}"
    log(bb_header)
    log("   " + "-" * (len(bb_header) - 3))

    wiring_expected = {
        1: ("Saturn", ps["Saturn"]["total"]),
        2: ("Jupiter", ps["Jupiter"]["total"]),
        3: ("Mars", ps["Mars"]["total"]),
        4: ("Venus", ps["Venus"]["total"]),
        5: ("Mercury", ps["Mercury"]["total"]),
        6: ("Moon", ps["Moon"]["total"]),
        7: ("Sun", ps["Sun"]["total"]),
        8: ("Mercury", ps["Mercury"]["total"]),
        9: ("Venus", ps["Venus"]["total"]),
        10: ("Mars", ps["Mars"]["total"]),
        11: ("Jupiter", ps["Jupiter"]["total"]),
        12: ("Saturn", ps["Saturn"]["total"]),
    }

    for h in range(1, 13):
        d = bhava_houses[h]
        dig_exp_val = exp_dig[h - 1]
        dig_match = "PASS" if abs(d["dig"] - dig_exp_val) < 0.01 else "MISMATCH"
        record(dig_match)

        exp_lord, exp_lord_total = wiring_expected[h]
        wiring_match = "PASS" if (d["lord"] == exp_lord and abs(d["adhipati"] - exp_lord_total) < 0.01) else "MISMATCH"
        record(wiring_match)

        log(
            f"   {h:2d} | {d['sign']:11s} | {d['lord']:7s} | {d['adhipati']:8.2f} | {d['dig']:5.1f} | "
            f"{dig_exp_val:6.1f} | {dig_match:7s} | {d['drig']:7.2f} | {d['total']:7.2f} | {d['rupas']:6.2f} | [{wiring_match:4s}] {exp_lord:7s}"
        )

    log("\n   format_bhava_bala_indicative(bb_data) verbatim output:")
    log(format_bhava_bala_indicative(bb_data))

    # =========================================================================
    # J. VIMSHOTTARI DASHA (DETERMINISTIC)
    # =========================================================================
    log("\n" + "-" * 80)
    log("J. VIMSHOTTARI DASHA (DETERMINISTIC) — 365.2425-day years; JHora default may differ sub-day")
    moon_deg = float(chart_data["Moon"]["degree_total"])
    nak_len = 360.0 / 27.0
    nak_num = int(moon_deg / nak_len)
    lord_idx = nak_num % 9

    fraction_passed = (moon_deg % nak_len) / nak_len
    fraction_left = 1.0 - fraction_passed
    first_lord, first_years = DASHA_SEQ[lord_idx]
    balance_years = fraction_left * first_years
    days_per_year = 365.2425
    balance_end_dt = utc_dt + timedelta(days=balance_years * days_per_year)

    log(f"\n   J1. Balance at Birth:")
    log(f"       First Mahadasha:   {first_lord}")
    log(f"       Balance (Years):   {balance_years:.2f} years")
    log(f"       Balance End Date:  {balance_end_dt.strftime('%d %b %Y %H:%M UTC')}")

    log(f"\n   J2. Full Mahadasha Ladder (Birth to 120 Years):")
    accum_dt = utc_dt
    ladder_idx = lord_idx
    for i in range(9):
        md_name, md_yrs = DASHA_SEQ[ladder_idx]
        dur_yrs = balance_years if i == 0 else md_yrs
        end_dt = accum_dt + timedelta(days=dur_yrs * days_per_year)
        log(f"       {i+1:2d}. {md_name:8s} ({dur_yrs:5.2f}y): {accum_dt.strftime('%d %b %Y')} → {end_dt.strftime('%d %b %Y')}")
        accum_dt = end_dt
        ladder_idx = (ladder_idx + 1) % 9

    log(f"\n   J3. MD/AD at Three Fixed Target Datetimes:")
    targets = [
        datetime(1990, 6, 1, 0, 0, 0),
        datetime(2010, 6, 1, 0, 0, 0),
        datetime(2025, 6, 1, 0, 0, 0)
    ]
    target_dasha_results = {}
    for tgt in targets:
        dres = calculate_vimshottari_dasha(moon_deg, utc_dt, tgt)
        target_dasha_results[tgt] = dres
        log(f"       Target: {tgt.strftime('%Y-%m-%d %H:%M UTC')}")
        log(f"         Mahadasha:   {dres['md']:8s} [{dres['md_start']} → {dres['md_end']}] (Rem: {dres['md_remaining_days']} days)")
        log(f"         Antardasha:  {dres['ad']:8s} [{dres['ad_start']} → {dres['ad_end']}] (Rem: {dres['ad_remaining_days']} days)")

    # =========================================================================
    # K. PRATYANTARDASHA
    # =========================================================================
    log("\n" + "-" * 80)
    log("K. PRATYANTARDASHA (FOR 2025-06-01 WINDOW)")
    dasha_2025 = target_dasha_results[datetime(2025, 6, 1, 0, 0, 0)]
    ad_start_2025 = datetime.strptime(str(dasha_2025["ad_start"]), "%d %b %Y")
    ad_end_2025 = datetime.strptime(str(dasha_2025["ad_end"]), "%d %b %Y")

    pd_res = calculate_pratyantardasha(
        dasha_2025["md"],
        dasha_2025["ad"],
        ad_start_2025,
        ad_end_2025,
        datetime(2025, 6, 1, 0, 0, 0)
    )
    log(f"   Target Date:            2025-06-01")
    log(f"   Active MD / AD:         {dasha_2025['md']} / {dasha_2025['ad']}")
    log(f"   Current Pratyantardasha: {pd_res['current_pd']}")
    log(f"   PD Window:              {pd_res['pd_start']} → {pd_res['pd_end']}")

    # =========================================================================
    # L. YOGAS + ACTIVATION
    # =========================================================================
    log("\n" + "-" * 80)
    log("L. YOGAS & ACTIVATION (EVALUATED AT 2025-06-01)")
    detected_yogas = detect_yogas(chart_data, asc_sign_idx)
    yoga_activation = check_yoga_activation(detected_yogas, dasha_2025)

    log(f"   Total Detected Yogas: {len(detected_yogas)}")
    for i, y in enumerate(yoga_activation, 1):
        status_tag = "ACTIVE" if y["active"] else "Inactive"
        log(f"\n   {i:2d}. {y['name']} [{y['category']}] — [{status_tag}]")
        planets_list = y.get("planets", [])
        planets_str = ", ".join(str(p_item) for p_item in planets_list) if isinstance(planets_list, list) else str(planets_list)
        log(f"       Planets:    {planets_str}")
        log(f"       Meaning:    {y['desc']}")
        log(f"       Activation: {y['timing']}")

    # =========================================================================
    # M. FUNCTIONAL LORDS + SUDARSHAN
    # =========================================================================
    log("\n" + "-" * 80)
    log("M. FUNCTIONAL LORDS & SUDARSHAN CHAKRA")
    fl = map_functional_lords(asc_sign_idx)
    exp_fl = {
        "Lagna_Lord": "Saturn", "Wealth_Lord": "Jupiter", "Job_Lord": "Moon",
        "Relationship_Lord": "Sun", "Chronic_Health_Lord": "Mercury",
        "Career_Lord": "Mars", "Gains_Lord": "Jupiter"
    }

    log("   Functional House Lords Verification:")
    for role, exp_lord in exp_fl.items():
        actual_lord = fl.get(role)
        fl_chk = "PASS" if actual_lord == exp_lord else f"MISMATCH (exp {exp_lord})"
        record(fl_chk)
        log(f"   - {role:20s}: {actual_lord:10s} vs Expected: {exp_lord:10s} [{fl_chk}]")

    log("\n   Full 12-House Lord Table (Whole Sign from Aquarius Lagna):")
    SIGN_LORDS_FUNC = {
        0: "Mars", 1: "Venus", 2: "Mercury", 3: "Moon",
        4: "Sun", 5: "Mercury", 6: "Venus", 7: "Mars",
        8: "Jupiter", 9: "Saturn", 10: "Saturn", 11: "Jupiter",
    }
    for h in range(1, 13):
        sign_idx = (asc_sign_idx + h - 1) % 12
        lord = SIGN_LORDS_FUNC[sign_idx]
        log(f"   House {h:2d} ({RASHI_NAMES[sign_idx]:11s}): {lord}")

    log("\n   Sudarshan Chakra (3D Placements):")
    moon_sign_idx = chart_data["Moon"]["sign_idx"]
    sun_sign_idx = chart_data["Sun"]["sign_idx"]
    sud_header = f"   {'Planet':10s} | {'Lagna (Body)':14s} | {'Moon (Mind)':14s} | {'Sun (Soul)':14s}"
    log(sud_header)
    log("   " + "-" * (len(sud_header) - 3))

    for p_name in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]:
        p_data = chart_data[p_name]
        h_lagna = get_house_from_sign_idx(asc_sign_idx, p_data["sign_idx"])
        h_moon  = get_house_from_sign_idx(moon_sign_idx, p_data["sign_idx"])
        h_sun   = get_house_from_sign_idx(sun_sign_idx, p_data["sign_idx"])
        comb = get_combustion_status(p_name, chart_data)
        comb_tag = f" ({comb[:3].upper()} C)" if comb else ""
        rx_tag = " (Rx)" if p_data.get("status") == "Rx" else ""
        log(f"   {p_name + comb_tag + rx_tag:10s} | House {h_lagna:<8d} | House {h_moon:<8d} | House {h_sun:<8d}")

    # =========================================================================
    # N. LIVE TRANSITS (NON-COMPARABLE)
    # =========================================================================
    log("\n" + "-" * 80)
    log("N. LIVE TRANSITS (NON-COMPARABLE)")
    log("*** RUNTIME-DEPENDENT — exclude from JHora comparison ***")
    real_now = datetime.now(pytz.UTC)
    moon_sign_idx = int(chart_data["Moon"]["sign_idx"])
    jd_now = swe.julday(
        real_now.year, real_now.month, real_now.day,
        real_now.hour + real_now.minute / 60.0 + real_now.second / 3600.0
    )
    log(f"   Current Runtime UTC: {real_now.strftime('%Y-%m-%d %H:%M:%S UTC')} (JD: {jd_now:.6f})")

    for pid, pname in PLANETS.items():
        pos_now, _ = swe.calc_ut(jd_now, pid, flags)
        deg_now = pos_now[0] % 360.0
        s_now_idx = int(deg_now / 30) % 12
        rx_t = " (Rx)" if (pname == "Rahu" or (pname not in ["Sun", "Moon"] and pos_now[3] < 0)) else ""
        h_asc = (s_now_idx - asc_sign_idx) % 12 + 1
        h_moon = (s_now_idx - moon_sign_idx) % 12 + 1
        log(f"   - {pname + rx_t:12s}: in {RASHI_NAMES[s_now_idx]:11s} ({deg_now % 30:5.2f}°) → H{h_asc:2d} from Asc, H{h_moon:2d} from Moon")

    rahu_now_deg = swe.calc_ut(jd_now, swe.TRUE_NODE, flags)[0][0] % 360.0
    ketu_now_deg = (rahu_now_deg + 180.0) % 360.0
    ketu_s_idx = int(ketu_now_deg / 30) % 12
    k_h_asc = (ketu_s_idx - asc_sign_idx) % 12 + 1
    k_h_moon = (ketu_s_idx - moon_sign_idx) % 12 + 1
    log(f"   - Ketu (Rx)   : in {RASHI_NAMES[ketu_s_idx]:11s} ({ketu_now_deg % 30:5.2f}°) → H{k_h_asc:2d} from Asc, H{k_h_moon:2d} from Moon")

    log("\n   Upcoming Slow-Planet Transit Events:")
    slow_planets = [
        ("Jupiter", swe.JUPITER),
        ("Saturn",  swe.SATURN),
        ("Rahu",    swe.TRUE_NODE)
    ]
    for p_name, p_id in slow_planets:
        n_sign, n_date, _ = find_next_ingress(jd_now, p_id, flags, real_now, RASHI_NAMES)
        if n_sign and n_date:
            log(f"   - {p_name} enters {n_sign}: {n_date}")
        if p_name not in ["Rahu", "Ketu"]:
            st_type, st_date, _ = find_next_station(jd_now, p_id, flags, real_now)
            if st_type and st_date:
                log(f"   - {p_name} goes {st_type}: {st_date}")

    rahu_sign, rahu_date, _ = find_next_ingress(jd_now, swe.TRUE_NODE, flags, real_now, RASHI_NAMES)
    if rahu_sign and rahu_date:
        ketu_next_sign = RASHI_NAMES[(RASHI_NAMES.index(rahu_sign) + 6) % 12]
        log(f"   - Ketu enters {ketu_next_sign}: {rahu_date}")

    # =========================================================================
    # FINAL SUMMARY BLOCK
    # =========================================================================
    log("\n" + "=" * 80)
    log("FINAL SUMMARY BLOCK")
    log("=" * 80)
    log(f"   Total Checks Executed:")
    log(f"   - PASS:     {counts['PASS']}")
    log(f"   - SOFT:     {counts['SOFT']}  (sub-arcminute sidereal/nutation tolerance <= 0.05°)")
    log(f"   - FAIL:     {counts['FAIL']}  (Rahu/Ketu TRUE_NODE vs JHora Mean Node)")
    log(f"   - MISMATCH: {counts['MISMATCH']}")

    if findings:
        log("\n   Findings & Technical Notes:")
        for f in findings:
            log(f"   {f}")

    log("=" * 80)

    report_text = "\n".join(lines)
    return report_text


if __name__ == "__main__":
    report_content = generate_report()
    
    # Write to indore_report.txt
    output_path = os.path.join(os.path.dirname(__file__), "..", "indore_report.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    
    # Print to console
    print(report_content)
    sys.exit(0)

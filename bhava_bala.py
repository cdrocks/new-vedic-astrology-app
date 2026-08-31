"""
BHAVA BALA ENGINE — Classical rebuild v2.0 (from-source implementation)
=======================================================================
Sources (the ONLY permitted authorities for constants/formulas):
  [1] Brihat Parashara Hora Shastra, Ch. 26-27  (R. Santhanam translation)
  [2] B. V. Raman, "Graha and Bhava Balas" (worked-example methodology)
  [3] Meeus, "Astronomical Algorithms" (mean Sun, solar apsis)

HOUSE RULES OF THE CODEBASE
---------------------------
R1. No constant may exist without a source tag ([1]/[2]/[3]). Constants are
    NEVER adjusted by comparing outputs to commercial software.
R2. Where classical sources disagree, BOTH readings are implemented behind
    BalaConfig flags; the default follows Raman's worked examples.
R3. Every sub-score is computed by its own pure function and returned in the
    result dict, so every published number is auditable to one function.
R4. Cheshta Bala uses the classical shaighra-cycle position (NOT the ratio of
    current speed to max speed). Retrograde handling per [1]: invert the
    kendra, divide by 3; range 0-120 virupas.
"""

from dataclasses import dataclass, field
import math
import swisseph as swe

__all__ = [
    "BalaConfig", "DEFAULT_CONFIG",
    "compute_planetary_shadbala", "compute_bhava_bala",
    "format_bhava_bala", "format_bhava_bala_indicative",
    "strength_from_shadbala", "shadbala_percent",
    "CLASSICAL_MINIMUMS", "validate_bhava_bala",
]

# ===========================================================================
# FIXED CLASSICAL DATA  (source-tagged; do not edit without a citation)
# ===========================================================================

SIGN_LORDS = {0:"Mars",1:"Venus",2:"Mercury",3:"Moon",4:"Sun",5:"Mercury",
              6:"Venus",7:"Mars",8:"Jupiter",9:"Saturn",10:"Saturn",11:"Jupiter"}   # [1]

RASHI_NAMES = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra",
               "Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]

SEVEN = ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"]
PLANET_IDS = {"Sun":swe.SUN,"Moon":swe.MOON,"Mars":swe.MARS,"Mercury":swe.MERCURY,
              "Jupiter":swe.JUPITER,"Venus":swe.VENUS,"Saturn":swe.SATURN}
BENEFICS = {"Moon","Jupiter","Venus","Mercury"}            # [1]
MALEFICS = {"Sun","Mars","Saturn"}

# Deep debilitation (dig-bala-zero) longitudes, sidereal  [1]
DEEP_DEBIL = {"Sun":190.0,"Moon":213.0,"Mars":118.0,"Mercury":345.0,
              "Jupiter":275.0,"Venus":177.0,"Saturn":20.0}

# Exaltation sign indices  [1]
EXALT_SIGN = {"Sun":0,"Moon":1,"Mars":9,"Mercury":5,"Jupiter":3,"Venus":11,"Saturn":6}

# Moolatrikona: (sign_index, start_deg, end_deg) in D1  [1]
MOOLATRIKONA = {"Sun":(4,0.0,20.0),"Moon":(1,3.0,30.0),"Mars":(0,0.0,12.0),
                "Mercury":(5,15.0,20.0),"Jupiter":(8,0.0,10.0),
                "Venus":(6,0.0,15.0),"Saturn":(10,0.0,20.0)}

# Natural friendship  [1]
FRIENDS  = {"Sun":{"Moon","Mars","Jupiter"},"Moon":{"Sun","Mercury"},
            "Mars":{"Sun","Moon","Jupiter"},"Mercury":{"Sun","Venus"},
            "Jupiter":{"Sun","Moon","Mars"},"Venus":{"Mercury","Saturn"},
            "Saturn":{"Mercury","Venus"}}
ENEMIES  = {"Sun":{"Venus","Saturn"},"Moon":set(),"Mars":{"Mercury"},
            "Mercury":{"Moon"},"Jupiter":{"Mercury","Venus"},
            "Venus":{"Sun","Moon"},"Saturn":{"Sun","Moon","Mars"}}

# Saptavargaja points  [1, Table in Santhanam ed.]
SAPTA = {"moolatrikona":45.0,"exaltation":30.0,"own":30.0,"great_friend":22.5,
         "friend":15.0,"neutral":7.5,"enemy":3.75,"bitter_enemy":1.875,
         "fallen":1.875}

# Naisargika bala: 60 shared in weekday order  [1]
NAISARGIKA = {"Sun":60.0,"Moon":51.43,"Venus":42.86,"Jupiter":34.29,
              "Mercury":25.71,"Mars":17.14,"Saturn":8.57}

# Required minimums in virupas  [1]  (rupas x60: 6.5,6,5,7,6.5,5.5,5)
CLASSICAL_MINIMUMS = {"Sun":390.0,"Moon":360.0,"Mars":300.0,"Mercury":420.0,
                      "Jupiter":390.0,"Venus":330.0,"Saturn":300.0}

WEEK_LORDS = ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"]
HORA_CYCLE = ["Saturn","Jupiter","Mars","Sun","Venus","Mercury","Moon"]   # Chaldean [1]

TEMP_FRIEND_DISTANCES = {2,3,4,10,11,12}     # temporary friend if host is these many houses away [1]


@dataclass
class BalaConfig:
    """Disputed-variant switches. Defaults follow Raman's worked examples [2]."""
    nathonnata_curve: str = "linear"      # "linear" (Raman arithmetic) | "sine"
    nathonnata_mercury: str = "always60"  # "always60" (strict [1]) | "max_of_both"
    sun_ayana_doubling: bool = False      # regional school doubles Sun's ayana; [1] silent
    bhava_dig_mode: str = "raman_step"    # "raman_step" (house-steps [2]) | "degree" (smooth)
    drik_divisor: float = 4.0             # net aspect divided by 4  [1]

DEFAULT_CONFIG = BalaConfig()

# ===========================================================================
# SMALL HELPERS
# ===========================================================================

def _norm(x):            return x % 360.0
def _shortest(a, b):
    """Shortest unsigned arc between two longitudes."""
    d = abs(_norm(a) - _norm(b))
    return 360.0 - d if d > 180.0 else d

def _sign_of(lon):       return int(_norm(lon) // 30)
def _deg_in_sign(lon):   return _norm(lon) % 30


def _vargas(lon):
    """Sign indices of D1,D2,D3,D4,D7,D9,D12 for a sidereal longitude.  [1]"""
    s, d = _sign_of(lon), _deg_in_sign(lon)
    d2  = ((4 if d < 15 else 3) if s % 2 == 0 else (3 if d < 15 else 4))
    d3  = (s + 4 * int(d / 10)) % 12
    d4s = s if s % 3 == 0 else (s + 3) % 12 if s % 3 == 1 else (s + 6) % 12
    d4  = (d4s + 3 * int(d / 7.5)) % 12
    d7  = ((s if s % 2 == 0 else s + 6) + int(d / (30.0 / 7))) % 12
    d9s = s if s % 3 == 0 else (s + 8 if s % 3 == 1 else s + 4)
    d9  = (d9s + int(d / (10.0 / 3))) % 12
    d12 = (s + int(d / 2.5)) % 12
    return [s, d2, d3, d4, d7, d9, d12]


def _natural_relation(planet, host):
    """+1 friend, -1 enemy, 0 neutral  [1]."""
    if host == planet:                       return 0
    if host in FRIENDS[planet]:              return 1
    if host in ENEMIES[planet]:              return -1
    return 0


# ===========================================================================
# DRISHTI (aspect) CURVE — one definition reused everywhere  [1]
# Anchors: 0 @30deg, 15 @60, 30 @90, 45 @120, 60 @180, mirror decay to 300.
# Special aspects (Mars 4th/8th, Jup 5th/9th, Sat 3rd/10th) reuse the SAME
# curve re-centred on the special angle, so peak 60 sits there and the curve
# joins the ordinary curve continuously at +/-45 deg.
# ===========================================================================

_SPECIAL_CENTERS = {"Mars": (90.0, 210.0), "Jupiter": (120.0, 240.0), "Saturn": (60.0, 270.0)}

def _base_curve(d):
    if d < 30 or d >= 300:  return 0.0
    if d < 60:              return (d - 30) / 2.0
    if d < 90:              return 15.0
    if d < 120:             return 15.0 + (d - 60) / 2.0
    if d < 180:             return 30.0 + (d - 90) / 6.0
    return (300.0 - d) / 2.0

def drishti_value(aspector, sep):
    """Aspect value (0..60) of `aspector` at separation `sep` degrees."""
    centers = _SPECIAL_CENTERS.get(aspector)
    if centers:
        for c in centers:
            off = abs(((sep - c + 180) % 360) - 180)
            if off <= 45.0:
                return _base_curve(180.0 - off)
    return _base_curve(sep)


# ===========================================================================
# SHADBALA SUB-SCORES
# ===========================================================================

def _uchcha(p, lon):                                  # [1] arc from deep-fall / 3
    return _shortest(lon, DEEP_DEBIL[p]) / 3.0

def _saptavargaja(p, lon, all_vg):                    # [1] dignity across 7 vargas
    total, vargas = 0.0, _vargas(lon)
    for vi, vs in enumerate(vargas):
        host = SIGN_LORDS[vs]
        if vi == 0:                                   # moolatrikona only meaningful in D1
            si, a, b = MOOLATRIKONA[p]
            if vs == si and a <= _deg_in_sign(lon) <= b:
                total += SAPTA["moolatrikona"]; continue
        if vs == EXALT_SIGN[p]:
            total += SAPTA["exaltation"]; continue
        if _sign_of(DEEP_DEBIL[p]) == vs:
            total += SAPTA["fallen"]; continue
        if host == p:
            total += SAPTA["own"]; continue
        nat = _natural_relation(p, host)
        dist = (all_vg[host][vi] - vs) % 12 + 1
        comp = nat + (1 if dist in TEMP_FRIEND_DISTANCES else -1)
        total += {2:SAPTA["great_friend"],1:SAPTA["friend"],0:SAPTA["neutral"],
                  -1:SAPTA["enemy"],-2:SAPTA["bitter_enemy"]}[comp]
    return total

def _ojhayugma(p, lon):                               # [1] odd/even rasi x navamsa
    odd_r, odd_n = (_sign_of(lon) % 2 == 0), (_vargas(lon)[5] % 2 == 0)
    return 15.0 if odd_r and odd_n else 7.5 if (not odd_r) and (not odd_n) else 0.0

def _kendradi(p, lon, asc_deg):                       # [1] 60/30/15 from Lagna
    h = (_sign_of(lon) - _sign_of(asc_deg)) % 12 + 1
    return 60.0 if h in (1,4,7,10) else 30.0 if h in (2,5,8,11) else 15.0

def _drekkana(p, lon):                                # [1] own third of sign
    k = int(_deg_in_sign(lon) / 10)
    return 15.0 if SIGN_LORDS[(_sign_of(lon) + 4 * k) % 12] == p else 7.5

def _planetary_dig(p, lon, asc_deg, mc_deg):          # [1] arc from weak point / 3
    ic, dc = _norm(mc_deg + 180), _norm(asc_deg + 180)
    weak = {"Sun": ic, "Mars": ic, "Moon": mc_deg, "Venus": mc_deg,
            "Mercury": dc, "Jupiter": dc, "Saturn": asc_deg}[p]
    return _shortest(lon, weak) / 3.0

def _mean_sun_sidereal(jd):                           # [3] mean Sun, made sidereal
    T = (jd - 2451545.0) / 36525.0
    L = 280.46646 + 36000.76983 * T + 0.0003032 * T * T
    return _norm(L - swe.get_ayanamsa_ut(jd))

def _shaighra_reference(p, jd, flags):                # [1] cycle reference point
    if p in ("Mercury", "Venus", "Moon"):
        return _mean_sun_sidereal(jd)
    if p == "Sun":                                    # solar apogee (mandocca) [3]
        T = (jd - 2451545.0) / 36525.0
        apo_tropical = _norm(282.94719 + 3.42663 * T)
        return _norm(apo_tropical - swe.get_ayanamsa_ut(jd))
    helio_flag = getattr(swe, "FLG_HELCTR", getattr(swe, "FLG_HELIO", 8))
    pos, _ = swe.calc_ut(jd, PLANET_IDS[p], flags | helio_flag)
    return _norm(pos[0] + 180.0)                      # outer planets: helio + 180

def _cheshta(p, jd, flags, lon, speed):               # [1]+[R4] cycle position, NOT speed ratio
    k = _norm(lon - _shaighra_reference(p, jd, flags))
    if speed < 0:
        k = 360.0 - k                                 # retrograde: inverted kendra [1]
    return k / 3.0, k                                 # 0..120 virupas, plus audit kendra


def _rise_set(jd, lat, lon):
    """Precise sunrise/sunset around jd. Returns (srise, sset, next_srise)."""
    _, tr = swe.rise_trans(jd, swe.SUN, swe.CALC_RISE, (lon, lat, 0))
    srise = tr[0]
    if srise > jd:
        _, tr = swe.rise_trans(jd - 1.0, swe.SUN, swe.CALC_RISE, (lon, lat, 0))
        srise = tr[0]
    _, tr = swe.rise_trans(srise, swe.SUN, swe.CALC_SET, (lon, lat, 0))
    sset = tr[0]
    _, tr = swe.rise_trans(sset + 0.1, swe.SUN, swe.CALC_RISE, (lon, lat, 0))
    return srise, sset, tr[0]

def _wrap_event(jd, probe, threshold_hi=40.0):
    """Most recent moment before jd when probe() wrapped (x->x+360). Bisection."""
    t = jd
    prev = probe(t)
    for _ in range(400):
        t -= 1.0
        cur = probe(t)
        if cur > 320.0 and prev < threshold_hi:
            lo, hi = t, t + 1.0
            for _ in range(40):
                m = 0.5 * (lo + hi)
                if probe(m) > 180.0: lo = m
                else:                hi = m
            return hi
        prev = cur
    return None

def _kala_bala(p, jd, cfg, lat, lon, flags, sun_lon, moon_lon):
    """All eight temporal strengths, itemised.  [1]"""
    srise, sset, nsrise = _rise_set(jd, lat, lon)
    is_day = srise <= jd <= sset

    # --- 1. Nathonnata: 60 at own peak (noon / midnight), 0 at opposite ---
    if is_day:
        x = (jd - srise) / (sset - srise)
        frac_noon = abs(x - 0.5) * 2.0                    # 0 at noon, 1 at edges
    else:
        span = nsrise - sset
        g = (jd - sset) / span if jd >= sset else (jd - (nsrise - 24*3600/86400*0) - 0) / span \
            if False else (jd - (srise - span)) / span    # elapsed night fraction
        g = min(max(g, 0.0), 1.0)
        x = g                                             # reuse x as elapsed-fraction
        frac_noon = abs((g + 0.5) % 1.0 - 0.5) * 2.0      # 0 at midnight
    if cfg.nathonnata_curve == "sine":
        day_val = 30.0 * (1.0 + math.cos(math.pi * frac_noon))
    else:
        day_val = 60.0 * (1.0 - frac_noon)
    day_val = min(max(day_val, 0.0), 60.0)
    if p in ("Sun", "Jupiter", "Venus"):  natho = day_val
    elif p in ("Moon", "Mars", "Saturn"): natho = 60.0 - day_val
    else:                                 natho = 60.0 if cfg.nathonnata_mercury == "always60" \
                                                else max(day_val, 60.0 - day_val)

    # --- 2. Paksha: illumination share ---
    e = _norm(moon_lon - sun_lon);  e = 360.0 - e if e > 180.0 else e
    paksha = (e / 3.0) if p in ("Moon", "Jupiter", "Venus") else \
             (60.0 - e / 3.0) if p in ("Sun", "Mars", "Saturn") else max(e / 3.0, 60.0 - e / 3.0)

    # --- 3. Tribhaga: ruler of current third of day/night ---
    frac_elapsed = x
    part = min(2, int(frac_elapsed * 3))
    tribhaga = 60.0 if p == (("Jupiter","Sun","Mercury") if is_day else ("Moon","Venus","Mars"))[part] else 0.0

    # --- 4-7. Dina / Hora / Masa / Varsha lords ---
    day_lord = WEEK_LORDS[int(srise + 1.5) % 7]
    dina  = 45.0 if p == day_lord else 0.0
    hidx  = int((jd - srise) * 24.0) % 7
    hora  = 60.0 if p == HORA_CYCLE[(HORA_CYCLE.index(day_lord) + hidx) % 7] else 0.0
    masa_probe   = lambda t: _norm(swe.calc_ut(t, swe.MOON, flags)[0][0] - swe.calc_ut(t, swe.SUN, flags)[0][0])
    nm   = _wrap_event(jd, masa_probe)
    masa = 30.0 if (nm and p == WEEK_LORDS[int(nm + 1.5) % 7]) else 0.0
    yr_probe = lambda t: _norm(swe.calc_ut(t, swe.SUN, flags)[0][0])
    sk   = _wrap_event(jd, yr_probe)
    varsha = 15.0 if (sk and p == WEEK_LORDS[int(sk + 1.5) % 7]) else 0.0

    # --- 8. Ayana from declination  [1] ---
    eq, _ = swe.calc_ut(jd, PLANET_IDS[p], swe.FLG_SWIEPH | swe.FLG_EQUATORIAL)
    kranti = eq[1]
    eps = swe.calc_ut(jd, swe.ECL_NUT)[0][0]
    if p in ("Sun", "Mars", "Jupiter", "Venus"): ay = (eps + kranti) * 30.0 / eps
    elif p in ("Moon", "Saturn"):                ay = (eps - kranti) * 30.0 / eps
    else:                                        ay = (eps + abs(kranti)) * 30.0 / eps
    ay = min(max(ay, 0.0), 60.0)
    if p == "Sun" and cfg.sun_ayana_doubling:
        ay *= 2.0

    return {"nathonnata": natho, "paksha": paksha, "tribhaga": tribhaga,
            "dina": dina, "hora": hora, "masa": masa, "varsha": varsha,
            "ayana": ay}


def _net_aspect_on(target_lon, bodies, exclude=None, divisor=4.0):
    """Benefic gazes minus malefic gazes on a point, divided by divisor  [1]."""
    val = 0.0
    for q, b in bodies.items():
        if q == exclude: continue
        sep = _norm(target_lon - b["lon"])
        v = drishti_value(q, sep)
        val += v if q in BENEFICS else -v
    return val / divisor

# ===========================================================================
# MASTER ASSEMBLY
# ===========================================================================

def compute_planetary_shadbala(bodies, jd, lat, lon, flags, asc_deg, mc_deg,
                               cfg: BalaConfig = DEFAULT_CONFIG):
    """Full itemised Shadbala for the seven planets.
    `bodies`: {name: {'lon': sidereal_lon, 'speed': daily_motion}}"""
    all_vg = {q: _vargas(bodies[q]["lon"]) for q in SEVEN}
    out = {}
    for p in SEVEN:
        b = bodies[p]
        lon_, spd = b["lon"], b["speed"]

        uch   = _uchcha(p, lon_)
        sapta = _saptavargaja(p, lon_, all_vg)
        ojha  = _ojhayugma(p, lon_)
        kend  = _kendradi(p, lon_, asc_deg)
        drek  = _drekkana(p, lon_)

        r_uch = round(uch, 2)
        r_sapta = round(sapta, 2)
        r_ojha = round(ojha, 2)
        r_kend = round(kend, 2)
        r_drek = round(drek, 2)
        r_sthana = round(r_uch + r_sapta + r_ojha + r_kend + r_drek, 2)

        dig  = _planetary_dig(p, lon_, asc_deg, mc_deg)
        kal  = _kala_bala(p, jd, cfg, lat, lon, flags, bodies["Sun"]["lon"], bodies["Moon"]["lon"])
        r_kala_parts = {k: round(v, 2) for k, v in kal.items()}
        r_kala = round(sum(r_kala_parts.values()), 2)
        cheshta, kendra_audit = _cheshta(p, jd, flags, lon_, spd)
        nais  = NAISARGIKA[p]
        drik  = _net_aspect_on(lon_, bodies, exclude=p, divisor=cfg.drik_divisor)

        r_dig = round(dig, 2)
        r_cheshta = round(cheshta, 2)
        r_nais = round(nais, 2)
        r_drik = round(drik, 2)
        total = round(r_sthana + r_dig + r_kala + r_cheshta + r_nais + r_drik, 2)

        out[p] = {
            "sthana_bala": r_sthana,
            "sub": {"uchcha": r_uch, "saptavargaja": r_sapta,
                    "ojhayugma": r_ojha, "kendradi": r_kend,
                    "drekkana": r_drek},
            "dig_bala": r_dig,
            "kala_parts": r_kala_parts,
            "kala_bala": r_kala,
            "cheshta_bala": r_cheshta, "cheshta_kendra": round(kendra_audit, 2),
            "naisargika_bala": r_nais,
            "drik_bala": r_drik,
            "total": total,
            "rupas": round(total / 60.0, 2),
            "required_min": CLASSICAL_MINIMUMS[p],
            "pct_of_required": round(total / CLASSICAL_MINIMUMS[p] * 100.0, 1),
        }
    return out

# ------------------------- Bhava-level pieces ------------------------------

_GROUP_STRONG_HOUSE = {"nara": 1, "jalachara": 4, "chatushpada": 10, "keeta": 7}  # [1][2]

def _group_of(sign_idx, deg_in_sign):
    """Directional class of a sign portion  [1]: Sag & Cap split at 15 deg."""
    if sign_idx in (2,5,6,10):                 return "nara"
    if sign_idx in (3,11):                     return "jalachara"
    if sign_idx in (0,1,4):                    return "chatushpada"
    if sign_idx == 7:                          return "keeta"
    if sign_idx == 8:                          return "chatushpada" if deg_in_sign >= 15 else "nara"
    if sign_idx == 9:                          return "jalachara" if deg_in_sign >= 15 else "chatushpada"
    return "nara"

_HOUSE_STRONG_POINT = {1: "asc", 4: "ic", 7: "dc", 10: "mc"}

def _bhava_dig_degree(house_num, madhya, asc_deg, mc_deg):
    """Smooth directional strength of a house: treat its middle degree like a
    virtual planet (same arc/3 law as planetary dig bala).  [methodology:2]"""
    g = _group_of(_sign_of(madhya), _deg_in_sign(madhya))
    pts = {"asc": asc_deg, "mc": mc_deg,
           "ic": _norm(mc_deg + 180), "dc": _norm(asc_deg + 180)}
    strong_pt = pts[_HOUSE_STRONG_POINT[_GROUP_STRONG_HOUSE[g]]]
    return _shortest(madhya, _norm(strong_pt + 180)) / 3.0

def _bhava_dig_step(house_num, sign_idx):
    """Raman's house-step variant (multiples of 10)  [2]. Kept for fixture tests."""
    g = _group_of(sign_idx, 0.0)
    fwd = (house_num - _GROUP_STRONG_HOUSE[g]) % 12
    return float(60 - 10*fwd if fwd <= 6 else 10*(fwd - 6))

# ------------------------------ Public API ---------------------------------

def compute_bhava_bala(chart_data, jd, lat, lon, flags, cfg: BalaConfig = DEFAULT_CONFIG):
    """Drop-in replacement. Same call signature and result keys as before."""
    _, ascmc = swe.houses_ex(jd, lat, lon, b'W', flags)
    asc_deg, mc_deg = ascmc[0], ascmc[1]
    asc_sign = _sign_of(asc_deg)

    bodies = {}
    for p in SEVEN:
        src = chart_data.get(p, {})
        if "degree_total" in src and "speed" in src:
            bodies[p] = {"lon": src["degree_total"], "speed": src["speed"]}
        else:
            r, _ = swe.calc_ut(jd, PLANET_IDS[p], flags)
            bodies[p] = {"lon": r[0] % 360.0, "speed": r[3]}

    shad = compute_planetary_shadbala(bodies, jd, lat, lon, flags, asc_deg, mc_deg, cfg)

    warring = []
    tar = [q for q in SEVEN if q not in ("Sun", "Moon")]
    for i in range(len(tar)):
        for j in range(i+1, len(tar)):
            sep = _shortest(bodies[tar[i]]["lon"], bodies[tar[j]]["lon"])
            if sep < 1.0:
                warring.append((tar[i], tar[j], round(sep, 2)))

    houses = {}
    for h in range(1, 13):
        sign_idx = (asc_sign + h - 1) % 12
        madhya   = _norm(asc_deg + 30.0*(h-1) + 15.0)             # equal-house madhya
        lord     = SIGN_LORDS[sign_idx]
        adhipati = shad[lord]["total"]
        dig = (_bhava_dig_step(h, sign_idx) if cfg.bhava_dig_mode == "raman_step"
               else _bhava_dig_degree(h, madhya, asc_deg, mc_deg))
        drig = _net_aspect_on(madhya, bodies, divisor=cfg.drik_divisor)
        r_adhipati = round(adhipati, 2)
        r_dig = round(dig, 2)
        r_drig = round(drig, 2)
        r_total = round(r_adhipati + r_dig + r_drig, 2)
        r_rupas = round(r_total / 60.0, 2)
        houses[h] = {
            "sign": RASHI_NAMES[sign_idx], "sign_idx": sign_idx, "lord": lord,
            "madhya": round(madhya, 4),
            "adhipati": r_adhipati, "dig": r_dig, "drig": r_drig,
            "total": r_total, "rupas": r_rupas,
            "strength": "Strong" if r_rupas >= 8.0 else "Weak" if r_rupas < 5.5 else "Medium",
        }

    return {"houses": houses, "planets_shadbala": shad,
            "warring_pairs": warring, "config": vars(cfg)}

# --------------------------- Formatting (unchanged shapes) ------------------

def format_bhava_bala(bb):
    houses = bb.get("houses", {})
    if not houses: return "No Bhava Bala data available.\n"
    out = ("#### Bhava Bala Summary (House Strength in Virupas & Rupas)\n\n"
           "| House | Sign | Lord | Lord's Bala | Dig Bala | Drig Bala | Total (Virupas) | Rupas | Strength |\n"
           "|---|---|---|---|---|---|---|---|---|\n")
    for h in range(1, 13):
        d = houses[h]
        out += (f"| {h} | {d['sign']} | {d['lord']} | {d['adhipati']:.2f} | "
                f"{d['dig']:.2f} | {d['drig']:.2f} | **{d['total']:.2f}** | "
                f"**{d['rupas']:.2f}** | {d['strength']} |\n")
    for p1, p2, sep in bb.get("warring_pairs", []):
        out += (f"\n* Note: {p1} and {p2} within 1 deg ({sep} deg, graha yuddha). "
                f"The classical war adjustment is not modelled; interpret those lords cautiously.\n")
    return out

def format_bhava_bala_indicative(bb):
    houses = bb.get("houses", {})
    if not houses: return "No Bhava Bala data available.\n"
    scores = {h: houses[h]["adhipati"] + houses[h]["dig"] for h in houses}
    order = sorted(scores, key=lambda h: (-scores[h], h))
    rank = {h: i+1 for i, h in enumerate(order)}
    lines = ["HOUSE SUPPORT INDICATORS (ordinal estimates for interpretation)\n"]
    for h in range(1, 13):
        d = houses[h]
        lines.append(f"H{h} {d['sign']} — {d['strength']} support | Rank {rank[h]}/12")
    lines.append(f"\nTOP-SUPPORTED HOUSES: " + ", ".join(f"H{h}" for h in order[:3]))
    lines.append("MOST CHALLENGED HOUSES: " + ", ".join(f"H{h}" for h in sorted(order[-3:])))
    lines.append("\nNOTE FOR INTERPRETATION: broad support ranges, not exact measurements.")
    return "\n".join(lines)

def shadbala_percent(total_virupas, planet):
    return round(total_virupas / CLASSICAL_MINIMUMS[planet] * 100.0)

def strength_from_shadbala(total_virupas, planet):
    pct = total_virupas / CLASSICAL_MINIMUMS[planet] * 100.0
    return "Strong" if pct >= 110 else "Weak" if pct < 85 else "Medium"

def validate_bhava_bala(bb):
    # 1. Validate planetary shadbala integrity
    ps = bb.get("planets_shadbala", {})
    if len(ps) != 7:
        return False, f"Expected 7 classical planets in Shadbala, found {len(ps)}"
    for p in SEVEN:
        if p not in ps:
            return False, f"Missing planet {p} in Shadbala"
        tot = ps[p].get("total", 0.0)
        if not isinstance(tot, (int, float)) or tot <= 0:
            return False, f"Invalid total Virupas for {p}: {tot}"
        sub_sum = round(
            ps[p]["sthana_bala"] + ps[p]["dig_bala"] + ps[p]["kala_bala"] +
            ps[p]["cheshta_bala"] + ps[p]["naisargika_bala"] + ps[p]["drik_bala"], 2
        )
        if abs(tot - sub_sum) > 0.05:
            return False, f"{p} Shadbala subscore sum mismatch: {tot} vs {sub_sum}"

    # 2. Validate houses bhava bala integrity
    houses = bb.get("houses", {})
    if len(houses) != 12:
        return False, "Expected 12 houses in Bhava Bala"
    for h, d in houses.items():
        if abs(d["total"] - (d["adhipati"] + d["dig"] + d["drig"])) > 0.05:
            return False, f"H{h}: total mismatch"
        if abs(d["rupas"] - round(d["total"] / 60.0, 2)) > 0.01:
            return False, f"H{h}: rupas mismatch"
    return True, "ok"

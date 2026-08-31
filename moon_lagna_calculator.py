import streamlit as st
import swisseph as swe
from geopy.geocoders import ArcGIS, Nominatim
from timezonefinder import TimezoneFinder
import pytz
from datetime import datetime, timedelta
import math
import os
import matplotlib.pyplot as plt

# ==========================================
# 1. EXACT MOON SPEC ENGINE
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

RASHI_NAMES = [
    "Aries (Mesha)", "Taurus (Vrishabha)", "Gemini (Mithuna)", "Cancer (Karkataka)",
    "Leo (Simha)", "Virgo (Kanya)", "Libra (Tula)", "Scorpio (Vrischika)",
    "Sagittarius (Dhanus)", "Capricorn (Makara)", "Aquarius (Kumbha)", "Pisces (Meena)"
]

PLANET_ABBR = {
    "Sun": "Su", "Moon": "Mo", "Mars": "Ma", "Mercury": "Me",
    "Jupiter": "Ju", "Venus": "Ve", "Saturn": "Sa", "Rahu": "Ra", "Ketu": "Ke"
}

DASHA_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
VIMSHOTTARI_YEARS = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
    "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17
}

def calculate_moon_details(L):
    """Calculates Sign, Nakshatra, and Pada using exact arc-minute math."""
    L = L % 360.0
    M = L * 60.0

    R = math.floor(L / 30.0)
    sign_name = RASHI_NAMES[R]

    advancement_deg = L - (R * 30.0)
    d_int = int(advancement_deg)
    m_int = int(round((advancement_deg - d_int) * 60))
    advancement_str = f"{d_int}° {m_int:02d}'"

    N = math.floor(M / 800.0)
    nak_name, nak_lord = NAKSHATRAS[N]

    remaining_minutes = M % 800.0
    P = math.floor(remaining_minutes / 200.0) + 1

    dist_to_pada_boundary = min(remaining_minutes % 200.0, 200.0 - (remaining_minutes % 200.0))

    return {
        "sign_index": R,
        "sign_name": sign_name,
        "advancement": advancement_str,
        "nakshatra": nak_name,
        "nakshatra_lord": nak_lord,
        "pada": P,
        "pada_boundary_distance_deg": dist_to_pada_boundary / 60.0
    }

def get_house_from_sign_idx(ref_sign_idx, planet_sign_idx):
    """Whole-sign house position relative to a reference sign (Asc or Moon)."""
    return (planet_sign_idx - ref_sign_idx) % 12 + 1

# ==========================================
# 2. VIMSHOTTARI DASHA ENGINE
# ==========================================
def calculate_mahadashas(moon_deg, birth_dt):
    M = (moon_deg % 360.0) * 60.0
    nak_index = int(M // 800.0)
    _, nak_lord = NAKSHATRAS[nak_index]

    remaining_minutes = M % 800.0
    traversed_fraction = remaining_minutes / 800.0
    first_dasha_years = VIMSHOTTARI_YEARS[nak_lord]
    balance_years = (1 - traversed_fraction) * first_dasha_years

    periods = []
    start_date = birth_dt
    end_date = start_date + timedelta(days=balance_years * 365.2425)
    periods.append({"lord": nak_lord, "start": start_date, "end": end_date, "years": balance_years})

    idx = DASHA_ORDER.index(nak_lord)
    current_date = end_date
    for i in range(1, 9):
        lord = DASHA_ORDER[(idx + i) % 9]
        yrs = VIMSHOTTARI_YEARS[lord]
        next_date = current_date + timedelta(days=yrs * 365.2425)
        periods.append({"lord": lord, "start": current_date, "end": next_date, "years": yrs})
        current_date = next_date
    return periods

def calculate_antardashas(mahadasha_lord, maha_start, maha_years):
    idx = DASHA_ORDER.index(mahadasha_lord)
    periods = []
    current = maha_start
    for i in range(9):
        lord = DASHA_ORDER[(idx + i) % 9]
        yrs = maha_years * VIMSHOTTARI_YEARS[lord] / 120.0
        end = current + timedelta(days=yrs * 365.2425)
        periods.append({"lord": lord, "start": current, "end": end, "years": yrs})
        current = end
    return periods

def find_current_period(periods, as_of):
    for p in periods:
        if p["start"] <= as_of <= p["end"]:
            return p
    if periods and as_of < periods[0]["start"]:
        return periods[0]
    return periods[-1] if periods else None

# ==========================================
# 3. NORTH INDIAN CHART GEOMETRY
# ==========================================
_A, _B, _C, _D = (0, 100), (100, 100), (100, 0), (0, 0)
_E, _F, _G, _H = (50, 100), (100, 50), (50, 0), (0, 50)
_O = (50, 50)
_P1, _P2, _P3, _P4 = (75, 75), (75, 25), (25, 25), (25, 75)

HOUSE_POLYGONS = {
    1:  [_E, _P1, _O, _P4],
    2:  [_A, _E, _P4],
    3:  [_A, _H, _P4],
    4:  [_H, _P4, _O, _P3],
    5:  [_D, _H, _P3],
    6:  [_D, _G, _P3],
    7:  [_G, _P2, _O, _P3],
    8:  [_C, _P2, _G],
    9:  [_F, _C, _P2],
    10: [_F, _P1, _O, _P2],
    11: [_B, _P1, _F],
    12: [_B, _E, _P1],
}

def _centroid(pts):
    n = len(pts)
    return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)

def _outer_point(pts):
    return max(pts, key=lambda p: (p[0] - 50) ** 2 + (p[1] - 50) ** 2)

def draw_north_indian_chart(ref_sign_idx, chart_data, title, asc_house=None, retro=None):
    retro = retro or {}
    house_planets = {h: [] for h in range(1, 13)}

    for abbr, sign_idx in chart_data.items():
        h = get_house_from_sign_idx(ref_sign_idx, sign_idx)
        label = f"{abbr}(R)" if retro.get(abbr) == "Rx" else abbr
        house_planets[h].append(label)

    if asc_house:
        house_planets[asc_house] = ["Asc"] + house_planets[asc_house]

    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    ax.set_xlim(-5, 105)
    ax.set_ylim(-5, 105)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)

    ax.plot([0, 100, 100, 0, 0], [0, 0, 100, 100, 0], color="black", lw=1.8)
    ax.plot([_A[0], _C[0]], [_A[1], _C[1]], color="black", lw=1.2)
    ax.plot([_B[0], _D[0]], [_B[1], _D[1]], color="black", lw=1.2)
    ax.plot([_E[0], _F[0], _G[0], _H[0], _E[0]], [_E[1], _F[1], _G[1], _H[1], _E[1]], color="black", lw=1.2)

    for h, pts in HOUSE_POLYGONS.items():
        sign_idx = (ref_sign_idx + h - 1) % 12
        cx, cy = _centroid(pts)
        ox, oy = _outer_point(pts)
        lx, ly = ox + (cx - ox) * 0.32, oy + (cy - oy) * 0.32

        ax.text(lx, ly, str(sign_idx + 1), ha="center", va="center",
                fontsize=8, color="#999999")

        planets = house_planets[h]
        if planets:
            label = "\n".join(planets) if len(planets) <= 3 else " ".join(planets)
            ax.text(cx, cy - 4, label, ha="center", va="center",
                    fontsize=9.5, color="#B00020", fontweight="bold")

    plt.tight_layout()
    return fig

def draw_transit_overlay_chart(ref_sign_idx, natal_data, transit_data, title, retro_natal=None, retro_transit=None):
    retro_natal = retro_natal or {}
    retro_transit = retro_transit or {}

    natal_house_planets = {h: [] for h in range(1, 13)}
    transit_house_planets = {h: [] for h in range(1, 13)}

    for abbr, sign_idx in natal_data.items():
        h = get_house_from_sign_idx(ref_sign_idx, sign_idx)
        label = f"{abbr}(R)" if retro_natal.get(abbr) == "Rx" else abbr
        natal_house_planets[h].append(label)

    for abbr, sign_idx in transit_data.items():
        h = get_house_from_sign_idx(ref_sign_idx, sign_idx)
        label = f"t{abbr}(R)" if retro_transit.get(abbr) == "Rx" else f"t{abbr}"
        transit_house_planets[h].append(label)

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.set_xlim(-5, 105)
    ax.set_ylim(-5, 105)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)

    ax.plot([0, 100, 100, 0, 0], [0, 0, 100, 100, 0], color="black", lw=1.8)
    ax.plot([_A[0], _C[0]], [_A[1], _C[1]], color="black", lw=1.2)
    ax.plot([_B[0], _D[0]], [_B[1], _D[1]], color="black", lw=1.2)
    ax.plot([_E[0], _F[0], _G[0], _H[0], _E[0]], [_E[1], _F[1], _G[1], _H[1], _E[1]], color="black", lw=1.2)

    for h, pts in HOUSE_POLYGONS.items():
        sign_idx = (ref_sign_idx + h - 1) % 12
        cx, cy = _centroid(pts)
        ox, oy = _outer_point(pts)
        lx, ly = ox + (cx - ox) * 0.32, oy + (cy - oy) * 0.32

        ax.text(lx, ly, str(sign_idx + 1), ha="center", va="center",
                fontsize=8, color="#999999")

        if natal_house_planets[h]:
            natal_label = "\n".join(natal_house_planets[h])
            ax.text(cx, cy + 6, natal_label, ha="center", va="center",
                    fontsize=9, color="#0D47A1", fontweight="bold")

        if transit_house_planets[h]:
            transit_label = "\n".join(transit_house_planets[h])
            ax.text(cx, cy - 6, transit_label, ha="center", va="center",
                    fontsize=9, color="#D32F2F", fontweight="bold")

    plt.tight_layout()
    return fig

# ==========================================
# 4. GEOLOCATION HELPER
# ==========================================
tf = TimezoneFinder()

@st.cache_data(ttl=86400)
def get_location_data(city_name):
    try:
        geolocator = ArcGIS(timeout=10.0)
        loc = geolocator.geocode(city_name)
        if loc is not None:
            tz_name = tf.timezone_at(lng=loc.longitude, lat=loc.latitude)
            if tz_name:
                return (loc.latitude, loc.longitude, tz_name, loc.address)
    except Exception:
        pass

    try:
        geolocator = Nominatim(user_agent="moon-lagna-calculator/2.0", timeout=10.0)
        loc = geolocator.geocode(city_name)
        if loc is not None:
            tz_name = tf.timezone_at(lng=loc.longitude, lat=loc.latitude)
            if tz_name:
                return (loc.latitude, loc.longitude, tz_name, loc.address)
    except Exception:
        pass

    return None

# ==========================================
# 5. STREAMLIT UI
# ==========================================
st.set_page_config(page_title="Moon Lagna & Dasha Calculator", page_icon="🌙", layout="centered")
st.title("🌙 Moon Sign, Chandra Lagna & Vimshottari Dasha")
st.markdown("Enter birth details for the Moon sign, Nakshatra, both charts (Ascendant-based and "
            "Moon-based), and the Vimshottari Dasha timeline used for timing predictions.")

col1, col2 = st.columns(2)

with col1:
    dob_input = st.date_input(
        "Date of Birth",
        value=datetime(1990, 1, 1),
        min_value=datetime(1900, 1, 1),
        max_value=datetime(2100, 12, 31)
    )

    st.write("**Time of Birth (24-hour format)**")
    h_col, m_col = st.columns(2)

    with h_col:
        hour_val = st.selectbox("Hour", options=list(range(0, 24)), format_func=lambda x: f"{x:02d}")

    with m_col:
        minute_val = st.selectbox("Minute", options=list(range(0, 60)), format_func=lambda x: f"{x:02d}")

    time_input = datetime.strptime(f"{hour_val:02d}:{minute_val:02d}", "%H:%M").time()

    node_type = st.selectbox(
        "Rahu/Ketu calculation",
        ["True Node", "Mean Node"],
        index=0,
        help="True Node tracks the Moon's actual orbital crossing points. "
             "Mean Node is the smoothed average position and is commonly used in Indian astrology software."
    )

with col2:
    city_part = st.text_input("City / Town", placeholder="e.g., Pune")
    state_part = st.text_input("State / Region", placeholder="e.g., Maharashtra")
    country_val = st.text_input("Country", value="India")

    query_parts = [p for p in [city_part, state_part, country_val] if p]
    city_input = ", ".join(query_parts)

with st.expander("⚙️ Advanced: override coordinates manually"):
    manual_override = st.checkbox("Enter latitude / longitude / timezone myself")
    man_lat = st.number_input("Latitude", value=0.0, format="%.6f")
    man_lon = st.number_input("Longitude", value=0.0, format="%.6f")
    man_tz = st.text_input("Timezone (IANA name)", value="Asia/Kolkata")

if dob_input.year < 1906:
    st.info("ℹ️ India adopted a single standard time zone (IST, UTC+5:30) on 1 Jan 1906. "
            "For dates before 1906, double-check the effective offset for the birthplace.")

submit_button = st.button("Calculate Chart ✨", type="primary")

# ==========================================
# 6. BACKEND CALCULATIONS
# ==========================================
if submit_button:
    if manual_override:
        lat, lon, tz_name = man_lat, man_lon, man_tz
        location_label = f"manual override ({lat:.4f}, {lon:.4f}, {tz_name})"
    else:
        if not city_input:
            st.warning("⚠️ Please enter your City and Country, or use the manual override.")
            st.stop()

        with st.spinner("Locating birthplace..."):
            result = get_location_data(city_input)

        if result is None:
            st.error("❌ Could not locate that place. Try adding the state, or use manual override.")
            st.stop()

        lat, lon, tz_name, matched_address = result
        location_label = matched_address
        st.caption(f"📍 Matched location: {matched_address}")

    tz = pytz.timezone(tz_name)
    local_naive = datetime.combine(dob_input, time_input)

    try:
        local_dt = tz.localize(local_naive, is_dst=None)
    except pytz.exceptions.NonExistentTimeError:
        st.error("⚠️ Time does not exist due to a DST transition. Please pick another time.")
        st.stop()
    except pytz.exceptions.AmbiguousTimeError:
        st.error("⚠️ Time is ambiguous due to a DST fallback. Please choose an hour later.")
        st.stop()

    utc_dt = local_dt.astimezone(pytz.UTC)
    jd = swe.julday(
        utc_dt.year,
        utc_dt.month,
        utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
    )

    swe.set_sid_mode(swe.SIDM_LAHIRI)
    ayanamsa = swe.get_ayanamsa_ut(jd)

    ephe_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ephe")
    using_moshier = True

    if os.path.isdir(ephe_dir) and os.listdir(ephe_dir):
        swe.set_ephe_path(ephe_dir)
        try:
            swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
            using_moshier = False
        except Exception:
            using_moshier = True

    node_flag = swe.MEAN_NODE if node_type == "Mean Node" else swe.TRUE_NODE
    flags = (swe.FLG_MOSEPH if using_moshier else swe.FLG_SWIEPH) | swe.FLG_SIDEREAL | swe.FLG_SPEED

    PLANETS = {
        swe.SUN: 'Sun',
        swe.MOON: 'Moon',
        swe.MERCURY: 'Mercury',
        swe.VENUS: 'Venus',
        swe.MARS: 'Mars',
        swe.JUPITER: 'Jupiter',
        swe.SATURN: 'Saturn',
        node_flag: 'Rahu'
    }

    chart_data = {}

    for planet_id, planet_name in PLANETS.items():
        pos, _ = swe.calc_ut(jd, planet_id, flags)
        deg_total = pos[0] % 360
        speed = pos[3]
        status = "Rx" if speed < 0 and planet_id not in [swe.SUN, swe.MOON] else "Dir"
        sign_idx = int(deg_total / 30) % 12

        chart_data[planet_name] = {
            "sign": RASHI_NAMES[sign_idx],
            "degree_total": deg_total,
            "degree_in_sign": deg_total % 30,
            "sign_idx": sign_idx,
            "status": status
        }

    rahu_deg = chart_data["Rahu"]["degree_total"]
    ketu_deg = (rahu_deg + 180) % 360
    ketu_sign_idx = int(ketu_deg / 30) % 12

    chart_data["Ketu"] = {
        "sign": RASHI_NAMES[ketu_sign_idx],
        "degree_total": ketu_deg,
        "degree_in_sign": ketu_deg % 30,
        "sign_idx": ketu_sign_idx,
        "status": "Rx"
    }

    cusps, ascmc = swe.houses(jd, lat, lon, b'P')
    sidereal_asc = (ascmc[0] - ayanamsa) % 360
    asc_sign_idx = int(sidereal_asc / 30) % 12

    moon_deg = chart_data["Moon"]["degree_total"]
    moon_details = calculate_moon_details(moon_deg)
    moon_sign_idx = moon_details["sign_index"]

    for p_name, p_data in chart_data.items():
        p_data["moon_house"] = get_house_from_sign_idx(moon_sign_idx, p_data["sign_idx"])
        p_data["asc_house"] = get_house_from_sign_idx(asc_sign_idx, p_data["sign_idx"])

    st.success("Chart calculated successfully!")
    st.caption(
        f"Engine: {'Moshier analytical model' if using_moshier else 'Swiss Ephemeris files'} · "
        f"Ayanamsa (Lahiri): {ayanamsa:.4f}° · {node_type}"
    )
    st.write("---")

    # ==========================================
    # MOON DETAILS
    # ==========================================
    st.header("🌕 Moon Sign Details")

    mcol1, mcol2, mcol3 = st.columns(3)

    with mcol1:
        st.metric("Moon Sign (Rasi)", moon_details["sign_name"])
        st.caption(f"Advancement: {moon_details['advancement']}")

    with mcol2:
        st.metric("Nakshatra", moon_details["nakshatra"])
        st.caption(f"Lord: {moon_details['nakshatra_lord']}")

    with mcol3:
        st.metric("Pada (Quarter)", moon_details["pada"])
        st.caption(f"Total Longitude: {moon_deg:.4f}°")

    if moon_details["pada_boundary_distance_deg"] < 0.5:
        st.warning(
            f"⚠️ The Moon is only {moon_details['pada_boundary_distance_deg'] * 60:.1f} arc-minutes "
            f"from a Pada boundary. If birth time is uncertain, double-check it."
        )

    st.write("---")

    # ==========================================
    # BIRTH CHARTS
    # ==========================================
    st.header("🌐 Birth Charts")

    ccol1, ccol2 = st.columns(2)

    chart_signs = {PLANET_ABBR[name]: d["sign_idx"] for name, d in chart_data.items()}
    chart_retro = {PLANET_ABBR[name]: d["status"] for name, d in chart_data.items()}

    with ccol1:
        fig1 = draw_north_indian_chart(
            asc_sign_idx,
            chart_signs,
            "Lagna Chart (D1)",
            asc_house=1,
            retro=chart_retro
        )
        st.pyplot(fig1)
        st.caption(f"Ascendant: {RASHI_NAMES[asc_sign_idx]}.")

    with ccol2:
        fig2 = draw_north_indian_chart(
            moon_sign_idx,
            chart_signs,
            "Chandra Lagna (Moon Chart)",
            retro=chart_retro
        )
        st.pyplot(fig2)
        st.caption("Moon as 1st house.")

    st.write("---")

    # ==========================================
    # PLANET TABLE
    # ==========================================
    st.header("📋 Planetary Positions")

    table_data = [{
        "Planet": "🌙 Moon (Chandra Lagna)",
        "Sign": moon_details["sign_name"],
        "House from Asc": "—",
        "House from Moon": 1,
        "Degree": f"{chart_data['Moon']['degree_in_sign']:.2f}°",
        "Status": "Dir"
    }]

    for p_name, p_data in chart_data.items():
        table_data.append({
            "Planet": p_name,
            "Sign": p_data["sign"],
            "House from Asc": p_data["asc_house"],
            "House from Moon": p_data["moon_house"],
            "Degree": f"{p_data['degree_in_sign']:.2f}°",
            "Status": p_data["status"]
        })

    st.table(table_data)

    with st.expander("🔍 View Raw Planetary Longitudes"):
        raw_str = f"Ascendant: {sidereal_asc:.4f}° ({RASHI_NAMES[asc_sign_idx]})\n"
        for p_name, p_data in chart_data.items():
            raw_str += f"{p_name}: {p_data['degree_total']:.4f}° ({p_data['sign']})\n"
        st.text(raw_str)

    st.write("---")

    # ==========================================
    # VIMSHOTTARI DASHA
    # ==========================================
    st.header("⏳ Vimshottari Dasha Timeline")

    mahadashas = calculate_mahadashas(moon_deg, local_dt)
    now_aware = datetime.now(pytz.UTC)
    current_maha = find_current_period(mahadashas, now_aware)

    dasha_table = [{
        "Mahadasha Lord": p["lord"],
        "Start": p["start"].strftime("%d %b %Y"),
        "End": p["end"].strftime("%d %b %Y"),
        "Duration (yrs)": f"{p['years']:.2f}",
        "Current": "◀ now" if p is current_maha else ""
    } for p in mahadashas]

    st.table(dasha_table)

    if current_maha:
        st.subheader(f"Current Mahadasha: {current_maha['lord']} — Antardasha breakdown")

        antardashas = calculate_antardashas(
            current_maha["lord"],
            current_maha["start"],
            current_maha["years"]
        )

        current_antar = find_current_period(antardashas, now_aware)

        antar_table = [{
            "Antardasha Lord": p["lord"],
            "Start": p["start"].strftime("%d %b %Y"),
            "End": p["end"].strftime("%d %b %Y"),
            "Duration": f"{p['years'] * 12:.1f} months",
            "Current": "◀ now" if p is current_antar else ""
        } for p in antardashas]

        st.table(antar_table)

    st.caption("Dasha dates use a 365.2425-day astronomical year approximation.")

    st.write("---")

    # ==========================================
    # CURRENT TRANSITS / GOCHAR
    # ==========================================
    st.header("🪐 Current Planet Transits (Gochar)")

    now_aware = datetime.now(pytz.UTC)
    now_local = now_aware.astimezone(tz)

    st.markdown(f"Live planetary positions as of **{now_local.strftime('%d %b %Y, %H:%M %Z')}**.")

    jd_now = swe.julday(
        now_aware.year,
        now_aware.month,
        now_aware.day,
        now_aware.hour + now_aware.minute / 60.0 + now_aware.second / 3600.0
    )

    transit_data = {}

    for planet_id, planet_name in PLANETS.items():
        pos, _ = swe.calc_ut(jd_now, planet_id, flags)
        deg_total = pos[0] % 360
        speed = pos[3]
        status = "Rx" if speed < 0 and planet_id not in [swe.SUN, swe.MOON] else "Dir"
        sign_idx = int(deg_total / 30) % 12

        transit_data[planet_name] = {
            "sign": RASHI_NAMES[sign_idx],
            "degree_total": deg_total,
            "degree_in_sign": deg_total % 30,
            "sign_idx": sign_idx,
            "status": status
        }

    rahu_deg_now = transit_data["Rahu"]["degree_total"]
    ketu_deg_now = (rahu_deg_now + 180) % 360
    ketu_sign_idx_now = int(ketu_deg_now / 30) % 12

    transit_data["Ketu"] = {
        "sign": RASHI_NAMES[ketu_sign_idx_now],
        "degree_total": ketu_deg_now,
        "degree_in_sign": ketu_deg_now % 30,
        "sign_idx": ketu_sign_idx_now,
        "status": "Rx"
    }

    current_moon_details = calculate_moon_details(transit_data["Moon"]["degree_total"])

    st.info(
        f"🌙 **Today's Transit Moon:** {current_moon_details['sign_name']} | "
        f"**Nakshatra:** {current_moon_details['nakshatra']} (Pada {current_moon_details['pada']})"
    )

    transit_ref = st.radio(
        "View transit chart relative to:",
        ["Natal Moon (Chandra Lagna)", "Natal Ascendant (Lagna)"],
        horizontal=True,
        index=0
    )

    if "Moon" in transit_ref:
        transit_ref_idx = moon_sign_idx
        transit_chart_title = "Transits over Natal Moon Chart"
    else:
        transit_ref_idx = asc_sign_idx
        transit_chart_title = "Transits over Natal Lagna Chart"

    natal_signs = {PLANET_ABBR[name]: d["sign_idx"] for name, d in chart_data.items()}
    natal_retro = {PLANET_ABBR[name]: d["status"] for name, d in chart_data.items()}

    transit_signs = {PLANET_ABBR[name]: d["sign_idx"] for name, d in transit_data.items()}
    transit_retro = {PLANET_ABBR[name]: d["status"] for name, d in transit_data.items()}

    fig_transit = draw_transit_overlay_chart(
        transit_ref_idx,
        natal_signs,
        transit_signs,
        transit_chart_title,
        natal_retro,
        transit_retro
    )

    st.pyplot(fig_transit)
    st.caption(
        "🔵 **Blue** = Natal planets | 🔴 **Red** = Current transit planets. "
        "Red planets with blue planets in the same box indicate transit over natal planets."
    )

    # ==========================================
    # TRANSIT TABLE (ORGANIZED BY MOON HOUSE)
    # ==========================================

    # Group Natal Planets by House from Moon
    natal_by_moon_house = {h: [] for h in range(1, 13)}
    for n_name, n_data in chart_data.items():
        label = PLANET_ABBR[n_name]
        if n_data["status"] == "Rx":
            label += "(R)"
        natal_by_moon_house[n_data["moon_house"]].append(label)

    # Group Transit Planets by House from Moon
    transit_by_moon_house = {h: [] for h in range(1, 13)}
    for t_name, t_data in transit_data.items():
        label = f"t{PLANET_ABBR[t_name]}"
        if t_data["status"] == "Rx":
            label += "(R)"
        h_moon = get_house_from_sign_idx(moon_sign_idx, t_data["sign_idx"])
        transit_by_moon_house[h_moon].append(label)

    # Build the table row by row (House 1 to 12 from Moon)
    moon_house_table = []
    for h in range(1, 13):
        # The zodiac sign for this house relative to the Natal Moon
        sign_idx = (moon_sign_idx + h - 1) % 12
        zodiac_name = RASHI_NAMES[sign_idx]
        
        natal_here = ", ".join(natal_by_moon_house[h]) if natal_by_moon_house[h] else "—"
        transit_here = ", ".join(transit_by_moon_house[h]) if transit_by_moon_house[h] else "—"
        
        moon_house_table.append({
            "House No": h,
            "Zodiac Sign": zodiac_name,
            "Natal Planets": natal_here,
            "Transit Planets": transit_here
        })

    st.table(moon_house_table)

    st.caption(
        "Organized strictly by your Natal Moon. This makes it easy to see exactly which "
        "house and zodiac sign your transiting planets (t-) are currently occupying alongside your birth planets."
    )
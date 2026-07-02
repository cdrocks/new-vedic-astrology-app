import streamlit as st
import swisseph as swe
from geopy.geocoders import ArcGIS, Nominatim
from timezonefinder import TimezoneFinder
import pytz
from datetime import datetime, timedelta
from openai import OpenAI
import re
import requests
import traceback
import os
from debug_utils import diagnose, log_crash, log_prompt, user_friendly_code
import uuid
import hashlib


from engine import (
    get_nakshatra,
    calculate_vimshottari_dasha,
    find_next_ingress,
    find_next_station,
    detect_yogas,
    check_yoga_activation,
    calculate_panchadha_maitri,
    calculate_planetary_strength,
    calculate_ashtakavarga,
    validate_sav_invariant,
    map_functional_lords,
    calculate_pratyantardasha,
    get_combustion_status
)
from prompts import COMMON_RULES, WORKFLOWS, classify_workflow


# --- FREE QUESTION LIMIT SYSTEM ---
if "CHART_USAGE" not in st.session_state:
    st.session_state["CHART_USAGE"] = {}  # Tracks how many questions each birth chart has asked

def get_chart_id(dob, birth_time, city, country):
    """Creates a unique code from birth details. Same person = same code always."""
    raw = f"{dob.isoformat()}|{birth_time.strftime('%H:%M')}|{city.strip().lower()}|{country.strip().lower()}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]

# Generate a unique Session ID for the user's visit if one doesn't exist yet
if 'session_id' not in st.session_state:
    st.session_state['session_id'] = str(uuid.uuid4())

if "reading_ready" not in st.session_state:
    st.session_state["reading_ready"] = False
if "question_widget" not in st.session_state:
    st.session_state["question_widget"] = ""
if "city_input" not in st.session_state:
    st.session_state["city_input"] = ""
if "country_select" not in st.session_state:
    st.session_state["country_select"] = "India"

# ==========================================
# TARGET DATE EXTRACTOR (Future Questions)
# ==========================================
def add_months(dt, months):
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    max_day = [31, 29 if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0) else 28,
               31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    day = min(dt.day, max_day)
    return dt.replace(year=year, month=month, day=day)

def add_years(dt, years):
    try:
        return dt.replace(year=dt.year + years)
    except ValueError:
        return dt.replace(year=dt.year + years, day=dt.day - 1)

def extract_target_date(question, base_dt):
    t = question.lower()

    m = re.search(r'(?:after|in|next)\s+(\d+)\s+months', t)
    if m:
        return add_months(base_dt, int(m.group(1)))

    m = re.search(r'(?:after|in|next)\s+(\d+)\s+years', t)
    if m:
        return add_years(base_dt, int(m.group(1)))

    m = re.search(r'(\d+)\s+(?:months|years)\s+from\s+now', t)
    if m:
        num = int(m.group(1))
        return add_months(base_dt, num) if 'months' in t else add_years(base_dt, num)

    if 'next year' in t or 'in a year' in t:
        return add_years(base_dt, 1)

    m = re.search(r'\b(20\d{2})\b', t)
    if m:
        year = int(m.group(1))
        if year >= base_dt.year:
            try:
                return base_dt.replace(year=year)
            except ValueError:
                return base_dt.replace(year=year, day=base_dt.day - 1)

    return base_dt

def log_conversation_to_make(dob, location, birth_time, question, ai_answer):
    webhook_url = "https://hook.eu2.make.com/orkovgpw41bs1pef5s4wgx36lxfngfog"
    payload = {
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Session ID": st.session_state['session_id'],
        "DOB": str(dob),
        "Location": location,
        "Time of Birth": str(birth_time),
        "Question": question,
        "AI Answer": ai_answer
    }
    try:
        requests.post(webhook_url, json=payload, timeout=5)
    except:
        pass


# ==========================================
# 0. QUESTION FILTER & SAFETY LAYER
# ==========================================
def classify_question(text: str):
    """
    Returns: (status, flag)
    status: "ALLOWED" | "BLOCKED"
    flag  : category string (e.g., "fatalistic", "trivial", "none")
    """
    text_clean = text.lower().strip()
    if len(text_clean) < 8:
        return "BLOCKED", "short"

    # 1. FATALISTIC / EXTREME
    fatal_patterns = [
        r'\b(when|how|will|am i).{0,20}(die|death|dead|dying)\b',
        r'\b(kill myself|end my life|suicide|suicidal)\b',
        r'\b(murder|get murdered|be killed|assassinate)\b',
        r'\b(terminal.{0,10}(cancer|illness|disease))\b',
        r'\bincurable\b', r'\bexact.{0,5}date.{0,10}death\b',
        r'\bhow long.{0,10}(live|survive)\b', r'\bfatal.{0,5}(accident|crash|disease)\b'
    ]
    for pat in fatal_patterns:
        if re.search(pat, text_clean):
            return "BLOCKED", "fatalistic"

    # 2. OCCULT / HARM TO OTHERS
    occult_patterns = [
        r'\bblack magic\b', r'\bvashikaran\b', r'\bwitchcraft\b',
        r'\btantra.{0,10}(harm|destroy|kill)\b',
        r'\b(mantra|spell|totka).{0,10}(harm|destroy|enemy|revenge)\b',
        r'\bcurse.{0,5}(someone|enemy|ex|him|her)\b'
    ]
    for pat in occult_patterns:
        if re.search(pat, text_clean):
            return "BLOCKED", "occult"

    # 3. GAMBLING / SPECULATION TIPS
    gambling_patterns = [
        r'\b(lottery|lotto|jackpot|gambl|betting|wager|casino)\b',
        r'\b(which|what).{0,15}(stock|share|crypto|bitcoin).{0,15}(buy|sell|tip|pick)\b'
    ]
    for pat in gambling_patterns:
        if re.search(pat, text_clean):
            return "BLOCKED", "gambling"

    # 4. ILLEGAL / MALICIOUS INTENT
    illegal_patterns = [
        r'\b(cheat in exam|cheat on exam|evade tax|break the law|bribe|commit fraud|how do i commit)\b'
    ]
    for pat in illegal_patterns:
        if re.search(pat, text_clean):
            return "BLOCKED", "illegal"

    # 4.5 DELUSIONAL / PARANOID THEMES
    delusion_patterns = [
        r'\b(people are after me|everyone is against me|being watched|surveillance on me)\b',
        r'\b(am i cursed|generational curse|possessed|demon|evil spirit)\b',
        r'\b(chosen one|special powers|divine mission|prophet)\b',
        r'\b(spiritual attack|psychic attack|entity attachment)\b'
    ]
    for pat in delusion_patterns:
        if re.search(pat, text_clean):
            return "BLOCKED", "mental_health"

    # 5. ASTROLOGY RELEVANCE CHECK
    astro_keywords = {
        "career", "job", "business", "work", "profession", "promotion", "office", "transfer",
        "marriage", "spouse", "husband", "wife", "wedding", "married", "love", "relationship",
        "divorce", "affair", "partner", "matrimony", "engagement",
        "health", "illness", "disease", "sick", "hospital", "surgery", "recovery", "mental",
        "anxiety", "stress", "depression", "heal", "medicine", "doctor",
        "debt", "loan", "money", "finance", "wealth", "income", "salary", "property",
        "house", "home", "land", "flat", "apartment", "vehicle", "car",
        "child", "children", "son", "daughter", "pregnancy", "fertility", "baby", "kid", "progeny",
        "education", "exam", "study", "abroad", "travel", "visa", "settlement", "foreign", "pr",
        "spirituality", "dharma", "karma", "meditation", "god", "temple", "puja", "worship", "mantra",
        "legal", "court", "case", "litigation", "police", "jail", "lawyer", "judge", "fir", "accuse",
        "enemy", "competition", "threat", "danger", "accident", "theft", "loss", "fraud", "cheat", "dispute",
        "timing", "when", "delay", "auspicious", "muhurta", "mahadasha", "antardasha", "dasha",
        "transit", "gochar", "rahu", "ketu", "saturn", "shani", "sade sati", "mangal", "manglik",
        "dosha", "kundali", "horoscope", "chart", "planet", "rashi", "nakshatra", "graha", "lagna"
    }
    words_set = set(re.findall(r'\w+', text_clean))
    has_astro = bool(words_set & astro_keywords)

    # 6. TRIVIAL / UNRELATED
    trivial_patterns = [
        r'\b(chicken|mutton|burger|pizza|biryani|food|lunch|dinner|breakfast|snack)\b',
        r'\b(cricket match|ipl|football|fifa|world cup|score|match result)\b',
        r'\b(weather|rain|sunny|temperature|snow|monsoon)\b',
        r'\b(should i eat|what should i eat|will it rain|is it hot)\b'
    ]
    for pat in trivial_patterns:
        if re.search(pat, text_clean) and not has_astro:
            return "BLOCKED", "trivial"

    if not has_astro and len(text_clean) < 22:
        return "BLOCKED", "unrelated"

    # 7. SENSITIVE FLAGS (allowed, but noted)
    sensitive_keywords = [
        "legal", "court", "case", "litigation", "police", "jail", "lawyer", "judge", "fir", "crime",
        "debt", "loan", "bankruptcy", "financial crisis",
        "illness", "disease", "surgery", "hospital", "mental", "cancer", "operation", "medic",
        "accident", "danger", "emergency", "threat", "enemy", "fraud", "cheat", "loss", "dispute",
        "divorce", "affair", "extramarital", "separation"
    ]
    flagged = [kw for kw in sensitive_keywords if kw in text_clean]
    return "ALLOWED", ",".join(flagged) if flagged else "none"





# ==========================================
# 1. FRONTEND UI & TEXTS
# ==========================================
st.set_page_config(page_title="Vedic Astrology Reader", page_icon="🔮", layout="centered")

t = {
    "title": "Vedic Astrology Reader",
    "info": "This app uses advanced mathematical and reasoning tools to provide guidance. For suggestions and queries, mail: astrologerchinmay@gmail.com",
    "intro": "Enter your birth details below to receive a deeply personalized astrological reading. If you do not know your exact time of birth, please select 12:00",
    "privacy": "We never ask for your name, email, or phone number. Your chart details are used solely for calculations and are not saved on this server",
    "dob": "Date of Birth",
    "time": "Time of Birth (24-hour format)",
    "city": "City & Country of Birth",
    "city_ph": "e.g., Pune, India",
    "question": "What would you like to ask?",
    "question_ph": "e.g., Based on my current timeline, what is the best path for my career right now?",
    "btn": "Get Reading ✨",
    "warn": "⚠️ Please fill in your City and your Question before submitting.",
    "spin": "The reader is calculating your planetary matrices... this takes about 60 seconds.",
    "success": "Chart interpretation ready.",
    "expand": "🔍 View Your Raw Chart Data",
    "blocked_fatalistic": "⚠️ We do not answer questions about death, suicide, terminal illness, or fatal accidents. If you are in distress, please contact a mental health professional or a trusted person in your life.",
    "blocked_occult": "⚠️ Questions involving black magic, vashikaran, revenge, or harming others are outside the scope of this service.",
    "blocked_gambling": "⚠️ We do not provide guidance on gambling, lotteries, stock tips, or illegal activities.",
    "blocked_illegal": "⚠️ We cannot advise on illegal activities, cheating, or evading the law.",
    "blocked_trivial": "⚠️ Your question appears random or unrelated to life themes. Please ask about career, relationships, health outlook, finance, or spiritual growth.",
    "blocked_short": "⚠️ Your question is too brief. Please describe your concern in a full sentence.",
    "blocked_unrelated": "⚠️ This does not appear to be an astrological question. Please ask something related to your chart and life circumstances.",
    "blocked_mental_health": "⚠️ We cannot interpret experiences involving paranoia, supernatural attacks, or persecution beliefs. If these experiences are causing distress, please seek support from a trusted professional or person in your life.",
    "agree": "I confirm I am 18 or older and agree to the [Terms & Conditions](https://eighthouse.in/terms-and-conditions/) and Privacy Policy.",
    "agree_warn": "⚠️ You must confirm you are 18 or older and agree to the terms to receive a reading.",
}

COUNTRIES = [
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Argentina", "Armenia", "Australia",
    "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium",
    "Belize", "Benin", "Bhutan", "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil",
    "Brunei", "Bulgaria", "Burkina Faso", "Burundi", "Cambodia", "Cameroon", "Canada",
    "Cape Verde", "Central African Republic", "Chad", "Chile", "China", "Colombia", "Comoros",
    "Congo", "Congo, Democratic Republic of the", "Costa Rica", "Croatia", "Cuba", "Cyprus",
    "Czech Republic", "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador", "Egypt",
    "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji",
    "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany", "Ghana", "Greece", "Grenada",
    "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti", "Honduras", "Hungary", "Iceland",
    "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy", "Jamaica", "Japan",
    "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Korea, North", "Korea, South", "Kosovo",
    "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya",
    "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar", "Malawi", "Malaysia", "Maldives",
    "Mali", "Malta", "Marshall Islands", "Mauritania", "Mauritius", "Mexico", "Micronesia",
    "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia",
    "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria",
    "North Macedonia", "Norway", "Oman", "Pakistan", "Palau", "Palestine", "Panama",
    "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar",
    "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia",
    "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe",
    "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia",
    "Slovenia", "Solomon Islands", "Somalia", "South Africa", "South Sudan", "Spain",
    "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria", "Taiwan", "Tajikistan",
    "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago", "Tunisia",
    "Turkey", "Turkmenistan", "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates",
    "United Kingdom", "United States", "Uruguay", "Uzbekistan", "Vanuatu", "Vatican City",
    "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe"
]
default_country_index = COUNTRIES.index("India")

st.title(t["title"])

with st.sidebar:
    st.header("🔧 System Health")
    for comp, ok, msg in diagnose():
        icon = "🟢" if ok else "🔴"
        st.text(f"{icon} {comp}: {msg}")
    st.markdown("---")
    st.caption("If any item above is 🔴, fix it before running a reading.")

st.info(t["info"])
st.write(t["intro"])
st.caption(t["privacy"])

col1, col2 = st.columns(2)
with col1:
    dob_input = st.date_input(
        t["dob"],
        value=datetime(1990, 1, 1),
        min_value=datetime(1900, 1, 1),
        max_value=datetime.now()
    )

    st.write(f"**{t['time']}**")
    h_col, m_col = st.columns(2)
    with h_col:
        hour_val = st.selectbox(
            "Hour",
            options=list(range(0, 24)),
            index=12,
            format_func=lambda x: f"{x:02d}"
        )
    with m_col:
        minute_val = st.selectbox(
            "Minute",
            options=list(range(0, 60)),
            index=0,
            format_func=lambda x: f"{x:02d}"
        )

    time_input = datetime.strptime(f"{hour_val:02d}:{minute_val:02d}", "%H:%M").time()

with col2:
    st.text_input("City / Town", placeholder="e.g., Mumbai", key="city_input")
    st.selectbox("Country", COUNTRIES, index=default_country_index, key="country_select")

    city_part = st.session_state["city_input"].strip()
    city_input = f"{city_part}, {st.session_state['country_select']}" if city_part else ""


# ==========================================
# 1.5 THE QUESTION SECTION
# ==========================================

def set_question(q_text):
    st.session_state["question_widget"] = q_text


st.write("---")

user_question = st.text_area(
    t["question"],
    placeholder=t["question_ph"],
    key="question_widget",
    height=100
)

with st.expander("💡 Not sure what to ask? Click here for ideas"):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.button("💼 Career Timeline", on_click=set_question, args=("Based on my current Dasha and transits, what is the best career trajectory for me over the next 12 to 18 months?",), use_container_width=True)
        st.button("💰 Wealth Potential", on_click=set_question, args=("Where does my chart show the greatest potential for financial growth, and what specific blocks do I need to clear?",), use_container_width=True)
        st.button("🔄 Career Pivot", on_click=set_question, args=("I am feeling stuck professionally. What planetary influences are causing this, and when will the energy shift?",), use_container_width=True)
    with c2:
        st.button("✨ Soul's Purpose", on_click=set_question, args=("What is my soul's true purpose in this lifetime, as indicated by my Atmakaraka and Ascendant?",), use_container_width=True)
        st.button("💎 Hidden Strengths", on_click=set_question, args=("Are there any hidden talents or dormant strengths in my natal chart that I am not currently utilizing?",), use_container_width=True)
        st.button("⚖️ Karmic Lesson", on_click=set_question, args=("Looking at Rahu and Ketu, what is the biggest karmic lesson I am meant to learn, and how can I navigate it?",), use_container_width=True)
    with c3:
        st.button("❤️ Relationships", on_click=set_question, args=("What does my chart reveal about my approach to partnerships and the timing for deep commitments?",), use_container_width=True)
        st.button("🔮 Upcoming Phase", on_click=set_question, args=("As my current Antardasha period progresses, what specific life themes or challenges should I be preparing for?",), use_container_width=True)
        st.button("🧠 Mental Clarity", on_click=set_question, args=("Based on my Moon's exact placement, what daily habits or environments will bring me the most mental clarity right now?",), use_container_width=True)

st.write("---")

# Show free question countdown before the button
temp_chart_id = get_chart_id(dob_input, time_input, st.session_state["city_input"], st.session_state["country_select"])
used = st.session_state["CHART_USAGE"].get(temp_chart_id, 0)
remaining = max(0, 3 - used)
st.caption(f"🎟️ Free questions remaining for this chart: **{remaining}/3**")

user_agrees = st.checkbox(t["agree"])
submit_button = st.button(t["btn"], type="primary")


# ==========================================
# HELPER: GEOLOCATION + TIMEZONE
# ==========================================
tf = TimezoneFinder()


@st.cache_data(ttl=86400)
def get_location_data(city_name):
    """Try ArcGIS first, fall back to Nominatim. Returns (lat, lon, tz_name) or None."""
    try:
        geolocator = ArcGIS(timeout=10.0)
        loc = geolocator.geocode(city_name)
        if loc is not None:
            tz_name = tf.timezone_at(lng=loc.longitude, lat=loc.latitude)
            if tz_name:
                return (loc.latitude, loc.longitude, tz_name)
    except Exception:
        pass

    try:
        geolocator = Nominatim(user_agent="vedic-oracle/1.0", timeout=10.0)
        loc = geolocator.geocode(city_name)
        if loc is not None:
            tz_name = tf.timezone_at(lng=loc.longitude, lat=loc.latitude)
            if tz_name:
                return (loc.latitude, loc.longitude, tz_name)
    except Exception:
        pass

    return None





# ==========================================
# 2. BACKEND LOGIC
# ==========================================
if submit_button:
    st.session_state["reading_ready"] = False

    if not user_agrees:
        st.error(t["agree_warn"])
        st.stop()

    if not city_input or not user_question.strip():
        st.warning(t["warn"])
        st.stop()

    # --- QUESTION FILTER GATE ---
    status, flag = classify_question(user_question)
    if status == "BLOCKED":
        msg_key = f"blocked_{flag}"
        display_msg = t.get(msg_key, t.get("blocked_unrelated"))
        st.error(display_msg)
        st.stop()

    # --- 3 QUESTION LIMIT GATE ---
    chart_id = get_chart_id(dob_input, time_input, st.session_state["city_input"], st.session_state["country_select"])

    used_count = st.session_state["CHART_USAGE"].get(chart_id, 0)
    if used_count >= 3:
        st.error("🔒 You have already used all 3 free questions for this birth chart. Please try again later.")
        st.stop()

    with st.spinner(t["spin"]):
        try:
            deepseek_key = None
            try:
                if hasattr(st, "secrets"):
                    deepseek_key = st.secrets.get("DEEPSEEK_API_KEY")
            except Exception:
                pass

            if not deepseek_key:
                deepseek_key = os.getenv("DEEPSEEK_API_KEY")

            if not deepseek_key:
                st.error("🔑 API key not found. Please add DEEPSEEK_API_KEY to your Streamlit secrets or environment variables.")
                st.stop()

            client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")

            # --- STEP 1: GEOLOCATION & TIMEZONE ---
            result = get_location_data(city_input)
            if result is None:
                st.error("❌ Could not locate that city. Please check the spelling, try a larger nearby city, or verify your country selection.")
                st.stop()

            lat, lon, tz_name = result
            tz = pytz.timezone(tz_name)
            local_naive = datetime.combine(dob_input, time_input)

            try:
                local_dt = tz.localize(local_naive, is_dst=None)
            except pytz.exceptions.NonExistentTimeError:
                st.error("⚠️ The selected time does not exist due to Daylight Saving Time (DST) transition. Please pick a valid time.")
                st.stop()
            except pytz.exceptions.AmbiguousTimeError:
                st.error("⚠️ The selected time is ambiguous due to a DST fallback. Please choose an hour later.")
                st.stop()

            utc_dt = local_dt.astimezone(pytz.UTC)
            jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day,
                            utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0)

            swe.set_sid_mode(swe.SIDM_LAHIRI)
            flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED

            # --- STEP 2: CALCULATE CHART DATA ---
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

            def get_rashi(degree):
                return RASHI_NAMES[int(degree / 30) % 12]

            def get_house_from_sign_idx(ref_sign_idx, planet_sign_idx):
                return (planet_sign_idx - ref_sign_idx) % 12 + 1



            DIGNITIES = {
                "Sun":     {"exalted": "Aries",     "debilitated": "Libra",      "own": ["Leo"]},
                "Moon":    {"exalted": "Taurus",    "debilitated": "Scorpio",    "own": ["Cancer"]},
                "Mars":    {"exalted": "Capricorn", "debilitated": "Cancer",     "own": ["Aries", "Scorpio"]},
                "Mercury": {"exalted": "Virgo",     "debilitated": "Pisces",     "own": ["Gemini", "Virgo"]},
                "Jupiter": {"exalted": "Cancer",    "debilitated": "Capricorn",  "own": ["Sagittarius", "Pisces"]},
                "Venus":   {"exalted": "Pisces",    "debilitated": "Virgo",      "own": ["Taurus", "Libra"]},
                "Saturn":  {"exalted": "Libra",     "debilitated": "Aries",      "own": ["Capricorn", "Aquarius"]}
            }



            def get_dignity(planet_name, sign):
                if planet_name not in DIGNITIES:
                    return None
                d = DIGNITIES[planet_name]
                if sign == d["exalted"]:     return "Exalted"
                elif sign == d["debilitated"]: return "Debilitated"
                elif sign in d["own"]:        return "Own Sign"
                return None

            # --- D9 NAVAMSA SIGN CALCULATOR ---
            def get_navamsa_sign_idx(deg_total):
                sign = int(deg_total / 30)
                deg_in_sign = deg_total % 30
                nav_num = int(deg_in_sign / (10.0 / 3.0))  # 0 to 8
                if sign % 3 == 0:    # Moveable (Aries, Cancer, Libra, Capricorn)
                    return (sign + nav_num) % 12
                elif sign % 3 == 1:  # Fixed (Taurus, Leo, Scorpio, Aquarius)
                    return (sign + 8 + nav_num) % 12
                else:                # Dual (Gemini, Virgo, Sagittarius, Pisces)
                    return (sign + 4 + nav_num) % 12

            # --- BUILD NATAL CHART ---
            chart_data = {}
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

            for planet_id, planet_name in PLANETS.items():
                pos, _ = swe.calc_ut(jd, planet_id, flags)
                deg_total = pos[0] % 360
                speed = pos[3]
                status = "Rx" if speed < 0 and planet_id not in [swe.SUN, swe.MOON] else "Dir"
                if planet_id == swe.TRUE_NODE:
                    status = "Rx"
                sign_idx = int(deg_total / 30) % 12

                nak_name, nak_lord, pada = get_nakshatra(deg_total)

                chart_data[planet_name] = {
                    "sign": RASHI_NAMES[sign_idx],
                    "house": get_house_from_sign_idx(asc_sign_idx, sign_idx),
                    "degree_total": deg_total,
                    "degree_in_sign": deg_total % 30,
                    "sign_idx": sign_idx,
                    "status": status,
                    "dignity": get_dignity(planet_name, RASHI_NAMES[sign_idx]),
                    "nakshatra": nak_name,
                    "nakshatra_lord": nak_lord,
                    "pada": pada
                }

            # KETU (always opposite Rahu)
            rahu_deg = chart_data["Rahu"]["degree_total"]
            ketu_deg = (rahu_deg + 180) % 360
            ketu_sign_idx = int(ketu_deg / 30) % 12

            nak_name, nak_lord, pada = get_nakshatra(ketu_deg)

            chart_data["Ketu"] = {
                "sign": RASHI_NAMES[ketu_sign_idx],
                "house": get_house_from_sign_idx(asc_sign_idx, ketu_sign_idx),
                "degree_total": ketu_deg,
                "degree_in_sign": ketu_deg % 30,
                "sign_idx": ketu_sign_idx,
                "status": "Rx",
                "dignity": None,
                "nakshatra": nak_name,
                "nakshatra_lord": nak_lord,
                "pada": pada
            }

            # --- PANCHADHA MAITRI CALCULATION ---
            # Package Sign Indices (0 to 11)
            natal_signs_for_maitri = {
                "Sun": chart_data["Sun"]["sign_idx"],
                "Moon": chart_data["Moon"]["sign_idx"],
                "Mars": chart_data["Mars"]["sign_idx"],
                "Mercury": chart_data["Mercury"]["sign_idx"],
                "Jupiter": chart_data["Jupiter"]["sign_idx"],
                "Venus": chart_data["Venus"]["sign_idx"],
                "Saturn": chart_data["Saturn"]["sign_idx"]
            }

            # Package House Positions (1 to 12)
            natal_houses_for_maitri = {
                "Sun": chart_data["Sun"]["house"],
                "Moon": chart_data["Moon"]["house"],
                "Mars": chart_data["Mars"]["house"],
                "Mercury": chart_data["Mercury"]["house"],
                "Jupiter": chart_data["Jupiter"]["house"],
                "Venus": chart_data["Venus"]["house"],
                "Saturn": chart_data["Saturn"]["house"]
            }

            # Execute the corrected function
            panchadha_data = calculate_panchadha_maitri(natal_signs_for_maitri, natal_houses_for_maitri)

            panchadha_string = "### PANCHADHA MAITRI (5-FOLD PLANETARY FRIENDSHIP)\n"
            for p_name, p_data in panchadha_data.items():
                panchadha_string += (
                    f"{p_name} in House {natal_houses_for_maitri[p_name]} "
                    f"→ Host: {p_data['Host']} | "
                    f"Natural: {p_data['Natural_Status']} | "
                    f"Temporary: {p_data['Temporary_Status']} | "
                    f"Final: {p_data['Final_Relationship']}\n"
                )

            # --- ASHTAKAVARGA (BAV + SAV) CALCULATION ---
            natal_positions_for_av = {
                "Ascendant": chart_data["Ascendant"]["sign_idx"] + 1,
                "Sun": chart_data["Sun"]["sign_idx"] + 1,
                "Moon": chart_data["Moon"]["sign_idx"] + 1,
                "Mars": chart_data["Mars"]["sign_idx"] + 1,
                "Mercury": chart_data["Mercury"]["sign_idx"] + 1,
                "Jupiter": chart_data["Jupiter"]["sign_idx"] + 1,
                "Venus": chart_data["Venus"]["sign_idx"] + 1,
                "Saturn": chart_data["Saturn"]["sign_idx"] + 1,
            }

            ashtakavarga_data = calculate_ashtakavarga(natal_positions_for_av)

            # Internal validation only (not shown to end users)
            invariant_ok, invariant_total = validate_sav_invariant(ashtakavarga_data)

            bav = ashtakavarga_data["Bhinnashtakavarga"]
            sav = ashtakavarga_data["Sarvashtakavarga"]

            # --- CALCULATE PLANETARY STRENGTH (Strong / Medium / Weak) ---
            for planet in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
                if planet in chart_data:
                    strength = calculate_planetary_strength(
                        planet, chart_data, panchadha_data, sav
                    )
                    chart_data[planet]["strength"] = strength

            # --- PLANETARY STRENGTH STRING ---
            strength_string = "### PLANETARY STRENGTH (Strong / Medium / Weak)\n"
            for planet in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
                if planet in chart_data:
                    strength = chart_data[planet].get("strength", "Medium")
                    strength_string += f"{planet}: {strength}\n"

            ashtakavarga_string = "### ASHTAKAVARGA SCORES\n\n"

            ashtakavarga_string += "#### Bhinnashtakavarga (BAV) — Individual Planetary Bindus\n"
            ashtakavarga_string += "| House | Sun | Moon | Mars | Mercury | Jupiter | Venus | Saturn |\n"
            ashtakavarga_string += "|-------|-----|------|------|---------|---------|-------|--------|\n"
            for h in range(1, 13):
                row = [str(bav[p][h]) for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]]
                ashtakavarga_string += f"| {h} | {' | '.join(row)} |\n"

            ashtakavarga_string += "\n#### Sarvashtakavarga (SAV) — Total Bindus per House\n"
            for h in range(1, 13):
                score = sav[h]
                strength = "Strong" if score >= 28 else "Weak" if score <= 18 else "Average"
                ashtakavarga_string += f"House {h}: {score} bindus ({strength})\n"


            # --- FUNCTIONAL HOUSE LORDS (WHOLE SIGN SYSTEM) ---
            functional_lords = map_functional_lords(asc_sign_idx)

            functional_lords_string = "### FUNCTIONAL HOUSE LORDS (KEY LIFE DOMAINS)\n"
            role_labels = {
                "Lagna_Lord": "1st House — Self / Vitality",
                "Wealth_Lord": "2nd House — Wealth / Assets",
                "Job_Lord": "6th House — Job / Debt / Acute Health",
                "Relationship_Lord": "7th House — Marriage / Partnerships",
                "Chronic_Health_Lord": "8th House — Longevity / Chronic Health",
                "Career_Lord": "10th House — Career / Status",
                "Gains_Lord": "11th House — Income / Gains",
            }
            for role, label in role_labels.items():
                functional_lords_string += f"{label}: {functional_lords[role]}\n"

            functional_lords_string += "\n#### Full Whole-Sign House Lord Table\n"
            SIGN_LORDS_FUNC = {
                0: "Mars", 1: "Venus", 2: "Mercury", 3: "Moon",
                4: "Sun", 5: "Mercury", 6: "Venus", 7: "Mars",
                8: "Jupiter", 9: "Saturn", 10: "Saturn", 11: "Jupiter",
            }
            for h in range(1, 13):
                sign_idx = (asc_sign_idx + h - 1) % 12
                lord = SIGN_LORDS_FUNC[sign_idx]
                functional_lords_string += f"House {h}: {lord}\n"

            # --- BUILD NAVAMSA (D9) CHART ---
            d9_chart_data = {}
            d9_asc_idx = get_navamsa_sign_idx(asc_deg)
            d9_chart_data["Ascendant"] = {
                "sign": RASHI_NAMES[d9_asc_idx],
                "sign_idx": d9_asc_idx
            }

            vargottama_planets = []

            for p_name, p_data in chart_data.items():
                if p_name == "Ascendant":
                    continue
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

            # --- STEP 3: BUILD AI STRINGS & DASHAS ---
            real_now = datetime.now(pytz.UTC)
            target_dt = extract_target_date(user_question, real_now)
            now_utc = target_dt  # All downstream code now uses the target date
            st.caption(f"Debug — Target date calculated: {now_utc.strftime('%d %b %Y %H:%M %Z')}")
            dasha_data = calculate_vimshottari_dasha(
                chart_data["Moon"]["degree_total"], utc_dt, now_utc
            )

            # --- PRATYANTARDASHA (3-TIER TIMING) ---
            ad_start_dt = datetime.strptime(dasha_data["ad_start"], "%d %b %Y")
            ad_end_dt = datetime.strptime(dasha_data["ad_end"], "%d %b %Y")

            pd_data = calculate_pratyantardasha(
                dasha_data["md"],
                dasha_data["ad"],
                ad_start_dt,
                ad_end_dt,
                now_utc.replace(tzinfo=None)
            )

            moon_nak, moon_nak_lord, moon_pada = get_nakshatra(chart_data["Moon"]["degree_total"])

            dasha_string = (
                f"### VIMSHOTTARI DASHA TIMELINE (CALCULATED FROM NATAL MOON)\n"
                f"Natal Moon Nakshatra: {moon_nak} (Lord: {moon_nak_lord}), Pada {moon_pada}\n"
                f"Current Mahadasha (Main Period): {dasha_data['md']}\n"
                f"  - Began: {dasha_data['md_start']} | Ends: {dasha_data['md_end']} (approx. {dasha_data['md_remaining_days']} days remaining)\n"
                f"Current Antardasha (Sub Period): {dasha_data['ad']}\n"
                f"  - Began: {dasha_data['ad_start']} | Ends: {dasha_data['ad_end']} (approx. {dasha_data['ad_remaining_days']} days remaining)\n"
                f"Current Pratyantardasha (Sub-Sub Period): {pd_data['current_pd']}\n"
                f"  - Began: {pd_data['pd_start']} | Ends: {pd_data['pd_end']}\n"
                f"Next Mahadasha: {dasha_data['md_next']} (begins {dasha_data['md_end']})\n"
                f"Next Antardasha: {dasha_data['ad_next']} (begins {dasha_data['ad_end']})\n"
            )

            # --- DETECT YOGAS & CHECK ACTIVATION ---
            detected_yogas = detect_yogas(chart_data, asc_sign_idx)
            yoga_activation = check_yoga_activation(detected_yogas, dasha_data)

            yoga_string = "### TOP YOGAS & DASHA ACTIVATION\n"
            if not yoga_activation:
                yoga_string += "No major classical yogas detected in this chart.\n"
            else:
                for i, y in enumerate(yoga_activation, 1):
                    status_icon = "🟢 ACTIVE" if y["active"] else "⚪ Inactive"
                    yoga_string += (
                        f"\n{i}. {y['name']} (Strength: {y['strength']}/100) — {status_icon}\n"
                        f"   Planets: {', '.join(y['planets'])}\n"
                        f"   Meaning: {y['desc']}\n"
                        f"   Activation: {y['timing']}\n"
                    )

            chart_string = (
                f"Ascendant: {chart_data['Ascendant']['sign']} "
                f"({chart_data['Ascendant']['degree_in_sign']:.2f}°) "
                f"[{chart_data['Ascendant']['nakshatra']} Pada {chart_data['Ascendant']['pada']}]\n"
            )

            aspects_string = ""

            def get_target_house(current_house, aspect_offset):
                return (current_house + aspect_offset - 2) % 12 + 1

            for p, pdata in chart_data.items():
                if p == "Ascendant":
                    continue

                combustion = get_combustion_status(p, chart_data)
                combust_tag = f" ({combustion} Combust)" if combustion else ""
                rx_tag = " (Retrograde)" if pdata.get('status') == 'Rx' else ""
                dignity_tag = f" ({pdata['dignity']})" if pdata.get("dignity") else ""
                nak_tag = f" — {pdata['nakshatra']} Pada {pdata['pada']}"

                chart_string += (
                    f"{p}: {pdata['sign']} ({pdata['degree_in_sign']:.2f}°) "
                    f"in House {pdata['house']}{nak_tag}{rx_tag}{combust_tag}{dignity_tag}\n"
                )

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

            # --- CHARA KARAKAS ---
            karaka_planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
            sorted_karakas = sorted(
                karaka_planets,
                key=lambda p: chart_data[p]["degree_in_sign"],
                reverse=True
            )

            karaka_labels = [
                "Atmakaraka (AK)", "Amatyakaraka (AmK)", "Bhratrikaraka (BK)",
                "Matrikaraka (MK)", "Putrakaraka (PK)", "Gnatikaraka (GK)", "Darakaraka (DK)"
            ]

            karaka_string = "### CHARA KARAKAS\n"
            for i, planet in enumerate(sorted_karakas):
                karaka_string += f"{karaka_labels[i]}: {planet} ({chart_data[planet]['degree_in_sign']:.2f}°)\n"

            # --- SUDARSHAN CHAKRA ---
            moon_sign_idx = chart_data["Moon"]["sign_idx"]
            sun_sign_idx = chart_data["Sun"]["sign_idx"]

            sudarshan_string = "### SUDARSHAN CHAKRA (3D PLACEMENTS)\n"
            sudarshan_string += "| Planet | Lagna (Body) | Moon (Mind) | Sun (Soul) |\n"
            sudarshan_string += "|---|---|---|---|\n"

            for p_name, p_data in chart_data.items():
                if p_name == "Ascendant":
                    continue
                h_lagna = get_house_from_sign_idx(asc_sign_idx, p_data["sign_idx"])
                h_moon  = get_house_from_sign_idx(moon_sign_idx, p_data["sign_idx"])
                h_sun   = get_house_from_sign_idx(sun_sign_idx, p_data["sign_idx"])

                combustion = get_combustion_status(p_name, chart_data)
                combust_flag = f" ({combustion[:3].upper()} C)" if combustion else ""
                rx_flag = " (Rx)" if p_data.get("status") == "Rx" else ""

                sudarshan_string += (
                    f"| {p_name}{combust_flag}{rx_flag} | House {h_lagna} | House {h_moon} | House {h_sun} |\n"
                )

            # --- LIVE TRANSITS (GOCHAR) ---
            jd_now = swe.julday(
                now_utc.year, now_utc.month, now_utc.day,
                now_utc.hour + now_utc.minute / 60.0 + now_utc.second / 3600.0
            )

            gochar_string = ""
            for p_id, p_name in PLANETS.items():
                pos_now, _ = swe.calc_ut(jd_now, p_id, flags)
                deg_now = pos_now[0] % 360
                sign_now_idx = int(deg_now / 30) % 12

                if p_name == "Rahu":
                    rx_tag = " (Rx)"
                elif p_name not in ["Sun", "Moon"] and pos_now[3] < 0:
                    rx_tag = " (Rx)"
                else:
                    rx_tag = ""

                house_from_asc  = (sign_now_idx - asc_sign_idx) % 12 + 1
                house_from_moon = (sign_now_idx - moon_sign_idx) % 12 + 1
                gochar_string += (
                    f"{p_name}{rx_tag} is transiting {RASHI_NAMES[sign_now_idx]} - "
                    f"Natal House {house_from_asc} (from Asc), "
                    f"Natal House {house_from_moon} (from Moon)\n"
                )

            # Ketu transit
            rahu_now_deg = swe.calc_ut(jd_now, swe.TRUE_NODE, flags)[0][0] % 360
            ketu_now_deg = (rahu_now_deg + 180) % 360
            ketu_transit_sign_idx = int(ketu_now_deg / 30) % 12
            ketu_house_asc  = (ketu_transit_sign_idx - asc_sign_idx) % 12 + 1
            ketu_house_moon = (ketu_transit_sign_idx - moon_sign_idx) % 12 + 1
            gochar_string += (
                f"Ketu (Rx) is transiting {RASHI_NAMES[ketu_transit_sign_idx]} - "
                f"Natal House {ketu_house_asc} (from Asc), "
                f"Natal House {ketu_house_moon} (from Moon)\n"
            )

            # Upcoming ingress & station events for slow planets
            transit_events = []
            slow_planets = [
                ("Jupiter", swe.JUPITER),
                ("Saturn",  swe.SATURN),
                ("Rahu",    swe.TRUE_NODE)
            ]

            for p_name, p_id in slow_planets:
                n_sign, n_date, n_dt = find_next_ingress(jd_now, p_id, flags, now_utc, RASHI_NAMES)
                if n_sign and n_date:
                    transit_events.append(f"{p_name} enters {n_sign}: {n_date}")

                if p_name not in ["Rahu", "Ketu"]:
                    st_type, st_date, st_dt = find_next_station(jd_now, p_id, flags, now_utc)
                    if st_type and st_date:
                        transit_events.append(f"{p_name} goes {st_type}: {st_date}")

            rahu_sign, rahu_date, _ = find_next_ingress(jd_now, swe.TRUE_NODE, flags, now_utc, RASHI_NAMES)
            if rahu_sign and rahu_date:
                ketu_next_sign = RASHI_NAMES[(RASHI_NAMES.index(rahu_sign) + 6) % 12]
                transit_events.append(f"Ketu enters {ketu_next_sign}: {rahu_date}")

            if transit_events:
                gochar_string += (
                    "\n### UPCOMING VERIFIED TRANSIT EVENTS\n"
                    + "\n".join(transit_events) + "\n"
                )

            # --- BUILD SENSITIVE DISCLAIMER IF NEEDED ---
            current_date = now_utc.strftime("%d %B %Y")

            sensitive_addon = ""
            if flag and flag != "none":
                topics = []
                if any(x in flag for x in ["legal", "court", "lawyer", "judge", "police", "fir"]):
                    topics.append("legal")
                if any(x in flag for x in ["illness", "disease", "surgery", "hospital", "mental", "cancer", "operation", "medic"]):
                    topics.append("medical")
                if any(x in flag for x in ["debt", "loan", "bankruptcy", "financial crisis"]):
                    topics.append("financial")

                if topics:
                    sensitive_addon = (
                        f"\nSENSITIVE AREA NOTICE: The user's question touches on {', '.join(topics)} matters. "
                        f"Provide only an astrological perspective. You MUST add a brief disclaimer that this is not a substitute for professional {' / '.join(topics)} advice."
                    )

            # --- SELECT WORKFLOW PROMPT ---
            workflow_type = classify_workflow(user_question)
            st.caption(f"Debug — Workflow: {workflow_type}")
            system_prompt = WORKFLOWS[workflow_type].format(
                chart_string=chart_string,
                aspects_string=aspects_string,
                d9_string=d9_string,
                panchadha_string=panchadha_string,
                strength_string=strength_string,
                ashtakavarga_string=ashtakavarga_string,
                functional_lords_string=functional_lords_string,
                dasha_string=dasha_string,
                gochar_string=gochar_string,
                yoga_string=yoga_string,
                karaka_string=karaka_string,
                current_date=current_date
            )

            # Append sensitive disclaimer if needed
            if sensitive_addon:
                system_prompt += sensitive_addon

            # --- DEBUG: VIEW EXACT PROMPT ---
            with st.expander("🔍 Debug — View raw prompt sent to DeepSeek"):
                st.text(f"Workflow: {workflow_type}\n")
                st.text(f"Target date: {now_utc.strftime('%d %b %Y %H:%M %Z')}\n")
                st.text(f"System prompt length: {len(system_prompt)} chars\n")
                st.text("-" * 40)
                st.text(system_prompt)
            log_prompt(system_prompt, workflow_type, user_question, chart_id)

            response = client.chat.completions.create(
                model="deepseek-v4-pro",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"The native asks: <question>{user_question}</question>"}
                ],
                temperature=0.4
            )

            # Only increment after a successful API response
            st.session_state["CHART_USAGE"][chart_id] = st.session_state["CHART_USAGE"].get(chart_id, 0) + 1

            st.session_state["reading_ready"] = True
            st.session_state["ai_response"] = response.choices[0].message.content
            log_conversation_to_make(dob_input, city_input, time_input, user_question, st.session_state["ai_response"])
            st.session_state["chart_string"]    = chart_string
            st.session_state["aspects_string"]  = aspects_string
            st.session_state["karaka_string"]   = karaka_string
            st.session_state["sudarshan_string"] = sudarshan_string
            st.session_state["dasha_string"]    = dasha_string
            st.session_state["gochar_string"]   = gochar_string
            st.session_state["yoga_string"]     = yoga_string
            st.session_state["d9_string"]       = d9_string
            st.session_state["panchadha_string"] = panchadha_string
            st.session_state["strength_string"] = strength_string
            st.session_state["ashtakavarga_string"] = ashtakavarga_string
            st.session_state["functional_lords_string"] = functional_lords_string
            st.session_state["pd_data"] = pd_data

        except Exception as e:
            err_msg = str(e)

            # Capture everything that is safe to record
            crash_context = {
                "dob": str(dob_input) if 'dob_input' in locals() else None,
                "time": str(time_input) if 'time_input' in locals() else None,
                "city": city_input if 'city_input' in locals() else None,
                "country": st.session_state.get("country_select"),
                "question": user_question if 'user_question' in locals() else None,
                "workflow": workflow_type if 'workflow_type' in locals() else None,
                "chart_id": chart_id if 'chart_id' in locals() else None,
            }
            crash_file = log_crash(e, crash_context)

            code = user_friendly_code(e)

            if "429" in err_msg or "rate" in err_msg.lower():
                st.error("💳 The DeepSeek account is out of credits or rate-limited.")
            elif "401" in err_msg:
                st.error("🔑 DeepSeek API key is invalid or revoked.")
            else:
                st.error(f"Something went wrong. {code}")

            with st.expander("🔧 Technical Details (copy this for support)"):
                st.write(f"**Log saved to:** `{crash_file}`")
                st.write(f"**Error code:** `{code}`")
                st.code(traceback.format_exc(), language="bash")


# ==========================================
# 5. DISPLAY OUTPUT
# ==========================================
if st.session_state["reading_ready"]:
    st.success(t["success"])
    st.write("---")
    st.markdown(st.session_state["ai_response"])

    with st.expander(t["expand"]):
        st.markdown("### Core Chart (D1)")
        st.text(st.session_state["chart_string"])

        st.markdown("### Planetary Aspects")
        st.text(st.session_state["aspects_string"])

        st.markdown(st.session_state["karaka_string"])
        st.markdown(st.session_state["sudarshan_string"])

        st.markdown("### Navamsa (D9) Chart")
        st.text(st.session_state["d9_string"])

        st.markdown(st.session_state["dasha_string"])
        st.markdown("### LIVE TRANSITS")
        st.text(st.session_state["gochar_string"])

        st.markdown("### Yogas & Activation")
        st.text(st.session_state["yoga_string"])

        st.markdown("### Panchadha Maitri (5-Fold Friendship)")
        st.text(st.session_state["panchadha_string"])

        st.markdown("### Planetary Strength")
        st.text(st.session_state["strength_string"])

        st.markdown("### Ashtakavarga (BAV + SAV)")
        st.text(st.session_state["ashtakavarga_string"])

        st.markdown("### Functional House Lords")
        st.text(st.session_state["functional_lords_string"])

        st.markdown("### Pratyantardasha (3-Tier Timing)")
        pd = st.session_state["pd_data"]
        st.write(f"**Current Pratyantardasha:** {pd['current_pd']}")
        st.write(f"**From:** {pd['pd_start']} → **To:** {pd['pd_end']}")

"""
theme.py
Indian traditional UI theme for the Vedic Astrology Reader app.
Import and call apply_theme() once, right after st.set_page_config().
"""

import streamlit as st


def apply_theme():
    st.markdown("""
    <style>
        /* Import a font that actually supports Devanagari (ॐ, शुभं भवतु) */
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari&family=Georgia&display=swap');

        /* Overall background with saffron gradient */
        .stApp {
            background: linear-gradient(135deg, #FFF5E1 0%, #FFDAB9 50%, #FFC0A0 100%);
        }

        /* Main content card - soft cream, rounded corners, shadow */
        .stApp .block-container {
            background-color: #FFFEF9;
            border-radius: 20px;
            padding: 2rem;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
            max-width: 800px;
            margin: 2rem auto;
            position: relative;
            z-index: 1;
        }

        /* Headers in a deep traditional colour */
        h1, h2, h3, h4, h5, h6 {
            color: #8B3A3A !important;
            font-family: 'Georgia', 'Times New Roman', serif !important;
        }

        /* Body text - scoped to actual content, NOT global div/span
           (global would break error/success/warning boxes) */
        .stApp .block-container p,
        .stApp .block-container label,
        .stMarkdown p,
        .stMarkdown li {
            color: #4A2C2A !important;
            font-family: 'Georgia', 'Times New Roman', serif !important;
        }

        /* Buttons - earthy gold (covers Get Reading, Check my balance,
           and the idea-suggestion buttons in the expander) */
        .stButton > button {
            background-color: #D4A76A !important;
            color: #3E2723 !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: bold !important;
            transition: all 0.3s ease;
        }
        .stButton > button:hover {
            background-color: #C5965B !important;
            box-shadow: 0 4px 12px rgba(180, 130, 50, 0.3);
        }
        /* Primary button (Get Reading) gets a slightly stronger accent */
        .stButton > button[kind="primary"] {
            background-color: #C1440E !important;
            color: #FFFEF9 !important;
        }
        .stButton > button[kind="primary"]:hover {
            background-color: #A8380B !important;
        }

        /* Text inputs and text areas (City/Town, identifier, question box) */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea {
            border: 1px solid #D4A76A !important;
            border-radius: 8px !important;
            background-color: #FFFEF9 !important;
            color: #4A2C2A !important;
        }

        /* Date input (Date of Birth) */
        .stDateInput > div > div > input {
            border: 1px solid #D4A76A !important;
            border-radius: 8px !important;
            background-color: #FFFEF9 !important;
            color: #4A2C2A !important;
        }

        /* Selectbox / dropdowns (Hour, Minute, Country) - closed state */
        .stSelectbox > div > div {
            border: 1px solid #D4A76A !important;
            border-radius: 8px !important;
            background-color: #FFFEF9 !important;
        }
        .stSelectbox > div > div > div {
            color: #4A2C2A !important;
        }
        /* Dropdown open menu + options (Country list is long - keep it legible) */
        div[data-baseweb="popover"] li {
            background-color: #FFFEF9 !important;
            color: #4A2C2A !important;
        }
        div[data-baseweb="popover"] li:hover {
            background-color: #F5E1C4 !important;
        }

        /* Checkbox (Terms & Conditions confirmation) */
        .stCheckbox label p {
            color: #4A2C2A !important;
        }

        /* Expander ("Not sure what to ask?" and the debug expanders) */
        .stExpander {
            border: 1px solid #D4A76A !important;
            border-radius: 8px !important;
            background-color: #FFFEF9 !important;
        }
        .stExpander summary {
            color: #8B3A3A !important;
            font-weight: bold !important;
        }

        /* Alert boxes: info (top notice), success (Chart interpretation ready),
           warning, error - kept individually readable rather than forced brown */
        div[data-testid="stAlert"] {
            border-radius: 10px !important;
        }
        div[data-testid="stAlertContentInfo"] p {
            color: #1B3A5C !important;
        }
        div[data-testid="stAlertContentSuccess"] p {
            color: #1E4620 !important;
        }
        div[data-testid="stAlertContentWarning"] p {
            color: #7A4A00 !important;
        }
        div[data-testid="stAlertContentError"] p {
            color: #7A1F1F !important;
        }
        div[data-testid="stAlert"] a {
            color: #8B3A3A !important;
            font-weight: bold;
        }

        /* Sidebar - deeper tone (covers older and newer Streamlit versions;
           your app shows a System Health panel here when not in production) */
        .stSidebar, [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #F5E1C4 0%, #E8CDA8 100%);
        }

        /* Om symbol watermark (subtle, behind content) */
        .stApp::before {
            content: "ॐ";
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 300px;
            color: rgba(180, 130, 50, 0.05);
            z-index: 0;
            pointer-events: none;
            font-family: 'Noto Sans Devanagari', sans-serif;
        }

        /* Mobile: tighter spacing, smaller headers, shrink the watermark
           so it stays a subtle background detail instead of dominating
           a narrow screen. Also stack the primary CTA full-width. */
        @media (max-width: 640px) {
            .stApp .block-container {
                padding: 1rem;
                margin: 0.5rem auto;
                border-radius: 12px;
            }
            h1 {
                font-size: 1.5rem !important;
            }
            h2, h3 {
                font-size: 1.15rem !important;
            }
            .stApp::before {
                font-size: 140px;
            }
            .stButton > button {
                width: 100%;
                padding: 0.6rem !important;
            }
        }
    </style>
    """, unsafe_allow_html=True)

    # Auspicious Om + tagline above the title
    st.markdown("""
    <div style="text-align: center; margin-bottom: -20px;">
        <span style="font-size: 48px; color: #D4A76A;">ॐ</span>
        <br>
        <span style="font-size: 14px; color: #8B3A3A; font-family: 'Noto Sans Devanagari', 'Georgia', serif;">
            शुभं भवतु • Shubham Bhavatu
        </span>
    </div>
    """, unsafe_allow_html=True)

"""
Sacred Divine Blessing Card Service.

Generates authentic, universally revered Vedic Deity Blessing Cards (Ashirwad Talismans)
based on the native's Atmakaraka (Soul Planet) and Janma Nakshatra.
"""

import os
import io
import base64
import logging
from typing import Dict, Any, Optional

from openai import OpenAI
from nakshatra_archetypes import get_nakshatra_archetype

logger = logging.getLogger("image_service")


# ==============================================================================
# 1. ATMAKARAKA DEITY MAPPINGS (BELOVED EVERYDAY VEDIC DEITIES)
# ==============================================================================

DEITY_BLESSINGS: Dict[str, Dict[str, str]] = {
    "Venus": {
        "deity": "Goddess Maha Lakshmi",
        "title": "Goddess of Supreme Grace, Love & Abundance",
        "iconography": "seated upon a glowing golden pink lotus, draped in royal red and gold Banarasi silk, holding fresh lotuses, showering golden light of prosperity, gentle compassionate smile, hand raised in Abhaya Varada Mudra",
        "blessing": "Bestows divine grace, emotional fulfillment, deep relationship harmony, and inner & outer prosperity."
    },
    "Moon": {
        "deity": "Lord Krishna",
        "title": "The Embodiment of Divine Love & Joy",
        "iconography": "standing in graceful Tribhanga posture holding a golden bansuri (flute), peacock feather crown, radiant azure complexion, draped in yellow pitambara silk, surrounded by glowing celestial starlight and blooming lotuses, peaceful loving smile",
        "blessing": "Bestows deep emotional serenity, pure unconditional love, mental peace, and joyful purpose."
    },
    "Sun": {
        "deity": "Lord Rama (Surya Narayana)",
        "title": "The Supreme Sovereign of Dharma & Nobility",
        "iconography": "standing in majestic royal grace with the divine bow Kodanda, glowing golden solar halo (Prabhamandala), jewel crown, serene noble countenance, embodying truth, honor, and sovereign spiritual dignity",
        "blessing": "Bestows supreme self-worth, moral clarity, righteous leadership, and unwavering life purpose."
    },
    "Saturn": {
        "deity": "Lord Hanuman",
        "title": "The Divine Protector & Vanquisher of Hardship",
        "iconography": "seated in deep devotional contemplation with radiant golden amber aura, hands in Anjali Mudra of pure devotion, immense spiritual power, serene compassionate expression, dispelling all fear, delays, and karmic burdens",
        "blessing": "Bestows indomitable courage, patience, endurance, and swift protection against all obstacles."
    },
    "Mars": {
        "deity": "Lord Hanuman & Lord Narasimha",
        "title": "The Invincible Shield of Courage",
        "iconography": "radiant divine aura of golden solar light, heroic grace, fearless protector posture granting Abhaya Mudra (protection from fear), radiating divine strength that removes doubts and clears obstacles",
        "blessing": "Bestows fearless determination, vibrant vitality, and triumph over all difficulties."
    },
    "Mercury": {
        "deity": "Goddess Saraswati",
        "title": "Goddess of Wisdom, Intellect & Fine Arts",
        "iconography": "seated gracefully upon a pure white lotus beside a serene swan, holding the sacred Veena and Vedas, draped in luminous white and gold silk, radiant third eye of intuition, serene and enlightened countenance",
        "blessing": "Bestows sharp intellect, articulate speech, business discernment, and creative mastery."
    },
    "Jupiter": {
        "deity": "Lord Vishnu (Guru Narayana)",
        "title": "The Supreme Preserver & Divine Guide",
        "iconography": "majestic four-armed Lord Vishnu seated in serene Padmasana on a glowing cosmic lotus, holding Shankha, Sudarshana Chakra, Gada, and Lotus, radiant golden Pitambara silk, benevolent smile granting divine boons",
        "blessing": "Bestows higher spiritual wisdom, fortune, moral expansion, and universal divine protection."
    },
    "Ketu": {
        "deity": "Lord Ganesha",
        "title": "The Remover of All Obstacles (Vighnaharta)",
        "iconography": "seated upon a golden throne holding a sacred modaka and lotus, sweet and wise elephant countenance, radiant third eye of spiritual vision, golden halo, raising right hand in divine blessing",
        "blessing": "Bestows effortless removal of hurdles, spiritual awakening, and auspicious new beginnings."
    },
    "Rahu": {
        "deity": "Maa Durga",
        "title": "The Supreme Mother & Slayer of Illusions",
        "iconography": "seated majestically on a golden lion, eight arms holding sacred instruments of light, divine compassionate yet fearless countenance, glowing radiant aura dispelling darkness, confusion, and fear",
        "blessing": "Bestows fearless confidence, deep inner clarity, protection against deceit, and worldly mastery."
    }
}

DEFAULT_DEITY = DEITY_BLESSINGS["Jupiter"]


def get_openai_api_key() -> Optional[str]:
    """Retrieve OpenAI API key from environment variables or .env / secrets.toml."""
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key

    # Check .env in workspace root
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENAI_API_KEY=") or ("OPENAI_API_KEY" in line and "=" in line and not line.startswith("#")):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if api_key:
                            return api_key
        except Exception as e:
            logger.debug(f"Failed to read .env: {e}")

    # Check .streamlit/secrets.toml fallback
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    if os.path.exists(secrets_path):
        try:
            with open(secrets_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "OPENAI_API_KEY" in line and "=" in line and not line.startswith("#"):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if api_key:
                            return api_key
        except Exception as e:
            logger.debug(f"Failed to read secrets.toml: {e}")

    return None


def _extract_image_result(item) -> Optional[str]:
    """Extract public URL or format base64 data URI from OpenAI response item."""
    if getattr(item, "url", None):
        return item.url
    b64 = getattr(item, "b64_json", None)
    if b64:
        return f"data:image/png;base64,{b64}"
    return None


def generate_divine_blessing_card(
    atmakaraka: str,
    nakshatra_name: str,
    seeker_name: str = "Seeker"
) -> Dict[str, Any]:
    """
    Generates an authentic, sacred Divine Blessing Card (Ashirwad Talisman)
    featuring the beloved ruling deity of the seeker's Atmakaraka (Soul Planet)
    blessing them within their Nakshatra's celestial aura.
    """
    api_key = get_openai_api_key()
    deity_info = DEITY_BLESSINGS.get(atmakaraka.strip().capitalize(), DEFAULT_DEITY)
    nak_info = get_nakshatra_archetype(nakshatra_name)

    if not api_key:
        logger.warning("OPENAI_API_KEY not found.")
        return {
            "image_url": None,
            "deity": deity_info["deity"],
            "deity_title": deity_info["title"],
            "blessing": deity_info["blessing"],
            "atmakaraka": atmakaraka,
            "nakshatra": nakshatra_name,
            "status": "missing_api_key"
        }

    try:
        client = OpenAI(api_key=api_key)

        prompt = (
            f"An authentic, breathtaking sacred Indian Vedic Temple Art & Blessing Card. "
            f"Depicting the divine form of {deity_info['deity']} ({deity_info['title']}). "
            f"{deity_info['iconography']}. "
            f"The deity is radiating warm, benevolent divine golden light of grace (Amrita Ashirwad), "
            f"showering sacred blessings upon the destiny of the seeker. "
            f"In the celestial background, the sacred starlight constellation of {nakshatra_name} Nakshatra "
            f"glows with deep cosmic midnight indigo, floating golden lotus petals, and warm temple oil lamp glow. "
            f"Framed in an exquisite, classical gold-leaf filigree temple arch with sacred Sanskrit aesthetic. "
            f"Masterpiece fine art, divine spiritual serene atmosphere, classical Indian devotional painting, "
            f"rich golden oil-canvas texture, 8k resolution, completely peaceful and awe-inspiring."
        )

        image_url = None
        for model_name in ["gpt-image-2", "chatgpt-image-latest", "gpt-image-1.5", "gpt-image-1"]:
            try:
                resp = client.images.generate(
                    model=model_name,
                    prompt=prompt,
                    size="1024x1024",
                    n=1
                )
                image_url = _extract_image_result(resp.data[0])
                if image_url:
                    logger.info(f"Generated divine blessing card via {model_name} for {deity_info['deity']}")
                    break
            except Exception as e:
                logger.warning(f"images.generate with {model_name} failed: {e}")

        if not image_url:
            return {
                "image_url": None,
                "deity": deity_info["deity"],
                "deity_title": deity_info["title"],
                "blessing": deity_info["blessing"],
                "atmakaraka": atmakaraka,
                "nakshatra": nakshatra_name,
                "status": "error: image generation failed for available models"
            }

        return {
            "image_url": image_url,
            "deity": deity_info["deity"],
            "deity_title": deity_info["title"],
            "blessing": deity_info["blessing"],
            "atmakaraka": atmakaraka,
            "nakshatra": nakshatra_name,
            "status": "success"
        }

    except Exception as exc:
        logger.error(f"Error generating divine blessing card: {exc}", exc_info=True)
        return {
            "image_url": None,
            "deity": deity_info["deity"],
            "deity_title": deity_info["title"],
            "blessing": deity_info["blessing"],
            "atmakaraka": atmakaraka,
            "nakshatra": nakshatra_name,
            "status": f"error: {str(exc)}"
        }


# Backward compatibility aliases
def generate_nakshatra_portrait(photo_base64: str = "", nakshatra_name: str = "Revati", guest_name: str = "Seeker") -> Dict[str, Any]:
    """Legacy alias: maps to divine blessing generation."""
    return generate_divine_blessing_card(atmakaraka="Venus", nakshatra_name=nakshatra_name, seeker_name=guest_name)


def generate_sacred_archetype(nakshatra_name: str) -> Dict[str, Any]:
    """Legacy alias: maps to divine blessing generation."""
    return generate_divine_blessing_card(atmakaraka="Jupiter", nakshatra_name=nakshatra_name)

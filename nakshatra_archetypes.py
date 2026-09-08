"""
Nakshatra Deity & Sacred Kuldevi Blessing Engine.

Defines canonical presiding deities (Nakshatra Lords / Kuldevis) and simple,
heartfelt divine blessings for all 27 Vedic Nakshatras.
"""

import logging
from typing import Dict

logger = logging.getLogger("nakshatra_archetypes")

# ==============================================================================
# 1. THE 27 NAKSHATRA DEITIES & SIMPLE SACRED BLESSINGS
# ==============================================================================

NAKSHATRA_ARCHETYPES: Dict[str, Dict[str, str]] = {
    "Ashwini": {
        "deity": "The Ashwini Kumaras",
        "title": "The Ashwini Kumaras",
        "blessing_message": "The Ashwini Kumaras are your Nakshatra Lords. May their divine healing and blessings guide you on your life journey.",
        "life_focus": "The Ashwini Kumaras are your Nakshatra Lords. May their divine healing and blessings guide you on your life journey.",
        "posture": "The divine Ashwini Kumaras, radiant twin celestial healers radiating golden dawn light and holding sacred healing amrita",
        "setting": "sacred Vedic dawn sanctuary with golden sunlight, blooming herbal flora, authentic Indian temple art aesthetic, 8k resolution"
    },
    "Bharani": {
        "deity": "Lord Yama (Dharmaraja)",
        "title": "Lord Yama (Dharmaraja)",
        "blessing_message": "Lord Dharmaraja is your Nakshatra Lord. May his divine truth, righteousness, and blessings guide you on your life journey.",
        "life_focus": "Lord Dharmaraja is your Nakshatra Lord. May his divine truth, righteousness, and blessings guide you on your life journey.",
        "posture": "Lord Dharmaraja seated in majestic dharmic composure holding the sacred sceptre of justice with glowing golden halo",
        "setting": "sacred ancient temple sanctum with warm earthen lamps, rich terracotta and gold hues, authentic Vedic art aesthetic, 8k resolution"
    },
    "Krittika": {
        "deity": "Lord Kartikeya (Murugan)",
        "title": "Lord Kartikeya (Murugan)",
        "blessing_message": "Lord Kartikeya is your Nakshatra Lord. May his divine courage and blessings guide you on your life journey.",
        "life_focus": "Lord Kartikeya is your Nakshatra Lord. May his divine courage and blessings guide you on your life journey.",
        "posture": "Lord Kartikeya holding the sacred Vel spear of victory, radiant youthful divine countenance with brilliant golden halo",
        "setting": "sacred temple courtyard with pure golden sacrificial flame, peacock feathers, warm amber glow, authentic Indian temple art, 8k resolution"
    },
    "Rohini": {
        "deity": "Lord Krishna",
        "title": "Lord Krishna",
        "blessing_message": "Lord Krishna is your Nakshatra Lord. May his divine love, grace, and blessings guide you on your life journey.",
        "life_focus": "Lord Krishna is your Nakshatra Lord. May his divine love, grace, and blessings guide you on your life journey.",
        "posture": "Lord Krishna in graceful Tribhanga posture playing a golden bansuri flute, wearing a peacock feather crown and pitambara silk, gentle loving smile",
        "setting": "sacred Vrindavan grove with blooming pink lotuses, soft silvery moonlight, celestial starlight, authentic classical Indian devotional art, 8k resolution"
    },
    "Mrigashira": {
        "deity": "Lord Chandra (Soma Dev)",
        "title": "Lord Chandra (Soma Dev)",
        "blessing_message": "Lord Chandra is your Nakshatra Lord. May his divine peace, calm wisdom, and blessings guide you on your life journey.",
        "life_focus": "Lord Chandra is your Nakshatra Lord. May his divine peace, calm wisdom, and blessings guide you on your life journey.",
        "posture": "Lord Chandra radiating luminous pearl-silver moonlight, holding sacred lotuses with tranquil compassionate smile",
        "setting": "celestial evening sky with crystalline crescent moon, floating water lilies, soft ethereal silver and indigo glow, authentic Vedic art, 8k resolution"
    },
    "Ardra": {
        "deity": "Lord Shiva (Rudra)",
        "title": "Lord Shiva (Rudra)",
        "blessing_message": "Lord Shiva is your Nakshatra Lord. May his divine protection, inner strength, and blessings guide you on your life journey.",
        "life_focus": "Lord Shiva is your Nakshatra Lord. May his divine protection, inner strength, and blessings guide you on your life journey.",
        "posture": "Lord Shiva in serene deep meditation with crescent moon in matted locks, sacred Ganga flowing, holding Trishula, radiating calm supreme peace",
        "setting": "sacred Himalayan Kailash peaks under twilight starlight, sacred ash, warm temple lamps, authentic Indian devotional painting, 8k resolution"
    },
    "Punarvasu": {
        "deity": "Goddess Aditi",
        "title": "Goddess Aditi (Cosmic Mother)",
        "blessing_message": "Goddess Aditi is your Nakshatra Deity. May her motherly grace, abundance, and blessings guide you on your life journey.",
        "life_focus": "Goddess Aditi is your Nakshatra Deity. May her motherly grace, abundance, and blessings guide you on your life journey.",
        "posture": "Goddess Aditi, the universal mother of light, seated gracefully upon a golden lotus with hands in Varada and Abhaya Mudra, gentle motherly smile",
        "setting": "radiant golden dawn sky with celestial rainbow of light, ancient temple pavilion, warm morning aura, authentic Indian temple art, 8k resolution"
    },
    "Pushya": {
        "deity": "Lord Brihaspati (Guru Dev)",
        "title": "Lord Brihaspati (Guru Dev)",
        "blessing_message": "Lord Brihaspati is your Nakshatra Lord. May his supreme wisdom, prosperity, and blessings guide you on your life journey.",
        "life_focus": "Lord Brihaspati is your Nakshatra Lord. May his supreme wisdom, prosperity, and blessings guide you on your life journey.",
        "posture": "Lord Brihaspati, divine preceptor of wisdom, seated in Padmasana holding sacred golden scriptures and rudraksha mala, radiant golden aura",
        "setting": "sacred temple sanctum with carved stone pillars, burning sandalwood incense, warm golden oil lamps, authentic Vedic aesthetic, 8k resolution"
    },
    "Ashlesha": {
        "deity": "Lord Shesha (Adi Shesha)",
        "title": "Lord Shesha (Adi Shesha)",
        "blessing_message": "Lord Shesha is your Nakshatra Lord. May his divine protection, intuition, and blessings guide you on your life journey.",
        "life_focus": "Lord Shesha is your Nakshatra Lord. May his divine protection, intuition, and blessings guide you on your life journey.",
        "posture": "The divine golden-hooded Lord Adi Shesha, cosmic guardian of spiritual wisdom, radiating celestial protective light with serene posture",
        "setting": "sacred celestial pool with blooming emerald lotuses, tranquil waters, mystical blue starlight, authentic Vedic art aesthetic, 8k resolution"
    },
    "Magha": {
        "deity": "Bhagwan Surya Narayana",
        "title": "Bhagwan Surya Narayana",
        "blessing_message": "Bhagwan Surya Narayana is your Nakshatra Lord. May his radiant grace, honor, and blessings guide you on your life journey.",
        "life_focus": "Bhagwan Surya Narayana is your Nakshatra Lord. May his radiant grace, honor, and blessings guide you on your life journey.",
        "posture": "Bhagwan Surya Narayana riding the golden solar chariot with radiant Prabhamandala halo, holding red lotuses, sovereign divine smile",
        "setting": "ancient temple courtyard overlooking majestic golden sunrise, banners of nobility, warm amber torchlight, authentic Vedic art, 8k resolution"
    },
    "Purva Phalguni": {
        "deity": "Goddess Maha Lakshmi",
        "title": "Goddess Maha Lakshmi",
        "blessing_message": "Goddess Maha Lakshmi is your Nakshatra Deity. May her divine grace, love, and abundance guide you on your life journey.",
        "life_focus": "Goddess Maha Lakshmi is your Nakshatra Deity. May her divine grace, love, and abundance guide you on your life journey.",
        "posture": "Goddess Maha Lakshmi seated gracefully upon a blooming golden-pink lotus, draped in royal crimson and gold silk, showering golden light of prosperity",
        "setting": "sacred golden temple pond with floating lotuses, warm rose-gold sunset glow, authentic classical Tanjore and temple devotional art, 8k resolution"
    },
    "Uttara Phalguni": {
        "deity": "Lord Aryaman",
        "title": "Lord Aryaman",
        "blessing_message": "Lord Aryaman is your Nakshatra Lord. May his divine honor, steadfastness, and blessings guide you on your life journey.",
        "life_focus": "Lord Aryaman is your Nakshatra Lord. May his divine honor, steadfastness, and blessings guide you on your life journey.",
        "posture": "Lord Aryaman seated in noble dharmic posture with radiant sunlit aura, hand raised in blessing of friendship and loyalty",
        "setting": "grand stone temple gateway under steady golden afternoon sun, saffron and terracotta light, authentic Vedic aesthetic, 8k resolution"
    },
    "Hasta": {
        "deity": "Bhagwan Savitur (Surya Dev)",
        "title": "Bhagwan Savitur",
        "blessing_message": "Bhagwan Savitur is your Nakshatra Lord. May his divine light, skill, and blessings guide you on your life journey.",
        "life_focus": "Bhagwan Savitur is your Nakshatra Lord. May his divine light, skill, and blessings guide you on your life journey.",
        "posture": "Bhagwan Savitur holding hands in radiant mudra of creative illumination, glowing with brilliant morning sunlight and golden warmth",
        "setting": "sacred temple terrace overlooking misty Himalayan dawn, soft golden light rays, authentic Indian temple art, 8k resolution"
    },
    "Chitra": {
        "deity": "Lord Vishwakarma",
        "title": "Lord Vishwakarma",
        "blessing_message": "Lord Vishwakarma is your Nakshatra Lord. May his divine creative genius and blessings guide you on your life journey.",
        "life_focus": "Lord Vishwakarma is your Nakshatra Lord. May his divine creative genius and blessings guide you on your life journey.",
        "posture": "Lord Vishwakarma, divine architect of the universe, holding sacred instruments of creation with luminous jewel crown and serene smile",
        "setting": "celestial temple palace with intricate carved golden arches, glowing crystalline jewels, starry cosmos, authentic Vedic aesthetic, 8k resolution"
    },
    "Swati": {
        "deity": "Goddess Saraswati",
        "title": "Goddess Saraswati",
        "blessing_message": "Goddess Saraswati is your Nakshatra Deity. May her divine wisdom, speech, and blessings guide you on your life journey.",
        "life_focus": "Goddess Saraswati is your Nakshatra Deity. May her divine wisdom, speech, and blessings guide you on your life journey.",
        "posture": "Goddess Saraswati seated gracefully upon a pure white lotus beside a serene swan, holding the sacred Veena and Vedas, luminous white silk, radiant halo",
        "setting": "sacred tranquil riverbank with blooming white lotuses, clear blue skies, soft morning breeze, authentic classical Indian devotional art, 8k resolution"
    },
    "Vishakha": {
        "deity": "Lord Kartikeya",
        "title": "Lord Kartikeya",
        "blessing_message": "Lord Kartikeya is your Nakshatra Lord. May his victorious strength, focus, and blessings guide you on your life journey.",
        "life_focus": "Lord Kartikeya is your Nakshatra Lord. May his victorious strength, focus, and blessings guide you on your life journey.",
        "posture": "Lord Kartikeya standing heroically with golden Vel spear and radiant aura of spiritual triumph, fearless compassionate countenance",
        "setting": "sacred temple hill top under triumphant amber sunset, warm temple lamps, authentic Indian temple painting, 8k resolution"
    },
    "Anuradha": {
        "deity": "Radha Rani & Lord Krishna",
        "title": "Radha Rani & Lord Krishna",
        "blessing_message": "Radha Rani and Lord Krishna bless your Nakshatra. May their pure love, harmony, and blessings guide you on your life journey.",
        "life_focus": "Radha Rani and Lord Krishna bless your Nakshatra. May their pure love, harmony, and blessings guide you on your life journey.",
        "posture": "Radha Rani and Lord Krishna standing together in divine harmony, holding a flute, radiating pure unconditional love and golden grace",
        "setting": "sacred lotus bower under gentle starry skies, soft glowing oil lamps, blooming kadamba trees, authentic devotional art, 8k resolution"
    },
    "Jyeshtha": {
        "deity": "Lord Narasimha",
        "title": "Lord Narasimha",
        "blessing_message": "Lord Narasimha is your Nakshatra Lord. May his fearless protection, courage, and blessings guide you on your life journey.",
        "life_focus": "Lord Narasimha is your Nakshatra Lord. May his fearless protection, courage, and blessings guide you on your life journey.",
        "posture": "Lord Narasimha seated in supreme protective majesty, hand raised in Abhaya Mudra granting total protection from all fear and harm",
        "setting": "ancient stone temple sanctum with glowing golden pillars, warm flame light, authentic Indian temple art, 8k resolution"
    },
    "Mula": {
        "deity": "Maa Mahakali",
        "title": "Maa Mahakali",
        "blessing_message": "Maa Mahakali is your Nakshatra Deity. May her fearless grace, transformation, and blessings guide you on your life journey.",
        "life_focus": "Maa Mahakali is your Nakshatra Deity. May her fearless grace, transformation, and blessings guide you on your life journey.",
        "posture": "Maa Mahakali in compassionate motherly protective form, hand raised in Abhaya Mudra dispelling all darkness and obstacles",
        "setting": "sacred temple altar with glowing earthen lamps, red flowers, deep midnight blue and gold starlight, authentic Vedic art, 8k resolution"
    },
    "Purva Ashadha": {
        "deity": "Maa Ganga",
        "title": "Maa Ganga",
        "blessing_message": "Maa Ganga is your Nakshatra Deity. May her pure waters of grace and divine blessings guide you on your life journey.",
        "life_focus": "Maa Ganga is your Nakshatra Deity. May her pure waters of grace and divine blessings guide you on your life journey.",
        "posture": "Maa Ganga seated upon a celestial white lotus holding a golden water vessel of amrita, radiating serene purity and gentle compassionate smile",
        "setting": "sacred river confluence under afternoon sunlight, sparkling crystalline waters, temple bells, authentic Indian devotional art, 8k resolution"
    },
    "Uttara Ashadha": {
        "deity": "Lord Ganesha",
        "title": "Lord Ganesha",
        "blessing_message": "Lord Ganesha is your Nakshatra Lord. May his auspicious grace, wisdom, and blessings guide you on your life journey.",
        "life_focus": "Lord Ganesha is your Nakshatra Lord. May his auspicious grace, wisdom, and blessings guide you on your life journey.",
        "posture": "Lord Ganesha seated upon a golden throne holding a sacred modaka and lotus, raising right hand in divine Abhaya blessing, sweet wise smile",
        "setting": "sacred temple pavilion with golden floral garlands, warm oil lamps, fragrant durva grass, authentic classical temple art, 8k resolution"
    },
    "Shravana": {
        "deity": "Lord Vishnu (Narayana)",
        "title": "Lord Vishnu (Narayana)",
        "blessing_message": "Lord Vishnu is your Nakshatra Lord. May his divine presence, peace, and blessings guide you on your life journey.",
        "life_focus": "Lord Vishnu is your Nakshatra Lord. May his divine presence, peace, and blessings guide you on your life journey.",
        "posture": "Lord Vishnu in serene four-armed form holding Shankha, Chakra, Gada, and Padma, draped in golden pitambara silk, radiant celestial smile",
        "setting": "celestial ocean of milk with blooming blue lotuses, glowing golden Prabhamandala halo, authentic classical Indian art, 8k resolution"
    },
    "Dhanishta": {
        "deity": "Lord Shiva",
        "title": "Lord Shiva",
        "blessing_message": "Lord Shiva is your Nakshatra Lord. May his divine harmony, prosperity, and blessings guide you on your life journey.",
        "life_focus": "Lord Shiva is your Nakshatra Lord. May his divine harmony, prosperity, and blessings guide you on your life journey.",
        "posture": "Lord Shiva seated in deep peaceful meditation holding damaru, radiating cosmic harmony, auspicious peace, and golden aura",
        "setting": "sacred temple courtyard under starry cosmos, warm brass oil lamps, authentic Indian temple painting, 8k resolution"
    },
    "Shatabhisha": {
        "deity": "Lord Dhanvantari",
        "title": "Lord Dhanvantari",
        "blessing_message": "Lord Dhanvantari is your Nakshatra Lord. May his divine healing, vitality, and blessings guide you on your life journey.",
        "life_focus": "Lord Dhanvantari is your Nakshatra Lord. May his divine healing, vitality, and blessings guide you on your life journey.",
        "posture": "Lord Dhanvantari, divine physician of the cosmos, holding the sacred pot of Amrita with radiant golden healing light",
        "setting": "sacred temple garden with flourishing medicinal herbs, soft golden sunbeams, tranquil starlight, authentic Vedic art aesthetic, 8k resolution"
    },
    "Purva Bhadrapada": {
        "deity": "Lord Shiva",
        "title": "Lord Shiva",
        "blessing_message": "Lord Shiva is your Nakshatra Lord. May his spiritual light, fortitude, and blessings guide you on your life journey.",
        "life_focus": "Lord Shiva is your Nakshatra Lord. May his spiritual light, fortitude, and blessings guide you on your life journey.",
        "posture": "Lord Shiva in dignified yogic tapasya beside sacred golden fire, radiating serene power, third eye of supreme intuition, peaceful countenance",
        "setting": "high mountain stone sanctum under midnight sky with warm golden ritual flame, authentic Indian temple art, 8k resolution"
    },
    "Uttara Bhadrapada": {
        "deity": "Lord Shiva",
        "title": "Lord Shiva",
        "blessing_message": "Lord Shiva is your Nakshatra Lord. May his deep peace, auspicious grace, and blessings guide you on your life journey.",
        "life_focus": "Lord Shiva is your Nakshatra Lord. May his deep peace, auspicious grace, and blessings guide you on your life journey.",
        "posture": "Lord Shiva seated in profound yogic stillness, radiant with deep compassion, golden crescent moon in hair, serene eyes granting peace",
        "setting": "calm sacred lake under silver moonlight, blooming lotuses, peaceful indigo and gold aura, authentic classical Vedic art, 8k resolution"
    },
    "Revati": {
        "deity": "Lord Vishnu",
        "title": "Lord Vishnu",
        "blessing_message": "Lord Vishnu is your Nakshatra Lord. May his loving protection, safe paths, and blessings guide you on your life journey.",
        "life_focus": "Lord Vishnu is your Nakshatra Lord. May his loving protection, safe paths, and blessings guide you on your life journey.",
        "posture": "Lord Vishnu as Pushan, the divine protector of journeys, extending gentle hand in Abhaya Varada blessing, holding golden lotus, benevolent smile",
        "setting": "sacred twilight riverbank with blooming pink lotuses, soft golden lanterns, starry night sky, authentic classical Indian devotional art, 8k resolution"
    }
}

# Default fallback if nakshatra is unrecognized
DEFAULT_ARCHETYPE = {
    "deity": "Lord Ganesha",
    "title": "Lord Ganesha",
    "blessing_message": "Lord Ganesha is your Nakshatra Lord. May his auspicious grace and divine blessings guide you on your life journey.",
    "life_focus": "Lord Ganesha is your Nakshatra Lord. May his auspicious grace and divine blessings guide you on your life journey.",
    "posture": "Lord Ganesha seated in divine blessing posture holding lotus and modaka with radiant golden halo",
    "setting": "sacred temple sanctum with warm oil lamps, authentic Indian temple art, 8k resolution"
}


def get_nakshatra_archetype(nakshatra_name: str) -> Dict[str, str]:
    """Retrieve the presiding Deity and simple blessing message for a given Nakshatra."""
    if not nakshatra_name:
        return DEFAULT_ARCHETYPE
    clean_name = nakshatra_name.strip()
    for key, val in NAKSHATRA_ARCHETYPES.items():
        if key.lower() in clean_name.lower():
            return val
    return DEFAULT_ARCHETYPE


# ==============================================================================
# 2. BACKWARD-COMPATIBILITY FORWARDER
# ==============================================================================
def generate_nakshatra_portrait(*args, **kwargs):
    """
    Deprecated: generate_nakshatra_portrait has moved to image_service.py.
    Forwarding call to image_service.generate_nakshatra_portrait for backward compatibility.
    """
    import image_service
    return image_service.generate_nakshatra_portrait(*args, **kwargs)


__all__ = [
    "NAKSHATRA_ARCHETYPES",
    "DEFAULT_ARCHETYPE",
    "get_nakshatra_archetype",
    "generate_nakshatra_portrait",
]

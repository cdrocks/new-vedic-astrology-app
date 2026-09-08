"""
Nakshatra Archetype & Sacred Visual Metadata Engine.

Defines canonical visual archetypes, postures, settings, and Life Focus summaries
for all 27 Vedic Nakshatras.
"""

import logging
from typing import Dict

logger = logging.getLogger("nakshatra_archetypes")

# ==============================================================================
# 1. THE 27 NAKSHATRA ARCHETYPES & LIFE FOCUS DEFINITIONS
# ==============================================================================

NAKSHATRA_ARCHETYPES: Dict[str, Dict[str, str]] = {
    "Ashwini": {
        "title": "The Celestial Healer & Pioneer",
        "posture": "seated in upright heroic poise with radiant dawn aura, gentle morning sunlight illuminating serene facial expression",
        "setting": "golden sunrise over sacred Himalayan foothills, gentle glowing herbal flora, celestial restorative light, authentic Indian Vedic spiritual aesthetic, 8k resolution, cinematic lighting",
        "life_focus": "Swift breakthroughs, pioneering new horizons, vibrant physical vitality, and natural restorative healing."
    },
    "Bharani": {
        "title": "The Sacred Vessel & Transformer",
        "posture": "seated in regal, deeply centered meditation with disciplined composure and warm inner focus",
        "setting": "ancient sanctum with glowing earthen lamps, rich crimson and terracotta hues, sacred banyan roots, celestial twilight, authentic Indian Vedic spiritual aesthetic, 8k resolution",
        "life_focus": "Deep personal transformation, moral courage, creative gestation, and unwavering sense of duty."
    },
    "Krittika": {
        "title": "The Flaming Torch & Truth-Seeker",
        "posture": "seated in dignified yogic posture with brilliant golden solar radiance, razor-sharp spiritual clarity",
        "setting": "sacred sacrificial fire altar with pure golden flames, clear starfield above, warm ambient amber light, authentic Indian Vedic aesthetic, 8k resolution",
        "life_focus": "Decisive leadership, illuminating absolute truth, burning away illusions, and protecting righteousness."
    },
    "Rohini": {
        "title": "The Radiant Creator & Nurturer",
        "posture": "seated gracefully in tranquil contemplation with a serene, compassionate smile, soft moonlight embracing the face",
        "setting": "flourishing sacred grove filled with blooming lotuses, gentle moonbeams reflecting on still crystal waters, ethereal emerald and silver aura, authentic Vedic aesthetic",
        "life_focus": "Artistic mastery, emotional nourishment, magnetic elegance, and building enduring material abundance."
    },
    "Mrigashira": {
        "title": "The Gentle Seeker & Visionary Scout",
        "posture": "seated in attentive, upright contemplation with gentle, curious, peaceful gaze",
        "setting": "mist-covered sacred deodar forest under twilight skies, soft golden-green forest glow, calm dew drops, authentic Indian Vedic aesthetic, 8k resolution",
        "life_focus": "Relentless pursuit of higher truth, intellectual curiosity, gentle wisdom, and lifelong learning."
    },
    "Ardra": {
        "title": "The Storm Master & Transformer",
        "posture": "seated in steady, unshakeable yogic poise amidst cleansing cosmic rainfall, calm expression of profound inner breakthrough",
        "setting": "celestial rain clouds breaking to reveal brilliant diamond starlight, soft electric-teal and indigo aura, authentic Vedic spiritual aesthetic, 8k resolution",
        "life_focus": "Overcoming emotional storms, intellectual rebirth, dismantling outdated illusions, and profound reinvention."
    },
    "Punarvasu": {
        "title": "The Restorer of Light & Abundance",
        "posture": "seated peacefully with open hands of benevolence, gentle golden light emanating from the heart center",
        "setting": "radiant dawn sky with a celestial golden rainbow, ancient stone pavilion overlooking lush valleys, warm morning glow, authentic Vedic aesthetic, 8k resolution",
        "life_focus": "Renewal after adversity, emotional recovery, ethical wealth, and guiding lost souls back to their light."
    },
    "Pushya": {
        "title": "The Divine Sage & Protector",
        "posture": "seated in noble, sovereign meditation with deep spiritual poise, golden halo of wisdom surrounding head",
        "setting": "ancient temple courtyard with carved stone pillars, warm golden lamps, sacred sandalwood fragrance in the air, authentic Indian Vedic aesthetic, 8k resolution",
        "life_focus": "Spiritual guardianship, unselfish nourishment, ethical leadership, and grounded, enduring dharma."
    },
    "Ashlesha": {
        "title": "The Intuitive Mystic & Awakener",
        "posture": "seated in deeply introspective yogic stillness with piercing, intuitive, knowing eyes",
        "setting": "secluded sacred pool surrounded by ancient flowering jasmine, mystical emerald and indigo moonlight, tranquil waters, authentic Vedic spiritual aesthetic, 8k resolution",
        "life_focus": "Awakening deep psychological intuition, mastering emotional currents, strategic vision, and inner alchemy."
    },
    "Magha": {
        "title": "The Sovereign Guardian of Heritage",
        "posture": "seated in stately, regal posture upon an ornate carved stone throne, projecting dignified self-respect and calm authority",
        "setting": "royal darbar hall with ancient ancestral banners, warm amber torchlight, celestial starlight beaming through high stone arches, authentic Vedic aesthetic",
        "life_focus": "Honoring ancestral legacy, authoritative leadership, dignified self-mastery, and noble family standing."
    },
    "Purva Phalguni": {
        "title": "The Joyous Creator & Alchemist",
        "posture": "seated in relaxed, graceful elegance amidst soft silk cushions, serene warm countenance filled with natural charm",
        "setting": "golden palace terrace overlooking blooming summer gardens, warm honeyed sunset skies, soft rose-gold ambient glow, authentic Indian Vedic aesthetic, 8k resolution",
        "life_focus": "Celebration of life, artistic refinement, harmonious relationships, and spreading warmth and creative delight."
    },
    "Uttara Phalguni": {
        "title": "The Steadfast Patron & Protector",
        "posture": "seated with upright, noble resolve, hands resting calmly in open mudra of protection and generosity",
        "setting": "grand stone temple gateway under steady radiant afternoon sun, warm saffron and terracotta light, authentic Vedic aesthetic, 8k resolution",
        "life_focus": "Honorable service, steadfast friendship, fulfilling solemn commitments, and uplifting those under your care."
    },
    "Hasta": {
        "title": "The Master Craftsman & Healer",
        "posture": "seated in focused meditation with hands held in a glowing sacred mudra of healing and creation",
        "setting": "sacred workshop overlooking misty mountains at sunrise, soft golden dust motes in the air, glowing sunbeams, authentic Indian Vedic aesthetic, 8k resolution",
        "life_focus": "Mastery of craft, precision of thought, healing touch, and turning mental visions into tangible reality."
    },
    "Chitra": {
        "title": "The Cosmic Architect & Innovator",
        "posture": "seated in visionary poise looking toward the horizon, surrounded by luminous, intricate sacred geometry",
        "setting": "celestial observatory with glowing crystalline facets, vibrant prismatic light, starry cosmos, authentic Vedic aesthetic, 8k resolution",
        "life_focus": "Architectural genius, aesthetic innovation, distinctive individuality, and crafting enduring masterpieces."
    },
    "Swati": {
        "title": "The Independent Breeze & Pathfinder",
        "posture": "seated in light, fluid meditation with soft celestial winds gently rustling clothing, peaceful detached smile",
        "setting": "wide open mountain summit under vast open azure skies, gentle swirling mist of light, soft morning breeze, authentic Vedic aesthetic, 8k resolution",
        "life_focus": "Free-spirited independence, diplomatic adaptability, self-made success, and wide-ranging wisdom."
    },
    "Vishakha": {
        "title": "The Triumphant Goal-Seeker",
        "posture": "seated with resolute, focused determination between twin golden pillars of spiritual light, unwavering gaze",
        "setting": "sacred archway atop a grand flight of stone stairs, brilliant amber twilight sky, triumphant starlight, authentic Vedic aesthetic, 8k resolution",
        "life_focus": "Single-minded perseverance, overcoming all obstacles, ambitious triumphs, and purposeful success."
    },
    "Anuradha": {
        "title": "The Devoted Soul & Peacemaker",
        "posture": "seated in deep devotional stillness with palms gently joined near heart center, serene, loving countenance",
        "setting": "peaceful lotus pond under deep midnight-blue skies studded with gentle stars, floating oil lamps, authentic Indian Vedic aesthetic, 8k resolution",
        "life_focus": "Unshakable loyalty, devotional friendship, resilience through trials, and building community harmony."
    },
    "Jyeshtha": {
        "title": "The Elder Sovereign & Guardian",
        "posture": "seated in commanding, protective composure with an ancient protective talisman, mature and perceptive gaze",
        "setting": "ancient stone sanctuary atop a cliff, golden protective aura against twilight storm skies, authentic Vedic aesthetic, 8k resolution",
        "life_focus": "Assuming senior responsibility, shielding the vulnerable, strategic foresight, and earned respect."
    },
    "Mula": {
        "title": "The Root Alchemist & Truth-Seeker",
        "posture": "seated in deep grounded meditation at the roots of an ancient banyan tree, eyes closed in profound detachment",
        "setting": "mystical forest clearing under starlit night, earthen roots illuminated with subtle golden glow, authentic Vedic spiritual aesthetic, 8k resolution",
        "life_focus": "Getting to the core root of reality, dismantling superficial falsehoods, and seeking spiritual liberation."
    },
    "Purva Ashadha": {
        "title": "The Invincible Stream & Purifier",
        "posture": "seated serenely by flowing waters, radiating calm and unshakeable inner confidence",
        "setting": "sacred mountain river cascading through smooth stones under afternoon sunlight, sparkling water droplets, authentic Vedic aesthetic, 8k resolution",
        "life_focus": "Unstoppable inner momentum, purifying relationships, emotional rejuvenation, and natural victory."
    },
    "Uttara Ashadha": {
        "title": "The Universal Victor & Statesman",
        "posture": "seated in unshakeable yogic stillness, radiant with calm nobility and quiet moral authority",
        "setting": "timeless mountain temple platform under clear golden sun, expansive horizon, authentic Indian Vedic aesthetic, 8k resolution",
        "life_focus": "Universal righteousness, enduring achievements, grounded humility, and leaving an honorable legacy."
    },
    "Shravana": {
        "title": "The Sacred Listener & Scholar",
        "posture": "seated in silent listening meditation with head slightly tilted, peaceful, highly attuned expression",
        "setting": "ancient hermitage library with palm leaf scrolls, soft golden candlelight, tranquil Himalayan breeze, authentic Vedic aesthetic, 8k resolution",
        "life_focus": "Attentive listening, deep scholarship, preserving sacred knowledge, and tuning into higher universal truths."
    },
    "Dhanishta": {
        "title": "The Rhythm of Cosmic Abundance",
        "posture": "seated with dynamic, rhythmic grace, holding a serene posture resonant with cosmic harmony",
        "setting": "celestial marble courtyard under starlit skies with golden harmonic soundwaves rippling through the air, authentic Vedic aesthetic, 8k resolution",
        "life_focus": "Living in cosmic rhythm, building material wealth, social prestige, and turning chaos into harmony."
    },
    "Shatabhisha": {
        "title": "The Solitary Healer & Mystic",
        "posture": "seated in solitary, deep contemplation under a canopy of shimmering constellations, calm and introspective gaze",
        "setting": "desert oasis under an ocean of a hundred stars, deep sapphire and electric-blue celestial aura, authentic Vedic spiritual aesthetic, 8k resolution",
        "life_focus": "Deep diagnostic healing, uncovering hidden mysteries, comfortable solitude, and visionary perception."
    },
    "Purva Bhadrapada": {
        "title": "The Sacred Fire & Spiritual Ascetic",
        "posture": "seated in powerful tapasya meditation beside a sacred golden fire, intense yet peaceful spiritual gravity",
        "setting": "high mountain stone sanctum under midnight sky with sacred ritual fire casting warm amber light on face, authentic Vedic aesthetic, 8k resolution",
        "life_focus": "Spiritual purification, extraordinary willpower, seeing future horizons, and fearless moral strength."
    },
    "Uttara Bhadrapada": {
        "title": "The Oceanic Sage & Serene Master",
        "posture": "seated in profound yogic stillness, countenance reflecting bottomless emotional peace and benevolence",
        "setting": "calm ocean shore under glowing moonlight, gentle lap of silver waves, serene indigo and pearl aura, authentic Vedic aesthetic, 8k resolution",
        "life_focus": "Deep psychological stability, psychic composure, unconditional benevolence, and deep spiritual contentment."
    },
    "Revati": {
        "title": "The Cosmic Mystic & Journeyer",
        "posture": "seated in tranquil yogic Padmasana meditation upon a glowing cosmic lotus, serene closed eyes and peaceful countenance",
        "setting": "sacred twilight cosmic waters reflecting starry galaxies, soft ethereal violet and golden aura, floating lotus blossoms, authentic Indian Vedic spiritual aesthetic, 8k resolution, cinematic lighting",
        "life_focus": "Universal compassion, spiritual transcendence, guiding others across life transitions, and transcendent wisdom."
    }
}

# Default fallback archetype if nakshatra is unrecognized
DEFAULT_ARCHETYPE = {
    "title": "The Cosmic Seeker",
    "posture": "seated in peaceful yogic meditation with calm, centered expression",
    "setting": "sacred Himalayan temple platform under starlit sky, glowing golden oil lamps, authentic Indian Vedic aesthetic, 8k resolution",
    "life_focus": "Spiritual alignment, inner clarity, noble purpose, and living in harmony with cosmic law."
}


def get_nakshatra_archetype(nakshatra_name: str) -> Dict[str, str]:
    """Retrieve the visual archetype and Life Focus for a given Nakshatra."""
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



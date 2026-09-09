"""Classical Vedic astrology lookup knowledge base for Panchanga & Muhurtha.

Compiled from classical authorities:
- Brihat Samhita (Varahamihira)
- Muhurtha Chintamani (Ramadayalu)
- Phaladeepika (Mantreswara)

Provides:
- 30 Tithis: Devanagari name, category (Nanda/Bhadra/Jaya/Rikta/Poorna), ruling deity, dos and don'ts.
- 27 Nakshatras: Devanagari name, energy archetype, deity, symbol, naming syllables for all 4 Padas, dos and don'ts.
- 27 Yogas: Devanagari name, benefic/malefic quality, and human guidance.
- 11 Karanas: Devanagari name, deity, nature, and specialized Bhadra (Vishti) rules.
"""

from __future__ import annotations
from typing import Dict, List, Any

# ===========================================================================
# 1. TITHI MEANINGS & DOS/DON'TS
# ===========================================================================

TITHI_DATA: Dict[int, Dict[str, Any]] = {
    1: {
        "name_sanskrit": "प्रतिपदा",
        "category": "Nanda (Delight)",
        "deity": "Agni (Fire)",
        "suitable_activities": ["Religious ceremonies", "Fire rituals (Homa)", "Planting seeds", "Starting education", "New beginnings"],
        "unfavorable_activities": ["Travel", "Cutting hair/nails", "Entering new houses"],
    },
    2: {
        "name_sanskrit": "द्वितीया",
        "category": "Bhadra (Propitious)",
        "deity": "Brahma (Creator)",
        "suitable_activities": ["Government foundations", "Purchasing vehicles", "Architecture & design", "Wearing new clothes", "Marriage ceremonies"],
        "unfavorable_activities": ["Severe disciplinary actions", "Lawsuits"],
    },
    3: {
        "name_sanskrit": "तृतीया",
        "category": "Jaya (Victory)",
        "deity": "Gauri (Mother Nature)",
        "suitable_activities": ["Music, arts & crafts", "Starting trades", "Hair cutting", "Entering new residence", "Overcoming obstacles"],
        "unfavorable_activities": ["Deed signing with adversaries", "Aggressive confrontations"],
    },
    4: {
        "name_sanskrit": "चतुर्थी",
        "category": "Rikta (Empty/Hollow)",
        "deity": "Ganesha / Yama",
        "suitable_activities": ["Overcoming obstacles", "Demolition", "Competitive strategy", "Firearm usage", "Eliminating pests"],
        "unfavorable_activities": ["Auspicious journeys", "Marriage", "Starting peaceful commercial ventures", "Lending money"],
    },
    5: {
        "name_sanskrit": "पञ्चमी",
        "category": "Poorna (Complete/Full)",
        "deity": "Nagas (Serpent Gods)",
        "suitable_activities": ["Administering medicine", "Surgery", "Treating chronic illness", "Spiritual devotion", "Beginning new business"],
        "unfavorable_activities": ["Lending loans", "Harsh actions"],
    },
    6: {
        "name_sanskrit": "षष्ठी",
        "category": "Nanda (Delight)",
        "deity": "Kartikeya (Commander of Gods)",
        "suitable_activities": ["Building friendship", "Physical sports", "Joining armed forces", "Wearing jewels", "Architectural work"],
        "unfavorable_activities": ["Woodwork", "Long-distance travel", "Medical surgeries"],
    },
    7: {
        "name_sanskrit": "सप्तमी",
        "category": "Bhadra (Propitious)",
        "deity": "Surya (Sun God)",
        "suitable_activities": ["Journeys", "Starting vehicles", "Buying transport", "Meeting influential leaders", "Music & arts"],
        "unfavorable_activities": ["Aggressive litigation", "Confining others"],
    },
    8: {
        "name_sanskrit": "अष्टमी",
        "category": "Jaya (Victory)",
        "deity": "Shiva / Rudra",
        "suitable_activities": ["Fortification", "Defense planning", "Crafting iron/tools", "Spiritual fasting", "Tantric contemplation"],
        "unfavorable_activities": ["Physical intimacy", "Auspicious journeys", "Medical administration"],
    },
    9: {
        "name_sanskrit": "नवमी",
        "category": "Rikta (Empty/Hollow)",
        "deity": "Durga (Divine Mother)",
        "suitable_activities": ["Competitive battles", "Physical training", "Discarding obsolete systems", "Overcoming enemies", "Hunting"],
        "unfavorable_activities": ["Travel", "Auspicious celebrations", "New investments", "Ceremonies"],
    },
    10: {
        "name_sanskrit": "दशमी",
        "category": "Poorna (Complete/Full)",
        "deity": "Aryaman / Yama",
        "suitable_activities": ["Government ceremonies", "Meeting authorities", "Wearing ornaments", "Starting partnerships", "House warming"],
        "unfavorable_activities": ["Illegal activities", "Underhanded transactions"],
    },
    11: {
        "name_sanskrit": "एकादशी",
        "category": "Nanda (Delight)",
        "deity": "Vishnu (Preserver)",
        "suitable_activities": ["Fasting & meditation", "Devotional charity", "Pilgrimage", "Sacred oaths", "Spiritual learning"],
        "unfavorable_activities": ["Eating heavy grains (traditional)", "Cruel or harsh deeds", "Lending money"],
    },
    12: {
        "name_sanskrit": "द्वादशी",
        "category": "Bhadra (Propitious)",
        "deity": "Vishnu (Hari)",
        "suitable_activities": ["Charitable gifting", "Breaking fasts with pure food", "Religious dedications", "Lighting lamps", "Road building"],
        "unfavorable_activities": ["New house foundation", "Legal disputation", "Oil baths"],
    },
    13: {
        "name_sanskrit": "त्रयोदशी",
        "category": "Jaya (Victory)",
        "deity": "Kamadeva (Love/Desire)",
        "suitable_activities": ["Wearing new garments", "Jewelry purchase", "Fine arts & romance", "Sensory celebrations", "Friendship"],
        "unfavorable_activities": ["Long journeys", "Funeral rights"],
    },
    14: {
        "name_sanskrit": "चतुर्दशी",
        "category": "Rikta (Empty/Hollow)",
        "deity": "Shiva / Kali",
        "suitable_activities": ["Spiritual surrender", "Meditation", "Subduing toxic habits", "Surgery", "Eliminating negative forces"],
        "unfavorable_activities": ["Auspicious journeys", "Hair cutting", "Marriage", "Financial contracts"],
    },
    15: {
        "name_sanskrit": "पूर्णिमा",
        "category": "Poorna (Complete/Full)",
        "deity": "Soma (Moon God)",
        "suitable_activities": ["Satyanarayan puja", "Full moon meditation", "Spiritual charity", "Healing ceremonies", "Festive gatherings"],
        "unfavorable_activities": ["Surgery (high bleeding risk)", "Aggressive speech", "Confrontations"],
    },
    30: {
        "name_sanskrit": "अमावस्या",
        "category": "Poorna (Pitru Tithi)",
        "deity": "Pitrus (Ancestors)",
        "suitable_activities": ["Ancestor memorial rites (Shraddha/Tarpan)", "Spiritual cleansing", "Donations to the needy", "Introspection"],
        "unfavorable_activities": ["Beginning new commercial ventures", "Weddings", "Entering new residence", "Traveling"],
    }
}

# Add Krishna Paksha 16-29 mapping to their respective lunar deities
for i in range(16, 30):
    shukla_equiv = i - 15
    if shukla_equiv in TITHI_DATA:
        base = TITHI_DATA[shukla_equiv]
        TITHI_DATA[i] = {
            "name_sanskrit": f"कृष्ण {base['name_sanskrit']}",
            "category": base["category"],
            "deity": base["deity"],
            "suitable_activities": base["suitable_activities"],
            "unfavorable_activities": base["unfavorable_activities"],
        }
TITHI_DATA[15]["name_sanskrit"] = "शुक्ल पूर्णिमा"
TITHI_DATA[30]["name_sanskrit"] = "कृष्ण अमावस्या"


# ===========================================================================
# 2. NAKSHATRA MEANINGS, ARCHETYPES & NAMING SYLLABLES
# ===========================================================================

NAKSHATRA_DATA: Dict[int, Dict[str, Any]] = {
    1: {
        "name_sanskrit": "अश्विनी",
        "energy": "Swift & Light (Laghu/Kshipra)",
        "deity": "Ashwini Kumaras (Divine Healers)",
        "symbol": "Horse's Head",
        "naming_syllables": {1: "Chu", 2: "Che", 3: "Cho", 4: "La"},
        "suitable_activities": ["Starting medical treatment", "Taking medicines", "Buying transport/vehicles", "Quick commerce", "Sports & athletics"],
        "unfavorable_activities": ["Marriage", "Matters requiring long endurance or slow gestation"],
    },
    2: {
        "name_sanskrit": "भरणी",
        "energy": "Fierce & Severe (Ugra)",
        "deity": "Yama (God of Dharma & Justice)",
        "symbol": "Yoni (Vessel of Creation)",
        "naming_syllables": {1: "Lee", 2: "Lu", 3: "Le", 4: "Lo"},
        "suitable_activities": ["Purging obsolete clutter", "Demolition", "Dealing with toxic situations", "Occult research", "Filing lawsuits"],
        "unfavorable_activities": ["Inaugurations", "Peaceful ceremonies", "Travel", "Lending money"],
    },
    3: {
        "name_sanskrit": "कृत्तिका",
        "energy": "Mixed / Sharp & Soft (Mishra)",
        "deity": "Agni (God of Fire)",
        "symbol": "Knife or Razor",
        "naming_syllables": {1: "A", 2: "Ee", 3: "U", 4: "E"},
        "suitable_activities": ["Culinary ventures", "Cooking & baking", "Cutting, soldering & metals", "Renouncing habits", "Direct confrontations"],
        "unfavorable_activities": ["Auspicious travels", "Social diplomacy", "Marriage ceremonies"],
    },
    4: {
        "name_sanskrit": "रोहिणी",
        "energy": "Fixed & Permanent (Dhruva/Sthira)",
        "deity": "Brahma / Prajapati (Creator)",
        "symbol": "Chariot / Temple cart",
        "naming_syllables": {1: "O", 2: "Va", 3: "Vi", 4: "Vu"},
        "suitable_activities": ["Weddings & romance", "Laying house foundations", "Planting trees/gardens", "Buying jewelry", "Financial investments"],
        "unfavorable_activities": ["Demolition", "Ending relationships", "Hostile disputes"],
    },
    5: {
        "name_sanskrit": "मृगशिरा",
        "energy": "Soft, Mild & Tender (Mridu)",
        "deity": "Soma (Chandra / Moon God)",
        "symbol": "Deer's Head",
        "naming_syllables": {1: "Ve", 2: "Vo", 3: "Ka", 4: "Kee"},
        "suitable_activities": ["Creative exploration", "Poetry, music & fine arts", "Dating & socialization", "Travel & touring", "Wearing ornaments"],
        "unfavorable_activities": ["Harsh confrontation", "Cruel or violent deeds"],
    },
    6: {
        "name_sanskrit": "आर्द्रा",
        "energy": "Sharp & Dreadful (Tikshna/Daruna)",
        "deity": "Rudra (Storm God)",
        "symbol": "Teardrop / Diamond",
        "naming_syllables": {1: "Ku", 2: "Gha", 3: "Nga", 4: "Chha"},
        "suitable_activities": ["Breaking bad habits", "Psychological catharsis", "Demolition", "Confronting deception", "Surgical removal"],
        "unfavorable_activities": ["Weddings", "Travel", "Giving gifts", "Peace agreements"],
    },
    7: {
        "name_sanskrit": "पुनर्वसु",
        "energy": "Movable & Ephemeral (Chara)",
        "deity": "Aditi (Cosmic Mother)",
        "symbol": "Bow and Quiver",
        "naming_syllables": {1: "Ke", 2: "Ko", 3: "Ha", 4: "Hee"},
        "suitable_activities": ["Returning home", "Reconciliations", "Renewal of vows", "Spiritual retreats", "Purchasing real estate"],
        "unfavorable_activities": ["Legal conflicts", "Retribution"],
    },
    8: {
        "name_sanskrit": "पुष्य",
        "energy": "Swift & Auspicious (Laghu/Kshipra)",
        "deity": "Brihaspati (Jupiter / Divine Priest)",
        "symbol": "Cow's Udder / Lotus",
        "naming_syllables": {1: "Hu", 2: "He", 3: "Ho", 4: "Da"},
        "suitable_activities": ["Supreme for all auspicious deeds", "Buying gold/jewelry", "Inaugurations", "Spiritual initiation", "Starting study"],
        "unfavorable_activities": ["Marriage ceremonies (classically prohibited in Pushya despite general auspiciousness)"],
    },
    9: {
        "name_sanskrit": "आश्लेषा",
        "energy": "Sharp & Dreadful (Tikshna/Daruna)",
        "deity": "Sarpas (Serpents of Wisdom)",
        "symbol": "Coiled Serpent",
        "naming_syllables": {1: "Dee", 2: "Du", 3: "De", 4: "Do"},
        "suitable_activities": ["Deep research & data mining", "Handling poison or venom", "Competitive defense", "Surgery", "Dealing with rivals"],
        "unfavorable_activities": ["Weddings", "House-warming (Griha Pravesh)", "Lending large loans"],
    },
    10: {
        "name_sanskrit": "मघा",
        "energy": "Fierce & Severe (Ugra)",
        "deity": "Pitrus (Ancestors)",
        "symbol": "Royal Throne",
        "naming_syllables": {1: "Ma", 2: "Mee", 3: "Mu", 4: "Me"},
        "suitable_activities": ["Honoring ancestors", "Coronations / assuming leadership", "Family heritage celebrations", "History & archaeology"],
        "unfavorable_activities": ["Lending money", "Modern progressive experiments", "Contractual humility"],
    },
    11: {
        "name_sanskrit": "पूर्वाफाल्गुनी",
        "energy": "Fierce & Passionate (Ugra)",
        "deity": "Bhaga (God of Fortune & Romance)",
        "symbol": "Hammock / Front legs of Couch",
        "naming_syllables": {1: "Mo", 2: "Ta", 3: "Tee", 4: "Tu"},
        "suitable_activities": ["Romance & courtship", "Relaxation & luxury", "Music, acting & performing arts", "Appealing to authorities"],
        "unfavorable_activities": ["Ascetic austerity", "Demanding physical labor", "Financial frugality"],
    },
    12: {
        "name_sanskrit": "उत्तराफाल्गुनी",
        "energy": "Fixed & Permanent (Dhruva/Sthira)",
        "deity": "Aryaman (God of Friendship & Oaths)",
        "symbol": "Four legs of Bed",
        "naming_syllables": {1: "Te", 2: "To", 3: "Pa", 4: "Pee"},
        "suitable_activities": ["Marriage ceremonies", "Signing long-term treaties", "Entering new homes", "Starting permanent ventures"],
        "unfavorable_activities": ["Severing ties", "Short ephemeral activities"],
    },
    13: {
        "name_sanskrit": "हस्त",
        "energy": "Swift & Light (Laghu/Kshipra)",
        "deity": "Savitr (Sun / Divine Creator)",
        "symbol": "Open Hand / Fist",
        "naming_syllables": {1: "Pu", 2: "Sha", 3: "Na", 4: "Tha"},
        "suitable_activities": ["Crafts, painting & fine dexterity", "Healing & massage", "Commerce & negotiations", "Humor & light-hearted events"],
        "unfavorable_activities": ["Long inactive periods", "Passive waiting"],
    },
    14: {
        "name_sanskrit": "चित्रा",
        "energy": "Soft, Mild & Tender (Mridu)",
        "deity": "Tvashtar / Vishwakarma (Cosmic Architect)",
        "symbol": "Bright Jewel / Pearl",
        "naming_syllables": {1: "Pe", 2: "Po", 3: "Ra", 4: "Ree"},
        "suitable_activities": ["Architectural design", "Fashion, modeling & styling", "Interior decorating", "Engineering innovations", "Jewelry making"],
        "unfavorable_activities": ["Direct confrontational warfare", "Routine bureaucratic paperwork"],
    },
    15: {
        "name_sanskrit": "स्वाती",
        "energy": "Movable & Ephemeral (Chara)",
        "deity": "Vayu (God of Wind)",
        "symbol": "Young Shoot swaying in wind",
        "naming_syllables": {1: "Ru", 2: "Re", 3: "Ro", 4: "Ta"},
        "suitable_activities": ["Travel & air transit", "Business networking", "Learning musical instruments", "Buying automobiles", "Flexibility & pivot"],
        "unfavorable_activities": ["Rigid stubborn stances", "Fierce combat"],
    },
    16: {
        "name_sanskrit": "विशाखा",
        "energy": "Mixed / Sharp & Soft (Mishra)",
        "deity": "Indragni (Indra & Agni)",
        "symbol": "Triumphal Arch",
        "naming_syllables": {1: "Tee", 2: "Tu", 3: "Te", 4: "To"},
        "suitable_activities": ["Goal accomplishment", "Competitive milestones", "Focused labor towards victory", "Ceremonies of triumph"],
        "unfavorable_activities": ["Marriage", "Diplomatic travel", "Passive reflection"],
    },
    17: {
        "name_sanskrit": "अनुराधा",
        "energy": "Soft, Mild & Tender (Mridu)",
        "deity": "Mitra (God of Divine Friendship)",
        "symbol": "Staff / Lotus flower",
        "naming_syllables": {1: "Na", 2: "Nee", 3: "Nu", 4: "Ne"},
        "suitable_activities": ["Friendship & community building", "Organization & alliance", "Foreign travel", "Devotional music", "Spiritual devotion"],
        "unfavorable_activities": ["Direct confrontation", "Cruel acts", "Litigation"],
    },
    18: {
        "name_sanskrit": "ज्येष्ठा",
        "energy": "Sharp & Dreadful (Tikshna/Daruna)",
        "deity": "Indra (King of Gods)",
        "symbol": "Circular Amulet / Umbrella",
        "naming_syllables": {1: "No", 2: "Ya", 3: "Yee", 4: "Yu"},
        "suitable_activities": ["Exercising authority", "Protection of subordinates", "Occult research", "Administration", "Confronting predators"],
        "unfavorable_activities": ["Weddings", "Gentle domestic activities", "Travel"],
    },
    19: {
        "name_sanskrit": "मूल",
        "energy": "Sharp & Dreadful (Tikshna/Daruna)",
        "deity": "Nirriti (Goddess of Dissolution)",
        "symbol": "Bunch of Roots",
        "naming_syllables": {1: "Ye", 2: "Yo", 3: "Bha", 4: "Bhee"},
        "suitable_activities": ["Root-cause analysis", "Research & deep medicine", "Gardening / planting roots", "Demolition of decayed systems"],
        "unfavorable_activities": ["Marriage", "Auspicious celebrations", "Lending money"],
    },
    20: {
        "name_sanskrit": "पूर्वाषाढा",
        "energy": "Fierce & Severe (Ugra)",
        "deity": "Apas (Cosmic Waters)",
        "symbol": "Winnowing Basket / Fan",
        "naming_syllables": {1: "Bhu", 2: "Dha", 3: "Pha", 4: "Dha"},
        "suitable_activities": ["Maritime ventures", "Water-related trade", "Inspiring public speech", "Competitive declarations", "Courageous tasks"],
        "unfavorable_activities": ["Travel by land", "Submissive compliance"],
    },
    21: {
        "name_sanskrit": "उत्तराषाढा",
        "energy": "Fixed & Permanent (Dhruva/Sthira)",
        "deity": "Vishvadevas (Universal Gods)",
        "symbol": "Elephant's Tusk",
        "naming_syllables": {1: "Bhe", 2: "Bho", 3: "Ja", 4: "Jee"},
        "suitable_activities": ["Laying permanent foundations", "Signing solemn contracts", "Public service inaugurations", "House construction"],
        "unfavorable_activities": ["Deceitful or underhanded acts", "Rapid short projects"],
    },
    22: {
        "name_sanskrit": "श्रवण",
        "energy": "Movable & Ephemeral (Chara)",
        "deity": "Vishnu (Preserver)",
        "symbol": "Ear / Three Footprints",
        "naming_syllables": {1: "Khi", 2: "Khu", 3: "Khe", 4: "Kho"},
        "suitable_activities": ["Listening to wisdom / lectures", "Higher education", "Philosophy & sacred texts", "Buying communication gear", "Travel"],
        "unfavorable_activities": ["Hostility", "Taking lawsuits"],
    },
    23: {
        "name_sanskrit": "धनिष्ठा",
        "energy": "Movable & Ephemeral (Chara)",
        "deity": "Eight Vasus (Elemental Gods of Abundance)",
        "symbol": "Drum / Flute",
        "naming_syllables": {1: "Ga", 2: "Gee", 3: "Gu", 4: "Ge"},
        "suitable_activities": ["Music, dance & rhythm", "Wealth creation & real estate", "Wearing new jewelry", "High-energy athletics", "Community festivals"],
        "unfavorable_activities": ["Routine mundane work", "Physical surrender"],
    },
    24: {
        "name_sanskrit": "शतभिषा",
        "energy": "Movable & Ephemeral (Chara)",
        "deity": "Varuna (God of Cosmic Waters & Truth)",
        "symbol": "Hundred Physicians / Empty Circle",
        "naming_syllables": {1: "Go", 2: "Sa", 3: "See", 4: "Su"},
        "suitable_activities": ["Medical healing & pharmacology", "Diagnosing difficult illnesses", "Astronomical / scientific research", "Spiritual seclusion"],
        "unfavorable_activities": ["Social superficiality", "Lawsuits", "Marriage"],
    },
    25: {
        "name_sanskrit": "पूर्वभाद्रपदा",
        "energy": "Fierce & Severe (Ugra)",
        "deity": "Aja Ekapada (One-Footed Unborn Serpent)",
        "symbol": "Front of Funeral Cot / Two-Faced Man",
        "naming_syllables": {1: "Se", 2: "So", 3: "Da", 4: "Dee"},
        "suitable_activities": ["Severe spiritual disciplines (Tapas)", "Overcoming severe obstacles", "Occult study", "Auditing / risk inspection"],
        "unfavorable_activities": ["Weddings", "Travel", "Beginning light-hearted social projects"],
    },
    26: {
        "name_sanskrit": "उत्तरभाद्रपदा",
        "energy": "Fixed & Permanent (Dhruva/Sthira)",
        "deity": "Ahirbudhnya (Serpent of the Depths)",
        "symbol": "Back of Funeral Cot",
        "naming_syllables": {1: "Du", 2: "Tha", 3: "Jha", 4: "Na"},
        "suitable_activities": ["Deep meditation", "Philanthropy", "Building permanent sanctuaries", "Spiritual retreats", "Financial security planning"],
        "unfavorable_activities": ["High-risk gambles", "Furious anger"],
    },
    27: {
        "name_sanskrit": "रेवती",
        "energy": "Soft, Mild & Tender (Mridu)",
        "deity": "Pushan (Nourisher & Guide of Souls)",
        "symbol": "Fish / Pair of Fish",
        "naming_syllables": {1: "De", 2: "Do", 3: "Cha", 4: "Chee"},
        "suitable_activities": ["Auspicious journeys", "Safe travel & transit", "Creative writing & storytelling", "Adopting pets", "Spiritual completion"],
        "unfavorable_activities": ["Cruel behavior", "Violent conflict"],
    },
}


# ===========================================================================
# 3. YOGA QUALITIES & ADVICE
# ===========================================================================

YOGA_DATA: Dict[int, Dict[str, Any]] = {
    1: {"name_sanskrit": "विष्कम्भ", "quality": "Malefic (Ashubha)", "recommendation": "Hindrances & obstacles. Postpone critical financial and legal signatures."},
    2: {"name_sanskrit": "प्रीति", "quality": "Benefic (Shubha)", "recommendation": "Love and affection. Excellent for partnerships, reconciliations, and friendship."},
    3: {"name_sanskrit": "आयुष्मान्", "quality": "Benefic (Shubha)", "recommendation": "Long life and vitality. Auspicious for medical treatments, health regimens, and charity."},
    4: {"name_sanskrit": "सौभाग्य", "quality": "Benefic (Shubha)", "recommendation": "Good fortune. Highly auspicious for marriages, travel, and wealth accumulation."},
    5: {"name_sanskrit": "शोभन", "quality": "Benefic (Shubha)", "recommendation": "Brilliant and elegant. Great for arts, new purchases, and creative execution."},
    6: {"name_sanskrit": "अतिगण्ड", "quality": "Malefic (Ashubha)", "recommendation": "Extreme complications. Avoid starting new journeys or entering contracts."},
    7: {"name_sanskrit": "सुकर्मा", "quality": "Benefic (Shubha)", "recommendation": "Virtuous deeds. Ideal for beginning public service, sacred oaths, and honest labor."},
    8: {"name_sanskrit": "धृति", "quality": "Benefic (Shubha)", "recommendation": "Patience and firmness. Excellent for laying foundations, research, and long-term planning."},
    9: {"name_sanskrit": "शूल", "quality": "Malefic (Ashubha)", "recommendation": "Sharp pain and conflict. Avoid confrontational discussions or physical risks."},
    10: {"name_sanskrit": "गण्ड", "quality": "Malefic (Ashubha)", "recommendation": "Obstacles and entanglement. Proceed with high caution and avoid rush decisions."},
    11: {"name_sanskrit": "वृद्धि", "quality": "Benefic (Shubha)", "recommendation": "Growth and prosperity. Favorable for investments, commerce, and scaling up."},
    12: {"name_sanskrit": "ध्रुव", "quality": "Benefic (Shubha)", "recommendation": "Stability and permanence. Excellent for house construction, permanent treaties, and deposits."},
    13: {"name_sanskrit": "व्याघात", "quality": "Malefic (Ashubha)", "recommendation": "Fierce and aggressive. High risk of accidents or verbal spats. Keep calm."},
    14: {"name_sanskrit": "हर्षण", "quality": "Benefic (Shubha)", "recommendation": "Joy and delight. Auspicious for parties, celebrations, and recreational meetings."},
    15: {"name_sanskrit": "वज्र", "quality": "Malefic (Ashubha)", "recommendation": "Diamond-hard / thunderbolt. Avoid taking loans or starting peaceful diplomatic talks."},
    16: {"name_sanskrit": "सिद्धि", "quality": "Benefic (Shubha)", "recommendation": "Supreme accomplishment. Outstanding for achieving success in any pending project."},
    17: {"name_sanskrit": "व्यतीपात", "quality": "Malefic (Ashubha)", "recommendation": "Deep calamity / sudden disruptions. Strictly avoid auspicious inaugurations."},
    18: {"name_sanskrit": "वरीयान्", "quality": "Benefic (Shubha)", "recommendation": "Superior comfort and ease. Great for enjoyment, luxury shopping, and romance."},
    19: {"name_sanskrit": "परिघ", "quality": "Malefic (Ashubha)", "recommendation": "Iron bar / barricade. Delays expected. Focus on internal work rather than outreach."},
    20: {"name_sanskrit": "शिव", "quality": "Benefic (Shubha)", "recommendation": "Auspicious and serene. Ideal for meditation, spiritual learning, and harmonious deals."},
    21: {"name_sanskrit": "सिद्ध", "quality": "Benefic (Shubha)", "recommendation": "Proven and established. Very good for scientific work, trades, and education."},
    22: {"name_sanskrit": "साध्य", "quality": "Benefic (Shubha)", "recommendation": "Attainable through discipline. Good for complex projects requiring dedication."},
    23: {"name_sanskrit": "शुभ", "quality": "Benefic (Shubha)", "recommendation": "Pure and auspicious. Favorable for beauty, health, weddings, and investments."},
    24: {"name_sanskrit": "शुक्ल", "quality": "Benefic (Shubha)", "recommendation": "Bright and radiant. Clear minds, fruitful discussions, and good news."},
    25: {"name_sanskrit": "ब्रह्म", "quality": "Benefic (Shubha)", "recommendation": "Divine knowledge. Best for study, teaching, philosophy, and high ethical tasks."},
    26: {"name_sanskrit": "ऐन्द्र", "quality": "Benefic (Shubha)", "recommendation": "Royal status and power. Favorable for executive decision-making and negotiations."},
    27: {"name_sanskrit": "वैधृति", "quality": "Malefic (Ashubha)", "recommendation": "Severe reversal / discord. Postpone vital launches, contracts, and travel."},
}


# ===========================================================================
# 4. KARANA MEANINGS & BHADRA RULES
# ===========================================================================

KARANA_DATA: Dict[str, Dict[str, Any]] = {
    "Bava": {
        "name_sanskrit": "बव",
        "deity": "Indra",
        "is_bhadra": False,
        "recommendation": "Favorable for health, medicine, and starting productive labor.",
    },
    "Balava": {
        "name_sanskrit": "बालव",
        "deity": "Brahma",
        "is_bhadra": False,
        "recommendation": "Auspicious for religious rituals, education, and pious actions.",
    },
    "Kaulava": {
        "name_sanskrit": "कौलव",
        "deity": "Mitra (Sun)",
        "is_bhadra": False,
        "recommendation": "Excellent for developing friendships, romance, and socializing.",
    },
    "Taitila": {
        "name_sanskrit": "तैतिल",
        "deity": "Aryaman",
        "is_bhadra": False,
        "recommendation": "Good for building wealth, home life, and decorating properties.",
    },
    "Gara": {
        "name_sanskrit": "गर",
        "deity": "Prithvi (Earth)",
        "is_bhadra": False,
        "recommendation": "Favorable for agriculture, planting, digging wells, and manual labor.",
    },
    "Vanija": {
        "name_sanskrit": "वणिज",
        "deity": "Lakshmi (Goddess of Wealth)",
        "is_bhadra": False,
        "recommendation": "Highly auspicious for sales, retail, trade, and financial contracts.",
    },
    "Vishti": {
        "name_sanskrit": "विष्टि (भद्रा)",
        "deity": "Yama",
        "is_bhadra": True,
        "recommendation": "STRICT CAUTION (Bhadra is active). Strictly avoid weddings, Griha Pravesh, journey starts, or property deals. Favorable only for defensive warfare, demolition, and poison eradication.",
    },
    "Shakuni": {
        "name_sanskrit": "शकुनि",
        "deity": "Vayu",
        "is_bhadra": False,
        "recommendation": "Medicinal preparations, binding spells, and strategic vigilance.",
    },
    "Chatushpada": {
        "name_sanskrit": "चतुष्पद",
        "deity": "Pashupati (Shiva)",
        "is_bhadra": False,
        "recommendation": "Agricultural work, cattle rearing, and veterinary medicine.",
    },
    "Naga": {
        "name_sanskrit": "नाग",
        "deity": "Nagas",
        "is_bhadra": False,
        "recommendation": "Subterranean work, mining, mineral exploration, and defense.",
    },
    "Kintughna": {
        "name_sanskrit": "किंस्तुघ्न",
        "deity": "Vayu / Kubera",
        "is_bhadra": False,
        "recommendation": "Auspicious start of spiritual cycles, weddings, and charitable works.",
    },
}

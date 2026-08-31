# Fixture Provenance Manifest

This manifest records the exact birth parameters and configuration settings for all 6 JHora differential test fixtures.

## Global Settings
- **Software**: Jagannatha Hora (JHora) Version 8.0 / Swiss Ephemeris 2.10
- **Ayanamsa**: Lahiri (Chitra Paksha) — SIDM_LAHIRI
- **House System**: Whole-Sign (Equal 30° Rashi-keyed)
- **Ascendant / Houses Coordinate System**: Geographic Latitude (b'W')
- **Lunar Node**: True Node (swe.TRUE_NODE)
- **Topocentric Positions**: OFF (Geocentric Planetary Longitudes)

## Supplied Screenshot Reference

`indore_screenshot_reference.json` is the frozen reference transcribed from
the three JHora screenshots supplied on 2026-08-25. It uses the screenshot's
coordinates (22°43'00" N, 75°50'00" E), rather than the slightly different
coordinates in `f1_golden.json`. `tests/jhora_parity.py` uses these frozen
longitudes so its comparison evaluates our calculation formulas rather than
small ephemeris-version differences.

It covers every numeric table supplied in the screenshots:

- 12 SAV values by house;
- planetary Shadbala totals, rupas, and percentages;
- 12 Bhava Bala totals, rupas, and lords.

---

## Fixtures Table

| Fixture ID | Description | Date (YYYY-MM-DD) | Time (IST) | Lat (°N) | Lon (°E) | Purpose / Test Coverage |
|:---|:---|:---:|:---:|:---:|:---:|:---|
| **F1_GOLDEN** | Golden Baseline Chart | 1981-02-09 | 08:21:55 | 22.7196 | 75.8577 | Full 7-lord Shadbala & 12-house Bhava Bala baseline |
| **F2_NIGHT** | Night Birth | 1985-05-15 | 02:30:00 | 28.6139 | 77.2090 | Nocturnal Tribhaga 3rd third (Mars) & Nathonnata night curve |
| **F3_WANING** | Waning Crescent Moon | 1992-08-25 | 15:30:00 | 12.9716 | 77.5946 | Moon-Sun elongation 321.83° (> 180°), Paksha illumination fold |
| **F4_HALFSIGN** | Discriminating Half-Sign | 1995-12-20 | 18:07:54 | 13.0827 | 80.2707 | Ascendant 70.0° (Gemini 10°); H7 Sandhi (Sag 10°) vs Madhya (Sag 25°) |
| **F5_YUDDHA** | Graha Yuddha Chart | 1981-02-09 | 08:21:55 | 22.7196 | 75.8577 | Jupiter & Saturn in Virgo within 0.64° conjunction |
| **F6_MERCURY_RX** | Mercury Retrograde Chart | 1981-02-09 | 08:21:55 | 22.7196 | 75.8577 | Mercury speed < 0 (Rx, Cheshta = 60 virupas) |

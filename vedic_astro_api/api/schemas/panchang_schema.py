"""Pydantic schemas for Panchanga and Muhurtha endpoints."""

from __future__ import annotations

import warnings
from datetime import date
from typing import Any, Dict, List, Literal, Optional
from zoneinfo import ZoneInfo
from pydantic import AliasChoices, BaseModel, Field, model_validator

from vedic_astro_api.core.ephemeris import (
    KERNEL_MIN_DATE,
    KERNEL_MAX_DATE,
    OutOfEphemerisRangeError,
)

# Derived dynamically from the kernel at startup
MIN_DATE, MAX_DATE = KERNEL_MIN_DATE, KERNEL_MAX_DATE


class PanchangRequest(BaseModel):
    year: int = Field(..., ge=1600, le=2400, examples=[2026], description="Year (e.g. 2026)")
    month: int = Field(..., ge=1, le=12, examples=[9], description="Month (1-12)")
    day: int = Field(..., ge=1, le=31, examples=[9], description="Day (1-31)")
    hour: int = Field(12, ge=0, le=23, examples=[12], description="Hour in 24h format (0-23)")
    minute: int = Field(0, ge=0, le=59, validation_alias=AliasChoices("minute", "min"), examples=[0], description="Minute (0-59)")
    second: int = Field(0, ge=0, le=59, validation_alias=AliasChoices("second", "sec"), examples=[0], description="Second (0-59)")
    lat: float = Field(..., ge=-90.0, le=90.0, examples=[28.6139], description="Latitude (-90.0 to +90.0)")
    lon: float = Field(..., ge=-180.0, le=180.0, examples=[77.2090], description="Longitude (-180.0 to +180.0)")
    timezone: str = Field(..., examples=["Asia/Kolkata"], description="IANA timezone name (required)")
    tzone: Optional[float] = Field(None, deprecated=True, description="REMOVED — send IANA 'timezone'")
    ayanamsha: Literal["lahiri", "true_chitra", "raman", "kp"] = Field("lahiri", description="Ayanamsha system")
    sunrise_convention: Literal["astronomical", "hindu_upper_limb", "hindu_center"] = Field(
        "astronomical",
        description="Sunrise convention: 'astronomical' (-50' upper limb refracted, DrikPanchang default ~49s RMS), 'hindu_upper_limb' (-16' upper limb no refraction), or 'hindu_center' (0° disc center no refraction)"
    )

    @model_validator(mode="after")
    def validate_request(self):
        try:
            d = date(self.year, self.month, self.day)
        except ValueError:
            raise ValueError(f"{self.year}-{self.month:02d}-{self.day:02d} is not a real calendar date")
        if not (MIN_DATE <= d <= MAX_DATE):
            raise OutOfEphemerisRangeError(
                f"Date {d.isoformat()} is outside supported query range. "
                f"Supported query range is {MIN_DATE.isoformat()} to {MAX_DATE.isoformat()}."
            )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            has_tzone = self.tzone is not None
        if has_tzone:
            raise ValueError("'tzone' is removed; send IANA 'timezone' instead")
        try:
            ZoneInfo(self.timezone)
        except Exception:
            raise ValueError(f"Unknown IANA timezone: '{self.timezone}'")
        return self


class ConventionsInfo(BaseModel):
    ayanamsha: str = "lahiri"
    ayanamsha_deg: float
    sunrise: str = "astronomical"
    hora: str = "indian_60min"
    choghadiya_night_lord: str = "classical_v1"


class MetaInfo(BaseModel):
    engine: str = "astro-engine/0.1.0"
    ephemeris: str = "DE421"
    conventions: ConventionsInfo
    jd_tt: float
    jd_ut1: float
    local: str
    utc: str
    engine_version: Optional[str] = "0.1.0"
    julian_day: Optional[float] = None
    ayanamsha_type: Optional[str] = None
    ayanamsha_deg: Optional[float] = None
    ayanamsha_dms: Optional[str] = None
    sunrise_convention: Optional[str] = None
    query_utc: Optional[str] = None
    query_local: Optional[str] = None
    timezone: Optional[str] = None


class SolarInfo(BaseModel):
    sunrise: Optional[str]
    sunset: Optional[str]
    next_sunrise: Optional[str]
    solar_noon: Optional[str]
    dina_mana_hours: Optional[float]
    ratri_mana_hours: Optional[float]
    is_daytime: bool
    polar_phenomenon: Optional[str] = None
    sunrise_astronomical: Optional[str] = None
    sunrise_hindu: Optional[str] = None


class TithiInfo(BaseModel):
    number: int
    name: str
    paksha: str
    paksha_tithi_number: int
    elapsed_percentage: float
    end_time: Optional[str]
    name_sanskrit: Optional[str] = None
    category: Optional[str] = None
    deity: Optional[str] = None
    suitable_activities: Optional[List[str]] = None
    unfavorable_activities: Optional[List[str]] = None


class VaraInfo(BaseModel):
    name: str
    lord: str


class NakshatraInfo(BaseModel):
    number: int
    name: str
    lord: str
    pada: int
    elapsed_percentage: float
    end_time: Optional[str]
    name_sanskrit: Optional[str] = None
    energy: Optional[str] = None
    deity: Optional[str] = None
    symbol: Optional[str] = None
    naming_syllable: Optional[str] = None
    suitable_activities: Optional[List[str]] = None
    unfavorable_activities: Optional[List[str]] = None


class YogaInfo(BaseModel):
    number: int
    name: str
    name_sanskrit: Optional[str] = None
    quality: Optional[str] = None
    recommendation: Optional[str] = None


class KaranaInfo(BaseModel):
    number: int
    name: str
    type: str
    name_sanskrit: Optional[str] = None
    deity: Optional[str] = None
    is_bhadra: Optional[bool] = False
    recommendation: Optional[str] = None


class PanchangGuidance(BaseModel):
    headline: str
    traffic_light: str  # "GREEN" | "YELLOW" | "RED"
    current_status: str
    actionable_advice: str
    active_choghadiya: Dict[str, str]
    best_time_window: Dict[str, Any]
    danger_time_window: Dict[str, Any]
    display_title: str


class VedicTimeInfo(BaseModel):
    ishta_kala: str = Field(..., description="Vedic elapsed time from sunrise in Ghati:Pala:Vipala (e.g. '27:02:39')")
    ghati: int = Field(..., description="Ghati elapsed (0-59)")
    pala: int = Field(..., description="Pala elapsed (0-59)")
    vipala: int = Field(..., description="Vipala elapsed (0-59)")
    total_ghati: float = Field(..., description="Total decimal Ghati elapsed")
    dinamana: str = Field(..., description="Duration of daylight (e.g. '12 Hours 21 Mins 03 Secs')")
    ratrimana: str = Field(..., description="Duration of night (e.g. '11 Hours 38 Mins 57 Secs')")


class BasicPanchangResponse(BaseModel):
    meta: MetaInfo
    solar: SolarInfo
    tithi: TithiInfo
    vara: VaraInfo
    nakshatra: NakshatraInfo
    yoga: YogaInfo
    karana: KaranaInfo
    vedic_time: Optional[VedicTimeInfo] = None


class AdvancedPanchangResponse(BasicPanchangResponse):
    abhijit_muhurta: Optional[Dict[str, Any]]
    rahu_kalam: Optional[Dict[str, str]]
    yamaganda: Optional[Dict[str, str]]
    gulika_kalam: Optional[Dict[str, str]]
    choghadiya_day: List[Dict[str, Any]]
    choghadiya_night: List[Dict[str, Any]]
    hora: List[Dict[str, Any]]
    guidance: Optional[PanchangGuidance] = None


class DailyVerdictResponse(BaseModel):
    meta: MetaInfo
    display_title: str
    traffic_light: str
    current_status: str
    actionable_advice: str
    headline: str
    best_time_window: Dict[str, Any]
    danger_time_window: Dict[str, Any]
    active_choghadiya: Dict[str, str]
    active_tithi: str
    active_nakshatra: str


class ChoghadiyaResponse(BaseModel):
    meta: MetaInfo
    solar: SolarInfo
    day_choghadiya: List[Dict[str, Any]]
    night_choghadiya: List[Dict[str, Any]]


class HoraResponse(BaseModel):
    meta: MetaInfo
    solar: SolarInfo
    hora: List[Dict[str, Any]]


class MonthlyPanchangRequest(BaseModel):
    year: int = Field(..., ge=1600, le=2400, examples=[2026], description="Year (e.g. 2026)")
    month: int = Field(..., ge=1, le=12, examples=[9], description="Month (1-12)")
    lat: float = Field(..., ge=-90.0, le=90.0, examples=[28.6139], description="Latitude (-90.0 to +90.0)")
    lon: float = Field(..., ge=-180.0, le=180.0, examples=[77.2090], description="Longitude (-180.0 to +180.0)")
    timezone: str = Field("Asia/Kolkata", examples=["Asia/Kolkata"], description="IANA timezone name")
    ayanamsha: Literal["lahiri", "true_chitra", "raman", "kp"] = Field("lahiri", description="Ayanamsha system")
    sunrise_convention: Literal["astronomical", "hindu_upper_limb", "hindu_center"] = Field(
        "astronomical",
        description="Sunrise convention"
    )

    @model_validator(mode="after")
    def validate_request(self):
        import calendar
        num_days = calendar.monthrange(self.year, self.month)[1]
        d_start = date(self.year, self.month, 1)
        d_end = date(self.year, self.month, num_days)
        if d_end < MIN_DATE or d_start > MAX_DATE:
            raise OutOfEphemerisRangeError(
                f"Month {self.year}-{self.month:02d} is outside supported query range. "
                f"Supported query range is {MIN_DATE.isoformat()} to {MAX_DATE.isoformat()}."
            )
        try:
            ZoneInfo(self.timezone)
        except Exception:
            raise ValueError(f"Unknown IANA timezone: '{self.timezone}'")
        return self


class MonthlyPanchangDayItem(BaseModel):
    day: int
    date: str
    weekday: str
    tithi: Dict[str, Any]
    nakshatra: Dict[str, Any]
    yoga: Dict[str, Any]
    karana: Dict[str, Any]
    sunrise: str
    sunset: str


class MonthlyPanchangResponse(BaseModel):
    meta: Dict[str, Any]
    days: List[MonthlyPanchangDayItem]


class PlanetPanchangRequest(PanchangRequest):
    node_type: Literal["mean", "true"] = Field(
        "mean",
        description="Lunar node calculation method: 'mean' (traditional Vedic/Lahiri/Raman standard) or 'true' (osculating true node)"
    )


class PlanetDetail(BaseModel):
    name: str
    full_degree: float
    norm_degree: float
    formatted_degree: str
    sign: str
    sign_number: int
    sign_lord: str
    nakshatra: str
    nakshatra_number: int
    nakshatra_lord: str
    nakshatra_pada: int
    is_retrograde: bool
    speed_deg_per_day: float


class PlanetPanchangResponse(BaseModel):
    meta: Dict[str, Any]
    planets: Dict[str, PlanetDetail]
    ascendant: PlanetDetail
    planets_list: List[PlanetDetail]


class SignChartDetail(BaseModel):
    sign_number: int = Field(..., description="Zodiac sign number (1=Aries .. 12=Pisces)")
    sign_name: str = Field(..., description="Zodiac sign name in English")
    sign_lord: str = Field(..., description="Planetary ruler of this sign")
    is_ascendant_sign: bool = Field(..., description="True if the Ascendant (Lagna) is placed in this sign")
    planets: List[PlanetDetail] = Field(default_factory=list, description="Planets placed in this sign")


class PanchangChartResponse(BaseModel):
    meta: Dict[str, Any]
    ascendant: PlanetDetail
    chart: List[SignChartDetail]
    planets_by_sign: Dict[str, List[PlanetDetail]]


class LagnaTableItem(BaseModel):
    lagna_number: int = Field(..., description="Zodiac sign number (1=Aries .. 12=Pisces)")
    lagna_name: str = Field(..., description="Zodiac sign name in English")
    lagna_sanskrit: str = Field(..., description="Zodiac sign name in Sanskrit")
    sign_lord: str = Field(..., description="Planetary lord of this sign")
    start_time: str = Field(..., description="Start timestamp of this rising Lagna (local time)")
    end_time: str = Field(..., description="End timestamp of this rising Lagna (local time)")
    start_time_iso: str = Field(..., description="Start timestamp in ISO 8601 format with offset")
    end_time_iso: str = Field(..., description="End timestamp in ISO 8601 format with offset")
    duration: str = Field(..., description="Human-readable duration string")
    duration_minutes: float = Field(..., description="Duration in minutes")
    is_sunrise_lagna: bool = Field(..., description="True if this sign was rising on eastern horizon at sunrise")


class LagnaTableResponse(BaseModel):
    meta: Dict[str, Any]
    lagna_table: List[LagnaTableItem]



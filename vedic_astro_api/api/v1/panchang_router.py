"""Panchanga & Muhurtha API Endpoints.

Supports both GET (with query parameters) and POST (with JSON payload).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from vedic_astro_api.core.ephemeris import OutOfEphemerisRangeError

from vedic_astro_api.calculations.panchang import (
    calculate_panchang,
    calculate_panchang_at_sunrise,
    calculate_monthly_panchang,
    PanchangResult,
)
from vedic_astro_api.calculations.planetary import (
    calculate_planet_panchang,
    calculate_planet_panchang_at_sunrise,
    PlanetPanchangResult,
    calculate_panchang_chart,
    calculate_panchang_chart_at_sunrise,
    PanchangChartResult,
    calculate_panchang_lagna_table,
    PanchangLagnaTableResult,
)
from vedic_astro_api.calculations.guidance import (
    get_tithi_rich_details,
    get_nakshatra_rich_details,
    get_yoga_rich_details,
    get_karana_rich_details,
    synthesize_daily_guidance,
)
from vedic_astro_api.api.schemas.panchang_schema import (
    PanchangRequest,
    BasicPanchangResponse,
    AdvancedPanchangResponse,
    ChoghadiyaResponse,
    HoraResponse,
    DailyVerdictResponse,
    MonthlyPanchangRequest,
    MonthlyPanchangResponse,
    PlanetPanchangRequest,
    PlanetPanchangResponse,
    PlanetDetail,
    PanchangChartResponse,
    SignChartDetail,
    LagnaTableItem,
    LagnaTableResponse,
    VedicTimeInfo,
    PanchangGuidance,
    ConventionsInfo,
    MetaInfo,
    SolarInfo,
    TithiInfo,
    VaraInfo,
    NakshatraInfo,
    YogaInfo,
    KaranaInfo,
)

router = APIRouter(prefix="/v1/vedic", tags=["Panchang & Muhurtha"])


def _extract_request(
    year: int = Query(..., examples=[2026], description="Year (e.g. 2026)"),
    month: int = Query(..., ge=1, le=12, examples=[9], description="Month (1-12)"),
    day: int = Query(..., ge=1, le=31, examples=[9], description="Day (1-31)"),
    hour: int = Query(12, ge=0, le=23, examples=[12], description="Hour in 24h format (0-23)"),
    minute: Optional[int] = Query(None, ge=0, le=59, examples=[0], description="Minute (0-59)"),
    second: Optional[int] = Query(None, ge=0, le=59, examples=[0], description="Second (0-59)"),
    min: Optional[int] = Query(None, ge=0, le=59, description="Legacy parameter for minute"),
    sec: Optional[int] = Query(None, ge=0, le=59, description="Legacy parameter for second"),
    lat: float = Query(..., ge=-90.0, le=90.0, examples=[28.6139], description="Latitude (-90 to +90)"),
    lon: float = Query(..., ge=-180.0, le=180.0, examples=[77.2090], description="Longitude (-180 to +180)"),
    tzone: Optional[float] = Query(None, examples=[5.5], description="REMOVED — send IANA 'timezone'"),
    timezone: str = Query("Asia/Kolkata", examples=["Asia/Kolkata"], description="IANA Timezone name (e.g. 'Asia/Kolkata')"),
    ayanamsha: Literal["lahiri", "true_chitra", "raman", "kp"] = Query("lahiri", description="Ayanamsha: 'lahiri', 'true_chitra', 'raman', 'kp'"),
    sunrise_convention: Literal["astronomical", "hindu_upper_limb", "hindu_center"] = Query(
        "astronomical",
        description="Sunrise convention: 'astronomical' (-50' refracted), 'hindu_upper_limb' (-16' no refraction), or 'hindu_center' (0° disc center)"
    ),
) -> PanchangRequest:
    eff_min = minute if minute is not None else (min if min is not None else 0)
    eff_sec = second if second is not None else (sec if sec is not None else 0)
    try:
        return PanchangRequest(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=eff_min,
            second=eff_sec,
            lat=lat,
            lon=lon,
            tzone=tzone,
            timezone=timezone,
            ayanamsha=ayanamsha,
            sunrise_convention=sunrise_convention,
        )
    except ValidationError as exc:
        for err in exc.errors():
            ctx = err.get("ctx", {})
            if isinstance(ctx.get("error"), OutOfEphemerisRangeError):
                raise ctx["error"]
        raise RequestValidationError(exc.errors())


def _execute_panchang(req: PanchangRequest) -> PanchangResult:
    dt = datetime(req.year, req.month, req.day, req.hour, req.minute, req.second)
    tz_str = req.timezone if req.timezone else "UTC"
    return calculate_panchang(
        dt=dt,
        lat=req.lat,
        lon=req.lon,
        tz_str=tz_str,
        ayanamsha_type=req.ayanamsha or "lahiri",
        sunrise_convention=req.sunrise_convention or "astronomical",
    )


def _extract_monthly_request(
    year: int = Query(..., examples=[2026], description="Year (e.g. 2026)"),
    month: int = Query(..., ge=1, le=12, examples=[9], description="Month (1-12)"),
    lat: float = Query(..., ge=-90.0, le=90.0, examples=[28.6139], description="Latitude (-90 to +90)"),
    lon: float = Query(..., ge=-180.0, le=180.0, examples=[77.2090], description="Longitude (-180 to +180)"),
    timezone: str = Query("Asia/Kolkata", examples=["Asia/Kolkata"], description="IANA Timezone name"),
    ayanamsha: Literal["lahiri", "true_chitra", "raman", "kp"] = Query("lahiri", description="Ayanamsha system"),
    sunrise_convention: Literal["astronomical", "hindu_upper_limb", "hindu_center"] = Query(
        "astronomical", description="Sunrise convention"
    ),
) -> MonthlyPanchangRequest:
    try:
        return MonthlyPanchangRequest(
            year=year,
            month=month,
            lat=lat,
            lon=lon,
            timezone=timezone,
            ayanamsha=ayanamsha,
            sunrise_convention=sunrise_convention,
        )
    except ValidationError as exc:
        for err in exc.errors():
            ctx = err.get("ctx", {})
            if isinstance(ctx.get("error"), OutOfEphemerisRangeError):
                raise ctx["error"]
        raise RequestValidationError(exc.errors())


def _execute_panchang_at_sunrise(req: PanchangRequest) -> PanchangResult:
    dt = datetime(req.year, req.month, req.day, 12, 0, 0)
    tz_str = req.timezone if req.timezone else "Asia/Kolkata"
    return calculate_panchang_at_sunrise(
        dt_local_date=dt,
        lat=req.lat,
        lon=req.lon,
        tz_str=tz_str,
        ayanamsha_type=req.ayanamsha or "lahiri",
        sunrise_convention=req.sunrise_convention or "astronomical",
    )


def _extract_planet_request(
    year: int = Query(..., examples=[2026], description="Year (e.g. 2026)"),
    month: int = Query(..., ge=1, le=12, examples=[9], description="Month (1-12)"),
    day: int = Query(..., ge=1, le=31, examples=[9], description="Day (1-31)"),
    hour: int = Query(12, ge=0, le=23, examples=[12], description="Hour in 24h format (0-23)"),
    minute: Optional[int] = Query(None, ge=0, le=59, examples=[0], description="Minute (0-59)"),
    second: Optional[int] = Query(None, ge=0, le=59, examples=[0], description="Second (0-59)"),
    min: Optional[int] = Query(None, ge=0, le=59, description="Legacy parameter for minute"),
    sec: Optional[int] = Query(None, ge=0, le=59, description="Legacy parameter for second"),
    lat: float = Query(..., ge=-90.0, le=90.0, examples=[28.6139], description="Latitude (-90 to +90)"),
    lon: float = Query(..., ge=-180.0, le=180.0, examples=[77.2090], description="Longitude (-180 to +180)"),
    tzone: Optional[float] = Query(None, examples=[5.5], description="REMOVED — send IANA 'timezone'"),
    timezone: str = Query("Asia/Kolkata", examples=["Asia/Kolkata"], description="IANA Timezone name"),
    ayanamsha: Literal["lahiri", "true_chitra", "raman", "kp"] = Query("lahiri", description="Ayanamsha system"),
    node_type: Literal["mean", "true"] = Query("mean", description="Lunar node: 'mean' (traditional Vedic default) or 'true'"),
) -> PlanetPanchangRequest:
    m = min if minute is None else minute
    s = sec if second is None else second
    try:
        return PlanetPanchangRequest(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=m or 0,
            second=s or 0,
            lat=lat,
            lon=lon,
            tzone=tzone,
            timezone=timezone,
            ayanamsha=ayanamsha,
            node_type=node_type,
        )
    except ValidationError as exc:
        for err in exc.errors():
            ctx = err.get("ctx", {})
            if isinstance(ctx.get("error"), OutOfEphemerisRangeError):
                raise ctx["error"]
        raise RequestValidationError(exc.errors())


def _execute_planet_panchang(req: PlanetPanchangRequest) -> PlanetPanchangResult:
    dt = datetime(req.year, req.month, req.day, req.hour, req.minute, req.second)
    tz_str = req.timezone if req.timezone else "Asia/Kolkata"
    return calculate_planet_panchang(
        dt=dt,
        lat=req.lat,
        lon=req.lon,
        tz_str=tz_str,
        ayanamsha_type=req.ayanamsha or "lahiri",
        node_type=req.node_type or "mean",
    )


def _execute_planet_panchang_at_sunrise(req: PlanetPanchangRequest) -> PlanetPanchangResult:
    dt = datetime(req.year, req.month, req.day, 12, 0, 0)
    tz_str = req.timezone if req.timezone else "Asia/Kolkata"
    return calculate_planet_panchang_at_sunrise(
        dt_date=dt,
        lat=req.lat,
        lon=req.lon,
        tz_str=tz_str,
        ayanamsha_type=req.ayanamsha or "lahiri",
        node_type=req.node_type or "mean",
        sunrise_convention=req.sunrise_convention or "astronomical",
    )


def _to_planet_response(res: PlanetPanchangResult) -> PlanetPanchangResponse:
    d = res.to_dict()
    meta = {
        "engine": "astro-engine/0.1.0",
        "engine_version": d["engine_version"],
        "ephemeris": "DE421",
        "query_local": d["query_local"],
        "query_utc": d["query_utc"],
        "timezone": d["timezone"],
        "ayanamsha": d["ayanamsha_type"],
        "ayanamsha_deg": d["ayanamsha_deg"],
        "ayanamsha_dms": d["ayanamsha_dms"],
        "node_type": d["node_type"],
    }
    if d.get("sunrise_time"):
        meta["sunrise_time"] = d["sunrise_time"]
    return PlanetPanchangResponse(
        meta=meta,
        planets=d["planets"],
        ascendant=d["ascendant"],
        planets_list=d["planets_list"],
    )


def _execute_panchang_chart(req: PlanetPanchangRequest) -> PanchangChartResult:
    dt = datetime(req.year, req.month, req.day, req.hour, req.minute, req.second)
    tz_str = req.timezone if req.timezone else "Asia/Kolkata"
    return calculate_panchang_chart(
        dt=dt,
        lat=req.lat,
        lon=req.lon,
        tz_str=tz_str,
        ayanamsha_type=req.ayanamsha or "lahiri",
        node_type=req.node_type or "mean",
    )


def _execute_panchang_chart_at_sunrise(req: PlanetPanchangRequest) -> PanchangChartResult:
    dt = datetime(req.year, req.month, req.day, 12, 0, 0)
    tz_str = req.timezone if req.timezone else "Asia/Kolkata"
    return calculate_panchang_chart_at_sunrise(
        dt_date=dt,
        lat=req.lat,
        lon=req.lon,
        tz_str=tz_str,
        ayanamsha_type=req.ayanamsha or "lahiri",
        node_type=req.node_type or "mean",
        sunrise_convention=req.sunrise_convention or "astronomical",
    )


def _to_chart_response(res: PanchangChartResult) -> PanchangChartResponse:
    d = res.to_dict()
    meta = {
        "engine": "astro-engine/0.1.0",
        "engine_version": d["engine_version"],
        "ephemeris": "DE421",
        "query_local": d["query_local"],
        "query_utc": d["query_utc"],
        "timezone": d["timezone"],
        "ayanamsha": d["ayanamsha_type"],
        "ayanamsha_deg": d["ayanamsha_deg"],
        "ayanamsha_dms": d["ayanamsha_dms"],
        "node_type": d["node_type"],
    }
    if d.get("sunrise_time"):
        meta["sunrise_time"] = d["sunrise_time"]
    return PanchangChartResponse(
        meta=meta,
        ascendant=d["ascendant"],
        chart=d["chart"],
        planets_by_sign=d["planets_by_sign"],
    )


def _execute_panchang_lagna_table(req: PanchangRequest) -> PanchangLagnaTableResult:
    dt = datetime(req.year, req.month, req.day, 12, 0, 0)
    tz_str = req.timezone if req.timezone else "Asia/Kolkata"
    return calculate_panchang_lagna_table(
        dt_date=dt,
        lat=req.lat,
        lon=req.lon,
        tz_str=tz_str,
        ayanamsha_type=req.ayanamsha or "lahiri",
        sunrise_convention=req.sunrise_convention or "astronomical",
    )


def _to_lagna_table_response(res: PanchangLagnaTableResult) -> LagnaTableResponse:
    d = res.to_dict()
    meta = {
        "engine": "astro-engine/0.1.0",
        "engine_version": d["engine_version"],
        "ephemeris": "DE421",
        "query_date": d["query_date"],
        "timezone": d["timezone"],
        "ayanamsha": d["ayanamsha_type"],
        "ayanamsha_deg": d["ayanamsha_deg"],
        "ayanamsha_dms": d["ayanamsha_dms"],
        "sunrise": d["sunrise_time"],
        "sunset": d["sunset_time"],
    }
    return LagnaTableResponse(
        meta=meta,
        lagna_table=d["lagna_table"],
    )




def _build_meta(d: Dict[str, Any]) -> MetaInfo:
    return MetaInfo(
        engine="astro-engine/0.1.0",
        ephemeris="DE421",
        conventions=ConventionsInfo(
            ayanamsha=d.get("ayanamsha_type", "lahiri"),
            ayanamsha_deg=d.get("ayanamsha_deg", 0.0),
            sunrise=d.get("sunrise_convention_key", "astronomical"),
            hora="indian_60min",
            choghadiya_night_lord="classical_v1",
        ),
        jd_tt=d.get("jd_tt", d.get("julian_day", 0.0)),
        jd_ut1=d.get("jd_ut1", d.get("julian_day", 0.0)),
        local=d.get("query_local", ""),
        utc=d.get("query_utc", ""),
        engine_version=d.get("engine_version", "0.1.0"),
        julian_day=d.get("julian_day"),
        ayanamsha_type=d.get("ayanamsha_type"),
        ayanamsha_deg=d.get("ayanamsha_deg"),
        ayanamsha_dms=d.get("ayanamsha_dms"),
        sunrise_convention=d.get("sunrise_convention"),
        query_utc=d.get("query_utc"),
        query_local=d.get("query_local"),
        timezone=d.get("timezone"),
    )


def _to_basic_response(res: PanchangResult) -> BasicPanchangResponse:
    d = res.to_dict()
    tithi_rich = get_tithi_rich_details(d["tithi_number"])
    nak_rich = get_nakshatra_rich_details(d["nakshatra_number"], d["nakshatra_pada"])
    yoga_rich = get_yoga_rich_details(d["yoga_number"])
    karana_rich = get_karana_rich_details(d["karana_name"])

    return BasicPanchangResponse(
        meta=_build_meta(d),
        solar=SolarInfo(
            sunrise=d["sunrise"],
            sunset=d["sunset"],
            next_sunrise=d["next_sunrise"],
            solar_noon=d["solar_noon"],
            dina_mana_hours=d["dina_mana_hours"],
            ratri_mana_hours=d["ratri_mana_hours"],
            is_daytime=d["is_daytime"],
            polar_phenomenon=d.get("polar_phenomenon"),
            sunrise_astronomical=d.get("sunrise_astronomical"),
            sunrise_hindu=d.get("sunrise_hindu"),
        ),
        tithi=TithiInfo(
            number=d["tithi_number"],
            name=d["tithi_name"],
            paksha=d["paksha"],
            paksha_tithi_number=d["paksha_tithi_number"],
            elapsed_percentage=d["tithi_elapsed_pct"],
            end_time=d["tithi_end_time_local"],
            name_sanskrit=tithi_rich.get("name_sanskrit"),
            category=tithi_rich.get("category"),
            deity=tithi_rich.get("deity"),
            suitable_activities=tithi_rich.get("suitable_activities"),
            unfavorable_activities=tithi_rich.get("unfavorable_activities"),
        ),
        vara=VaraInfo(name=d["vara_name"], lord=d["vara_lord"]),
        nakshatra=NakshatraInfo(
            number=d["nakshatra_number"],
            name=d["nakshatra_name"],
            lord=d["nakshatra_lord"],
            pada=d["nakshatra_pada"],
            elapsed_percentage=d["nakshatra_elapsed_pct"],
            end_time=d["nakshatra_end_time_local"],
            name_sanskrit=nak_rich.get("name_sanskrit"),
            energy=nak_rich.get("energy"),
            deity=nak_rich.get("deity"),
            symbol=nak_rich.get("symbol"),
            naming_syllable=nak_rich.get("naming_syllable"),
            suitable_activities=nak_rich.get("suitable_activities"),
            unfavorable_activities=nak_rich.get("unfavorable_activities"),
        ),
        yoga=YogaInfo(
            number=d["yoga_number"],
            name=d["yoga_name"],
            name_sanskrit=yoga_rich.get("name_sanskrit"),
            quality=yoga_rich.get("quality"),
            recommendation=yoga_rich.get("recommendation"),
        ),
        karana=KaranaInfo(
            number=d["karana_number"],
            name=d["karana_name"],
            type=d["karana_type"],
            name_sanskrit=karana_rich.get("name_sanskrit"),
            deity=karana_rich.get("deity"),
            is_bhadra=karana_rich.get("is_bhadra", False),
            recommendation=karana_rich.get("recommendation"),
        ),
        vedic_time=d.get("vedic_time"),
    )


def _to_advanced_response(res: PanchangResult) -> AdvancedPanchangResponse:
    basic = _to_basic_response(res)
    d = res.to_dict()
    try:
        q_dt = datetime.strptime(d["query_local"][:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        q_dt = datetime.now()
    guidance_dict = synthesize_daily_guidance(d, q_dt)
    guidance_obj = PanchangGuidance(**guidance_dict)

    return AdvancedPanchangResponse(
        **basic.model_dump(),
        abhijit_muhurta=d["abhijit_muhurta"],
        rahu_kalam=d["rahu_kalam"],
        yamaganda=d["yamaganda"],
        gulika_kalam=d["gulika_kalam"],
        choghadiya_day=d["choghadiya_day"],
        choghadiya_night=d["choghadiya_night"],
        hora=d["hora"],
        guidance=guidance_obj,
    )


def _to_daily_verdict_response(res: PanchangResult) -> DailyVerdictResponse:
    d = res.to_dict()
    try:
        q_dt = datetime.strptime(d["query_local"][:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        q_dt = datetime.now()
    g = synthesize_daily_guidance(d, q_dt)
    return DailyVerdictResponse(
        meta=_build_meta(d),
        display_title=g["display_title"],
        traffic_light=g["traffic_light"],
        current_status=g["current_status"],
        actionable_advice=g["actionable_advice"],
        headline=g["headline"],
        best_time_window=g["best_time_window"],
        danger_time_window=g["danger_time_window"],
        active_choghadiya=g["active_choghadiya"],
        active_tithi=d["tithi_name"],
        active_nakshatra=f"{d['nakshatra_name']} (Pada {d['nakshatra_pada']})",
    )


# ===========================================================================
# ENDPOINTS (DUAL GET + POST)
# ===========================================================================

@router.get("/basic_panchang", response_model=BasicPanchangResponse, summary="Get Basic Panchang (GET)")
def get_basic_panchang(req: PanchangRequest = Depends(_extract_request)) -> BasicPanchangResponse:
    res = _execute_panchang(req)
    return _to_basic_response(res)


@router.post("/basic_panchang", response_model=BasicPanchangResponse, summary="Get Basic Panchang (POST)")
def post_basic_panchang(req: PanchangRequest) -> BasicPanchangResponse:
    res = _execute_panchang(req)
    return _to_basic_response(res)


@router.get("/advanced_panchang", response_model=AdvancedPanchangResponse, summary="Get Advanced Panchang & Muhurtha (GET)")
def get_advanced_panchang(req: PanchangRequest = Depends(_extract_request)) -> AdvancedPanchangResponse:
    res = _execute_panchang(req)
    return _to_advanced_response(res)


@router.post("/advanced_panchang", response_model=AdvancedPanchangResponse, summary="Get Advanced Panchang & Muhurtha (POST)")
def post_advanced_panchang(req: PanchangRequest) -> AdvancedPanchangResponse:
    res = _execute_panchang(req)
    return _to_advanced_response(res)


@router.get("/choghadiya_muhurta", response_model=ChoghadiyaResponse, summary="Get Day & Night Choghadiya (GET)")
def get_choghadiya(req: PanchangRequest = Depends(_extract_request)) -> ChoghadiyaResponse:
    res = _execute_panchang(req)
    d = res.to_dict()
    basic = _to_basic_response(res)
    return ChoghadiyaResponse(
        meta=basic.meta,
        solar=basic.solar,
        day_choghadiya=d["choghadiya_day"],
        night_choghadiya=d["choghadiya_night"],
    )


@router.post("/choghadiya_muhurta", response_model=ChoghadiyaResponse, summary="Get Day & Night Choghadiya (POST)")
def post_choghadiya(req: PanchangRequest) -> ChoghadiyaResponse:
    res = _execute_panchang(req)
    d = res.to_dict()
    basic = _to_basic_response(res)
    return ChoghadiyaResponse(
        meta=basic.meta,
        solar=basic.solar,
        day_choghadiya=d["choghadiya_day"],
        night_choghadiya=d["choghadiya_night"],
    )


@router.get("/hora_muhurta", response_model=HoraResponse, summary="Get 24 Indian Horas (GET)")
def get_hora(req: PanchangRequest = Depends(_extract_request)) -> HoraResponse:
    res = _execute_panchang(req)
    d = res.to_dict()
    basic = _to_basic_response(res)
    return HoraResponse(
        meta=basic.meta,
        solar=basic.solar,
        hora=d["hora"],
    )


@router.post("/hora_muhurta", response_model=HoraResponse, summary="Get 24 Indian Horas (POST)")
def post_hora(req: PanchangRequest) -> HoraResponse:
    res = _execute_panchang(req)
    d = res.to_dict()
    basic = _to_basic_response(res)
    return HoraResponse(
        meta=basic.meta,
        solar=basic.solar,
        hora=d["hora"],
    )


@router.get("/daily_verdict", response_model=DailyVerdictResponse, summary="Get Instant Daily Verdict & Cosmic Traffic Light (GET)")
def get_daily_verdict(req: PanchangRequest = Depends(_extract_request)) -> DailyVerdictResponse:
    """Returns a pre-digested cosmic traffic light (GREEN, YELLOW, RED), executive summary, and best/worst hours."""
    res = _execute_panchang(req)
    return _to_daily_verdict_response(res)


@router.post("/daily_verdict", response_model=DailyVerdictResponse, summary="Get Instant Daily Verdict & Cosmic Traffic Light (POST)")
def post_daily_verdict(req: PanchangRequest) -> DailyVerdictResponse:
    """Returns a pre-digested cosmic traffic light (GREEN, YELLOW, RED), executive summary, and best/worst hours."""
    res = _execute_panchang(req)
    return _to_daily_verdict_response(res)


# ===========================================================================
# SUNRISE (SURYODAYA KALINA) ENDPOINTS
# ===========================================================================

@router.get("/basic_panchang/sunrise", response_model=BasicPanchangResponse, summary="Get Basic Panchang at Sunrise (GET)")
def get_basic_panchang_at_sunrise(req: PanchangRequest = Depends(_extract_request)) -> BasicPanchangResponse:
    """Returns basic Panchanga evaluated at the exact instant of sunrise (Suryodaya Kalina)."""
    res = _execute_panchang_at_sunrise(req)
    return _to_basic_response(res)


@router.post("/basic_panchang/sunrise", response_model=BasicPanchangResponse, summary="Get Basic Panchang at Sunrise (POST)")
def post_basic_panchang_at_sunrise(req: PanchangRequest) -> BasicPanchangResponse:
    """Returns basic Panchanga evaluated at the exact instant of sunrise (Suryodaya Kalina)."""
    res = _execute_panchang_at_sunrise(req)
    return _to_basic_response(res)


@router.get("/advanced_panchang/sunrise", response_model=AdvancedPanchangResponse, summary="Get Advanced Panchang at Sunrise (GET)")
def get_advanced_panchang_at_sunrise(req: PanchangRequest = Depends(_extract_request)) -> AdvancedPanchangResponse:
    """Returns advanced Panchanga & Muhurthas evaluated at the exact instant of sunrise."""
    res = _execute_panchang_at_sunrise(req)
    return _to_advanced_response(res)


@router.post("/advanced_panchang/sunrise", response_model=AdvancedPanchangResponse, summary="Get Advanced Panchang at Sunrise (POST)")
def post_advanced_panchang_at_sunrise(req: PanchangRequest) -> AdvancedPanchangResponse:
    """Returns advanced Panchanga & Muhurthas evaluated at the exact instant of sunrise."""
    res = _execute_panchang_at_sunrise(req)
    return _to_advanced_response(res)


# ===========================================================================
# MONTHLY CALENDAR PANCHANG ENDPOINTS
# ===========================================================================

@router.get("/monthly_panchang", response_model=MonthlyPanchangResponse, summary="Get Monthly Panchang Calendar (GET)")
def get_monthly_panchang(req: MonthlyPanchangRequest = Depends(_extract_monthly_request)) -> MonthlyPanchangResponse:
    """Returns a full monthly calendar grid of Tithi, Nakshatra, Yoga, Karana, Sunrise, and Sunset for each day."""
    data = calculate_monthly_panchang(
        year=req.year,
        month=req.month,
        lat=req.lat,
        lon=req.lon,
        tz_str=req.timezone,
        ayanamsha_type=req.ayanamsha,
        sunrise_convention=req.sunrise_convention,
    )
    return MonthlyPanchangResponse(**data)


@router.post("/monthly_panchang", response_model=MonthlyPanchangResponse, summary="Get Monthly Panchang Calendar (POST)")
def post_monthly_panchang(req: MonthlyPanchangRequest) -> MonthlyPanchangResponse:
    """Returns a full monthly calendar grid of Tithi, Nakshatra, Yoga, Karana, Sunrise, and Sunset for each day."""
    data = calculate_monthly_panchang(
        year=req.year,
        month=req.month,
        lat=req.lat,
        lon=req.lon,
        tz_str=req.timezone,
        ayanamsha_type=req.ayanamsha,
        sunrise_convention=req.sunrise_convention,
    )
    return MonthlyPanchangResponse(**data)


# ===========================================================================
# PLANETARY POSITIONS (GRAHA PANCHANG) ENDPOINTS
# ===========================================================================

@router.get("/planet_panchang", response_model=PlanetPanchangResponse, summary="Get Planetary Positions & Lagna (GET)")
def get_planet_panchang(req: PlanetPanchangRequest = Depends(_extract_planet_request)) -> PlanetPanchangResponse:
    """Returns sidereal positions, signs, degrees, nakshatras, speeds, and retrograde statuses for all 9 Grahas and the Ascendant."""
    res = _execute_planet_panchang(req)
    return _to_planet_response(res)


@router.post("/planet_panchang", response_model=PlanetPanchangResponse, summary="Get Planetary Positions & Lagna (POST)")
def post_planet_panchang(req: PlanetPanchangRequest) -> PlanetPanchangResponse:
    """Returns sidereal positions, signs, degrees, nakshatras, speeds, and retrograde statuses for all 9 Grahas and the Ascendant."""
    res = _execute_planet_panchang(req)
    return _to_planet_response(res)


@router.get("/planet_panchang/sunrise", response_model=PlanetPanchangResponse, summary="Get Planetary Positions at Sunrise (GET)")
def get_planet_panchang_at_sunrise(req: PlanetPanchangRequest = Depends(_extract_planet_request)) -> PlanetPanchangResponse:
    """Returns sidereal positions, signs, degrees, nakshatras, speeds, and retrograde statuses for all 9 Grahas and sunrise Lagna."""
    res = _execute_planet_panchang_at_sunrise(req)
    return _to_planet_response(res)


@router.post("/planet_panchang/sunrise", response_model=PlanetPanchangResponse, summary="Get Planetary Positions at Sunrise (POST)")
def post_planet_panchang_at_sunrise(req: PlanetPanchangRequest) -> PlanetPanchangResponse:
    """Returns sidereal positions, signs, degrees, nakshatras, speeds, and retrograde statuses for all 9 Grahas and sunrise Lagna."""
    res = _execute_planet_panchang_at_sunrise(req)
    return _to_planet_response(res)


# ===========================================================================
# PANCHANG CHART (KUNDLI SIGN-BY-SIGN) ENDPOINTS
# ===========================================================================

@router.get("/panchang_chart", response_model=PanchangChartResponse, summary="Get Panchang Kundli Chart (GET)")
def get_panchang_chart(req: PlanetPanchangRequest = Depends(_extract_planet_request)) -> PanchangChartResponse:
    """Returns sign-by-sign planetary mappings across the 12 zodiac signs and the Ascendant for Kundli charts."""
    res = _execute_panchang_chart(req)
    return _to_chart_response(res)


@router.post("/panchang_chart", response_model=PanchangChartResponse, summary="Get Panchang Kundli Chart (POST)")
def post_panchang_chart(req: PlanetPanchangRequest) -> PanchangChartResponse:
    """Returns sign-by-sign planetary mappings across the 12 zodiac signs and the Ascendant for Kundli charts."""
    res = _execute_panchang_chart(req)
    return _to_chart_response(res)


@router.get("/panchang_chart/sunrise", response_model=PanchangChartResponse, summary="Get Panchang Chart at Sunrise (GET)")
def get_panchang_chart_at_sunrise(req: PlanetPanchangRequest = Depends(_extract_planet_request)) -> PanchangChartResponse:
    """Returns sign-by-sign planetary positions and Lagna evaluated at sunrise for Kundli charts."""
    res = _execute_panchang_chart_at_sunrise(req)
    return _to_chart_response(res)


@router.post("/panchang_chart/sunrise", response_model=PanchangChartResponse, summary="Get Panchang Chart at Sunrise (POST)")
def post_panchang_chart_at_sunrise(req: PlanetPanchangRequest) -> PanchangChartResponse:
    """Returns sign-by-sign planetary positions and Lagna evaluated at sunrise for Kundli charts."""
    res = _execute_panchang_chart_at_sunrise(req)
    return _to_chart_response(res)


# ===========================================================================
# PANCHANG LAGNA TABLE (UDAYA LAGNA 24-HOUR RISING SIGNS) ENDPOINTS
# ===========================================================================

@router.get("/panchang_lagna_table", response_model=LagnaTableResponse, summary="Get Panchang Lagna Table (GET)")
def get_panchang_lagna_table(req: PanchangRequest = Depends(_extract_request)) -> LagnaTableResponse:
    """Returns start and end times for all 12 rising signs (Udaya Lagna) throughout the 24-hour day from sunrise."""
    res = _execute_panchang_lagna_table(req)
    return _to_lagna_table_response(res)


@router.post("/panchang_lagna_table", response_model=LagnaTableResponse, summary="Get Panchang Lagna Table (POST)")
def post_panchang_lagna_table(req: PanchangRequest) -> LagnaTableResponse:
    """Returns start and end times for all 12 rising signs (Udaya Lagna) throughout the 24-hour day from sunrise."""
    res = _execute_panchang_lagna_table(req)
    return _to_lagna_table_response(res)



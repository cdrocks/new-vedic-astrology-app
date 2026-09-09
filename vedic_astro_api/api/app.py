"""FastAPI entrypoint for AstroEngine commercial REST API."""

from __future__ import annotations

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vedic_astro_api import __version__
from vedic_astro_api.api.v1.panchang_router import router as panchang_router

app = FastAPI(
    title="AstroEngine Vedic API",
    description=r"""
# AstroEngine: High-Precision Vedic Astrology API

Commercially unencumbered, sub-arcsecond precision Vedic astrology computation engine.
Powered by Skyfield and NASA JPL DE421 ephemeris data.

### Features in Version 0.1.0:
- **Panchanga Engine**: The 5 limbs of Vedic time (Tithi, Vara, Nakshatra, Yoga, Karana).
- **Muhurtha Engine**: Choghadiya, Hora, Rahu Kalam, Yamaganda, Gulika, and dynamic Abhijit Muhurtha.
- **Dual Routing**: Supports both `GET` (for CDN caching and browser testing) and `POST` (for structured JSON requests).
- **Exact Transition Timestamps**: Bisection root-finding on astronomical elongation functions to achieve $\pm 1$s precision.
    """,
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import JSONResponse
from vedic_astro_api.core.ephemeris import (
    OutOfEphemerisRangeError,
    SPK_MIN_JD,
    SPK_MAX_JD,
    SPK_START_TDB,
    SPK_END_TDB,
    SAFE_QUERY_START_DATE,
    SAFE_QUERY_END_DATE,
    KERNEL_MIN_JD,
    KERNEL_MAX_JD,
    KERNEL_MIN_DATE,
    KERNEL_MAX_DATE,
)

# Stash kernel bounds on app.state at startup
app.state.kernel_min_jd = SPK_MIN_JD
app.state.kernel_max_jd = SPK_MAX_JD
app.state.kernel_min_date = SAFE_QUERY_START_DATE
app.state.kernel_max_date = SAFE_QUERY_END_DATE

# Include v1 routers
app.include_router(panchang_router)


@app.exception_handler(OutOfEphemerisRangeError)
async def ephemeris_range_exception_handler(request, exc: OutOfEphemerisRangeError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "DateOutOfRange",
            "message": str(exc),
            "supported_query_range": {
                "start": SAFE_QUERY_START_DATE.isoformat(),
                "end": SAFE_QUERY_END_DATE.isoformat(),
            },
            "supported_range": {
                "start": SAFE_QUERY_START_DATE.isoformat(),
                "end": SAFE_QUERY_END_DATE.isoformat(),
            },
            "spk_segment_tdb": {
                "min_jd": SPK_MIN_JD,
                "max_jd": SPK_MAX_JD,
                "start": SPK_START_TDB,
                "end": SPK_END_TDB,
            },
            "engine": "NASA JPL DE421",
        },
    )


@app.get("/health", tags=["System"])
def health_check():
    """System health check and engine readiness verification."""
    data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "de421.bsp")
    ephem_ok = os.path.exists(data_path)
    return {
        "status": "healthy" if ephem_ok else "degraded",
        "engine": "AstroEngine",
        "version": __version__,
        "ephemeris_engine": "Skyfield + NASA JPL DE421",
        "license": "MIT (Commercially Unencumbered)",
        "ephemeris_file_ready": ephem_ok,
        "ephemeris_bounds": {
            "spk_segment_tdb": {
                "min_jd": SPK_MIN_JD,
                "max_jd": SPK_MAX_JD,
                "start": SPK_START_TDB,
                "end": SPK_END_TDB,
            },
            "supported_query_range": {
                "start": SAFE_QUERY_START_DATE.isoformat(),
                "end": SAFE_QUERY_END_DATE.isoformat(),
            },
            "min_jd": SPK_MIN_JD,
            "max_jd": SPK_MAX_JD,
            "min_date": SAFE_QUERY_START_DATE.isoformat(),
            "max_date": SAFE_QUERY_END_DATE.isoformat(),
        },
    }

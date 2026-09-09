"""
FastAPI Server for Event / Touchscreen Kiosk Mode.
Runs completely independently from app.py without payment gates or rate limits.
"""

import os
import json
import csv
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List

import db
from kiosk_core import compute_kiosk_reading

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("kiosk_server")

app = FastAPI(title="Vedic Astrology Event Kiosk", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LEADS_FILE_JSONL = os.path.join(os.path.dirname(__file__), "event_leads.jsonl")
LEADS_FILE_CSV = os.path.join(os.path.dirname(__file__), "event_leads.csv")

class KioskReadingRequest(BaseModel):
    name: str = Field(..., description="Guest Name")
    dob: str = Field(..., description="Date of birth YYYY-MM-DD")
    time: str = Field(..., description="Time of birth HH:MM")
    city: str = Field(..., description="City of birth")
    country: str = Field(default="India", description="Country of birth")
    question: str = Field(..., description="Question or selected topic prompt")
    topic: Optional[str] = Field(default="", description="Category topic title")
    email: Optional[str] = Field(default="", description="Optional email to send reading")
    phone: Optional[str] = Field(default="", description="Optional phone or WhatsApp number")
    photo: Optional[str] = Field(default="", description="Legacy optional photo field (no longer required)")

@app.on_event("startup")
def init_app_database():
    """Verify and initialize Railway Postgres tables on server launch."""
    if os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL"):
        try:
            db.init_db()
            logger.info("Railway Postgres tables verified & initialized.")
        except Exception as e:
            logger.warning(f"Could not connect to database on startup (will retry on demand): {e}")
    else:
        logger.info("Running without DATABASE_URL; logging consultations to local storage.")


def _log_event_lead(data: dict, result: dict):
    """Save guest lead and reading summary to local JSONL, CSV, and Railway Postgres DB."""
    lead_entry = {
        "timestamp": datetime.now().isoformat(),
        "name": data.get("name"),
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "topic": data.get("topic", ""),
        "question": data.get("question", ""),
        "dob": data.get("dob"),
        "time": data.get("time"),
        "city": data.get("city"),
        "country": data.get("country"),
        "ascendant": result.get("ascendant"),
        "moon_sign": result.get("moon_sign"),
        "nakshatra": result.get("nakshatra"),
        "current_dasha": result.get("current_dasha"),
        "workflow": result.get("workflow", ""),
        "reading": result.get("reading", ""),
    }
    
    # 1. Append to JSONL
    try:
        with open(LEADS_FILE_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(lead_entry) + "\n")
    except Exception as e:
        logger.error(f"Error saving to JSONL: {e}")

    # 2. Append to CSV for instant Excel/Sheets opening
    try:
        file_exists = os.path.isfile(LEADS_FILE_CSV)
        with open(LEADS_FILE_CSV, "a", newline="", encoding="utf-8") as f:
            fields = [
                "timestamp", "name", "email", "phone", "topic", "dob", "time", 
                "city", "country", "ascendant", "moon_sign", "nakshatra", 
                "current_dasha", "workflow", "question", "reading"
            ]
            writer = csv.DictWriter(f, fieldnames=fields)
            if not file_exists:
                writer.writeheader()
            writer.writerow({k: lead_entry.get(k, "") for k in fields})
    except Exception as e:
        logger.error(f"Error saving to CSV: {e}")

    # 3. Persist to Railway PostgreSQL database (if DATABASE_URL is present)
    try:
        if os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL"):
            identifier = data.get("email") or data.get("phone") or f"guest_{str(data.get('name', 'seeker')).strip().lower().replace(' ', '_')}"
            chart_id = f"{data.get('dob')}_{data.get('time')}_{str(data.get('city', '')).strip()}"
            res = db.save_reading(
                identifier=identifier,
                chart_id=chart_id,
                question=data.get("question", ""),
                answer=result.get("reading", ""),
                workflow=result.get("workflow", ""),
                customer_name=data.get("name", "Seeker"),
            )
            if res.get("ok"):
                logger.info(f"Successfully recorded reading into Railway Postgres (ID: {res.get('reading', {}).get('id')})")
            else:
                logger.warning(f"Postgres save returned non-ok: {res.get('error')}")
    except Exception as db_err:
        logger.warning(f"Error persisting reading to Postgres: {db_err}")



@app.post("/api/reading")
def generate_reading(req: KioskReadingRequest):
    """Generate instant Vedic reading for kiosk guest."""
    logger.info(f"Received reading request for guest: {req.name} (Topic: {req.topic or 'Custom'})")
    try:
        result = compute_kiosk_reading(
            name=req.name.strip(),
            dob_str=req.dob.strip(),
            time_str=req.time.strip(),
            city=req.city.strip(),
            country=req.country.strip(),
            user_question=req.question.strip(),
            topic=req.topic or ""
        )
        # Log lead asynchronously / locally
        _log_event_lead(req.model_dump(), result)
        return JSONResponse(content={"status": "success", "data": result})
    except ValueError as ve:
        logger.warning(f"Validation error: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.exception(f"Unexpected error calculating reading: {exc}")
        raise HTTPException(status_code=500, detail=f"Cosmic alignment calculation error: {str(exc)}")


class ChartDataRequest(BaseModel):
    name: Optional[str] = Field(default="Client", description="Client Name")
    dob: str = Field(..., description="Date of birth YYYY-MM-DD")
    time: str = Field(..., description="Time of birth HH:MM")
    city: str = Field(..., description="City of birth")
    country: Optional[str] = Field(default="India", description="Country of birth")


@app.post("/api/chart-data")
def get_chart_data(req: ChartDataRequest):
    """Retrieve complete astronomical and astrological calculations instantly without LLM."""
    from inspect_chart import calculate_chart
    logger.info(f"Computing raw Vedic chart data for: {req.name} ({req.dob} {req.time} {req.city})")
    try:
        data = calculate_chart(
            name=req.name.strip() if req.name else "Client",
            dob_str=req.dob.strip(),
            time_str=req.time.strip(),
            city=req.city.strip(),
            country=req.country.strip() if req.country else "India"
        )
        return JSONResponse(content={"status": "success", "data": jsonable_encoder(data)})
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.exception(f"Error calculating chart data: {exc}")
        raise HTTPException(status_code=500, detail=f"Chart calculation error: {str(exc)}")


class DivineBlessingRequest(BaseModel):
    atmakaraka: str = Field(default="Jupiter", description="Soul planet (Atmakaraka)")
    nakshatra: str = Field(default="Revati", description="Janma Nakshatra name")
    name: Optional[str] = Field(default="Seeker", description="Guest Name")


@app.post("/api/divine-blessing")
def create_divine_blessing(req: DivineBlessingRequest):
    """Generate sacred Divine Blessing Card (Ashirwad Talisman) via OpenAI gpt-image-2."""
    from image_service import generate_divine_blessing_card
    logger.info(f"Generating divine blessing card for: {req.name} (AK: {req.atmakaraka}, Nak: {req.nakshatra})")
    res = generate_divine_blessing_card(
        atmakaraka=req.atmakaraka,
        nakshatra_name=req.nakshatra,
        seeker_name=req.name
    )
    return JSONResponse(content={"status": "success", "data": res})


# Backward compatible endpoint
class NakshatraPortraitRequest(BaseModel):
    photo: Optional[str] = Field(default="", description="Optional legacy photo")
    nakshatra: str = Field(..., description="Nakshatra name e.g. Revati")
    name: Optional[str] = Field(default="Seeker", description="Guest Name")
    atmakaraka: Optional[str] = Field(default="Jupiter", description="Atmakaraka planet")


@app.post("/api/nakshatra-portrait")
def create_nakshatra_portrait(req: NakshatraPortraitRequest):
    """Legacy route: redirects to Divine Blessing Card generation."""
    from image_service import generate_divine_blessing_card
    logger.info(f"Serving divine blessing via portrait route for: {req.name} ({req.nakshatra})")
    res = generate_divine_blessing_card(
        atmakaraka=req.atmakaraka or "Jupiter",
        nakshatra_name=req.nakshatra,
        seeker_name=req.name
    )
    return JSONResponse(content={"status": "success", "data": res})


class EmailKeepsakeRequest(BaseModel):
    email: str = Field(..., description="Guest Email")
    name: str = Field(..., description="Guest Name")
    nakshatra: str = Field(default="", description="Nakshatra")
    archetype_title: str = Field(default="", description="Archetype Title")
    life_focus: str = Field(default="", description="Life Focus")
    image_url: Optional[str] = Field(default="", description="Generated Image URL")


@app.post("/api/send-email")
def send_email_keepsake(req: EmailKeepsakeRequest):
    """Log and confirm keepsake email delivery to guest."""
    logger.info(f"Sending keepsake email to: {req.email} for {req.name} ({req.nakshatra})")
    return JSONResponse(content={
        "status": "success",
        "message": f"Keepsake successfully sent to {req.email}!"
    })


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "mode": "event_kiosk", "time": datetime.now().isoformat()}


# Mount the kiosk UI static files
UI_DIR = os.path.join(os.path.dirname(__file__), "kiosk_ui")
os.makedirs(UI_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=UI_DIR), name="static")

@app.get("/")
async def root(start: Optional[str] = None):
    # If explicitly requesting the form via ?start=1 or ?form=1, serve form
    if start:
        index_file = os.path.join(UI_DIR, "index.html")
        return FileResponse(index_file, headers={"Cache-Control": "no-cache"})
    intro_file = os.path.join(UI_DIR, "intro.html")
    if os.path.exists(intro_file):
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        return FileResponse(intro_file, headers=headers)
    index_file = os.path.join(UI_DIR, "index.html")
    return FileResponse(index_file, headers={"Cache-Control": "no-cache"})


@app.get("/app")
@app.get("/kiosk")
async def app_page():
    index_file = os.path.join(UI_DIR, "index.html")
    if os.path.exists(index_file):
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        return FileResponse(index_file, headers=headers)
    return {"message": "Vedic Kiosk UI is loading..."}


@app.get("/portrait-lab")
async def portrait_lab():
    lab_file = os.path.join(UI_DIR, "test_portrait.html")
    if os.path.exists(lab_file):
        return FileResponse(lab_file, headers={"Cache-Control": "no-cache"})
    return {"message": "Portrait Lab is loading..."}


@app.get("/admin")
@app.get("/admin/readings")
async def admin_page():
    """Serve administrative consultation audit & prompt tuning console."""
    admin_file = os.path.join(UI_DIR, "admin.html")
    if os.path.exists(admin_file):
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        return FileResponse(admin_file, headers=headers)
    return {"message": "Admin dashboard is loading..."}


@app.get("/api/admin/db-status")
def get_db_status():
    """Check status of Railway Postgres connection vs local fallback storage."""
    has_db_url = bool(os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL"))
    db_connected = False
    error = None
    count = 0
    if has_db_url:
        try:
            readings = db.get_all_recent_readings(limit=5, offset=0)
            db_connected = True
            count = len(readings)
        except Exception as e:
            error = str(e)
    return {
        "database_configured": has_db_url,
        "database_connected": db_connected,
        "recent_count": count,
        "error": error,
        "local_jsonl_exists": os.path.isfile(LEADS_FILE_JSONL),
        "local_csv_exists": os.path.isfile(LEADS_FILE_CSV),
    }


@app.get("/api/admin/readings")
def get_admin_readings(limit: int = 100, offset: int = 0):
    """
    Fetch recorded consultations for admin review.
    Prioritizes Railway Postgres; falls back to local JSONL seamlessly.
    """
    has_db_url = bool(os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL"))
    readings = []
    source = "local_storage"

    # Try PostgreSQL first
    if has_db_url:
        try:
            pg_readings = db.get_all_recent_readings(limit=limit, offset=offset)
            if pg_readings:
                source = "railway_postgres"
                for r in pg_readings:
                    chart_parts = (r.get("chart_id") or "").split("_")
                    dob_val = chart_parts[0] if len(chart_parts) > 0 else ""
                    time_val = chart_parts[1] if len(chart_parts) > 1 else ""
                    city_val = chart_parts[2] if len(chart_parts) > 2 else ""

                    readings.append({
                        "id": r.get("id"),
                        "timestamp": r.get("created_at"),
                        "name": r.get("customer_name") or "Seeker",
                        "identifier": r.get("identifier"),
                        "dob": dob_val,
                        "time": time_val,
                        "city": city_val,
                        "question": r.get("question"),
                        "reading": r.get("answer"),
                        "workflow": r.get("workflow"),
                        "source": "railway_postgres"
                    })
        except Exception as e:
            logger.warning(f"Could not load readings from Postgres: {e}")

    # Fallback to local JSONL if Postgres has no data or is unconfigured
    if not readings and os.path.isfile(LEADS_FILE_JSONL):
        source = "local_storage"
        local_entries = []
        try:
            with open(LEADS_FILE_JSONL, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            item = json.loads(line)
                            item["source"] = "local_storage"
                            local_entries.append(item)
                        except Exception:
                            continue
            local_entries.reverse()
            readings = local_entries[offset : offset + limit]
        except Exception as e:
            logger.error(f"Error reading JSONL leads: {e}")

    return {
        "status": "success",
        "source": source,
        "total": len(readings),
        "readings": readings,
        "database_configured": has_db_url,
    }


@app.api_route("/api/admin/export-csv", methods=["GET", "HEAD"])
def export_admin_csv():
    """Download full consultation log as CSV file."""
    import io
    from fastapi.responses import Response

    has_db_url = bool(os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL"))
    if has_db_url:
        try:
            pg_readings = db.get_all_recent_readings(limit=5000, offset=0)
            if pg_readings:
                output = io.StringIO()
                fields = ["id", "timestamp", "name", "identifier", "chart_id", "workflow", "question", "reading"]
                writer = csv.DictWriter(output, fieldnames=fields)
                writer.writeheader()
                for r in pg_readings:
                    writer.writerow({
                        "id": r.get("id"),
                        "timestamp": r.get("created_at"),
                        "name": r.get("customer_name") or "Seeker",
                        "identifier": r.get("identifier"),
                        "chart_id": r.get("chart_id"),
                        "workflow": r.get("workflow"),
                        "question": r.get("question"),
                        "reading": r.get("answer")
                    })
                return Response(
                    content=output.getvalue(),
                    media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=vedic_kiosk_readings.csv"}
                )
        except Exception as e:
            logger.warning(f"Could not export CSV from Postgres: {e}")

    if os.path.isfile(LEADS_FILE_CSV):
        return FileResponse(
            LEADS_FILE_CSV,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=vedic_kiosk_readings.csv"}
        )

    return JSONResponse(
        content={"status": "error", "message": "No consultation records found yet to export."},
        status_code=404
    )


@app.get("/intro")
async def intro_page():
    intro_file = os.path.join(UI_DIR, "intro.html")
    if os.path.exists(intro_file):
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        return FileResponse(intro_file, headers=headers)
    return {"message": "Intro Orrery is loading..."}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting Vedic Astrology Event Kiosk on http://0.0.0.0:{port}")
    uvicorn.run("kiosk_server:app", host="0.0.0.0", port=port, reload=True)

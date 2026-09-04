"""
FastAPI Server for Event / Touchscreen Kiosk Mode.
Runs completely independently from app.py without payment gates or rate limits.
"""

import os
import json
import csv
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

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

def _log_event_lead(data: dict, result: dict):
    """Save guest lead and reading summary to local JSONL and CSV."""
    lead_entry = {
        "timestamp": datetime.now().isoformat(),
        "name": data.get("name"),
        "email": data.get("email", ""),
        "topic": data.get("topic", ""),
        "question": data.get("question", ""),
        "dob": data.get("dob"),
        "time": data.get("time"),
        "city": data.get("city"),
        "country": data.get("country"),
        "ascendant": result.get("ascendant"),
        "moon_sign": result.get("moon_sign"),
        "current_dasha": result.get("current_dasha"),
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
            fields = ["timestamp", "name", "email", "topic", "dob", "time", "city", "country", "ascendant", "moon_sign", "current_dasha", "question"]
            writer = csv.DictWriter(f, fieldnames=fields)
            if not file_exists:
                writer.writeheader()
            writer.writerow({k: lead_entry.get(k, "") for k in fields})
    except Exception as e:
        logger.error(f"Error saving to CSV: {e}")


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


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "mode": "event_kiosk", "time": datetime.now().isoformat()}


# Mount the kiosk UI static files
UI_DIR = os.path.join(os.path.dirname(__file__), "kiosk_ui")
os.makedirs(UI_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=UI_DIR), name="static")

@app.get("/")
async def root():
    index_file = os.path.join(UI_DIR, "index.html")
    if os.path.exists(index_file):
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        return FileResponse(index_file, headers=headers)
    return {"message": "Vedic Kiosk UI is loading..."}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting Vedic Astrology Event Kiosk on http://0.0.0.0:{port}")
    uvicorn.run("kiosk_server:app", host="0.0.0.0", port=port, reload=True)

# Tech Stack

## Language & runtime
- Python 3.11.9 (pinned in `runtime.txt`).
- Local dev may run on Python 3.12; code is compatible.

## Web / UI
- Streamlit — main app UI (`app.py`).
- FastAPI + Uvicorn — payment service (`payment_service.py`).

## Astrology & geo
- `pyswisseph` — Swiss Ephemeris calculations.
- `geopy` (ArcGIS + Nominatim fallback) — geocoding.
- `timezonefinder` + `pytz` — timezone resolution and DST handling.

## AI
- `openai` SDK calling DeepSeek (`base_url=https://api.deepseek.com`).
- Models: `deepseek-v4-pro` for readings, `deepseek-chat` for safety classifier.

## Database
- PostgreSQL via `psycopg2-binary`.
- Schema auto-created by `init_db()`; no migration framework.

## Payments
- `razorpay` Python SDK.

## Security / crypto
- `itsdangerous` — signed handoff tokens between WordPress and Streamlit.

## Deployment
- Railway (Procfile + `runtime.txt`).
- `nixpacks.toml` also present for alternative Railway build path.
- `mise.toml` disables Python GitHub attestations.

## Package management
- `requirements.txt` only; no lock file.
- Install: `pip install -r requirements.txt`.

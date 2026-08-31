# new-vedic-astrology-app — Core Source Map

## Entrypoints
- `app.py` — Streamlit UI + reading orchestration. Main Railway process.
- `payment_service.py` — FastAPI service for Razorpay orders/webhooks. Second Railway process.

## Module graph
- `app.py` imports `engine`, `prompts`, `db`, `handoff_token`, `debug_utils`.
- `payment_service.py` imports `db`, `handoff_token`.
- `db.py` is the only Postgres client; uses `psycopg2` + `DATABASE_URL`/`SUPABASE_DB_URL`.
- `engine.py` is pure astrology math (swisseph); no I/O.
- `prompts.py` loads `workflows/*.txt` at import time.
- `debug_utils.py` writes to `debug_logs/` only in non-production.

## Project-wide invariants
- Production is detected by `RAILWAY_ENVIRONMENT` env var or `IS_PRODUCTION=true`.
- Debug logs, raw prompt viewer, and system-health sidebar are disabled in production.
- All credit mutations are atomic DB transactions in `db.py`.
- Razorpay webhook signature verification is the only path that grants paid credits.
- Handoff tokens are convenience-only; they do not grant credits.
- Workflow prompts are loaded from disk; `workflows/common.txt` must contain `{chart_string}`, `{dasha_string}`, `{current_date}` placeholders.

## Key environment variables
- `DATABASE_URL` / `SUPABASE_DB_URL`
- `DEEPSEEK_API_KEY`
- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`
- `HANDOFF_TOKEN_SECRET`
- `WORDPRESS_DOMAIN`
- `ADMIN_API_KEY`
- `READING_SUBMISSIONS_PER_IP_PER_HOUR`, `READING_RATE_LIMIT_WINDOW_SECONDS`
- `ORDER_LIMIT_PER_IDENTIFIER_PER_HOUR`, `ORDER_LIMIT_PER_IP_PER_HOUR`, `ORDER_RATE_LIMIT_WINDOW_SECONDS`

## Further reading
- Tech stack and runtime: `mem:tech_stack`
- Commands to run locally and on deploy: `mem:suggested_commands`
- Code conventions and style: `mem:conventions`
- Task-completion verification: `mem:task_completion"

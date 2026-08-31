# Code Conventions

## Style
- PEP 8-ish, but pragmatic. Line lengths are not strictly enforced.
- Type hints are used sporadically (`-> str`, `-> bool`, `Optional[...]`); not required everywhere.
- Docstrings explain *why* more than *what* for non-obvious logic.

## Naming
- `snake_case` for functions/variables.
- `PascalCase` for classes (`BaseModel`, `FastAPI` models).
- Constants at module level are `UPPER_SNAKE_CASE`.
- Streamlit session-state keys are strings.

## Module responsibilities
- Keep astrology math in `engine.py`; no Streamlit or DB imports there.
- Keep DB logic in `db.py`; no Streamlit imports there.
- Keep payment logic in `payment_service.py`; no Streamlit imports there.
- `app.py` is allowed to import everything and orchestrate.

## Error handling
- Prefer graceful degradation in UI paths (log and continue rather than crash).
- Use `st.stop()` after `st.error()` in Streamlit flow control.
- Payment service raises `HTTPException` with clear status codes.

## Safety / privacy
- Hash identifiers with SHA-256 before logging (`_hash_identifier`).
- Sanitize DOB to year-only and truncate questions in crash logs.
- Never log Razorpay secrets, webhook payloads, or raw handoff tokens.
- Debug logs are written to `debug_logs/` only when not in production.

## Database
- Use `FOR UPDATE` when reading a user row before mutating credits.
- Credit transactions are idempotent by `razorpay_payment_id`.
- `normalize_identifier()` lowercases and strips before lookup.

## Prompts
- Workflow files live in `workflows/*.txt`.
- `workflows/common.txt` must include placeholders: `{chart_string}`, `{dasha_string}`, `{current_date}`.
- `prompts.py` concatenates `COMMON_RULES + specific workflow`.

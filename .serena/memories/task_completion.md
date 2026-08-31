# Task Completion Checklist

Run these before considering a coding task done:

1. **Static syntax check**
   ```bash
   python -m py_compile app.py payment_service.py engine.py db.py prompts.py debug_utils.py handoff_token.py
   ```

2. **Import smoke test** (requires deps installed)
   ```bash
   python -c "import app, payment_service, engine, db, prompts, debug_utils, handoff_token"
   ```

3. **Run the Streamlit app briefly** (manual / local only)
   ```bash
   streamlit run app.py
   ```

4. **Run the payment service briefly** (manual / local only)
   ```bash
   uvicorn payment_service:app --port 8000
   ```

5. **Check for stale memories** (after any memory edits)
   ```bash
   serena memories check
   ```

Note: There is no automated test suite. Verification is manual / smoke-test based.

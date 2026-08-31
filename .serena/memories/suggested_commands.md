# Suggested Commands

## Local development
```bash
# Install dependencies
pip install -r requirements.txt

# Run the Streamlit app
streamlit run app.py

# Run the payment service (in another terminal)
uvicorn payment_service:app --reload --port 8000
```

## Environment checks
```bash
# Verify required env vars are present (fill values first)
python -c "import os; print('DEEPSEEK_API_KEY' in os.environ)"
python -c "import db; db.init_db()"
```

## Database
```bash
# Print schema SQL for manual setup
python -c "import db; print(db.schema_sql())"

# Initialize tables from Python shell
python -c "from db import init_db; init_db()"
```

## Production / Railway
```bash
# Railway CLI deploy (if logged in)
railway up

# Tail logs
railway logs
```

## macOS-specific notes
- No special `sed`/`grep`/`ls` flags are required; standard BSD variants work.
- Use `python` or `python3` depending on the active venv.

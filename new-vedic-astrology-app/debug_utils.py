# =======================
# DEBUG & DIAGNOSTIC AGENT
# =======================
import hashlib
import os
import sys
import json
import traceback
from datetime import datetime, timedelta

# Auto-create the evidence folder next to this file.
# IMPORTANT: This directory is inside the project root. Streamlit does not
# automatically serve arbitrary subdirectories, but to be extra safe we keep
# it outside any known static path and do not expose it via the UI. In a
# future hardening step, move this to /tmp or a dedicated non-web volume.
_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_logs")
os.makedirs(_LOG_DIR, exist_ok=True)

# How long to keep crash/prompt logs on disk (default 30 days).
_LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "30"))


def _hash_identifier(value: str) -> str:
    """One-way hash for correlating logs to a user without storing raw PII."""
    return hashlib.sha256(value.lower().strip().encode("utf-8")).hexdigest()[:16]


def _sanitize_dob(dob) -> str:
    """Keep only the year from a date string/object to reduce PII."""
    if dob is None:
        return None
    try:
        s = str(dob)
        # ISO date strings start with YYYY-MM-DD
        return s[:4] if len(s) >= 4 else s
    except Exception:
        return "[redacted]"


def _sanitize_question(question: str) -> str:
    """Truncate question text so logs don't store full user queries."""
    if not question:
        return None
    text = str(question).strip()
    if len(text) <= 40:
        return text
    return text[:40] + "...[truncated]"


def _cleanup_old_logs():
    """Delete log files older than _LOG_RETENTION_DAYS on startup."""
    try:
        cutoff = datetime.now() - timedelta(days=_LOG_RETENTION_DAYS)
        for filename in os.listdir(_LOG_DIR):
            path = os.path.join(_LOG_DIR, filename)
            if os.path.isfile(path):
                mtime = datetime.fromtimestamp(os.path.getmtime(path))
                if mtime < cutoff:
                    os.remove(path)
    except Exception:
        # Don't crash the app if cleanup fails.
        pass


# Run cleanup once at module import time.
_cleanup_old_logs()


def _now():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def diagnose():
    """
    Returns a list of (component_name, is_ok, message).
    Used to draw the 🟢 / 🔴 sidebar panel in the UI.
    """
    results = []

    # 1. Python version
    v = sys.version_info
    results.append(("Python version", True, f"{v.major}.{v.minor}.{v.micro}"))

    # 2. Critical imports
    critical = {
        "streamlit": None,
        "swisseph": "swe",
        "geopy.geocoders": "ArcGIS",
        "timezonefinder": "TimezoneFinder",
        "pytz": None,
        "openai": "OpenAI",
        "requests": None,
    }
    for mod, obj in critical.items():
        try:
            m = __import__(mod, fromlist=[""])
            if obj:
                getattr(m, obj)
            results.append((f"Library: {mod.split('.')[0]}", True, "OK"))
        except Exception as e:
            results.append((f"Library: {mod.split('.')[0]}", False, str(e)))

    # 3. API Key present?
    key_ok = False
    key_msg = "Not checked"
    try:
        import streamlit as st
        key = None
        try:
            if hasattr(st, "secrets"):
                key = st.secrets.get("DEEPSEEK_API_KEY")
        except Exception:
            pass
        if not key:
            key = os.getenv("DEEPSEEK_API_KEY")
        key_ok = bool(key)
        key_msg = "Found" if key_ok else "Missing: add DEEPSEEK_API_KEY to Streamlit secrets or environment variables"
    except Exception as e:
        key_msg = f"Could not check secrets: {e}"
    results.append(("DeepSeek API Key", key_ok, key_msg))

    # 4. Workflow text files integrity
    wf_dir = os.path.join(os.path.dirname(__file__), "workflows")
    if not os.path.isdir(wf_dir):
        results.append(("workflows/ folder", False, f"Missing directory: {wf_dir}"))
    else:
        results.append(("workflows/ folder", True, "Found"))
        required = [
            "common","career","wealth","marriage",
            "relationships","health","children","foreign","legal","general"
        ]
        for name in required:
            path = os.path.join(wf_dir, f"{name}.txt")
            if not os.path.exists(path):
                results.append((f"  {name}.txt", False, "Missing"))
            else:
                sz = os.path.getsize(path)
                ok, msg = True, f"{sz} bytes"
                # Only common.txt must have the placeholders app.py expects
                if name == "common":
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read()
                        needed = ["{chart_string}","{dasha_string}","{current_date}"]
                        missing = [p for p in needed if p not in content]
                        if missing:
                            ok = False
                            msg = f"Missing placeholders: {missing}"
                    except Exception as read_err:
                        ok = False
                        msg = f"Read failed: {read_err}"
                results.append((f"  {name}.txt", ok, msg))

    return results


def is_production():
    return "RAILWAY_ENVIRONMENT" in os.environ or os.getenv("IS_PRODUCTION", "").lower() == "true"


def log_crash(exc, context_dict):
    ts = _now()

    # Sanitize PII before writing to disk.
    safe_context = {}
    for key, value in (context_dict or {}).items():
        if key == "identifier":
            safe_context["identifier_hash"] = _hash_identifier(value) if value else None
        elif key == "dob":
            safe_context["dob_year"] = _sanitize_dob(value)
        elif key == "question":
            safe_context["question_preview"] = _sanitize_question(value)
        else:
            # city, country, chart_id, workflow are lower-sensitivity but we still
            # keep them as-is; city/country are not unique identifiers.
            safe_context[key] = value

    payload = {
        "timestamp": ts,
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "context": safe_context,
        "traceback": traceback.format_exc()
    }
    if is_production():
        # Log securely to stdout/stderr for display on the private Railway dashboard logs
        import sys
        print(f"CRASH OCCURRED: {json.dumps(payload, ensure_ascii=False)}", file=sys.stderr)
        return "Logged to Railway console"

    out_path = os.path.join(_LOG_DIR, f"crash_{ts}.json")
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return out_path
    except Exception as e:
        print(f"Warning: Could not write crash log to disk: {e}")
        return "Not saved (read-only filesystem)"


def log_prompt(system_prompt, workflow, question, chart_id):
    if is_production():
        return "Disabled in production"

    ts = _now()
    out_path = os.path.join(_LOG_DIR, f"prompt_{ts}.json")
    payload = {
        "timestamp": ts,
        "workflow": workflow,
        "question": question,
        "chart_id": chart_id,
        "prompt_length": len(system_prompt),
        "prompt": system_prompt
    }
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return out_path
    except Exception as e:
        print(f"Warning: Could not write prompt log to disk: {e}")
        return "Not saved (read-only filesystem)"


ERR_CODES = {
    "ModuleNotFoundError": "ERR-IMPORT-001: A Python package is missing. Run: pip install -r requirements.txt",
    "FileNotFoundError": "ERR-FILE-001: A required file (often in workflows/) is missing.",
    "KeyError": "ERR-PROMPT-001: A prompt placeholder is missing. Check workflows/common.txt or app.py arguments.",
    "TypeError": "ERR-CODE-001: Wrong argument type passed to a function.",
    "ValueError": "ERR-CODE-002: Invalid input value (often date/time).",
    "AttributeError": "ERR-CODE-003: Tried to use a module/component that did not load correctly.",
    "swe.Error": "ERR-CALC-001: Swiss Ephemeris failed (bad date or coordinates).",
    "requests.exceptions.ConnectionError": "ERR-NET-001: Could not reach DeepSeek API. Check internet.",
    "requests.exceptions.Timeout": "ERR-NET-002: API request timed out.",
}


def user_friendly_code(exc):
    t = type(exc).__name__
    return ERR_CODES.get(t, f"ERR-UNKNOWN ({t}): Please share the crash log from the debug_logs folder.")

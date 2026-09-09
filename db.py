"""
Database module for the Vedic Astrology credit ledger.

MIGRATION NOTE:
---------------
Tables are created automatically when the app starts via `init_db()`.
No external migration framework is required at this scale.

If you need to run the schema manually (e.g. against a fresh Railway Postgres
addon), connect with psql using the DATABASE_URL environment variable and
execute the SQL returned by `schema_sql()`:

    import db
    print(db.schema_sql())

Or, from a Python shell:

    from db import init_db
    init_db()

Environment variables:
- DATABASE_URL (preferred, e.g. postgres://user:pass@host:port/dbname)
- SUPABASE_DB_URL (legacy fallback, kept for compatibility with existing deploys)
"""

import os
import re
from datetime import datetime
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor


# Railway Postgres addons typically expose DATABASE_URL.
# We keep SUPABASE_DB_URL as a fallback for older deploys.
DB_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")


def get_connection():
    if not DB_URL:
        raise ValueError(
            "DATABASE_URL (or SUPABASE_DB_URL) environment variable not set"
        )
    return psycopg2.connect(DB_URL)


def schema_sql() -> str:
    """Return the DDL used to create the credit-ledger tables."""
    return """
    CREATE TABLE IF NOT EXISTS users (
        identifier TEXT PRIMARY KEY,
        customer_name TEXT,
        free_credit_used BOOLEAN DEFAULT FALSE,
        credits_remaining INTEGER DEFAULT 0,
        credits_purchased_total INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS credit_transactions (
        id SERIAL PRIMARY KEY,
        identifier TEXT NOT NULL REFERENCES users(identifier) ON DELETE CASCADE,
        type TEXT NOT NULL CHECK (type IN ('free_grant', 'purchase', 'consumption')),
        credits_delta INTEGER NOT NULL,
        razorpay_payment_id TEXT,
        razorpay_order_id TEXT,
        plan_id TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_credit_transactions_identifier
        ON credit_transactions(identifier);

    CREATE TABLE IF NOT EXISTS pending_orders (
        order_id TEXT PRIMARY KEY,
        identifier TEXT NOT NULL,
        customer_name TEXT,
        plan_id TEXT NOT NULL,
        credits INTEGER NOT NULL,
        status TEXT DEFAULT 'created',
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_pending_orders_identifier
        ON pending_orders(identifier);

    CREATE TABLE IF NOT EXISTS rate_limit_events (
        id SERIAL PRIMARY KEY,
        key TEXT NOT NULL,
        event_type TEXT NOT NULL,
        occurred_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_rate_limit_events_key_type_time
        ON rate_limit_events(key, event_type, occurred_at);

    CREATE TABLE IF NOT EXISTS readings (
        id SERIAL PRIMARY KEY,
        identifier TEXT NOT NULL REFERENCES users(identifier) ON DELETE CASCADE,
        customer_name TEXT,
        chart_id TEXT NOT NULL,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        workflow TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_readings_identifier
        ON readings(identifier);

    CREATE INDEX IF NOT EXISTS idx_readings_chart_id
        ON readings(chart_id);

    ALTER TABLE users
        ADD COLUMN IF NOT EXISTS customer_name TEXT;

    ALTER TABLE readings
        ADD COLUMN IF NOT EXISTS customer_name TEXT;

    ALTER TABLE credit_transactions
        ADD COLUMN IF NOT EXISTS razorpay_order_id TEXT;

    ALTER TABLE credit_transactions
        ADD COLUMN IF NOT EXISTS plan_id TEXT;

    ALTER TABLE pending_orders
        ADD COLUMN IF NOT EXISTS customer_name TEXT;
    """


def init_db():
    """Create tables if they do not already exist. Safe to call on startup."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(schema_sql())
            conn.commit()
    finally:
        conn.close()


def normalize_identifier(identifier: str) -> str:
    """Normalize email/phone identifiers for consistent lookup."""
    return identifier.strip().lower()


def normalize_customer_name(customer_name: Optional[str]) -> Optional[str]:
    """Keep names searchable while avoiding empty strings in the database."""
    if customer_name is None:
        return None
    cleaned = " ".join(customer_name.strip().split())
    return cleaned or None


def is_valid_identifier(identifier: str) -> bool:
    """
    Basic plausibility check for an email or phone number.
    Not strict validation — just enough to catch obvious garbage.
    """
    s = identifier.strip()
    if len(s) < 5:
        return False

    # Email: something@something.something
    if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", s):
        return True

    # Phone: digits, optionally starting with +, with at least 7 digits.
    digits = re.sub(r"\D", "", s)
    if len(digits) >= 7:
        return True

    return False


def now_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# --- USER LEDGER HELPERS ---

def get_or_create_user(identifier: str, customer_name: Optional[str] = None):
    """
    Look up a user by identifier, creating a row with defaults if none exists.
    Returns a dict-like RealDictRow.
    """
    normalized = normalize_identifier(identifier)
    normalized_name = normalize_customer_name(customer_name)
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM users WHERE identifier = %s FOR UPDATE",
                (normalized,),
            )
            user = cur.fetchone()
            if user is None:
                cur.execute(
                    """
                    INSERT INTO users
                        (identifier, customer_name, free_credit_used, credits_remaining,
                         credits_purchased_total, created_at, updated_at)
                    VALUES
                        (%s, %s, FALSE, 0, 0, NOW(), NOW())
                    ON CONFLICT (identifier) DO NOTHING
                    RETURNING *
                    """,
                    (normalized, normalized_name),
                )
                user = cur.fetchone()
                # If another request created the row between SELECT and INSERT,
                # fetch it now.
                if user is None:
                    cur.execute(
                        "SELECT * FROM users WHERE identifier = %s",
                        (normalized,),
                    )
                    user = cur.fetchone()
            elif normalized_name and user.get("customer_name") != normalized_name:
                cur.execute(
                    """
                    UPDATE users
                    SET customer_name = %s,
                        updated_at = NOW()
                    WHERE identifier = %s
                    RETURNING *
                    """,
                    (normalized_name, normalized),
                )
                user = cur.fetchone()
            conn.commit()
            return user
    finally:
        conn.close()


def has_available_credit(identifier: str) -> bool:
    """Return True if the user still has their free question or paid credits."""
    user = get_or_create_user(identifier)
    if not user:
        return False
    return (not user["free_credit_used"]) or (user["credits_remaining"] > 0)


def create_pending_order(
    order_id: str,
    identifier: str,
    plan_id: str,
    credits: int,
    customer_name: Optional[str] = None,
):
    """Record a Razorpay order that has been created but not yet paid."""
    normalized = normalize_identifier(identifier)
    normalized_name = normalize_customer_name(customer_name)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pending_orders
                    (order_id, identifier, customer_name, plan_id, credits, status, created_at)
                VALUES
                    (%s, %s, %s, %s, %s, 'created', NOW())
                ON CONFLICT (order_id) DO NOTHING
                """,
                (order_id, normalized, normalized_name, plan_id, credits),
            )
            conn.commit()
    finally:
        conn.close()


def get_pending_order(order_id: str):
    """Fetch a pending order by Razorpay order id."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM pending_orders WHERE order_id = %s", (order_id,)
            )
            return cur.fetchone()
    finally:
        conn.close()


def find_transaction_by_payment_id(razorpay_payment_id: str):
    """Check whether a payment has already been credited (idempotency)."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id FROM credit_transactions WHERE razorpay_payment_id = %s",
                (razorpay_payment_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def count_recent_events(key: str, event_type: str, window_seconds: int) -> int:
    """Count how many rate-limit events occurred for a key within the last window."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM rate_limit_events
                WHERE key = %s
                  AND event_type = %s
                  AND occurred_at >= NOW() - INTERVAL '1 second' * %s
                """,
                (key, event_type, window_seconds),
            )
            row = cur.fetchone()
            return row[0] if row else 0
    finally:
        conn.close()


def record_rate_limit_event(key: str, event_type: str):
    """Record a rate-limitable event in the database."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rate_limit_events (key, event_type, occurred_at)
                VALUES (%s, %s, NOW())
                """,
                (key, event_type),
            )
            conn.commit()
    finally:
        conn.close()


def cleanup_old_rate_limit_events(max_age_seconds: int = 86400):
    """Remove rate-limit events older than the given window to keep the table small."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM rate_limit_events
                WHERE occurred_at < NOW() - INTERVAL '1 second' * %s
                """,
                (max_age_seconds,),
            )
            conn.commit()
    finally:
        conn.close()


def grant_purchase_credits(
    identifier: str,
    credits: int,
    razorpay_payment_id: str,
    order_id: str,
) -> dict:
    """
    Idempotently grant purchased credits in a single DB transaction.
    Updates the user's balance, records the purchase transaction, and marks
    the pending order as completed.
    """
    normalized = normalize_identifier(identifier)
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Ensure user exists and lock the row.
            cur.execute(
                "SELECT * FROM users WHERE identifier = %s FOR UPDATE",
                (normalized,),
            )
            user = cur.fetchone()
            if user is None:
                cur.execute(
                    """
                    INSERT INTO users
                        (identifier, free_credit_used, credits_remaining,
                         credits_purchased_total, created_at, updated_at)
                    VALUES
                        (%s, FALSE, 0, 0, NOW(), NOW())
                    RETURNING *
                    """,
                    (normalized,),
                )
                user = cur.fetchone()
            if not user:
                raise RuntimeError("User record not found in record_purchase")

            # Idempotency check inside the transaction as well.
            cur.execute(
                "SELECT id FROM credit_transactions WHERE razorpay_payment_id = %s",
                (razorpay_payment_id,),
            )
            if cur.fetchone() is not None:
                conn.commit()
                return {"already_processed": True, "credits_remaining": user["credits_remaining"]}

            new_remaining = user["credits_remaining"] + credits
            new_purchased = user["credits_purchased_total"] + credits
            cur.execute(
                "SELECT plan_id, customer_name FROM pending_orders WHERE order_id = %s",
                (order_id,),
            )
            pending_order = cur.fetchone()
            plan_id = pending_order["plan_id"] if pending_order else None
            order_customer_name = (
                normalize_customer_name(pending_order["customer_name"])
                if pending_order
                else None
            )
            if order_customer_name and user.get("customer_name") != order_customer_name:
                cur.execute(
                    """
                    UPDATE users
                    SET customer_name = %s,
                        updated_at = NOW()
                    WHERE identifier = %s
                    """,
                    (order_customer_name, normalized),
                )

            cur.execute(
                """
                UPDATE users
                SET credits_remaining = %s,
                    credits_purchased_total = %s,
                    updated_at = NOW()
                WHERE identifier = %s
                """,
                (new_remaining, new_purchased, normalized),
            )
            cur.execute(
                """
                INSERT INTO credit_transactions
                    (identifier, type, credits_delta, razorpay_payment_id,
                     razorpay_order_id, plan_id)
                VALUES
                    (%s, 'purchase', %s, %s, %s, %s)
                """,
                (normalized, credits, razorpay_payment_id, order_id, plan_id),
            )
            cur.execute(
                """
                UPDATE pending_orders
                SET status = 'completed'
                WHERE order_id = %s
                """,
                (order_id,),
            )
            conn.commit()
            return {
                "already_processed": False,
                "credits_remaining": new_remaining,
                "credits_purchased_total": new_purchased,
            }
    finally:
        conn.close()


def consume_credit(identifier: str) -> dict:
    """
    Consume one credit from the user's ledger in a single transaction.

    - If free_credit_used is False: mark it True and record a consumption
      transaction with credits_delta=0 (free question, paid balance untouched).
    - Else: decrement credits_remaining by 1 and record credits_delta=-1.

    Raises RuntimeError if no credit is available. Callers should check
    has_available_credit() first; this function is a safety net against races.
    """
    normalized = normalize_identifier(identifier)
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM users WHERE identifier = %s FOR UPDATE",
                (normalized,),
            )
            user = cur.fetchone()

            if user is None:
                # Create the user row first, then consume the free credit.
                cur.execute(
                    """
                    INSERT INTO users
                        (identifier, free_credit_used, credits_remaining,
                         credits_purchased_total, created_at, updated_at)
                    VALUES
                        (%s, FALSE, 0, 0, NOW(), NOW())
                    RETURNING *
                    """,
                    (normalized,),
                )
                user = cur.fetchone()
            if not user:
                raise RuntimeError("User record not found in consume_credit")

            if not user["free_credit_used"]:
                cur.execute(
                    """
                    UPDATE users
                    SET free_credit_used = TRUE,
                        updated_at = NOW()
                    WHERE identifier = %s
                    """,
                    (normalized,),
                )
                cur.execute(
                    """
                    INSERT INTO credit_transactions
                        (identifier, type, credits_delta, razorpay_payment_id)
                    VALUES
                        (%s, 'consumption', 0, NULL)
                    """,
                    (normalized,),
                )
                result = {"used_free": True, "credits_remaining": user["credits_remaining"]}
            elif user["credits_remaining"] > 0:
                new_balance = user["credits_remaining"] - 1
                cur.execute(
                    """
                    UPDATE users
                    SET credits_remaining = %s,
                        updated_at = NOW()
                    WHERE identifier = %s
                    """,
                    (new_balance, normalized),
                )
                cur.execute(
                    """
                    INSERT INTO credit_transactions
                        (identifier, type, credits_delta, razorpay_payment_id)
                    VALUES
                        (%s, 'consumption', -1, NULL)
                    """,
                    (normalized,),
                )
                result = {"used_free": False, "credits_remaining": new_balance}
            else:
                conn.rollback()
                raise RuntimeError(
                    "No available credit: free question already used and "
                    "paid credit balance is zero."
                )

            conn.commit()
            return result
    finally:
        conn.close()


def consume_credit_and_save_reading(
    identifier: str,
    chart_id: str,
    question: str,
    answer: str,
    workflow: Optional[str] = None,
    customer_name: Optional[str] = None,
) -> dict:
    """
    Atomically consume one available credit and persist the completed reading.

    This keeps support/refund records consistent: if the transaction commits, the
    user was charged and the answer is stored; if anything fails, neither happens.
    """
    if not identifier or not chart_id or not question or not answer:
        return {"ok": False, "error": "Missing required reading fields"}

    normalized = normalize_identifier(identifier)
    normalized_name = normalize_customer_name(customer_name)
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM users WHERE identifier = %s FOR UPDATE",
                (normalized,),
            )
            user = cur.fetchone()

            if user is None:
                cur.execute(
                    """
                    INSERT INTO users
                        (identifier, customer_name, free_credit_used, credits_remaining,
                         credits_purchased_total, created_at, updated_at)
                    VALUES
                        (%s, %s, FALSE, 0, 0, NOW(), NOW())
                    RETURNING *
                    """,
                    (normalized, normalized_name),
                )
                user = cur.fetchone()
            elif normalized_name and user.get("customer_name") != normalized_name:
                cur.execute(
                    """
                    UPDATE users
                    SET customer_name = %s,
                        updated_at = NOW()
                    WHERE identifier = %s
                    RETURNING *
                    """,
                    (normalized_name, normalized),
                )
                user = cur.fetchone()
            if not user:
                raise RuntimeError("User record not found in consume_credit_and_save_reading")

            if not user["free_credit_used"]:
                cur.execute(
                    """
                    UPDATE users
                    SET free_credit_used = TRUE,
                        updated_at = NOW()
                    WHERE identifier = %s
                    """,
                    (normalized,),
                )
                cur.execute(
                    """
                    INSERT INTO credit_transactions
                        (identifier, type, credits_delta, razorpay_payment_id)
                    VALUES
                        (%s, 'consumption', 0, NULL)
                    """,
                    (normalized,),
                )
                credit_result = {
                    "used_free": True,
                    "credits_remaining": user["credits_remaining"],
                }
            elif user["credits_remaining"] > 0:
                new_balance = user["credits_remaining"] - 1
                cur.execute(
                    """
                    UPDATE users
                    SET credits_remaining = %s,
                        updated_at = NOW()
                    WHERE identifier = %s
                    """,
                    (new_balance, normalized),
                )
                cur.execute(
                    """
                    INSERT INTO credit_transactions
                        (identifier, type, credits_delta, razorpay_payment_id)
                    VALUES
                        (%s, 'consumption', -1, NULL)
                    """,
                    (normalized,),
                )
                credit_result = {"used_free": False, "credits_remaining": new_balance}
            else:
                conn.rollback()
                return {"ok": False, "error": "No available credit"}

            cur.execute(
                """
                INSERT INTO readings
                    (identifier, customer_name, chart_id, question, answer, workflow, created_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, NOW())
                RETURNING *
                """,
                (normalized, normalized_name, chart_id, question, answer, workflow),
            )
            reading = cur.fetchone()
            conn.commit()
            return {"ok": True, "credit": credit_result, "reading": reading}
    except Exception as exc:
        conn.rollback()
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


# --- LEGACY COMPATIBILITY HELPERS (kept for any external callers) ---

def add_user(email: str):
    """Legacy helper: ensure a user row exists for an email identifier."""
    get_or_create_user(email)


def get_user(email: str):
    """Legacy helper: fetch a user row by email identifier."""
    normalized = normalize_identifier(email)
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM users WHERE identifier = %s", (normalized,)
            )
            return cur.fetchone()
    finally:
        conn.close()


def update_user_credits(email: str, purchased: int = 0, used: int = 0):
    """Legacy helper: adjust purchased/used totals (best-effort)."""
    normalized = normalize_identifier(email)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET credits_purchased_total = credits_purchased_total + %s,
                    credits_remaining = GREATEST(credits_remaining - %s, 0),
                    updated_at = NOW()
                WHERE identifier = %s
                """,
                (purchased, used, normalized),
            )
            conn.commit()
    finally:
        conn.close()


def get_paid_remaining(email: str) -> int:
    """Legacy helper: return remaining paid credits for an email identifier."""
    user = get_user(email)
    if not user:
        return 0
    return max(0, user["credits_remaining"])


def deduct_paid_credit(email: str) -> bool:
    """Legacy helper: deduct one paid credit if available."""
    normalized = normalize_identifier(email)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET credits_remaining = credits_remaining - 1,
                    updated_at = NOW()
                WHERE identifier = %s AND credits_remaining > 0
                """,
                (normalized,),
            )
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


# --- READING HISTORY HELPERS ---

def save_reading(
    identifier: str,
    chart_id: str,
    question: str,
    answer: str,
    workflow: Optional[str] = None,
    customer_name: Optional[str] = None,
) -> dict:
    """
    Persist a completed reading. Returns the created row as a dict.
    Does not raise on DB failure; returns {"ok": False, "error": ...} so the
    UI can log the issue without breaking the user experience.
    """
    if not identifier or not chart_id or not question or not answer:
        return {"ok": False, "error": "Missing required reading fields"}

    normalized = normalize_identifier(identifier)
    normalized_name = normalize_customer_name(customer_name)
    try:
        conn = get_connection()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO users
                    (identifier, customer_name, free_credit_used, credits_remaining,
                     credits_purchased_total, created_at, updated_at)
                VALUES
                    (%s, %s, FALSE, 0, 0, NOW(), NOW())
                ON CONFLICT (identifier) DO UPDATE
                SET customer_name = COALESCE(EXCLUDED.customer_name, users.customer_name),
                    updated_at = NOW()
                """,
                (normalized, normalized_name),
            )
            cur.execute(
                """
                INSERT INTO readings
                    (identifier, customer_name, chart_id, question, answer, workflow, created_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, NOW())
                RETURNING *
                """,
                (normalized, normalized_name, chart_id, question, answer, workflow),
            )
            row = cur.fetchone()
            conn.commit()
            return {"ok": True, "reading": row}
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return {"ok": False, "error": str(exc)}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_readings(identifier: str, limit: int = 50, offset: int = 0):
    """
    Return a list of recent readings for an identifier, newest first.
    """
    normalized = normalize_identifier(identifier)
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, chart_id, question, answer, workflow, created_at
                FROM readings
                WHERE identifier = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (normalized, limit, offset),
            )
            return cur.fetchall()
    finally:
        conn.close()


def get_reading_by_id(identifier: str, reading_id: int):
    """Fetch a single reading by id, verifying it belongs to the identifier."""
    normalized = normalize_identifier(identifier)
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, chart_id, question, answer, workflow, created_at
                FROM readings
                WHERE id = %s AND identifier = %s
                """,
                (reading_id, normalized),
            )
            return cur.fetchone()
    finally:
        conn.close()


def get_all_recent_readings(limit: int = 100, offset: int = 0):
    """
    Return a list of recent readings across all users/guests, newest first.
    Used for administrative review and prompt tuning.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, identifier, customer_name, chart_id, question, answer, workflow, created_at
                FROM readings
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = cur.fetchall()
            # Convert datetime objects to string for JSON serialization
            for r in rows:
                if r.get("created_at") and hasattr(r["created_at"], "isoformat"):
                    r["created_at"] = r["created_at"].isoformat()
            return rows
    finally:
        conn.close()


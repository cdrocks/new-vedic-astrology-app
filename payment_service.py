"""
Standalone FastAPI service for Razorpay order creation and webhooks.

This service runs as a second process on Railway (e.g. on port 8000) so that
Streamlit does not have to serve arbitrary API routes.

Environment variables required:
- RAZORPAY_KEY_ID            (public, returned to frontend)
- RAZORPAY_KEY_SECRET        (server-side only, never exposed)
- RAZORPAY_WEBHOOK_SECRET    (server-side only, used to verify webhook signatures)
- HANDOFF_TOKEN_SECRET       (server-side only, used to sign return-to-app tokens)
- DATABASE_URL               (or SUPABASE_DB_URL fallback in db.py)
- WORDPRESS_DOMAIN           (e.g. https://eighthouse.in — used for CORS)
- PORT                       (optional, defaults to 8000)
- ADMIN_API_KEY              (server-side only, for the reconciliation endpoint)
"""

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import razorpay
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from db import (
    init_db,
    is_valid_identifier,
    create_pending_order,
    get_pending_order,
    find_transaction_by_payment_id,
    grant_purchase_credits,
    count_recent_events,
    record_rate_limit_event,
    cleanup_old_rate_limit_events,
)
from handoff_token import generate_handoff_token

# Configure logging. We never log the webhook secret or full raw payloads.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("payment_service")


# --- CONFIGURATION ---

PLANS = {
    "plan_a": {"amount_inr": 199, "credits": 3},
    "plan_b": {"amount_inr": 299, "credits": 5},
    "plan_c": {"amount_inr": 449, "credits": 8},
}

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
HANDOFF_TOKEN_SECRET = os.getenv("HANDOFF_TOKEN_SECRET", "")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

# WordPress domain for CORS. The user will set this in Railway.
WORDPRESS_DOMAIN = os.getenv("WORDPRESS_DOMAIN", "")

# Rate limit configuration (configurable via env vars).
_ORDER_LIMIT_PER_IDENTIFIER = int(
    os.getenv("ORDER_LIMIT_PER_IDENTIFIER_PER_HOUR", "10")
)
_ORDER_LIMIT_PER_IP = int(os.getenv("ORDER_LIMIT_PER_IP_PER_HOUR", "20"))
_ORDER_RATE_LIMIT_WINDOW_SECONDS = int(
    os.getenv("ORDER_RATE_LIMIT_WINDOW_SECONDS", "3600")
)


def _hash_identifier(identifier: str) -> str:
    """Return a short one-way hash of an identifier for logging without PII."""
    return hashlib.sha256(identifier.lower().strip().encode("utf-8")).hexdigest()[:16]


def _get_client_ip(request: Request) -> str:
    """Extract the client IP, respecting Railway's X-Forwarded-For header."""
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.headers.get(
        "X-Real-Ip", request.client.host if request.client else "unknown"
    )


def _is_rate_limited(key: str, event_type: str, limit: int) -> bool:
    """Check whether a key has exceeded its DB-backed rate limit.

    If the database is unreachable, fail open so a temporary DB outage does
    not block order creation with an unhandled 500 error.
    """
    if not key or key == "unknown":
        return False
    try:
        recent = count_recent_events(
            key, event_type, _ORDER_RATE_LIMIT_WINDOW_SECONDS
        )
        return recent >= limit
    except Exception:
        # Fail open on DB errors; the real correctness gate is the payment
        # provider and idempotent credit granting.
        return False


def _record_order_request(key: str, event_type: str):
    """Record an order-creation attempt for rate limiting."""
    if not key or key == "unknown":
        return
    try:
        record_rate_limit_event(key, event_type)
    except Exception:
        # Don't block order creation if rate-limit logging fails.
        pass


def _get_razorpay_client() -> razorpay.Client:
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Razorpay credentials are not configured on the server.",
        )
    return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


# --- FASTAPI APP ---

app = FastAPI(title="Vedic Astrology Payment Service")

# Initialize DB tables on startup.
@app.on_event("startup")
def startup():
    init_db()
    cleanup_old_rate_limit_events(max_age_seconds=86400)


# CORS: allow only the configured WordPress domain.
# If WORDPRESS_DOMAIN is not set, the endpoint still works but no cross-origin
# browser requests will succeed, which is safer than allowing all origins.
allowed_origins = []
if WORDPRESS_DOMAIN:
    allowed_origins.append(WORDPRESS_DOMAIN.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)


# --- REQUEST/RESPONSE MODELS ---

class CreateOrderRequest(BaseModel):
    plan_id: str = Field(..., min_length=1)
    identifier: str = Field(..., min_length=1)


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int  # amount in INR (rupees), not paise
    currency: str
    key_id: str
    handoff_token: str


class ReconcileRequest(BaseModel):
    order_id: str = Field(..., min_length=1)


class ReconcileResponse(BaseModel):
    order_id: str
    status: str
    payment_id: Optional[str] = None
    credited: bool
    credits: Optional[int] = None


# --- ENDPOINTS ---

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/create-order", response_model=CreateOrderResponse)
def create_order(payload: CreateOrderRequest, request: Request):
    # 1. Validate plan
    plan = PLANS.get(payload.plan_id)
    if plan is None:
        raise HTTPException(status_code=400, detail="Invalid plan_id.")

    # 2. Validate identifier
    identifier = payload.identifier.strip()
    if not identifier or not is_valid_identifier(identifier):
        raise HTTPException(
            status_code=400, detail="Invalid identifier. Provide a valid email or phone number."
        )

    # 3. Rate limit by identifier and by IP
    normalized_id = identifier.lower()
    client_ip = _get_client_ip(request)

    if _is_rate_limited(
        normalized_id, "order_creation_identifier", _ORDER_LIMIT_PER_IDENTIFIER
    ):
        raise HTTPException(
            status_code=429,
            detail="You've made several requests recently — please wait a bit and try again.",
        )
    if _is_rate_limited(client_ip, "order_creation_ip", _ORDER_LIMIT_PER_IP):
        raise HTTPException(
            status_code=429,
            detail="You've made several requests recently — please wait a bit and try again.",
        )

    # 4. Create Razorpay order
    amount_inr = plan["amount_inr"]
    credits = plan["credits"]
    client = _get_razorpay_client()

    try:
        razorpay_order = client.order.create(
            {
                "amount": amount_inr * 100,  # Razorpay expects paise
                "currency": "INR",
                "notes": {
                    "identifier": identifier,
                    "plan_id": payload.plan_id,
                },
            }
        )
    except Exception as exc:
        # Log the exception class/message but never the secret key.
        raise HTTPException(
            status_code=502,
            detail=f"Razorpay order creation failed: {type(exc).__name__}",
        )

    order_id = razorpay_order.get("id")
    if not order_id:
        raise HTTPException(
            status_code=502, detail="Razorpay did not return an order id."
        )

    # 5. Persist pending order so the webhook can credit the user later
    try:
        create_pending_order(order_id, identifier, payload.plan_id, credits)
    except Exception:
        # If DB write fails, do not leak the Razorpay order to the user because
        # the webhook would not be able to fulfill it. Surface a generic error.
        raise HTTPException(
            status_code=500,
            detail="Order created at gateway but could not be recorded. Please retry.",
        )

    # Record rate-limit events only after a successful order creation.
    _record_order_request(normalized_id, "order_creation_identifier")
    _record_order_request(client_ip, "order_creation_ip")

    # Generate a signed token so WordPress can send the user back to the app
    # with a verifiable identifier. This is a convenience token only.
    handoff_token = generate_handoff_token(identifier)

    return CreateOrderResponse(
        order_id=order_id,
        amount=amount_inr,
        currency="INR",
        key_id=RAZORPAY_KEY_ID,
        handoff_token=handoff_token,
    )


@app.post("/razorpay-webhook")
async def razorpay_webhook(request: Request, x_razorpay_signature: str = Header(default="")):
    """
    Razorpay webhook handler for payment.captured events.
    Signature verification is mandatory before any credit is granted.
    """
    raw_body = await request.body()

    logger.info(
        "Webhook received",
        extra={
            "signature_present": bool(x_razorpay_signature),
            "body_length": len(raw_body),
        },
    )

    if not RAZORPAY_WEBHOOK_SECRET:
        logger.error("RAZORPAY_WEBHOOK_SECRET is not configured")
        raise HTTPException(status_code=500, detail="Webhook secret not configured.")

    # Verify signature: HMAC-SHA256 of raw body with webhook secret.
    computed_signature = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed_signature, x_razorpay_signature):
        logger.warning("Webhook signature verification failed")
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.warning("Webhook payload is not valid JSON")
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    event = payload.get("event", "")
    logger.info("Webhook verified", extra={"event": event})

    # We only act on payment.captured. Other events are acknowledged but ignored.
    if event != "payment.captured":
        return JSONResponse({"status": "ignored", "event": event})

    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    razorpay_order_id = payment_entity.get("order_id")
    razorpay_payment_id = payment_entity.get("id")
    payment_status = payment_entity.get("status")

    if not razorpay_order_id or not razorpay_payment_id:
        logger.warning("Webhook missing order_id or payment_id")
        raise HTTPException(status_code=400, detail="Missing order_id or payment_id.")

    logger.info(
        "Processing payment.captured",
        extra={
            "order_id": razorpay_order_id,
            "payment_id": razorpay_payment_id,
            "payment_status": payment_status,
        },
    )

    # Look up the pending order created by /create-order.
    pending_order = get_pending_order(razorpay_order_id)
    if not pending_order:
        logger.warning(
            "Pending order not found for webhook",
            extra={"order_id": razorpay_order_id},
        )
        # Return 200 so Razorpay stops retrying; manual reconciliation can fix this.
        return JSONResponse({"status": "pending_order_not_found"})

    if pending_order["status"] == "completed":
        logger.info(
            "Pending order already completed",
            extra={"order_id": razorpay_order_id},
        )
        return JSONResponse({"status": "already_completed"})

    # Idempotency: check if this payment_id was already credited.
    existing_txn = find_transaction_by_payment_id(razorpay_payment_id)
    if existing_txn:
        logger.info(
            "Payment already credited",
            extra={"payment_id": razorpay_payment_id},
        )
        return JSONResponse({"status": "already_credited"})

    # Grant credits atomically.
    try:
        result = grant_purchase_credits(
            identifier=pending_order["identifier"],
            credits=pending_order["credits"],
            razorpay_payment_id=razorpay_payment_id,
            order_id=razorpay_order_id,
        )
    except Exception as exc:
        logger.exception("Failed to grant purchase credits")
        raise HTTPException(status_code=500, detail="Failed to grant credits.")

    logger.info(
        "Credits granted",
        extra={
            "order_id": razorpay_order_id,
            "payment_id": razorpay_payment_id,
            "identifier_hash": _hash_identifier(pending_order["identifier"]),
            "credits": pending_order["credits"],
            "already_processed": result.get("already_processed", False),
        },
    )

    return JSONResponse({"status": "credited"})


@app.post("/admin/reconcile", response_model=ReconcileResponse)
def reconcile_order(payload: ReconcileRequest, x_admin_key: str = Header(default="")):
    """
    Admin-only fallback: query Razorpay directly for an order's payment status
    and credit the user if a completed payment exists but the webhook was missed.
    Protected by ADMIN_API_KEY.
    """
    if not ADMIN_API_KEY or not hmac.compare_digest(x_admin_key, ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized.")

    client = _get_razorpay_client()
    order_id = payload.order_id

    try:
        order = client.order.fetch(order_id)
    except Exception as exc:
        logger.exception("Admin reconcile: failed to fetch order")
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch order from Razorpay: {type(exc).__name__}",
        )

    pending_order = get_pending_order(order_id)
    if not pending_order:
        raise HTTPException(status_code=404, detail="Order not found in local database.")

    # Razorpay order status: created, attempted, paid.
    order_status = order.get("status", "unknown")
    if order_status != "paid":
        return ReconcileResponse(
            order_id=order_id,
            status=order_status,
            credited=False,
            credits=None,
        )

    # Find the payment_id associated with this order.
    payments = client.order.fetch_payments(order_id)
    captured_payment = None
    for payment in payments.get("items", []):
        if payment.get("status") == "captured":
            captured_payment = payment
            break

    if not captured_payment:
        return ReconcileResponse(
            order_id=order_id,
            status=order_status,
            credited=False,
            credits=None,
        )

    payment_id = captured_payment["id"]

    # Idempotency check.
    if find_transaction_by_payment_id(payment_id):
        return ReconcileResponse(
            order_id=order_id,
            status=order_status,
            payment_id=payment_id,
            credited=True,
            credits=pending_order["credits"],
        )

    # Grant credits.
    try:
        grant_purchase_credits(
            identifier=pending_order["identifier"],
            credits=pending_order["credits"],
            razorpay_payment_id=payment_id,
            order_id=order_id,
        )
    except Exception:
        logger.exception("Admin reconcile: failed to grant credits")
        raise HTTPException(status_code=500, detail="Failed to grant credits.")

    return ReconcileResponse(
        order_id=order_id,
        status=order_status,
        payment_id=payment_id,
        credited=True,
        credits=pending_order["credits"],
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("payment_service:app", host="0.0.0.0", port=port)

"""
Shared handoff token utilities for the Streamlit app and the FastAPI payment service.

These tokens are signed with HANDOFF_TOKEN_SECRET and are used only to let the
WordPress pricing page send the user back to the Streamlit app with a verifiable
identifier. They are a convenience/privacy safeguard only — they do NOT grant
credits. Credit granting happens exclusively via Razorpay webhook signature
verification in payment_service.py.

Both the Streamlit process and the FastAPI process run from the same Railway
deployment and read the same HANDOFF_TOKEN_SECRET environment variable.
"""

import os
from typing import Optional

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired


HANDOFF_TOKEN_SECRET = os.getenv("HANDOFF_TOKEN_SECRET", "")

_serializer: Optional[URLSafeTimedSerializer] = None


def _get_serializer() -> URLSafeTimedSerializer:
    global _serializer
    if _serializer is None:
        if not HANDOFF_TOKEN_SECRET:
            raise ValueError(
                "HANDOFF_TOKEN_SECRET environment variable is not set. "
                "Generate a long random string and set it identically for both "
                "the Streamlit app and the FastAPI payment service."
            )
        _serializer = URLSafeTimedSerializer(HANDOFF_TOKEN_SECRET)
    return _serializer


def generate_handoff_token(identifier: str) -> str:
    """Sign an identifier into a short-lived URL-safe token."""
    return _get_serializer().dumps(identifier)


def verify_handoff_token(token: str, max_age_seconds: int = 900) -> Optional[str]:
    """
    Verify a handoff token and return the identifier if valid and not expired.
    Returns None if the token is invalid or expired.
    """
    try:
        return _get_serializer().loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None

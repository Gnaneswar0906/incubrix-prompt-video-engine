"""
IncuBrix HMAC Webhook Utilities
Signs webhook payloads with HMAC-SHA256 in the X-IncuBrix-Signature header.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import urllib.request
from typing import Any, Dict

logger = logging.getLogger("incubrix.webhook")


def compute_hmac_signature(payload_bytes: bytes, secret: str) -> str:
    """
    Computes hex HMAC-SHA256 signature over payload bytes.
    Format: sha256=<hex_digest>
    """
    mac = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


# Alias for compatibility
generate_signature = compute_hmac_signature


def dispatch_webhook(callback_url: str, payload: Dict[str, Any], secret: str) -> bool:
    """
    Sends POST request to callback_url with X-IncuBrix-Signature header.
    Returns True if request delivered successfully, False otherwise.
    """
    payload_json = json.dumps(payload, sort_keys=True)
    payload_bytes = payload_json.encode("utf-8")
    signature = compute_hmac_signature(payload_bytes, secret)

    req = urllib.request.Request(
        callback_url,
        data=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-IncuBrix-Signature": signature,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            logger.info(f"Delivered webhook to {callback_url} with status {resp.status}")
            return resp.status < 400
    except Exception as e:
        logger.warning(f"Failed to dispatch webhook to {callback_url}: {e}")
        return False

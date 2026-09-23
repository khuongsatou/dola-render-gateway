"""Authentication helpers for API clients and live-stream access."""
import hashlib
import hmac
import time


def make_stream_token(admin_key: str, ttl: int = 300, now: float | None = None) -> str:
    """Builds a short-lived token for EventSource URLs, which cannot send headers."""
    if not admin_key:
        return ""
    expires_at = int((time.time() if now is None else now) + max(1, ttl))
    payload = f"dola-stream:{expires_at}"
    signature = hmac.new(
        admin_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{expires_at}.{signature}"


def is_stream_token_valid(
    admin_key: str,
    token: str | None,
    now: float | None = None,
) -> bool:
    """Validates a stream token against the configured admin key and expiry."""
    if not admin_key:
        return True
    if not token or "." not in token:
        return False
    raw_expires, signature = token.split(".", 1)
    try:
        expires_at = int(raw_expires)
    except ValueError:
        return False

    current_time = int(time.time() if now is None else now)
    if expires_at < current_time:
        return False

    payload = f"dola-stream:{expires_at}"
    expected = hmac.new(
        admin_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

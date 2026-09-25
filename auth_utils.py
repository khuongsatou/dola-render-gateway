"""Authentication helpers for API clients and live-stream access."""
import hashlib
import hmac
import time


def _sign(secret: str, payload: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _split_token(token: str | None, now: float | None) -> tuple[int, str] | None:
    if not token or "." not in token:
        return None
    raw_expires, signature = token.split(".", 1)
    try:
        expires_at = int(raw_expires)
    except ValueError:
        return None
    current_time = int(time.time() if now is None else now)
    if expires_at < current_time:
        return None
    return expires_at, signature


def make_signed_token(
    secret: str,
    scope: str,
    resource: str = "",
    ttl: int = 300,
    now: float | None = None,
) -> str:
    """Builds an expiring HMAC token bound to one scope and resource."""
    if not secret:
        return ""
    expires_at = int((time.time() if now is None else now) + max(1, ttl))
    return f"{expires_at}.{_sign(secret, f'{scope}:{expires_at}:{resource}')}"


def is_signed_token_valid(
    secret: str,
    scope: str,
    resource: str = "",
    token: str | None = None,
    now: float | None = None,
) -> bool:
    """Validates an expiring HMAC token against one scope and resource."""
    if not secret:
        return False
    parsed = _split_token(token, now)
    if not parsed:
        return False
    expires_at, signature = parsed
    expected = _sign(secret, f"{scope}:{expires_at}:{resource}")
    return hmac.compare_digest(expected, signature)


def make_media_token(
    secret: str,
    filename: str,
    ttl: int = 3600,
    now: float | None = None,
) -> str:
    """Builds a signed download link token for one stored video file."""
    return make_signed_token(secret, "media", filename, ttl=ttl, now=now)


def is_media_token_valid(
    secret: str,
    filename: str,
    token: str | None,
    now: float | None = None,
) -> bool:
    """Validates a signed download link token for one stored video file."""
    return is_signed_token_valid(secret, "media", filename, token, now=now)


def make_stream_token(admin_key: str, ttl: int = 300, now: float | None = None) -> str:
    """Builds a short-lived token for EventSource URLs, which cannot send headers."""
    if not admin_key:
        return ""
    expires_at = int((time.time() if now is None else now) + max(1, ttl))
    payload = f"dola-stream:{expires_at}"
    signature = _sign(admin_key, payload)
    return f"{expires_at}.{signature}"


def is_stream_token_valid(
    admin_key: str,
    token: str | None,
    now: float | None = None,
) -> bool:
    """Validates a stream token against the configured admin key and expiry."""
    if not admin_key:
        return True
    parsed = _split_token(token, now)
    if not parsed:
        return False
    expires_at, signature = parsed
    payload = f"dola-stream:{expires_at}"
    expected = _sign(admin_key, payload)
    return hmac.compare_digest(expected, signature)

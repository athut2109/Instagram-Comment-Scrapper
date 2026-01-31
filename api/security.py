from fastapi import Header, HTTPException, Request
import os
import time
from typing import Dict

# New: support DB-backed API keys and Redis-backed rate limiter when available
from . import auth as api_auth

_RATE_LIMIT_STORE: Dict[str, list] = {}
RATE_LIMIT = int(os.getenv('POC_RATE_LIMIT', '20'))  # requests per WINDOW
WINDOW = int(os.getenv('POC_RATE_WINDOW', '60'))  # seconds
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')


from fastapi import Header

def get_api_key(x_api_key: str | None = Header(None), authorization: str | None = Header(None)):
    """Resolve/validate the API key.

    Accepts either `X-API-KEY: <token>` or `Authorization: Bearer <token>`.

    Priority:
      1. If env var POC_API_KEY is set, accept only that (backwards compat).
      2. Otherwise, validate against DB stored hashed keys.
      3. If no env var and no header, allow None (dev convenience).
    """
    # Extract token from Authorization if present
    token = x_api_key
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            token = parts[1]

    expected = os.getenv('POC_API_KEY')
    if expected:
        if not token or token != expected:
            raise HTTPException(status_code=401, detail="Invalid or missing API Key")
        return {'token': token, 'is_env_key': True}

    # No env var: if header missing allow development convenience
    if not token:
        return None

    # Lookup in DB
    try:
        rec = api_auth.lookup_key(token)
    except Exception:
        rec = None
    if not rec:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")
    if rec.get('revoked'):
        raise HTTPException(status_code=401, detail="API Key revoked")

    # update last_used asynchronously (best-effort)
    try:
        api_auth.touch_last_used(rec['key_id'])
    except Exception:
        pass

    return rec


def _use_redis_rate_limiter(key: str) -> bool:
    try:
        import redis as _redis
        r = _redis.from_url(REDIS_URL)
        # token-bucket style: use simple counter with expiry = WINDOW. Return True if OK.
        k = f"rate:{key}"
        cur = r.incr(k)
        if cur == 1:
            r.expire(k, WINDOW)
        if cur > RATE_LIMIT:
            return False
        return True
    except Exception:
        return None


def rate_limiter(api_key: str | None, request: Request):
    """Sliding-window limiter: prefer Redis if available, else in-memory."""
    key = None
    if api_key and isinstance(api_key, dict):
        key = api_key.get('key_id') or api_key.get('token')
    else:
        key = api_key or (request.client.host if request and request.client else 'anon')

    # Try Redis-driven limiter
    redis_ok = _use_redis_rate_limiter(key)
    if redis_ok is False:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    if redis_ok is True:
        return True

    # Fallback: in-memory sliding window
    now = time.time()
    timestamps = _RATE_LIMIT_STORE.get(key, [])
    timestamps = [t for t in timestamps if now - t < WINDOW]
    if len(timestamps) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    timestamps.append(now)
    _RATE_LIMIT_STORE[key] = timestamps
    return True

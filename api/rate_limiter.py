"""Redis-backed sliding-window rate limiter helper.

Implements a standard ZSET-based sliding window:
 - ZADD key current_timestamp_ms member
 - ZREMRANGEBYSCORE key 0 (current_timestamp_ms - window_ms)
 - ZCARD key -> number of events in window
 - If > limit -> reject
 - Ensure key has expiry for cleanup

Provides a small wrapper `allow_request(redis_conn, key, limit, window_seconds)` which returns True/False.
"""
import time


def allow_request(redis_conn, key: str, limit: int, window_seconds: int) -> bool:
    """Return True if request allowed, False if rate limit exceeded."""
    if not redis_conn:
        return None

    now_ms = int(time.time() * 1000)
    window_ms = int(window_seconds * 1000)
    min_score = now_ms - window_ms
    zkey = f"rate:{key}"

    # Use a pipeline for atomicity
    pipe = redis_conn.pipeline()
    pipe.zremrangebyscore(zkey, 0, min_score)
    pipe.zcard(zkey)
    pipe.execute()

    # Check count before adding the new request
    count_before = redis_conn.zcard(zkey)
    
    if count_before >= limit:
        return False
    
    # Add the new request to the window
    redis_conn.zadd(zkey, {str(now_ms): now_ms})
    redis_conn.expire(zkey, window_seconds + 1)
    
    return True

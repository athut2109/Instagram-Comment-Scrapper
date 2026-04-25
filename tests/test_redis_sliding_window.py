import fakeredis
import time
from api.rate_limiter import allow_request


def test_sliding_window_allows_until_limit():
    r = fakeredis.FakeRedis()
    key = 'user1'
    limit = 5
    window = 2  # seconds

    # Send `limit` requests -> all allowed
    for i in range(limit):
        result = allow_request(r, key, limit, window)
        assert result is True, f"Request {i+1} should be allowed, got {result}"
        time.sleep(0.01)  # small delay between requests to ensure different timestamps

    # Next one should be rejected (we've hit the limit)
    result = allow_request(r, key, limit, window)
    assert result is False, f"Request {limit+1} (6th) should be rejected, got {result}"

    # Wait for window to expire
    time.sleep(window + 0.1)
    # Now should be allowed again
    result = allow_request(r, key, limit, window)
    assert result is True, f"Request after window expiry should be allowed, got {result}"
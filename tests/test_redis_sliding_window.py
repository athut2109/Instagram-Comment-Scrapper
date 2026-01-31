import fakeredis
import time
from api.rate_limiter import allow_request


def test_sliding_window_allows_until_limit():
    r = fakeredis.FakeRedis()
    key = 'user1'
    limit = 5
    window = 2  # seconds

    # Send `limit` requests -> allowed
    for i in range(limit):
        assert allow_request(r, key, limit, window) is True

    # Next one should be rejected
    assert allow_request(r, key, limit, window) is False

    # Wait for window to expire
    time.sleep(window + 0.1)
    # Now should be allowed again
    assert allow_request(r, key, limit, window) is True
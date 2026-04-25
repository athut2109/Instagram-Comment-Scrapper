import fakeredis
import time
from api import security
from scripts.init_db import main as init_db


def setup_module(module):
    init_db()


def test_redis_rate_limiter(monkeypatch):
    fake_r = fakeredis.FakeRedis()

    def fake_use_redis_rate_limiter(key):
        k = f"rate:{key}"
        cur = fake_r.incr(k)
        if cur == 1:
            fake_r.expire(k, security.WINDOW)
        return cur <= security.RATE_LIMIT

    monkeypatch.setattr(security, '_use_redis_rate_limiter', fake_use_redis_rate_limiter)

    # Use same key repeatedly up to limit
    key = 'test-key'
    for i in range(security.RATE_LIMIT):
        assert security.rate_limiter({'key_id': key}, None) is True

    # Next call should raise 429
    try:
        security.rate_limiter({'key_id': key}, None)
        assert False, 'Expected rate limit to be exceeded'
    except Exception as e:
        assert getattr(e, 'status_code', None) == 429
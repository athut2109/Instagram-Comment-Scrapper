import os
import sqlite3
import time

import redis
import rq

from scripts.init_db import main as init_db
import api.tasks as tasks
import api.adapters as adapters


def setup_module(module):
    init_db()


def test_e2e_enqueue_with_real_redis(monkeypatch):
    # Skip if REDIS not available in environment
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    r = redis.from_url(redis_url)
    try:
        r.ping()
    except Exception:
        import pytest
        pytest.skip('Redis not available')

    # Prepare DB scan
    conn = sqlite3.connect('insta_poc.db')
    cur = conn.cursor()
    cur.execute("INSERT INTO scans (post_url, mode, threshold, scrolls, scroll_delay, status, created_at) VALUES (?,?,?,?,?,?,?)",
                ('https://www.instagram.com/p/E2E123/', 'keyword', 0.7, 10, 100, 'enqueued', '2026-01-01T00:00:00'))
    conn.commit()
    scan_id = cur.lastrowid
    conn.close()

    # Point tasks at real redis
    tasks.redis_conn = r

    # Patch adapters for deterministic output
    def fake_scrape(post_url, max_scrolls=50, scroll_delay=1500):
        return [ {'text': 'bad', 'username': 'u1', 'link': f'{post_url}#1'} ]
    def fake_detect(comments, mode='keyword', threshold=0.7):
        return {'abusive_comments': [{'original': 'bad', 'username': 'u1', 'link': comments[0]['link'], 'matched_words':['bad'], 'confidence':0.9}]}

    monkeypatch.setattr(adapters, 'scrape_post', fake_scrape)
    monkeypatch.setattr(adapters, 'detect_comments', fake_detect)

    q = rq.Queue('default', connection=tasks.redis_conn)
    job = q.enqueue(tasks.process_scan, scan_id)

    # Start a SimpleWorker in-process to process the job
    worker = rq.SimpleWorker([q], connection=tasks.redis_conn)
    worker.work(burst=True)

    # Allow small delay for DB writes
    time.sleep(0.5)

    conn = sqlite3.connect('insta_poc.db')
    cur = conn.cursor()
    cur.execute('SELECT status, result_json FROM scans WHERE id = ?', (scan_id,))
    row = cur.fetchone()
    assert row is not None
    status, result_json = row
    assert status == 'done'
    assert result_json is not None
    conn.close()
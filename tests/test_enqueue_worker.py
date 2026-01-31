import sqlite3
from threading import Thread
import time

import fakeredis
import rq

from scripts.init_db import main as init_db
import api.tasks as tasks
import api.adapters as adapters


def setup_module(module):
    init_db()


def test_enqueue_and_worker_processes_scan(monkeypatch, tmp_path):
    # Prepare DB with a test scan
    conn = sqlite3.connect('insta_poc.db')
    cur = conn.cursor()
    cur.execute("INSERT INTO scans (post_url, mode, threshold, scrolls, scroll_delay, status, created_at) VALUES (?,?,?,?,?,?,?)",
                ('https://www.instagram.com/p/TEST123/', 'keyword', 0.7, 10, 100, 'enqueued', '2026-01-01T00:00:00'))
    conn.commit()
    scan_id = cur.lastrowid
    conn.close()

    # Use fakeredis and monkeypatch tasks.redis_conn
    fake_redis = fakeredis.FakeRedis()
    tasks.redis_conn = fake_redis

    # Patch adapters to deterministic functions
    def fake_scrape(post_url, max_scrolls=50, scroll_delay=1500):
        return [
            {'text': 'You are an idiot', 'username': 'user_1', 'link': f'{post_url}#c1'},
            {'text': 'Nice!', 'username': 'user_2', 'link': f'{post_url}#c2'}
        ]

    def fake_detect(comments, mode='keyword', threshold=0.7):
        return {
            'abusive_comments': [
                {'original': 'You are an idiot', 'username': 'user_1', 'link': comments[0].get('link'), 'matched_words': ['idiot'], 'confidence': 0.9}
            ]
        }

    monkeypatch.setattr(adapters, 'scrape_post', fake_scrape)
    monkeypatch.setattr(adapters, 'detect_comments', fake_detect)

    # Enqueue job
    q = rq.Queue('default', connection=tasks.redis_conn)
    job = q.enqueue(tasks.process_scan, scan_id)

    # Run a SimpleWorker in the background to process the job (burst mode)
    worker = rq.SimpleWorker([q], connection=tasks.redis_conn)

    def run_worker():
        worker.work(burst=True)

    t = Thread(target=run_worker)
    t.start()
    t.join(timeout=10)

    # Check DB for results
    conn = sqlite3.connect('insta_poc.db')
    cur = conn.cursor()
    cur.execute('SELECT status, result_json FROM scans WHERE id = ?', (scan_id,))
    row = cur.fetchone()
    assert row is not None
    status, result_json = row
    assert status == 'done'
    assert result_json is not None

    cur.execute('SELECT id, scan_id, original, username FROM comments WHERE scan_id = ?', (scan_id,))
    comments = cur.fetchall()
    assert len(comments) >= 1
    conn.close()
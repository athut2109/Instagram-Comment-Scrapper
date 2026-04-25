"""Background task implementations using RQ.
"""
import json
import sqlite3
from datetime import datetime
import rq
import redis

import api.adapters as adapters

REDIS_URL = "redis://localhost:6379"
redis_conn = redis.from_url(REDIS_URL)


def enqueue_scan(scan_id: int):
    q = rq.Queue("default", connection=redis_conn)
    job = q.enqueue(process_scan, scan_id)
    return job.get_id()


def process_scan(scan_id: int):
    conn = sqlite3.connect("insta_poc.db")
    try:
        cur = conn.cursor()
        # Mark running
        cur.execute("UPDATE scans SET status = ? WHERE id = ?", ("running", scan_id))
        conn.commit()

        # Load scan params
        cur.execute("SELECT post_url, mode, threshold, scrolls, scroll_delay FROM scans WHERE id = ?", (scan_id,))
        row = cur.fetchone()
        if not row:
            cur.execute("UPDATE scans SET status = ? WHERE id = ?", ("failed", scan_id))
            conn.commit()
            return

        post_url, mode, threshold, scrolls, scroll_delay = row

        # Scrape
        comments = adapters.scrape_post(post_url, max_scrolls=scrolls, scroll_delay=scroll_delay)

        # Detect
        results = adapters.detect_comments(comments, mode=mode, threshold=threshold)

        # Persist results JSON
        timestamp = datetime.utcnow().isoformat()
        results_meta = {
            "scan_id": scan_id,
            "post_url": post_url,
            "mode": mode,
            "timestamp": timestamp,
            "summary": {
                "total_comments": len(comments),
                "abusive_count": len(results.get('abusive_comments', []))
            },
            "abusive_comments": results.get('abusive_comments', [])
        }
        cur.execute("UPDATE scans SET result_json = ?, status = ?, finished_at = ? WHERE id = ?",
                    (json.dumps(results_meta), "done", timestamp, scan_id))

        # Insert comments into comments table
        for item in results.get('abusive_comments', []):
            # item may come from ML detector (dict) or keyword adapter
            original = item.get('original') or item.get('comment') or ''
            username = item.get('username', '')
            link = item.get('link', '')
            matched = item.get('matched_words', [])
            category = item.get('category', '')
            confidence = item.get('confidence', None) or item.get('max_score', None)

            cur.execute(
                "INSERT INTO comments (scan_id, original, normalized, username, link, matched_words, category, confidence) VALUES (?,?,?,?,?,?,?,?)",
                (scan_id, original, '', username, link, json.dumps(matched), category, confidence)
            )

        conn.commit()
    except Exception as e:
        cur.execute("UPDATE scans SET status = ? WHERE id = ?", ("failed", scan_id))
        conn.commit()
        raise
    finally:
        conn.close()

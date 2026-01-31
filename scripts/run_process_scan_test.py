# Run process_scan on a test scan row, with mocked scraper
import sqlite3
from importlib import reload
import api.adapters as adapters
import api.tasks as tasks

# Mock scrape_post to return sample comments
def fake_scrape(post_url, max_scrolls=50, scroll_delay=1500):
    return [
        {"text": "You are an idiot", "username": "user_1", "link": "https://instagram.com/p/ABC123/#c1"},
        {"text": "Nice picture!", "username": "user_2", "link": "https://instagram.com/p/ABC123/#c2"}
    ]

adapters.scrape_post = fake_scrape
# Run the process_scan for scan id 1
tasks.process_scan(1)

# Query DB to show results
conn = sqlite3.connect('insta_poc.db')
cur = conn.cursor()
cur.execute('SELECT id, status, result_json FROM scans WHERE id = 1')
print('SCAN:', cur.fetchone())
cur.execute('SELECT id, scan_id, original, username FROM comments')
print('COMMENTS:', cur.fetchall())
conn.close()

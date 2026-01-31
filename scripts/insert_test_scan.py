import sqlite3

conn = sqlite3.connect('insta_poc.db')
cur = conn.cursor()
cur.execute("INSERT INTO scans (post_url, mode, threshold, scrolls, scroll_delay, status, created_at) VALUES (?,?,?,?,?,?,?)",
            ('https://www.instagram.com/p/ABC123/','keyword',0.7,50,1500,'enqueued','2026-01-30T00:00:00'))
conn.commit()
print('Inserted', cur.lastrowid)
cur.execute('SELECT id,post_url,status FROM scans')
print(cur.fetchall())
conn.close()

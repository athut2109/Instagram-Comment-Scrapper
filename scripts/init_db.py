# scripts/init_db.py
"""Initialize the PoC SQLite DB.

This script prefers SQLAlchemy metadata when available, but falls back to
explicit sqlite3 CREATE TABLE statements so it is safe to run even if
SQLAlchemy import causes issues in the runtime environment.
"""
from datetime import datetime
import sqlite3
import os

DB_PATH = os.getenv('POC_DB_PATH', 'insta_poc.db')

SQL_CREATE = [
    # Scans table (keeps parity with SQLAlchemy models)
    """
    CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_url TEXT NOT NULL,
        mode TEXT DEFAULT 'ml',
        threshold REAL DEFAULT 0.7,
        scrolls INTEGER DEFAULT 50,
        scroll_delay INTEGER DEFAULT 1500,
        status TEXT DEFAULT 'enqueued',
        result_json TEXT,
        created_at TEXT,
        finished_at TEXT
    )
    """,

    # Comments table
    """
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id INTEGER,
        original TEXT,
        normalized TEXT,
        username TEXT,
        link TEXT,
        matched_words TEXT,
        category TEXT,
        confidence REAL
    )
    """,

    # API keys table for DB-backed keys
    """
    CREATE TABLE IF NOT EXISTS api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_id TEXT UNIQUE,
        key_prefix TEXT,
        key_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        iterations INTEGER NOT NULL,
        scopes TEXT,
        description TEXT,
        created_at TEXT,
        last_used TEXT,
        revoked INTEGER DEFAULT 0,
        expires_at TEXT
    )
    """,
]


def main():
    # Try SQLAlchemy first when available (keeps previous behaviour where it worked)
    try:
        from api.database import engine, Base  # type: ignore
        import api.models  # noqa: F401
        Base.metadata.create_all(bind=engine)
        print("Initialized DB via SQLAlchemy metadata.")
        return
    except Exception:
        # Fall back to sqlite3 DDL
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            for s in SQL_CREATE:
                cur.execute(s)
            conn.commit()
            print(f"Initialized DB at {DB_PATH} (sqlite3 fallback)")
        finally:
            conn.close()


if __name__ == '__main__':
    main()

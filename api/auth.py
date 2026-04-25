"""API Key helpers: generation, hashing, verification, and DB operations.

Uses PBKDF2-HMAC-SHA256 with a per-key salt and configurable iterations.
Stores only the hash and salt in the DB; plaintext token is returned to the caller
only once at creation time.
"""
import os
import sqlite3
import secrets
import hashlib
import base64
import uuid
from datetime import datetime
from typing import Optional, Dict

DB_PATH = os.getenv('POC_DB_PATH', 'insta_poc.db')
PBKDF2_ITERS = int(os.getenv('API_KEY_PBKDF2_ITER', '100000'))


def _hash_token(token: str, salt: Optional[str] = None, iterations: int = PBKDF2_ITERS):
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', token.encode('utf-8'), salt.encode('utf-8'), iterations)
    return base64.b64encode(dk).decode('ascii'), salt, iterations


def _row_to_dict(row) -> Dict:
    return {
        'id': row[0],
        'key_id': row[1],
        'key_prefix': row[2],
        'scopes': row[6] or '',
        'description': row[7],
        'created_at': row[8],
        'last_used': row[9],
        'revoked': bool(row[10]),
        'expires_at': row[11]
    }


def create_key(scopes: str = 'read,write', description: Optional[str] = None, expires_at: Optional[str] = None) -> Dict:
    """Create a new API key record and return the plaintext token and metadata.

    Returns: {'key_id': ..., 'token': ..., 'scopes': ..., 'description': ...}
    """
    token = secrets.token_urlsafe(32)
    key_id = uuid.uuid4().hex
    key_prefix = token[:8]
    key_hash, salt, iterations = _hash_token(token)
    created_at = datetime.utcnow().isoformat()

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO api_keys (key_id, key_prefix, key_hash, salt, iterations, scopes, description, created_at, revoked, expires_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (key_id, key_prefix, key_hash, salt, iterations, scopes, description, created_at, 0, expires_at)
        )
        conn.commit()
    finally:
        conn.close()

    return {'key_id': key_id, 'token': token, 'scopes': scopes, 'description': description, 'created_at': created_at}


def lookup_key(token: str) -> Optional[Dict]:
    """Try to find a DB API key record that matches the provided token.

    Uses the key_prefix to narrow candidates then verifies the PBKDF2 hash.
    """
    if not token:
        return None
    prefix = token[:8]
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id,key_id,key_prefix,key_hash,salt,iterations,scopes,description,created_at,last_used,revoked,expires_at FROM api_keys WHERE key_prefix = ?", (prefix,))
        rows = cur.fetchall()
        for row in rows:
            key_hash = row[3]
            salt = row[4]
            iterations = int(row[5] or PBKDF2_ITERS)
            dk = hashlib.pbkdf2_hmac('sha256', token.encode('utf-8'), salt.encode('utf-8'), iterations)
            candidate_hash = base64.b64encode(dk).decode('ascii')
            if secrets.compare_digest(candidate_hash, key_hash):
                return _row_to_dict(row)
        return None
    finally:
        conn.close()


def list_keys() -> list:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id,key_id,key_prefix,key_hash,salt,iterations,scopes,description,created_at,last_used,revoked,expires_at FROM api_keys ORDER BY id DESC")
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def revoke_key(key_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("UPDATE api_keys SET revoked = 1 WHERE key_id = ?", (key_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def touch_last_used(key_id: str):
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("UPDATE api_keys SET last_used = ? WHERE key_id = ?", (datetime.utcnow().isoformat(), key_id))
        conn.commit()
    finally:
        conn.close()
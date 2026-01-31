import os
import sqlite3
from api import auth
from scripts.init_db import main as init_db
from fastapi.testclient import TestClient
from api.app import app


def setup_module(module):
    # Ensure DB exists and tables created
    init_db()


def test_create_and_lookup_key():
    rec = auth.create_key(scopes='admin', description='test admin')
    assert 'token' in rec and 'key_id' in rec

    lookup = auth.lookup_key(rec['token'])
    assert lookup is not None
    assert lookup['key_id'] == rec['key_id']


def test_admin_endpoints_flow():
    # Create bootstrap admin key
    admin = auth.create_key(scopes='admin', description='test admin endpoint')
    client = TestClient(app)

    headers = { 'X-API-KEY': admin['token'] }

    # Create a new key via admin endpoint
    r = client.post('/admin/keys', headers=headers, json={'scopes':'read,write','description':'test created key'})
    assert r.status_code == 200
    body = r.json()
    assert 'token' in body and 'key_id' in body

    created_token = body['token']
    created_id = body['key_id']

    # Use the created key to call a protected scans endpoint (should be allowed)
    r2 = client.post('/scans', headers={'X-API-KEY': created_token}, json={
        'post_url': 'https://www.instagram.com/p/TEST123/',
        'mode': 'keyword',
        'threshold': 0.7,
        'scrolls': 1,
        'scroll_delay': 100
    })
    assert r2.status_code == 202

    # Revoke the created key
    r3 = client.post(f'/admin/keys/{created_id}/revoke', headers=headers)
    assert r3.status_code == 200

    # After revoke, using that key should fail auth on protected endpoint
    r4 = client.post('/scans', headers={'X-API-KEY': created_token}, json={
        'post_url': 'https://www.instagram.com/p/TEST123/',
        'mode': 'keyword',
        'threshold': 0.7,
        'scrolls': 1,
        'scroll_delay': 100
    })
    assert r4.status_code == 401
from fastapi.testclient import TestClient
from scripts.init_db import main as init_db
from api import auth
from api.app import app


def setup_module(module):
    init_db()


def test_admin_ui_returns_html():
    admin = auth.create_key(scopes='admin', description='ui test')
    client = TestClient(app)
    headers = {'X-API-KEY': admin['token']}
    r = client.get('/admin/ui', headers=headers)
    assert r.status_code == 200
    assert '<title>Admin - API Keys</title>' in r.text

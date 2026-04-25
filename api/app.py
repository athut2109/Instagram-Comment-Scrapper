# api/app.py - minimal FastAPI skeleton for PoC
from fastapi import FastAPI, HTTPException, Depends, Request, Header
from pydantic import BaseModel, HttpUrl, confloat, conint
import sqlite3
import json
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import os
from pathlib import Path

from api.security import get_api_key, rate_limiter

DB_PATH = "insta_poc.db"

app = FastAPI(title="Insta Moderator (PoC)")
logger = logging.getLogger("api")
logger.setLevel(logging.INFO)

# Tune limits via env
SYNC_RUN_TIMEOUT = int(os.getenv('POC_SYNC_TIMEOUT', '30'))  # seconds for blocking mock runs


@app.on_event("startup")
def app_startup():
    api_key = os.getenv('POC_API_KEY')
    if api_key:
        logger.info("API Key auth enabled")
    else:
        logger.warning("No POC_API_KEY set - API endpoints are NOT authenticated (development mode)")
    logger.info("Rate limit: %s requests per %s seconds", os.getenv('POC_RATE_LIMIT', '20'), os.getenv('POC_RATE_WINDOW', '60'))

class ScanCreate(BaseModel):
    post_url: HttpUrl
    mode: str = "ml"
    threshold: confloat(ge=0, le=1) = 0.7
    scrolls: conint(ge=1, le=500) = 50
    scroll_delay: conint(ge=0, le=10000) = 1500

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/scans", status_code=202)
def create_scan(payload: ScanCreate, api_key: str | None = Depends(get_api_key), request: Request = None):
    # Rate limit check
    rate_limiter(api_key, request)

    # Basic URL sanity checks
    url_str = str(payload.post_url)
    if "instagram.com" not in url_str.lower():
        raise HTTPException(status_code=400, detail="post_url must be an Instagram URL")
    if '/p/' not in url_str and '/reel/' not in url_str and '/explore/tags/' not in url_str:
        raise HTTPException(status_code=400, detail="post_url must be a post, reel, or hashtag URL")

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        created_at = datetime.utcnow().isoformat()
        cur.execute(
            "INSERT INTO scans (post_url, mode, threshold, scrolls, scroll_delay, status, created_at) VALUES (?,?,?,?,?,?,?)",
            (url_str, payload.mode, float(payload.threshold), int(payload.scrolls), int(payload.scroll_delay), 'enqueued', created_at)
        )
        conn.commit()
        scan_id = cur.lastrowid
        # Try to enqueue async job (RQ)
        try:
            from api.tasks import enqueue_scan
            job_id = enqueue_scan(scan_id)
            logger.info(f"Enqueued scan %s as job %s", scan_id, job_id)
            return {"scan_id": scan_id, "status": "enqueued", "job_id": job_id}
        except Exception as enqueue_err:
            logger.warning("Enqueue failed: %s", enqueue_err)
            return {"scan_id": scan_id, "status": "enqueued", "enqueue_error": str(enqueue_err)}
    except Exception as e:
        logger.exception("Error creating scan: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/scans/{scan_id}")
def get_scan(scan_id: int, api_key: str | None = Depends(get_api_key), request: Request = None):
    rate_limiter(api_key, request)
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, post_url, status, created_at, finished_at FROM scans WHERE id = ?", (scan_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Scan not found")
        return {
            "scan_id": row[0],
            "post_url": row[1],
            "status": row[2],
            "created_at": row[3],
            "finished_at": row[4]
        }
    finally:
        conn.close()

@app.get("/scans/{scan_id}/results")
def get_scan_results(scan_id: int, api_key: str | None = Depends(get_api_key), request: Request = None):
    rate_limiter(api_key, request)
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT result_json FROM scans WHERE id = ?", (scan_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Scan not found")
        result_json = row[0]
        if result_json:
            return {"scan_id": scan_id, "result": json.loads(result_json)}
        return {"scan_id": scan_id, "result": None}
    finally:
        conn.close()


### Admin key management endpoints (DB-backed)
from pydantic import BaseModel


class KeyCreate(BaseModel):
    scopes: str = 'read,write'
    description: str | None = None


def _require_admin(api_key: str | None = Depends(get_api_key)):
    """Allow admin if either:
      - the legacy env POC_API_KEY is set and matched (env-key is admin), OR
      - the DB-backed key has 'admin' in its scopes
    """
    # env-key mode handled in get_api_key (it returns {'is_env_key': True})
    if api_key is None:
        # dev mode: disallow admin actions unless an env admin key exists
        if os.getenv('POC_ADMIN_KEY'):
            return True
        raise HTTPException(status_code=403, detail='Admin actions require an admin API key')

    # If env bootstrap key used, allow admin
    if isinstance(api_key, dict) and api_key.get('is_env_key'):
        return True

    # Otherwise, check scopes
    if isinstance(api_key, dict):
        scopes = api_key.get('scopes', '')
        if 'admin' in [s.strip() for s in scopes.split(',') if s.strip()]:
            return True

    # Also allow a dedicated POC_ADMIN_KEY env variable
    if os.getenv('POC_ADMIN_KEY') and (isinstance(api_key, dict) and api_key.get('token') == os.getenv('POC_ADMIN_KEY')):
        return True

    raise HTTPException(status_code=403, detail='Admin actions require an admin API key')


@app.post('/admin/keys')
def admin_create_key(req: KeyCreate, api_key: str | None = Depends(get_api_key)):
    # Admin-only
    _require_admin(api_key)
    try:
        from api import auth as keyman
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    record = keyman.create_key(scopes=req.scopes, description=req.description)
    # Return plaintext token once to operator
    return {'key_id': record['key_id'], 'token': record['token'], 'scopes': record['scopes'], 'description': record['description']}


@app.get('/admin/ui')
def admin_ui(api_key: str | None = Depends(get_api_key)):
    """Serve a very small single-file admin UI for key management.

    The page prompts for an admin token (unless an env key is used by the browser) and then allows create/list/revoke via the API.
    """
    from fastapi.responses import HTMLResponse
    html = Path(__file__).parent / 'static' / 'admin_keys.html'
    try:
        content = html.read_text(encoding='utf-8')
        return HTMLResponse(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/admin/keys')
def admin_list_keys(api_key: str | None = Depends(get_api_key)):
    _require_admin(api_key)
    from api import auth as keyman
    keys = keyman.list_keys()
    return {'keys': keys}


@app.post('/admin/keys/{key_id}/revoke')
def admin_revoke_key(key_id: str, api_key: str | None = Depends(get_api_key)):
    _require_admin(api_key)
    from api import auth as keyman
    ok = keyman.revoke_key(key_id)
    if not ok:
        raise HTTPException(status_code=404, detail='Key not found')
    return {'revoked': True}


@app.post("/scans/{scan_id}/run")
def run_scan(scan_id: int, mock: bool = False, api_key: str | None = Depends(get_api_key), request: Request = None):
    """Run a scan synchronously for quick testing.

    Query params:
      - mock: if true, uses a simple fake scraper (no Playwright) for testing.

    WARNING: This blocks the request until the scan is complete; use only for testing.
    """
    rate_limiter(api_key, request)

    # Only allow blocking synchronous runs when mock=true (safety)
    if not mock:
        raise HTTPException(status_code=400, detail="Synchronous run only allowed with mock=true for safety; use async POST /scans instead")

    # Install a fake scraper in adapters for quick deterministic test
    try:
        from api import adapters
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Adapters import failed: {e}")

    def _fake_scrape(post_url, max_scrolls=50, scroll_delay=1500):
        return [
            {"text": "You are an idiot", "username": "user_1", "link": f"{post_url}#c1"},
            {"text": "Lovely photo", "username": "user_2", "link": f"{post_url}#c2"}
        ]

    adapters.scrape_post = _fake_scrape

    # Run the task synchronously with timeout
    try:
        from api.tasks import process_scan
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    with ThreadPoolExecutor(max_workers=1) as exe:
        future = exe.submit(process_scan, scan_id)
        try:
            future.result(timeout=SYNC_RUN_TIMEOUT)
        except TimeoutError:
            # mark as failed due to timeout
            conn = sqlite3.connect(DB_PATH)
            try:
                cur = conn.cursor()
                cur.execute("UPDATE scans SET status = ?, finished_at = ? WHERE id = ?", ("failed", datetime.utcnow().isoformat(), scan_id))
                conn.commit()
            finally:
                conn.close()
            raise HTTPException(status_code=504, detail="Synchronous run timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"process_scan failed: {e}")

    # Return final scan status and results
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT status, result_json FROM scans WHERE id = ?", (scan_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Scan not found after running")
        status, result_json = row
        return {"scan_id": scan_id, "status": status, "result": json.loads(result_json) if result_json else None}
    finally:
        conn.close()

Development notes & quickstart

1) Install dependencies
   - Recommended: create a venv and activate it, then:
     python -m pip install --upgrade pip
     pip install -r requirements.txt

2) Initialize DB
   - python scripts/init_db.py

3) Create an admin key (one-time)
   - python scripts/generate_api_key.py --scopes "admin" --description "bootstrap admin"
   - Save the printed token safely; use it in the X-API-KEY header.

4) Start Redis (for async enqueue)
   - bash scripts/start_redis.sh

5) Run worker
   - bash scripts/run_worker.sh

6) Running tests
   - pytest -q

CI: The repo includes a GitHub Actions workflow at .github/workflows/ci.yml that starts Redis as a service and runs pytest.

Security notes
- The PoC also supports a legacy POC_API_KEY env var; for production use DB-backed opaque keys and store only their hashes. Use the admin endpoints to manage keys.


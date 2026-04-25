# API PoC notes

Commands & scripts:

- Initialize DB:
  - `python scripts/init_db.py`

- Create an API key (prints plaintext token once):
  - `python scripts/generate_api_key.py --scopes "admin" --description "bootstrap admin"`

- Start Redis (local using docker-compose):
  - `bash scripts/start_redis.sh`

- Run an RQ worker (foreground):
  - `bash scripts/run_worker.sh`

Auth:
- PoC supports two modes:
  1. Legacy mode: set `POC_API_KEY` env var and the server will accept that header (or `Authorization: Bearer <token>`).
  2. DB-backed keys: use `scripts/generate_api_key.py` to issue a token and store its hash in DB. Use the token in the `X-API-KEY` header or as `Authorization: Bearer <token>`.

- Admin operations (creating/revoking keys) require an admin-scoped key. Use `--scopes admin` when generating the first key.

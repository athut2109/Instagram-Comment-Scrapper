#!/usr/bin/env bash
# Start an RQ worker attached to local Redis
set -euo pipefail

echo "Starting RQ worker (connects to redis://localhost:6379)"
python -m rq worker default -u redis://localhost:6379

#!/usr/bin/env bash
# Bring up redis via docker-compose
set -euo pipefail

if ! command -v docker &> /dev/null; then
  echo "docker not found in PATH; please install Docker or start Redis manually"
  exit 1
fi

docker-compose up -d redis

echo "Redis started (container)."
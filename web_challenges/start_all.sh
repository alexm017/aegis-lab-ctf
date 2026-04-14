#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$BASE_DIR"
docker-compose -f docker-compose.yml up -d

echo
echo "Web challenge services status:"
docker-compose -f docker-compose.yml ps

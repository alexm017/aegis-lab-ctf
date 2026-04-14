#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[i] Running pre-publish security checks in: $ROOT_DIR"

echo
echo "[1/4] Checking for likely secrets in text files..."
grep -RInE \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  --exclude-dir=.data \
  --exclude='*.png' \
  --exclude='*.jpg' \
  --exclude='*.jpeg' \
  --exclude='*.ico' \
  --exclude='*.gif' \
  --exclude='*.woff' \
  --exclude='*.woff2' \
  --exclude='*.ttf' \
  --exclude='*.eot' \
  --exclude='*.pdf' \
  --exclude='*.zip' \
  --exclude='*.tar' \
  --exclude='*.gz' \
  "(sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)" \
  . \
  | grep -v "AKIAIOSFODNN7EXAMPLE" || true

echo
echo "[2/4] Checking local secret/env files still present..."
find . -type f \( -name ".env" -o -name ".env.*" -o -name "*.pem" -o -name "*.key" -o -name "*.crt" \) \
  | sed 's#^\./##' | sort

echo
echo "[3/4] Checking root directory cleanliness..."
find . -maxdepth 1 -type f \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.ico" \) \
  | sed 's#^\./##' || true

echo
echo "[4/4] Quick checklist"
echo "- Ensure .gitignore is loaded before first git add"
echo "- Rotate any credentials that were ever exposed"
echo "- Review staged files: git diff --staged"
echo "- Confirm no runtime data is staged (.data, logs, pids, shared_flags)"

echo
echo "[✓] Pre-publish checks completed."

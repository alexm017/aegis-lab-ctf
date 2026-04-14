#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/update_challenge_ip.sh <NEW_IP> [--no-restart]

What it updates:
1) Uptime checker challenge URLs in ../OpenML_Alphabit/discord_uptime_bot/sites.json
2) CTFd Web challenge links in DB challenge description/connection_info (ports 32854-32860)

By default it also restarts:
- Uptime bot
- Aegis Lab bot

Examples:
  ./update_challenge_ip.sh 203.0.113.25
  ./update_challenge_ip.sh 203.0.113.25 --no-restart
EOF
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage
  exit 1
fi

NEW_IP="$1"
RESTART_BOTS=true
if [[ "${2:-}" == "--no-restart" ]]; then
  RESTART_BOTS=false
elif [[ $# -eq 2 ]]; then
  echo "[!] Unknown option: $2"
  usage
  exit 1
fi

if ! [[ "$NEW_IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  echo "[!] Invalid IPv4: $NEW_IP"
  exit 1
fi

IFS='.' read -r o1 o2 o3 o4 <<< "$NEW_IP"
for octet in "$o1" "$o2" "$o3" "$o4"; do
  if ((octet < 0 || octet > 255)); then
    echo "[!] Invalid IPv4: $NEW_IP"
    exit 1
  fi
done

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[!] Missing required command: $cmd"
    exit 1
  fi
}

require_cmd python3
require_cmd docker-compose

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
UPTIME_JSON="$ROOT_DIR/../OpenML_Alphabit/discord_uptime_bot/sites.json"
UPTIME_DIR="$ROOT_DIR/../OpenML_Alphabit/discord_uptime_bot"
AEGIS_BOT_DIR="$ROOT_DIR/Aegis_Lab_Discord_Bot"
CTFD_DIR="$ROOT_DIR/CTFd"

if [[ ! -f "$UPTIME_JSON" ]]; then
  echo "[!] Missing file: $UPTIME_JSON"
  exit 1
fi

if [[ ! -d "$CTFD_DIR" ]]; then
  echo "[!] Missing directory: $CTFD_DIR"
  exit 1
fi

OLD_IP="$(python3 - "$UPTIME_JSON" <<'PY'
import json
import sys
from urllib.parse import urlparse

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

for site in data:
    if not isinstance(site, dict):
        continue
    if str(site.get("category", "")).strip() != "CTF Web Challenges":
        continue
    url = str(site.get("url", "")).strip()
    if not url:
        continue
    host = urlparse(url).hostname
    if host:
        print(host)
        break
PY
)"

if [[ -z "$OLD_IP" ]]; then
  echo "[!] Could not detect existing challenge IP from $UPTIME_JSON"
  exit 1
fi

echo "[i] Old challenge IP: $OLD_IP"
echo "[i] New challenge IP: $NEW_IP"

python3 - "$UPTIME_JSON" "$NEW_IP" <<'PY'
import json
import sys
from urllib.parse import urlparse

path = sys.argv[1]
new_ip = sys.argv[2]
valid_ports = {32854, 32855, 32856, 32857, 32858, 32859, 32860}

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

changed = 0
for site in data:
    if not isinstance(site, dict):
        continue
    if str(site.get("category", "")).strip() != "CTF Web Challenges":
        continue
    url = str(site.get("url", "")).strip()
    if not url:
        continue

    parsed = urlparse(url)
    if parsed.port not in valid_ports:
        continue
    scheme = parsed.scheme or "http"
    site["url"] = f"{scheme}://{new_ip}:{parsed.port}/"
    changed += 1

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
    f.write("\n")

print(changed)
PY

echo "[✓] Updated uptime challenge URLs in sites.json"

run_sql() {
  local sql="$1"
  (
    cd "$CTFD_DIR"
    docker-compose exec -T db mysql -uctfd -pctfd -D ctfd -e "$sql"
  )
}

ports=(32854 32855 32856 32857 32858 32859 32860)
for port in "${ports[@]}"; do
  run_sql "UPDATE challenges
SET
  description = REPLACE(
    REPLACE(
      REPLACE(
        REPLACE(description, 'http://${OLD_IP}:${port}/', 'http://${NEW_IP}:${port}/'),
        'http://${OLD_IP}:${port}', 'http://${NEW_IP}:${port}'
      ),
      'https://${OLD_IP}:${port}/', 'http://${NEW_IP}:${port}/'
    ),
    'https://${OLD_IP}:${port}', 'http://${NEW_IP}:${port}'
  ),
  connection_info = REPLACE(
    REPLACE(
      REPLACE(
        REPLACE(connection_info, 'http://${OLD_IP}:${port}/', 'http://${NEW_IP}:${port}/'),
        'http://${OLD_IP}:${port}', 'http://${NEW_IP}:${port}'
      ),
      'https://${OLD_IP}:${port}/', 'http://${NEW_IP}:${port}/'
    ),
    'https://${OLD_IP}:${port}', 'http://${NEW_IP}:${port}'
  )
WHERE category = 'Web';"
done

echo "[✓] Updated CTFd Web challenge links in DB"

run_sql "SELECT id, name
FROM challenges
WHERE category='Web'
  AND (description LIKE '%${NEW_IP}:3285%' OR description LIKE '%${NEW_IP}:32860%'
       OR connection_info LIKE '%${NEW_IP}:3285%' OR connection_info LIKE '%${NEW_IP}:32860%')
ORDER BY id;"

run_sql "SELECT COUNT(*) AS old_ip_remaining
FROM challenges
WHERE category='Web'
  AND (description LIKE '%${OLD_IP}:%' OR connection_info LIKE '%${OLD_IP}:%');"

restart_bot_for_dir() {
  local bot_dir="$1"
  local label="$2"
  local found=false

  for p in $(pgrep -f '\.venv/bin/python -u bot.py' || true); do
    local cwd
    cwd="$(readlink -f "/proc/$p/cwd" 2>/dev/null || true)"
    if [[ "$cwd" == "$bot_dir" ]]; then
      kill "$p" || true
      found=true
    fi
  done

  if [[ "$found" == true ]]; then
    sleep 1
  fi

  (
    cd "$bot_dir"
    setsid -f .venv/bin/python -u bot.py >> runtime.log 2>&1 < /dev/null
  )
  sleep 1

  local pid=""
  for p in $(pgrep -f '\.venv/bin/python -u bot.py' || true); do
    local cwd
    cwd="$(readlink -f "/proc/$p/cwd" 2>/dev/null || true)"
    if [[ "$cwd" == "$bot_dir" ]]; then
      pid="$p"
      break
    fi
  done

  if [[ -n "$pid" ]]; then
    echo "[✓] Restarted $label (pid: $pid)"
  else
    echo "[!] Could not verify $label restart"
  fi
}

if [[ "$RESTART_BOTS" == true ]]; then
  restart_bot_for_dir "$UPTIME_DIR" "Uptime bot"
  restart_bot_for_dir "$AEGIS_BOT_DIR" "Aegis Lab bot"
else
  echo "[i] Bot restart skipped (--no-restart)"
fi

echo
echo "[DONE] Challenge IP switch complete."
echo "       You can run this any time with:"
echo "       ./update_challenge_ip.sh <NEW_IP>"

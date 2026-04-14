# Aegis Lab CTF Project

CTF infrastructure for Aegis Lab, including:
- `CTFd/` - CTFd platform instance
- `web_challenges/` - standalone web challenge services
- `Aegis_Lab_Discord_Bot/` - Discord assistant/events bot
- `assets/` - project media assets
- `scripts/` - utility scripts

## Prerequisites
- Linux with `docker` and `docker-compose`
- `python3` (for Discord bot)
- Apache can run in parallel as long as CTFd is exposed on `127.0.0.1:8000`

## 1) Local Environment Setup
```bash
cp CTFd/.env.example CTFd/.env
cp Aegis_Lab_Discord_Bot/.env.example Aegis_Lab_Discord_Bot/.env
```

Then edit:
- `CTFd/.env` with strong DB passwords
- `Aegis_Lab_Discord_Bot/.env` with bot/OpenAI credentials (if you use the bot)

Do not commit local `.env` files.

## 2) Start CTFd
```bash
cd CTFd
docker-compose up -d db cache ctfd
docker-compose ps
```

CTFd URL:
- `http://127.0.0.1:8000`

Notes:
- This starts CTFd without its nginx container, so it does not conflict with Apache on port 80.

## 3) Start Web Challenges
```bash
cd ../web_challenges
./start_all.sh
./status.sh
```

Challenge URLs:
- Cookie Jar: `http://127.0.0.1:32854`
- SQL Rookie: `http://127.0.0.1:32855`
- Template Leak: `http://127.0.0.1:32856`
- SSRF Notes: `http://127.0.0.1:32857`
- IDOR Vault: `http://127.0.0.1:32858`
- Ping Commander: `http://127.0.0.1:32859`
- File Viewer v2: `http://127.0.0.1:32860`

## 4) Optional: Run Discord Bot
```bash
cd ../Aegis_Lab_Discord_Bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

## 5) Stop Services
```bash
cd CTFd && docker-compose down
cd ../web_challenges && ./stop_all.sh
```

## Utility Script
Update external challenge IPs in bot/CTFd references:
```bash
./scripts/update_challenge_ip.sh <NEW_IP>
```

Optional pre-publish check:
- `./scripts/security_prepublish_check.sh`

# Aegis Lab CTF Project

This repository contains:
- `CTFd/` - CTFd platform (core + local configuration)
- `web_challenges/` - standalone web challenge services
- `Aegis_Lab_Discord_Bot/` - Discord assistant/events bot
- `assets/` - project media assets
- `scripts/` - operational scripts

## Safe Setup (Local)
1. Copy bot env template:
   - `cp Aegis_Lab_Discord_Bot/.env.example Aegis_Lab_Discord_Bot/.env`
2. Copy CTFd env template:
   - `cp CTFd/.env.example CTFd/.env`
3. Fill credentials locally (do not commit `.env` files).

## Security
See `SECURITY_ASSESSMENT.md` for findings, remediations, and publish checklist.

Optional pre-publish check:
- `./scripts/security_prepublish_check.sh`

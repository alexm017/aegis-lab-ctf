# Security Assessment (Pre-GitHub)

Date: 2026-04-14

## Scope
- Root project layout
- `Aegis_Lab_Discord_Bot/`
- `CTFd/`
- `web_challenges/`

## High-Risk Findings (Fixed)
1. Exposed credentials in `Aegis_Lab_Discord_Bot/.env`:
   - Discord bot token
   - OpenAI API key
   - Status: sanitized (values removed)

2. Hardcoded database credentials in `CTFd/docker-compose.yml`:
   - `DATABASE_URL=mysql+pymysql://ctfd:ctfd@db/ctfd`
   - `MARIADB_ROOT_PASSWORD=ctfd`
   - `MARIADB_PASSWORD=ctfd`
   - Status: replaced with environment variables

## Repository Hardening Applied
- Added root `.gitignore` with strict rules for:
  - secrets/env files (`.env`, `.pem`, `.key`, etc.)
  - runtime data (`CTFd/.data`, logs, pid files)
  - CTFd secret key (`CTFd/.ctfd_secret_key`)
  - bot runtime/private files (`runtime.log`, `.venv`, event metadata)
  - internal notes/tmp artifacts

- Added `CTFd/.env.example` for safe credential templating.

## Project Structure Cleanup Applied
- Moved loose root images into `assets/branding/`
- Moved temp images into `assets/reference/tmp/`
- Moved internal notes into `docs/internal/` (ignored)
- Moved `update_challenge_ip.sh` to `scripts/update_challenge_ip.sh`

## Remaining Manual Security Actions (Required)
1. Rotate all credentials that were ever exposed previously:
   - Discord bot token(s)
   - OpenAI API key(s)
2. If any secret was ever committed in a previous Git history, rewrite history before publishing:
   - `git filter-repo` or BFG
3. Resolve embedded repository metadata before root publish:
   - `CTFd/` currently contains its own `.git` directory.
   - For a single monorepo publish, remove `CTFd/.git` (or publish CTFd as a true submodule).
4. Before push, run a final local secret scan and review staged files:
   - `git status`
   - `git diff --staged`

## Notes
- CTF challenge apps are intentionally vulnerable by design; deploy only in isolated environments.
- Runtime CTF data (`CTFd/.data/`, challenge logs/flags) is now excluded from version control.

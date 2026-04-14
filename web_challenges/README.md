# ZeroSec Web Challenges

This folder contains live local web challenge services used by CTFd `Web` challenges.

## Services

- `cookie_jar` -> `http://127.0.0.1:32854`
- `sql_rookie` -> `http://127.0.0.1:32855`
- `template_leak` -> `http://127.0.0.1:32856`
- `ssrf_notes` -> `http://127.0.0.1:32857`
- `idor_vault` -> `http://127.0.0.1:32858`
- `ping_commander` -> `http://127.0.0.1:32859`
- `file_viewer_v2` -> `http://127.0.0.1:32860`

## Commands

```bash
./web_challenges/start_all.sh
./web_challenges/status.sh
./web_challenges/stop_all.sh
```

All services are managed by `web_challenges/docker-compose.yml` and use the local `ctfd_ctfd` image.
For shell/filesystem challenges, flags are mounted inside containers at `/flag.txt`.

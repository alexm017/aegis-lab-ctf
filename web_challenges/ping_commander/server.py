#!/usr/bin/env python3
import os
import subprocess
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8106"))
FLAG = os.getenv("FLAG", "flag{shell_injection_on_ping}")
FLAG_FILE = "/flag.txt"


def render_shell(title: str, content: str) -> str:
    return f"""<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <title>{escape(title)}</title>
    <style>
      body {{ margin:0; background:#101215; color:#d7f5db; font-family:"Courier New", monospace; }}
      .term {{ width:min(900px,95vw); margin:20px auto; border:1px solid #4a4f55; background:#171b20; }}
      .bar {{ background:#2a2f36; color:#b8bec6; padding:8px 10px; font-size:13px; }}
      .body {{ padding:12px; }}
      h1 {{ margin:0 0 10px; font-size:22px; color:#7cf58a; }}
      .line {{ margin:8px 0; }}
      label {{ display:block; margin-bottom:5px; color:#9de7a4; }}
      input {{ width:100%; box-sizing:border-box; border:1px solid #4a525b; background:#0f1318; color:#d7f5db; padding:8px; font-family:inherit; }}
      button, a.btn {{ margin-top:8px; border:1px solid #4f6854; background:#1f2d23; color:#9be9a3; padding:7px 10px; font-family:inherit; cursor:pointer; text-decoration:none; display:inline-block; }}
      button:hover, a.btn:hover {{ background:#28382d; }}
      pre {{ margin:10px 0; border:1px solid #3a424b; background:#0f1318; color:#d7f5db; padding:10px; overflow-x:auto; }}
      code {{ color:#ffd89b; }}
    </style>
  </head>
  <body>
    <div class=\"term\">
      <div class=\"bar\">network-tools@ops:~</div>
      <div class=\"body\">{content}</div>
    </div>
  </body>
</html>
"""


def ensure_flag_file() -> None:
    if os.path.exists(FLAG_FILE):
        return
    try:
        with open(FLAG_FILE, "w", encoding="utf-8") as f:
            f.write(FLAG + "\n")
    except OSError:
        pass


class Handler(BaseHTTPRequestHandler):
    server_version = "PingCommander/1.0"

    def send_html(self, body: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            content = """
<h1>Ping Commander</h1>
<form method=\"GET\" action=\"/run\">
  <label>host</label>
  <input name=\"host\" value=\"127.0.0.1\">
  <button type=\"submit\">run</button>
</form>
"""
            self.send_html(render_shell("Ping Commander", content))
            return

        if path == "/run":
            params = parse_qs(parsed.query)
            host = params.get("host", [""])[0].strip()
            if not host:
                self.send_html(render_shell("Error", "<h1>error</h1><p>missing host</p><a class='btn' href='/'>back</a>"), status=400)
                return

            cmd = f"echo PING {host}"
            try:
                out = subprocess.check_output(
                    cmd,
                    shell=True,
                    stderr=subprocess.STDOUT,
                    timeout=3,
                    text=True,
                )
            except subprocess.CalledProcessError as exc:
                out = exc.output
            except Exception as exc:
                out = str(exc)

            content = f"""
<h1>Run Result</h1>
<div class=\"line\">$ <code>{escape(cmd)}</code></div>
<pre>{escape(out)}</pre>
<a class=\"btn\" href=\"/\">back</a>
"""
            self.send_html(render_shell("Run Result", content))
            return

        self.send_html(render_shell("404", "<h1>404</h1>"), status=404)


if __name__ == "__main__":
    ensure_flag_file()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[ping_commander] listening on http://{HOST}:{PORT}")
    server.serve_forever()

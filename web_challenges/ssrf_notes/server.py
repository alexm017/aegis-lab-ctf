#!/usr/bin/env python3
import os
import urllib.error
import urllib.request
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8104"))
FLAG = os.getenv("FLAG", "flag{ssrf_hits_internal_notes}")
BOT_HEADER = "X-From-Backend"
BOT_VALUE = "ssrf-bot"


def page(title: str, inner: str) -> str:
    return f"""<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <title>{escape(title)}</title>
    <style>
      body {{ margin:0; background:#edf2f9; font-family:Verdana, Arial, sans-serif; color:#1d2a38; }}
      .head {{ background:#1f4d7b; color:#fff; padding:11px 16px; font-weight:bold; }}
      .wrap {{ width:min(900px,94vw); margin:18px auto; display:grid; grid-template-columns:190px 1fr; gap:10px; }}
      .side {{ background:#d9e4f2; border:1px solid #7e94ae; padding:10px; }}
      .side h3 {{ margin:0 0 8px; font-size:14px; }}
      .side a {{ color:#17395a; text-decoration:none; display:block; margin:5px 0; }}
      .main {{ background:#fff; border:1px solid #7e94ae; padding:12px; }}
      h1 {{ margin:0 0 10px; font-size:22px; color:#17395a; }}
      .box {{ border:1px solid #a7b9cf; background:#f7faff; padding:10px; margin:10px 0; }}
      label {{ display:block; font-weight:bold; margin-bottom:6px; }}
      input {{ width:100%; box-sizing:border-box; border:1px solid #7f93a8; padding:7px; font-family:Consolas, monospace; }}
      button, .btn {{ margin-top:8px; border:1px solid #596d83; background:#dce8f7; padding:6px 10px; cursor:pointer; text-decoration:none; color:#132b45; display:inline-block; }}
      pre {{ border:1px solid #a5b6ca; background:#eef4fb; padding:10px; overflow-x:auto; font-family:Consolas, monospace; }}
      @media (max-width: 760px) {{ .wrap {{ grid-template-columns:1fr; }} }}
    </style>
  </head>
  <body>
    <div class=\"head\">Support Fetcher Console</div>
    <div class=\"wrap\">
      <aside class=\"side\">
        <h3>Menu</h3>
        <a href=\"/\">URL Fetch</a>
        <a href=\"/internal/flag\">Internal Notes</a>
      </aside>
      <main class=\"main\">{inner}</main>
    </div>
  </body>
</html>"""


def is_local_client(ip: str) -> bool:
    return ip in ("127.0.0.1", "::1")


class Handler(BaseHTTPRequestHandler):
    server_version = "SSRFNotes/1.0"

    def send_html(self, body: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/":
            inner = """
<h1>URL Fetch Utility</h1>
<div class=\"box\">
  <form method=\"GET\" action=\"/fetch\">
    <label>Target URL</label>
    <input name=\"url\" placeholder=\"http://example.org\">
    <button type=\"submit\">Fetch</button>
  </form>
</div>
"""
            self.send_html(page("URL Fetch", inner))
            return

        if parsed.path == "/internal/flag":
            remote_ip = self.client_address[0]
            marker = self.headers.get(BOT_HEADER, "")
            if not (is_local_client(remote_ip) and marker == BOT_VALUE):
                inner = """
<h1>403 Forbidden</h1>
<div class=\"box\"><p>Internal endpoint. Backend requests only.</p><a class=\"btn\" href=\"/\">Back</a></div>
"""
                self.send_html(page("Forbidden", inner), status=403)
                return
            inner = f"""
<h1>Internal Note</h1>
<div class=\"box\"><pre>{escape(FLAG)}</pre></div>
"""
            self.send_html(page("Internal Note", inner))
            return

        if parsed.path == "/fetch":
            params = parse_qs(parsed.query)
            target = params.get("url", [""])[0].strip()
            if not target:
                self.send_html(page("Input Error", "<h1>Error</h1><div class='box'><p>Missing url parameter.</p></div>"), status=400)
                return

            parsed_target = urlparse(target)
            if parsed_target.scheme not in ("http", "https"):
                self.send_html(page("Input Error", "<h1>Error</h1><div class='box'><p>Only http/https URLs are allowed.</p></div>"), status=400)
                return

            req = urllib.request.Request(target, headers={BOT_HEADER: BOT_VALUE, "User-Agent": "ssrf-bot/1.0"})
            try:
                with urllib.request.urlopen(req, timeout=4) as resp:
                    data = resp.read(4096).decode("utf-8", errors="replace")
                inner = f"""
<h1>Fetch Result</h1>
<div class=\"box\">
  <p><b>URL:</b> <code>{escape(target)}</code></p>
  <pre>{escape(data)}</pre>
  <a class=\"btn\" href=\"/\">Back</a>
</div>
"""
                self.send_html(page("Fetch Result", inner))
            except (urllib.error.URLError, ValueError) as exc:
                inner = f"""
<h1>Fetch Error</h1>
<div class=\"box\"><pre>{escape(str(exc))}</pre><a class=\"btn\" href=\"/\">Back</a></div>
"""
                self.send_html(page("Fetch Error", inner), status=502)
            return

        self.send_html(page("404", "<h1>404</h1><div class='box'><p>Page not found.</p></div>"), status=404)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[ssrf_notes] listening on http://{HOST}:{PORT}")
    server.serve_forever()

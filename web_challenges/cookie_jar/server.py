#!/usr/bin/env python3
import base64
import json
import os
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8101"))
FLAG = os.getenv("FLAG", "flag{cookie_role_escalation}")

BASE_STYLE = """
<style>
body { margin: 0; background: #cfd6db; color: #111; font-family: Tahoma, Verdana, Arial, sans-serif; font-size: 14px; }
#wrapper { width: min(760px, 94vw); margin: 22px auto; border: 1px solid #2f2f2f; background: #fff; }
#topbar { background: #2d3f50; color: #fff; padding: 10px 12px; font-weight: bold; letter-spacing: .2px; }
#content { padding: 12px; }
.panel { border: 1px solid #999; background: #f5f5f5; padding: 10px; margin-bottom: 10px; }
.panel h2 { margin: 0 0 8px; font-size: 16px; }
button, .btn { background: #e9e9e9; border: 1px solid #666; color: #111; padding: 6px 10px; font: inherit; cursor: pointer; text-decoration: none; display: inline-block; }
button:hover, .btn:hover { background: #dcdcdc; }
pre, code { background: #efefef; border: 1px solid #bbb; font-family: Consolas, "Courier New", monospace; }
code { padding: 1px 4px; }
pre { padding: 8px; overflow-x: auto; }
.note { color: #5a5a5a; font-size: 12px; border-top: 1px dashed #aaa; padding-top: 8px; margin-top: 12px; }
</style>
"""


def render_page(title: str, section: str, body: str) -> str:
    return f"""<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <title>{escape(title)}</title>
    {BASE_STYLE}
  </head>
  <body>
    <div id=\"wrapper\">
      <div id=\"topbar\">{escape(section)}</div>
      <div id=\"content\">{body}</div>
    </div>
  </body>
</html>
"""


def parse_cookie_header(cookie_header: str) -> dict:
    cookies = {}
    if not cookie_header:
        return cookies
    for part in cookie_header.split(";"):
        if "=" not in part:
            continue
        key, value = part.strip().split("=", 1)
        cookies[key] = value
    return cookies


def build_auth_cookie(role: str = "user") -> str:
    payload = {"user": "guest", "role": role}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    token = base64.urlsafe_b64encode(raw).decode("utf-8")
    return token.rstrip("=")


def decode_auth_cookie(token: str) -> dict:
    if not token:
        return {}
    padded = token + ("=" * (-len(token) % 4))
    raw = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
    return json.loads(raw)


class Handler(BaseHTTPRequestHandler):
    server_version = "CookieJar/1.0"

    def send_html(self, body: str, status: int = 200, extra_headers=None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        cookies = parse_cookie_header(self.headers.get("Cookie", ""))
        auth_cookie = cookies.get("auth")

        if path == "/":
            headers = {}
            if not auth_cookie:
                auth_cookie = build_auth_cookie("user")
                headers["Set-Cookie"] = f"auth={auth_cookie}; Path=/; HttpOnly"

            body = f"""
<div class=\"panel\">
  <h2>Session Center</h2>
  <p>Logged in as guest user.</p>
  <p>Auth cookie:</p>
  <pre>{escape(auth_cookie)}</pre>
  <a class=\"btn\" href=\"/dashboard\">Open Dashboard</a>
  <div class=\"note\">Debug mode is enabled for this environment.</div>
</div>
"""
            self.send_html(render_page("Cookie Jar", "Session Console", body), extra_headers=headers)
            return

        if path == "/dashboard":
            role = "user"
            user = "guest"
            try:
                decoded = decode_auth_cookie(auth_cookie)
                role = str(decoded.get("role", "user"))
                user = str(decoded.get("user", "guest"))
            except Exception:
                pass

            if role == "admin":
                body = f"""
<div class=\"panel\">
  <h2>Admin Dashboard</h2>
  <p>Welcome back, <b>{escape(user)}</b>.</p>
  <pre>{escape(FLAG)}</pre>
  <a class=\"btn\" href=\"/\">Back</a>
</div>
"""
                self.send_html(render_page("Dashboard", "Session Console", body))
            else:
                body = f"""
<div class=\"panel\">
  <h2>User Dashboard</h2>
  <p>User: <b>{escape(user)}</b></p>
  <p>Role: <code>{escape(role)}</code></p>
  <a class=\"btn\" href=\"/\">Back</a>
</div>
"""
                self.send_html(render_page("Dashboard", "Session Console", body))
            return

        self.send_html(render_page("404", "Session Console", "<div class='panel'><h2>404</h2><p>Page not found.</p></div>"), status=404)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[cookie_jar] listening on http://{HOST}:{PORT}")
    server.serve_forever()

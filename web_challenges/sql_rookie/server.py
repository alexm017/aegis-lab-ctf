#!/usr/bin/env python3
import os
import sqlite3
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8102"))
FLAG = os.getenv("FLAG", "flag{sqli_login_bypass}")
DB_PATH = os.getenv("DB_PATH", "/tmp/sql_rookie.db")


def render_login_page() -> str:
    return """<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Admin Dashboard Login</title>
    <style>
      :root {
        --bg: #e7edf3;
        --line: #b8c3d1;
        --line-strong: #8ea2bb;
        --text: #1f2e40;
        --muted: #5c6f86;
        --panel: #ffffff;
        --top: #334a67;
        --top-2: #2b405a;
        --accent: #4a78af;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        min-height: 100vh;
        background: var(--bg);
        color: var(--text);
        font-family: Arial, Helvetica, sans-serif;
      }
      .top {
        height: 52px;
        border-bottom: 1px solid #1f3146;
        background: linear-gradient(180deg, var(--top) 0%, var(--top-2) 100%);
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 14px;
      }
      .logo {
        font-size: 15px;
        font-weight: 700;
        color: #f4f8ff;
      }
      .status {
        font-size: 12px;
        color: #d4dfec;
      }
      .shell {
        width: min(390px, 94vw);
        margin: 8vh auto 0;
      }
      .login-box {
        border: 1px solid var(--line-strong);
        background: var(--panel);
        box-shadow: 0 8px 18px rgba(36, 50, 68, 0.14);
      }
      .login-head {
        background: #f5f8fc;
        border-bottom: 1px solid var(--line);
        padding: 10px 12px;
        font-size: 13px;
        color: #3d516b;
        font-weight: 700;
      }
      .login-body {
        padding: 14px 12px 12px;
      }
      h1 {
        margin: 0 0 8px;
        font-size: 21px;
        color: #2e445f;
      }
      label {
        display: block;
        margin: 8px 0 5px;
        font-size: 12px;
        color: #4d6078;
        text-transform: uppercase;
        letter-spacing: 0.05em;
      }
      input {
        width: 100%;
        border: 1px solid #9eb0c6;
        background: #fff;
        color: #25384d;
        padding: 8px 9px;
        font-family: Consolas, "Courier New", monospace;
      }
      button {
        margin-top: 12px;
        width: 100%;
        border: 1px solid #3f6592;
        background: var(--accent);
        color: #f2f7ff;
        font-weight: 700;
        padding: 8px 10px;
        cursor: pointer;
      }
      button:hover { background: #436f9f; }
      .help {
        margin-top: 9px;
        font-size: 12px;
        color: var(--muted);
      }
    </style>
  </head>
  <body>
    <div class="top">
      <div class="logo">Northbridge CMS</div>
      <div class="status">Admin Console</div>
    </div>

    <div class="shell">
      <form class="login-box" method="POST" action="/login">
        <div class="login-head">Authentication Required</div>
        <div class="login-body">
          <h1>Admin Dashboard Login</h1>
          <label>Username</label>
          <input name="username" autocomplete="off">

          <label>Password</label>
          <input name="password" type="password" autocomplete="off">

          <button type="submit">Sign In</button>
          <div class="help">Use your administrator account to continue.</div>
        </div>
      </form>
    </div>
  </body>
</html>
"""


def render_dashboard(title: str, content: str) -> str:
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(title)}</title>
    <style>
      :root {{
        --bg: #e7edf3;
        --line: #b8c3d1;
        --line-strong: #8ea2bb;
        --text: #1f2e40;
        --muted: #5c6f86;
        --panel: #ffffff;
        --top: #334a67;
        --top-2: #2b405a;
        --accent: #4a78af;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        min-height: 100vh;
        background: var(--bg);
        color: var(--text);
        font-family: Arial, Helvetica, sans-serif;
      }}
      .top {{
        height: 52px;
        border-bottom: 1px solid #1f3146;
        background: linear-gradient(180deg, var(--top) 0%, var(--top-2) 100%);
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 14px;
      }}
      .logo {{
        font-size: 15px;
        font-weight: 700;
        color: #f4f8ff;
      }}
      .top a {{
        color: #e9f1fd;
        text-decoration: none;
        border: 1px solid #6483a8;
        background: #3b5879;
        padding: 6px 10px;
        font-size: 12px;
      }}
      .main {{
        width: min(900px, 95vw);
        margin: 18px auto;
      }}
      .main h1 {{
        margin: 0 0 10px;
        font-size: 24px;
        color: #2c425d;
      }}
      .cards {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
      }}
      .stat {{
        border: 1px solid var(--line);
        background: var(--panel);
        padding: 10px;
      }}
      .stat b {{
        display: block;
        font-size: 20px;
      }}
      .stat span {{
        color: var(--muted);
        font-size: 12px;
      }}
      .panel {{
        margin-top: 10px;
        border: 1px solid var(--line);
        background: var(--panel);
        padding: 11px;
      }}
      .panel h2 {{
        margin: 0 0 8px;
        font-size: 17px;
        color: #334d6d;
      }}
      .panel p {{
        margin: 7px 0;
        color: #314860;
      }}
      pre {{
        margin: 8px 0;
        padding: 10px;
        border: 1px solid #c7d1de;
        background: #f3f7fb;
        color: #223247;
        overflow-x: auto;
        font-family: Consolas, "Courier New", monospace;
      }}
      .table {{
        width: 100%;
        border-collapse: collapse;
      }}
      .table th, .table td {{
        border: 1px solid var(--line);
        padding: 7px 8px;
        text-align: left;
        font-size: 13px;
      }}
      .table th {{
        background: #e3ebf5;
        color: #2b405b;
      }}
      .table td {{
        background: #fff;
        color: #304860;
      }}
      @media (max-width: 900px) {{
        .cards {{ grid-template-columns: 1fr; }}
      }}
    </style>
  </head>
  <body>
    <div class="top">
      <div class="logo">Northbridge CMS</div>
      <a href="/">Sign Out</a>
    </div>
    <main class="main">{content}</main>
  </body>
</html>
"""


def render_error_panel(title: str, message: str) -> str:
    content = f"""
<h1>{escape(title)}</h1>
<div class="panel">
  <p>{escape(message)}</p>
  <p><a href="/" style="color:#4a78af;">Back to Login</a></p>
</div>
"""
    return render_dashboard(title, content)


def render_admin_panel(user: str, note: str) -> str:
    content = f"""
<h1>Admin Dashboard</h1>
<div class="cards">
  <div class="stat"><b>18</b><span>Published Today</span></div>
  <div class="stat"><b>4</b><span>Pending Reviews</span></div>
  <div class="stat"><b>312</b><span>Active Editors</span></div>
</div>

<div class="panel">
  <h2>Welcome, {escape(user)}</h2>
  <p>System scope: Full administrator access.</p>
</div>

<div class="panel">
  <h2>Credential Vault</h2>
  <pre>{escape(note)}</pre>
</div>

<div class="panel">
  <h2>Recent Publishing Queue</h2>
  <table class="table">
    <thead>
      <tr><th>Content</th><th>Status</th><th>Editor</th></tr>
    </thead>
    <tbody>
      <tr><td>Spring Workshop Recap</td><td>Scheduled</td><td>amelia</td></tr>
      <tr><td>Threat Intel Digest</td><td>Draft</td><td>radu</td></tr>
      <tr><td>Lab Maintenance Notice</td><td>Published</td><td>admin</td></tr>
    </tbody>
  </table>
</div>
"""
    return render_dashboard("Admin Dashboard", content)


def render_user_panel(user: str, note: str) -> str:
    content = f"""
<h1>Editor Dashboard</h1>
<div class="cards">
  <div class="stat"><b>3</b><span>Drafts</span></div>
  <div class="stat"><b>1</b><span>Pending Approval</span></div>
  <div class="stat"><b>0</b><span>System Alerts</span></div>
</div>

<div class="panel">
  <h2>Welcome, {escape(user)}</h2>
  <p>Role scope: Standard editor permissions.</p>
</div>

<div class="panel">
  <h2>Notes</h2>
  <p>{escape(note)}</p>
</div>
"""
    return render_dashboard("Editor Dashboard", content)


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            note TEXT NOT NULL
        )
        """
    )
    cur.execute("DELETE FROM users")
    cur.execute(
        "INSERT INTO users(username, password, is_admin, note) VALUES (?, ?, ?, ?)",
        ("admin", "DontGuessMe!", 1, f"Admin note: {FLAG}"),
    )
    cur.execute(
        "INSERT INTO users(username, password, is_admin, note) VALUES (?, ?, ?, ?)",
        ("guest", "guest123", 0, "No privileged notes for this account"),
    )
    conn.commit()
    conn.close()


class Handler(BaseHTTPRequestHandler):
    server_version = "SQLRookie/2.0"

    def send_html(self, body: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self) -> None:
        if self.path == "/" or self.path.startswith("/?"):
            self.send_html(render_login_page())
            return
        self.send_html(render_error_panel("404", "Page not found."), status=404)

    def do_POST(self) -> None:
        if self.path != "/login":
            self.send_html(render_error_panel("404", "Page not found."), status=404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        params = parse_qs(raw)
        username = params.get("username", [""])[0]
        password = params.get("password", [""])[0]

        query = (
            "SELECT username, is_admin, note FROM users "
            f"WHERE username = '{username}' AND password = '{password}'"
        )

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        try:
            row = cur.execute(query).fetchone()
        except sqlite3.Error as exc:
            conn.close()
            self.send_html(render_error_panel("Database Error", str(exc)))
            return
        conn.close()

        if not row:
            self.send_html(render_error_panel("Access Denied", "Invalid username or password."))
            return

        user, is_admin, note = row
        if is_admin:
            self.send_html(render_admin_panel(user, note))
        else:
            self.send_html(render_user_panel(user, note))


if __name__ == "__main__":
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[sql_rookie] listening on http://{HOST}:{PORT}")
    server.serve_forever()

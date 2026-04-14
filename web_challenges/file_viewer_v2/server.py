#!/usr/bin/env python3
import mimetypes
import os
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8107"))
FLAG = os.getenv("FLAG", "flag{path_traversal_reads_private_file}")
FLAG_FILE = "/flag.txt"

ROOT = "/tmp/file_viewer_v2"
PAGES_DIR = os.path.join(ROOT, "cms_pages")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIR = os.path.join(BASE_DIR, "media")


def ensure_flag() -> None:
    if os.path.exists(FLAG_FILE):
        return
    try:
        with open(FLAG_FILE, "w", encoding="utf-8") as f:
            f.write(FLAG + "\n")
    except OSError:
        pass


def prepare_pages() -> None:
    os.makedirs(PAGES_DIR, exist_ok=True)
    pages = {
        "home.php": """
<h2>Welcome to OakTrail Journal</h2>
<p>A small cozy blog about daily dog walks, coffee stops and neighborhood stories.</p>
<div class="grid">
  <article class="card">
    <h3>Morning Walk Logs</h3>
    <p>Track sunrise walks, routes and tiny moments from the park.</p>
  </article>
  <article class="card">
    <h3>Pup Gallery</h3>
    <p>Save snapshots from trail days, rainy walks and weekend hikes.</p>
  </article>
  <article class="card">
    <h3>Story Pages</h3>
    <p>Browse sections using the <code>page</code> parameter in the URL.</p>
  </article>
</div>
""",
        "posts.php": """
<h2>Latest Walk Stories</h2>
<article class="post">
  <h3>Golden Hour River Walk</h3>
  <p class="meta">Posted by Mara • March 2026</p>
  <p>Bruno chased leaves along the river path and made three new dog friends before sunset.</p>
</article>
<article class="post">
  <h3>Rainy Day Cafe Stop</h3>
  <p class="meta">Posted by Mara • March 2026</p>
  <p>We ended our short rainy walk with warm tea and a blanket corner by the window.</p>
</article>
<article class="post">
  <h3>Sunday Forest Trail</h3>
  <p class="meta">Posted by Mara • March 2026</p>
  <p>Long path, muddy paws, happy tail. Packed snacks, water, and a small first-aid kit.</p>
</article>
""",
        "gallery.php": """
<h2>Pup Gallery</h2>
<div class="gallery">
  <figure class="photo"><img src="/media/dogs/dog1.jpg" alt="Dog walk photo 1"><figcaption>Maple Street • 07:20</figcaption></figure>
  <figure class="photo"><img src="/media/dogs/dog2.jpg" alt="Dog walk photo 2"><figcaption>Riverside Path • 18:10</figcaption></figure>
  <figure class="photo"><img src="/media/dogs/dog3.jpg" alt="Dog walk photo 3"><figcaption>Raincoat Day • 11:45</figcaption></figure>
  <figure class="photo"><img src="/media/dogs/dog4.jpg" alt="Dog walk photo 4"><figcaption>Pine Hill Trail • 09:30</figcaption></figure>
  <figure class="photo"><img src="/media/dogs/dog5.jpg" alt="Dog walk photo 5"><figcaption>Old Town Bench • 16:05</figcaption></figure>
  <figure class="photo"><img src="/media/dogs/dog6.jpg" alt="Dog walk photo 6"><figcaption>Sunday Park • 08:55</figcaption></figure>
</div>
""",
        "about.php": """
<h2>About OakTrail Journal</h2>
<p>OakTrail Journal is a tiny classic blog used to keep friendly notes from daily dog walks.</p>
<p>It keeps old-style page routing for compatibility with legacy templates.</p>
""",
        "contact.php": """
<h2>Contact</h2>
<p>Writer: mara@oaktrail.local</p>
<p>Photo Submissions: photos@oaktrail.local</p>
<p>Response window: Mon-Fri 09:00 - 17:00</p>
""",
    }

    for name, content in pages.items():
        path = os.path.join(PAGES_DIR, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")


def render_layout(active_page: str, content: str, info: str = "") -> str:
    links = [
        ("home.php", "Home"),
        ("posts.php", "Posts"),
        ("gallery.php", "Gallery"),
        ("about.php", "About"),
        ("contact.php", "Contact"),
    ]

    nav_items = []
    for page, label in links:
        cls = "active" if page == active_page else ""
        nav_items.append(f'<a class="{cls}" href="/?page={escape(page)}">{escape(label)}</a>')
    nav_html = "".join(nav_items)

    info_block = ""

    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>OakTrail Journal</title>
    <style>
      :root {{
        --bg: #e8dccb;
        --line: #c3ae93;
        --line-strong: #a68a6a;
        --text: #3b2a1f;
        --muted: #705642;
        --panel: #fff9f0;
        --header: #6e4f36;
        --header-2: #5a3f2b;
        --accent: #8f5e36;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        background:
          radial-gradient(circle at 15% 10%, #f5ebdc 0%, var(--bg) 40%),
          linear-gradient(180deg, #ecdfcf 0%, #e5d7c5 100%);
        color: var(--text);
        font-family: "Trebuchet MS", Arial, sans-serif;
      }}
      .top {{
        background: linear-gradient(180deg, var(--header) 0%, var(--header-2) 100%);
        border-bottom: 1px solid #4b3423;
        color: #fff1df;
      }}
      .top .inner {{
        width: min(980px, 96vw);
        margin: 0 auto;
        padding: 12px 10px;
        display: flex;
        align-items: center;
        justify-content: space-between;
      }}
      .brand {{
        font-size: 18px;
        font-weight: 700;
        letter-spacing: 0.02em;
      }}
      .sub {{
        font-size: 12px;
        color: #ecd7bf;
      }}
      .nav {{
        width: min(980px, 96vw);
        margin: 0 auto;
        padding: 9px 10px 10px;
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }}
      .nav a {{
        text-decoration: none;
        border: 1px solid #9f7a57;
        color: #fff2de;
        background: #7b573a;
        padding: 6px 10px;
        font-size: 13px;
      }}
      .nav a.active {{
        border-color: #ebc392;
        background: #946744;
      }}
      .main {{
        width: min(980px, 96vw);
        margin: 14px auto;
        border: 1px solid var(--line-strong);
        background: var(--panel);
        box-shadow: 0 8px 18px rgba(95, 69, 46, 0.14);
      }}
      .content {{
        padding: 14px;
      }}
      h2 {{
        margin: 0 0 10px;
        color: #5f422d;
      }}
      h3 {{
        margin: 0 0 8px;
        color: #654730;
      }}
      p {{
        line-height: 1.45;
        margin: 8px 0;
      }}
      .grid {{
        margin-top: 10px;
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
      }}
      .card {{
        border: 1px solid var(--line);
        background: #f8ecdb;
        padding: 10px;
      }}
      .post {{
        border: 1px solid var(--line);
        background: #fbefde;
        padding: 10px;
        margin-bottom: 10px;
      }}
      .meta {{
        margin: 0 0 6px;
        color: var(--muted);
        font-size: 12px;
      }}
      .gallery {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
      }}
      .photo {{
        margin: 0;
        border: 1px solid var(--line);
        background: #f1e2cf;
        padding: 6px;
      }}
      .photo img {{
        width: 100%;
        height: 170px;
        object-fit: cover;
        display: block;
        border: 1px solid #c9b095;
      }}
      .photo figcaption {{
        margin-top: 6px;
        color: #6a4d37;
        font-size: 13px;
        text-align: center;
      }}
      .info {{
        margin-top: 12px;
        border-top: 1px dashed var(--line);
        padding-top: 9px;
        color: #5e6f86;
        font-size: 12px;
      }}
      pre {{
        margin: 0;
        border: 1px solid var(--line);
        background: #f8efe2;
        padding: 10px;
        overflow-x: auto;
        color: #3b2a1f;
      }}
      code {{
        background: #f1e3d0;
        border: 1px solid var(--line);
        padding: 1px 4px;
        font-family: Consolas, "Courier New", monospace;
      }}
      @media (max-width: 800px) {{
        .grid, .gallery {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>
  </head>
  <body>
    <header class="top">
      <div class="inner">
        <div class="brand">OakTrail Journal</div>
        <div class="sub">Cozy blog mode • Legacy page loader</div>
      </div>
      <nav class="nav">{nav_html}</nav>
    </header>

    <main class="main">
      <section class="content">
        {content}
        {info_block}
      </section>
    </main>
  </body>
</html>
"""


def load_page(page_name: str) -> tuple[str, str, int]:
    if not page_name:
        page_name = "home.php"

    target = os.path.join(PAGES_DIR, page_name)
    try:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
    except Exception as exc:
        html = f"""
<h2>Page Load Error</h2>
<p>Unable to load the requested page.</p>
<pre>{escape(str(exc))}</pre>
"""
        info = f"Current parameter: page={escape(page_name)}"
        return html, info, 404

    if page_name.endswith(".php"):
        rendered = raw
    else:
        rendered = f"<pre>{escape(raw)}</pre>"

    info = f"Current parameter: page={escape(page_name)}"
    return rendered, info, 200


class Handler(BaseHTTPRequestHandler):
    server_version = "FileViewerV2/3.0"

    def send_html(self, body: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def send_file(self, path: str) -> None:
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            self.send_html(render_layout("home.php", "<h2>404</h2><p>Media not found.</p>"), 404)
            return

        content_type, _ = mimetypes.guess_type(path)
        if not content_type:
            content_type = "application/octet-stream"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/media/"):
            rel_path = parsed.path[len("/media/") :]
            norm = os.path.normpath(rel_path)
            if norm.startswith(".."):
                self.send_html(render_layout("home.php", "<h2>403</h2><p>Access denied.</p>"), 403)
                return
            media_target = os.path.join(MEDIA_DIR, norm)
            self.send_file(media_target)
            return

        if parsed.path != "/":
            self.send_html(render_layout("home.php", "<h2>404</h2><p>Page not found.</p>"), 404)
            return

        params = parse_qs(parsed.query)
        page_name = params.get("page", ["home.php"])[0]
        content, info, status = load_page(page_name)
        self.send_html(render_layout(page_name, content, info), status)


if __name__ == "__main__":
    ensure_flag()
    prepare_pages()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[file_viewer_v2] listening on http://{HOST}:{PORT}")
    server.serve_forever()

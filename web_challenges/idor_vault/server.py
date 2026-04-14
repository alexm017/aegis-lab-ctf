#!/usr/bin/env python3
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from urllib.parse import urlparse

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8105"))
FLAG = os.getenv("FLAG", "flag{idor_exposes_admin_data}")

OWNERS = {
    1000: {"name": "Operations Admin", "email": "ops-admin@workspace.local"},
    1001: {"name": "Amelia Popescu", "email": "amelia@workspace.local"},
    1002: {"name": "Radu M.", "email": "radu@workspace.local"},
}

# This app is intentionally single-workspace and has no login wall.
ACTIVE_OWNER_ID = 1001

NOTES = {
    7001: {
        "owner_id": 1001,
        "title": "Campus Lab Network Checklist",
        "content": (
            "- Verify patch levels on lab endpoints\n"
            "- Rotate workshop VM snapshots\n"
            "- Confirm backup sync after classes"
        ),
        "updated_at": "2026-03-17 08:45 UTC",
    },
    7002: {
        "owner_id": 1001,
        "title": "Weekly Training Agenda",
        "content": (
            "Monday: recon fundamentals\n"
            "Wednesday: web exploit lab\n"
            "Friday: incident simulation drill"
        ),
        "updated_at": "2026-03-18 15:12 UTC",
    },
    7003: {
        "owner_id": 1002,
        "title": "Reverse Lab TODO",
        "content": "Finish unpacker script and validate sample traces before next practice.",
        "updated_at": "2026-03-18 11:04 UTC",
    },
    7004: {
        "owner_id": 1000,
        "title": "Quarterly Vault Rotation",
        "content": f"Primary recovery token: {FLAG}",
        "updated_at": "2026-03-19 06:25 UTC",
    },
    7005: {
        "owner_id": 1002,
        "title": "Tooling Request",
        "content": "Need one extra debugging workstation for binary patching exercises.",
        "updated_at": "2026-03-20 09:31 UTC",
    },
    7006: {
        "owner_id": 1001,
        "title": "Sponsor Meeting Notes",
        "content": "Prepare short demo of the student training platform and monitoring stack.",
        "updated_at": "2026-03-20 18:09 UTC",
    },
}

NEXT_NOTE_ID = max(NOTES) + 1
STATE_LOCK = Lock()


def now_utc_string() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def render_index_page() -> str:
    owner = OWNERS[ACTIVE_OWNER_ID]
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Workspace Notes</title>
    <style>
      :root {{
        --bg: #efe2cf;
        --bg-dark: #dcc6ac;
        --panel: #f7f0e5;
        --panel-2: #f1e6d5;
        --line: #a5896d;
        --line-soft: #c8b399;
        --text: #392a1f;
        --text-soft: #715948;
        --accent: #a56d3a;
        --accent-2: #7e4d27;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        min-height: 100vh;
        background:
          radial-gradient(circle at 15% 12%, #f6ecdf 0%, var(--bg) 38%),
          repeating-linear-gradient(
            0deg,
            rgba(255, 255, 255, 0.04) 0px,
            rgba(255, 255, 255, 0.04) 1px,
            rgba(0, 0, 0, 0.02) 1px,
            rgba(0, 0, 0, 0.02) 2px
          );
        color: var(--text);
        font-family: "Trebuchet MS", Tahoma, Verdana, Arial, sans-serif;
      }}
      .topbar {{
        height: 54px;
        border-bottom: 1px solid var(--line);
        background: linear-gradient(180deg, #e7d3b7 0%, var(--bg-dark) 100%);
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 16px;
      }}
      .brand {{
        color: #4a341f;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 13px;
      }}
      .brand b {{
        font-size: 15px;
      }}
      .user {{
        font-size: 12px;
        color: #5a4636;
      }}
      .layout {{
        display: grid;
        grid-template-columns: 310px 1fr;
        min-height: calc(100vh - 54px);
      }}
      .sidebar {{
        border-right: 1px solid var(--line);
        background: #ead8bf;
        padding: 11px;
      }}
      .panel {{
        border: 1px solid var(--line-soft);
        background: var(--panel);
      }}
      .panel-head {{
        border-bottom: 1px solid var(--line-soft);
        background: var(--panel-2);
        color: #5d4737;
        padding: 9px 10px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-size: 12px;
      }}
      .panel-body {{
        padding: 10px;
      }}
      #search {{
        width: 100%;
        border: 1px solid #b69d82;
        background: #fff9f0;
        color: var(--text);
        padding: 7px 8px;
        font-family: Consolas, "Courier New", monospace;
      }}
      #notes-list {{
        list-style: none;
        margin: 9px 0 0;
        padding: 0;
        max-height: calc(100vh - 250px);
        overflow-y: auto;
      }}
      #notes-list li + li {{
        margin-top: 8px;
      }}
      #notes-list button {{
        width: 100%;
        text-align: left;
        border: 1px solid #bea58a;
        background: #fff9ef;
        color: #3f2f23;
        padding: 8px 9px;
        cursor: pointer;
      }}
      #notes-list button:hover {{
        background: #f7ebda;
      }}
      #notes-list .meta {{
        display: block;
        margin-top: 4px;
        color: #7a624f;
        font-size: 11px;
      }}
      .main {{
        padding: 13px;
        background: rgba(255, 252, 248, 0.4);
      }}
      .viewer {{
        border: 1px solid var(--line-soft);
        background: var(--panel);
        min-height: 340px;
      }}
      .viewer-head {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;
        border-bottom: 1px solid var(--line-soft);
        background: var(--panel-2);
        padding: 9px 11px;
      }}
      #note-title {{
        margin: 0;
        font-size: 20px;
        color: #513a2c;
      }}
      #note-meta {{
        color: #7a624f;
        font-size: 12px;
      }}
      #note-content {{
        margin: 0;
        padding: 12px;
        white-space: pre-wrap;
        line-height: 1.45;
        color: #3a2b20;
        font-family: "Trebuchet MS", Tahoma, Verdana, Arial, sans-serif;
      }}
      .empty {{
        color: #8a715e;
        font-size: 13px;
      }}
      .compose {{
        margin-top: 10px;
        border: 1px solid var(--line-soft);
        background: var(--panel);
      }}
      .compose-head {{
        border-bottom: 1px solid var(--line-soft);
        background: var(--panel-2);
        color: #5d4737;
        padding: 9px 11px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-size: 12px;
      }}
      .compose form {{
        padding: 11px;
      }}
      .compose label {{
        display: block;
        margin-bottom: 5px;
        color: #6b5443;
        font-size: 12px;
      }}
      .compose input,
      .compose textarea {{
        width: 100%;
        border: 1px solid #b69d82;
        background: #fffaf1;
        color: #3d2d21;
        padding: 8px;
        font-family: Consolas, "Courier New", monospace;
      }}
      .compose textarea {{
        min-height: 120px;
        resize: vertical;
      }}
      .compose button {{
        margin-top: 8px;
        border: 1px solid var(--accent-2);
        background: var(--accent);
        color: #fff6ea;
        font-weight: 700;
        padding: 8px 12px;
        cursor: pointer;
      }}
      .status {{
        margin-top: 8px;
        color: #7e4d27;
        font-size: 12px;
        min-height: 16px;
      }}
      @media (max-width: 920px) {{
        .layout {{
          grid-template-columns: 1fr;
        }}
        .sidebar {{
          border-right: 0;
          border-bottom: 1px solid var(--line);
        }}
        #notes-list {{
          max-height: 220px;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="topbar">
      <div class="brand"><b>Workspace Notes</b> • Team Notebook</div>
      <div class="user">{owner["name"]} • {owner["email"]}</div>
    </div>

    <div class="layout">
      <aside class="sidebar">
        <div class="panel">
          <div class="panel-head">My Notes</div>
          <div class="panel-body">
            <input id="search" type="text" placeholder="Search by title">
            <ul id="notes-list"></ul>
          </div>
        </div>
      </aside>

      <main class="main">
        <section class="viewer">
          <div class="viewer-head">
            <h1 id="note-title">Select a note</h1>
            <span id="note-meta"></span>
          </div>
          <pre id="note-content" class="empty">Pick a note from the left panel to read it.</pre>
        </section>

        <section class="compose">
          <div class="compose-head">Create Note</div>
          <form id="create-note-form">
            <label for="new-title">Title</label>
            <input id="new-title" name="title" maxlength="90" required>

            <label for="new-content" style="margin-top:8px;">Content</label>
            <textarea id="new-content" name="content" required></textarea>

            <button type="submit">Save Note</button>
            <div id="create-status" class="status"></div>
          </form>
        </section>
      </main>
    </div>

    <script>
      const notesList = document.getElementById("notes-list");
      const searchInput = document.getElementById("search");
      const noteTitle = document.getElementById("note-title");
      const noteMeta = document.getElementById("note-meta");
      const noteContent = document.getElementById("note-content");
      const createForm = document.getElementById("create-note-form");
      const createStatus = document.getElementById("create-status");

      let notesIndex = [];

      function escapeHtml(s) {{
        return String(s)
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;");
      }}

      function setViewer(title, meta, content, isEmpty = false) {{
        noteTitle.textContent = title;
        noteMeta.textContent = meta || "";
        noteContent.textContent = content || "";
        if (isEmpty) {{
          noteContent.classList.add("empty");
        }} else {{
          noteContent.classList.remove("empty");
        }}
      }}

      async function loadNotes() {{
        const res = await fetch("/api/notes");
        const data = await res.json();
        notesIndex = Array.isArray(data.notes) ? data.notes : [];
        renderList(notesIndex);
      }}

      function renderList(items) {{
        notesList.innerHTML = "";
        if (!items.length) {{
          const li = document.createElement("li");
          li.className = "empty";
          li.textContent = "No notes available.";
          notesList.appendChild(li);
          return;
        }}

        for (const note of items) {{
          const li = document.createElement("li");
          const btn = document.createElement("button");
          btn.type = "button";
          btn.dataset.id = String(note.id);
          btn.innerHTML = `
            <strong>${{escapeHtml(note.title)}}</strong>
            <span class="meta">#${{note.id}} • ${{escapeHtml(note.updated_at)}}</span>
          `;
          btn.addEventListener("click", () => openNote(note.id));
          li.appendChild(btn);
          notesList.appendChild(li);
        }}
      }}

      async function openNote(noteId) {{
        const res = await fetch(`/api/notes/${{noteId}}`);
        if (!res.ok) {{
          setViewer("Note not found", "", "The selected note could not be loaded.", true);
          return;
        }}
        const data = await res.json();
        setViewer(data.title, `${{data.owner_name}} • ${{data.updated_at}} • #${{data.id}}`, data.content);
      }}

      searchInput.addEventListener("input", () => {{
        const q = searchInput.value.trim().toLowerCase();
        if (!q) {{
          renderList(notesIndex);
          return;
        }}
        renderList(notesIndex.filter((n) =>
          n.title.toLowerCase().includes(q) || String(n.id).includes(q)
        ));
      }});

      createForm.addEventListener("submit", async (ev) => {{
        ev.preventDefault();
        createStatus.textContent = "";

        const payload = {{
          title: document.getElementById("new-title").value.trim(),
          content: document.getElementById("new-content").value.trim(),
        }};

        if (!payload.title || !payload.content) {{
          createStatus.textContent = "Title and content are required.";
          return;
        }}

        const res = await fetch("/api/notes", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(payload),
        }});

        if (!res.ok) {{
          createStatus.textContent = "Could not save note.";
          return;
        }}

        const data = await res.json();
        document.getElementById("new-title").value = "";
        document.getElementById("new-content").value = "";
        createStatus.textContent = "Note saved.";
        await loadNotes();
        await openNote(data.id);
      }});

      loadNotes();
    </script>
  </body>
</html>
"""


def notes_for_active_owner():
    out = []
    for note_id, note in NOTES.items():
        if note["owner_id"] == ACTIVE_OWNER_ID:
            out.append({"id": note_id, "title": note["title"], "updated_at": note["updated_at"]})
    out.sort(key=lambda row: row["id"], reverse=True)
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "IDORVault/3.0"

    def send_html(self, body: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def send_json(self, payload: dict, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            return {}
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self.send_html(render_index_page())
            return

        if path == "/api/notes":
            self.send_json({"ok": True, "notes": notes_for_active_owner()})
            return

        if path.startswith("/api/notes/"):
            tail = path[len("/api/notes/") :]
            if "/" in tail or not tail.isdigit():
                self.send_json({"ok": False, "error": "not found"}, status=404)
                return

            note_id = int(tail)
            note = NOTES.get(note_id)
            if note is None:
                self.send_json({"ok": False, "error": "note not found"}, status=404)
                return

            # Intentional access control flaw: direct object fetch without ownership check.
            owner = OWNERS.get(note["owner_id"], {"name": "Unknown"})
            self.send_json(
                {
                    "ok": True,
                    "id": note_id,
                    "title": note["title"],
                    "content": note["content"],
                    "updated_at": note["updated_at"],
                    "owner_name": owner["name"],
                }
            )
            return

        self.send_html("<h1>404</h1>", status=404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/notes":
            self.send_json({"ok": False, "error": "not found"}, status=404)
            return

        body = self.read_json_body()
        title = str(body.get("title", "")).strip()
        content = str(body.get("content", "")).strip()

        if not title or not content:
            self.send_json({"ok": False, "error": "title and content are required"}, status=400)
            return
        if len(title) > 90:
            self.send_json({"ok": False, "error": "title too long"}, status=400)
            return

        global NEXT_NOTE_ID
        with STATE_LOCK:
            note_id = NEXT_NOTE_ID
            NEXT_NOTE_ID += 1
            NOTES[note_id] = {
                "owner_id": ACTIVE_OWNER_ID,
                "title": title,
                "content": content,
                "updated_at": now_utc_string(),
            }

        self.send_json({"ok": True, "id": note_id}, status=201)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[idor_vault] listening on http://{HOST}:{PORT}")
    server.serve_forever()

#!/usr/bin/env python3
import os
import re
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8103"))
FLAG = os.getenv("FLAG", "flag{template_context_escape}")

MACRO_RE = re.compile(r"\{\{(.*?)\}\}")

CAMPAIGNS = {
    "ops_bulletin": {
        "title": "Ops Bulletin 24.11",
        "owner": "night-shift",
        "priority": "medium",
        "template": (
            "== Ops Bulletin ==\n"
            "Owner: {{owner}}\n"
            "Priority: {{priority}}\n"
            "Window: 23:00-01:00 UTC\n"
            "Patch queue: 8 nodes pending\n"
            "\n"
            "Summary:\n"
            " - Legacy renderer still active\n"
            " - Macro sandbox in compatibility mode\n"
            "\n"
            "Signed: %%signature%%\n"
        ),
    },
    "retro_mailer": {
        "title": "Retro Mailer Rollout",
        "owner": "release-team",
        "priority": "high",
        "template": (
            "== Mailer Notice ==\n"
            "Owner: {{owner}}\n"
            "Priority: {{priority}}\n"
            "Deployment ring: ring-b\n"
            "Status: staged\n"
            "\n"
            "Notes:\n"
            " - Footer blocks are still interpreted by legacy macro pass\n"
            " - Keep signatures short\n"
            "\n"
            "Signed: %%signature%%\n"
        ),
    },
    "incident_042": {
        "title": "Incident 042 - Cache Drift",
        "owner": "incident-core",
        "priority": "high",
        "template": (
            "== Incident 042 ==\n"
            "Owner: {{owner}}\n"
            "Priority: {{priority}}\n"
            "Issue: stale cache nodes serving archived context\n"
            "ETA: 35m\n"
            "\n"
            "Action:\n"
            " - Rebuild template cache index\n"
            " - Verify macro output in preview lane\n"
            "\n"
            "Signed: %%signature%%\n"
        ),
    },
}


def render_macros(raw: str, scope: dict) -> str:
    def sub(match: re.Match) -> str:
        expr = match.group(1).strip()
        try:
            return str(
                eval(  # noqa: S307 - intentionally unsafe for challenge behavior
                    expr,
                    {"__builtins__": {}},
                    scope,
                )
            )
        except Exception as exc:
            return f"[macro-error: {exc}]"

    return MACRO_RE.sub(sub, raw)


def page(selected_id: str, signature: str, rendered: str, status_line: str) -> str:
    rows = []
    for key, value in CAMPAIGNS.items():
        marker = ">>" if key == selected_id else "  "
        rows.append(
            f"<tr><td class='mark'>{marker}</td><td><a href='/?campaign={escape(key)}'>{escape(value['title'])}</a></td></tr>"
        )
    rows_html = "".join(rows)

    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Legacy Campaign Console</title>
    <style>
      body {{
        margin: 0;
        background: #0f1318;
        color: #d4d8dd;
        font-family: "Courier New", monospace;
      }}
      .frame {{
        width: min(1180px, 96vw);
        margin: 16px auto;
        border: 2px solid #5a6570;
        background: #1a2028;
        box-shadow: 0 0 0 2px #0d1015 inset;
      }}
      .topbar {{
        background: #2f3f52;
        color: #dce8f6;
        border-bottom: 2px solid #5a6570;
        padding: 8px 12px;
        font-size: 14px;
        letter-spacing: 0.3px;
      }}
      .status {{
        background: #151b22;
        border-bottom: 1px solid #3c4650;
        color: #9fb2c7;
        padding: 6px 12px;
        font-size: 13px;
      }}
      .grid {{
        display: grid;
        grid-template-columns: 290px 1fr;
        gap: 12px;
        padding: 12px;
      }}
      .panel {{
        border: 1px solid #4f5a66;
        background: #151b22;
      }}
      .panel .head {{
        background: #243140;
        color: #dbe8f5;
        border-bottom: 1px solid #4f5a66;
        padding: 7px 9px;
        font-size: 13px;
        font-weight: 700;
      }}
      .panel .body {{
        padding: 10px;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
      }}
      td {{
        border-bottom: 1px dashed #33404e;
        padding: 6px 4px;
      }}
      td.mark {{
        width: 30px;
        color: #8cc5ff;
      }}
      a {{
        color: #9ac7f8;
        text-decoration: none;
      }}
      a:hover {{
        text-decoration: underline;
      }}
      label {{
        display: block;
        margin-bottom: 6px;
        color: #b7c5d6;
        font-size: 13px;
      }}
      input, select {{
        width: 100%;
        box-sizing: border-box;
        border: 1px solid #4b5764;
        background: #0f141a;
        color: #d8e3ef;
        padding: 8px;
        font-family: inherit;
      }}
      .btn {{
        margin-top: 9px;
        border: 1px solid #6c7e90;
        background: #2d3c4d;
        color: #dbe8f6;
        padding: 8px 12px;
        font-family: inherit;
        cursor: pointer;
      }}
      .btn:hover {{
        background: #364a60;
      }}
      pre {{
        margin: 0;
        border: 1px solid #495666;
        background: #0f141a;
        color: #d5dde7;
        min-height: 320px;
        padding: 10px;
        overflow-x: auto;
        white-space: pre-wrap;
      }}
      .hint {{
        margin-top: 10px;
        font-size: 12px;
        color: #8fa0b4;
      }}
      @media (max-width: 860px) {{
        .grid {{ grid-template-columns: 1fr; }}
        pre {{ min-height: 220px; }}
      }}
    </style>
  </head>
  <body>
    <div class="frame">
      <div class="topbar">Legacy Campaign Console :: preview-lab</div>
      <div class="status">{escape(status_line)}</div>
      <div class="grid">
        <div class="panel">
          <div class="head">Archive</div>
          <div class="body">
            <table>{rows_html}</table>
          </div>
        </div>
        <div class="panel">
          <div class="head">Preview Lane</div>
          <div class="body">
            <form method="GET" action="/preview">
              <label>Campaign</label>
              <select name="campaign">
                <option value="ops_bulletin" {"selected" if selected_id == "ops_bulletin" else ""}>Ops Bulletin 24.11</option>
                <option value="retro_mailer" {"selected" if selected_id == "retro_mailer" else ""}>Retro Mailer Rollout</option>
                <option value="incident_042" {"selected" if selected_id == "incident_042" else ""}>Incident 042 - Cache Drift</option>
              </select>
              <label style="margin-top:10px;">Footer Signature</label>
              <input name="signature" value="{escape(signature, quote=True)}">
              <button class="btn" type="submit">Render Preview</button>
            </form>
            <div class="hint">Legacy mode still parses inline macros in generated text blocks.</div>
            <div style="margin-top:12px;">
              <pre>{escape(rendered)}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </body>
</html>
"""


def pick_campaign(campaign_id: str) -> tuple[str, dict]:
    if campaign_id in CAMPAIGNS:
        return campaign_id, CAMPAIGNS[campaign_id]
    fallback = "ops_bulletin"
    return fallback, CAMPAIGNS[fallback]


class Handler(BaseHTTPRequestHandler):
    server_version = "TemplateLeak/2.0"

    def send_html(self, body: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path not in ("/", "/preview"):
            self.send_html("<!doctype html><h1>404</h1>", 404)
            return

        campaign_id = params.get("campaign", ["ops_bulletin"])[0]
        signature = params.get("signature", ["ops-team"])[0]
        campaign_id, campaign = pick_campaign(campaign_id)

        template = campaign["template"].replace("%%signature%%", signature)
        scope = {
            "owner": campaign["owner"],
            "priority": campaign["priority"],
            "flag": FLAG,
            "len": len,
            "str": str,
        }
        rendered = render_macros(template, scope)

        if parsed.path == "/preview":
            status_line = (
                "renderer=legacy-macro :: cache=warm :: lane=preview :: mode=compat"
            )
        else:
            status_line = (
                "renderer=legacy-macro :: cache=warm :: lane=preview :: mode=compat"
            )
        self.send_html(page(campaign_id, signature, rendered, status_line))


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[template_leak] listening on http://{HOST}:{PORT}")
    server.serve_forever()


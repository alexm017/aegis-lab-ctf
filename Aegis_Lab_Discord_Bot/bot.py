#!/usr/bin/env python3
"""Aegis Lab Discord bot.

Features:
- /events: list upcoming Discord scheduled events.
- /calendar: show a monthly calendar and mark event days.
- /addevent /editevent /deleteevent: role-gated event management.
- /socials: list Aegis Lab social platforms.
- /ask: answer questions using OpenAI Responses API.
"""

from __future__ import annotations

import asyncio
import calendar
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import aiohttp
import discord
from discord import app_commands
from dotenv import load_dotenv


LOGGER = logging.getLogger("aegis-lab-bot")
DEFAULT_EVENT_MANAGER_ROLE_ID = 1483074945561923584
INFO_COMMAND_ID = 1483088330966040677
EVENTS_COMMAND_ID = 1483072763425194134
ASK_COMMAND_ID = 1483070857243787348
EVENT_MODE_ONLINE = "online"
EVENT_MODE_ONSITE = "onsite"
EVENT_META_PREFIX = "[AegisMeta]"
EVENT_META_DB_FILENAME = "event_meta.json"
DEFAULT_EVENTS_PAGE_URL = "https://aegislab.ro/events"
MAIN_SITE_BASE_URL = "https://aegislab.ro/"
DEFAULT_CTF_URL = "https://ctf.aegislab.ro/"
DEFAULT_CONTACT_EMAIL = "contact@aegislab.ro"
DEFAULT_APPLICATION_FORM_RO_URL = "https://forms.gle/D8Yv7RE3ZJp8Uc6g9"
DEFAULT_APPLICATION_FORM_EN_URL = "https://forms.gle/5dq9svpiGNDMUCxp8"
PROJECTS_ROOT = Path(__file__).resolve().parents[2]
MAIN_SITE_ROOT = PROJECTS_ROOT / "ZeroSec_Main"
MAIN_SITE_MEMBERS_PATH = MAIN_SITE_ROOT / "data" / "members.json"
MAIN_SITE_CONTENT_PATH = MAIN_SITE_ROOT / "data" / "site_content.json"
UPTIME_SITES_PATH = PROJECTS_ROOT / "OpenML_Alphabit" / "discord_uptime_bot" / "sites.json"
try:
    ROMANIA_TZ = ZoneInfo("Europe/Bucharest")
except Exception:  # noqa: BLE001
    ROMANIA_TZ = timezone(timedelta(hours=2))


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name, "").strip()
    if raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        LOGGER.warning("Invalid %s=%r, using default=%s", name, raw, default)
        return default
    if value < minimum:
        LOGGER.warning("Invalid %s=%s (<%s), using default=%s", name, value, minimum, default)
        return default
    return value


def env_optional_int(name: str, minimum: int = 1) -> Optional[int]:
    raw = os.getenv(name, "").strip()
    if raw == "":
        return None
    try:
        value = int(raw)
    except ValueError:
        LOGGER.warning("Invalid %s=%r, ignoring", name, raw)
        return None
    if value < minimum:
        LOGGER.warning("Invalid %s=%s (<%s), ignoring", name, value, minimum)
        return None
    return value


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if raw == "":
        return default
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    LOGGER.warning("Invalid %s=%r, using default=%s", name, raw, default)
    return default


def format_event_status(status: discord.EventStatus) -> str:
    mapping = {
        discord.EventStatus.scheduled: "Scheduled",
        discord.EventStatus.active: "Active",
        discord.EventStatus.completed: "Completed",
        discord.EventStatus.cancelled: "Cancelled",
    }
    return mapping.get(status, str(status))


def to_ro(dt: datetime) -> datetime:
    return dt.astimezone(ROMANIA_TZ)


def ro_date_text(dt: Optional[datetime]) -> str:
    if dt is None:
        return "TBD"
    return to_ro(dt).strftime("%d-%m-%Y")


def ro_time_text(dt: Optional[datetime]) -> str:
    if dt is None:
        return "TBD"
    ro_dt = to_ro(dt)
    return f"{ro_dt.strftime('%H:%M')} ({ro_dt.strftime('%Z')}, Ora Romaniei)"


def ro_month_day_text(dt: Optional[datetime]) -> str:
    if dt is None:
        return "TBD"
    ro_dt = to_ro(dt)
    return f"{calendar.month_name[ro_dt.month]} {ro_dt.day}"


def ro_input_to_utc(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    local_dt = datetime(year, month, day, hour, minute, tzinfo=ROMANIA_TZ)
    return local_dt.astimezone(timezone.utc)


def render_calendar(year: int, month: int, marked_days: set[int]) -> str:
    cal = calendar.Calendar(firstweekday=0)
    col_width = 5
    total_width = col_width * 7
    title = f"{calendar.month_name[month]} {year}"
    weekday_headers = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    lines = [
        title.center(total_width),
        "".join(day.center(col_width) for day in weekday_headers),
    ]

    for week in cal.monthdayscalendar(year, month):
        tokens: list[str] = []
        for day in week:
            if day == 0:
                token = " " * col_width
            elif day in marked_days:
                token = f"[{day:02d}]*"
            else:
                token = f" {day:02d}  "
            tokens.append(token)
        lines.append("".join(tokens).rstrip())

    return "\n".join(lines)


def normalize_http_url(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must start with http:// or https://")
    return value


def normalize_optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in {"none", "null", "n/a", "-"}:
        return None
    return text


def normalize_event_mode(raw: Optional[str]) -> str:
    mode = (raw or EVENT_MODE_ONSITE).strip().lower().replace("_", "-").replace(" ", "-")
    if mode in {"on-site", "onsite"}:
        return EVENT_MODE_ONSITE
    if mode in {"online"}:
        return EVENT_MODE_ONLINE
    if mode not in {EVENT_MODE_ONSITE, EVENT_MODE_ONLINE}:
        raise ValueError("Mode must be `onsite` or `online`")
    return mode


def strip_event_meta(description: Optional[str]) -> str:
    if not description:
        return ""
    idx = description.rfind(EVENT_META_PREFIX)
    if idx < 0:
        return description.strip()
    return description[:idx].strip()


def event_info_line(events_page_url: str) -> str:
    return f"More information you can find on the Aegis Lab Website: [Events Page]({events_page_url})"


def build_public_event_description(base_description: Optional[str], events_page_url: str) -> str:
    header = event_info_line(events_page_url)
    clean = (base_description or "").strip()
    if clean:
        return truncate(f"{header}\n\n{clean}", 1000)
    return truncate(header, 1000)


def strip_public_event_info(description: Optional[str], events_page_url: str) -> str:
    text = (description or "").strip()
    if not text:
        return ""
    header = event_info_line(events_page_url)
    if text.startswith(header):
        return text[len(header) :].strip()
    return text


def parse_event_meta(description: Optional[str]) -> Optional[dict[str, Any]]:
    if not description:
        return None
    idx = description.rfind(EVENT_META_PREFIX)
    if idx < 0:
        return None

    payload = description[idx + len(EVENT_META_PREFIX) :].strip()
    if not payload:
        return None
    try:
        meta = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(meta, dict):
        return None
    return meta


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def slash_mention(name: str, command_id: int) -> str:
    return f"</{name}:{command_id}>"


def extract_openai_text(payload: dict[str, Any]) -> str:
    top = payload.get("output_text")
    if isinstance(top, str) and top.strip():
        return top.strip()

    chunks: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for part in item.get("content", []):
            if not isinstance(part, dict):
                continue
            part_type = part.get("type")
            text = part.get("text")
            if part_type in {"output_text", "text"} and isinstance(text, str) and text.strip():
                chunks.append(text.strip())

    return "\n".join(chunks).strip()


def split_for_discord(text: str, chunk_size: int = 1900) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    current = ""
    for paragraph in text.split("\n"):
        candidate = paragraph if not current else f"{current}\n{paragraph}"
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
        if len(paragraph) <= chunk_size:
            current = paragraph
        else:
            start = 0
            while start < len(paragraph):
                end = min(start + chunk_size, len(paragraph))
                chunks.append(paragraph[start:end])
                start = end
            current = ""

    if current:
        chunks.append(current)
    return chunks


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except Exception:  # noqa: BLE001
        pass
    return {}


def load_json_list(path: Path) -> list[Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return raw
    except Exception:  # noqa: BLE001
        pass
    return []


def load_team_links(site_content: dict[str, Any]) -> dict[str, str]:
    main_url = str(site_content.get("main_url", MAIN_SITE_BASE_URL)).strip() or MAIN_SITE_BASE_URL
    ctf_url = str(site_content.get("ctf_url", DEFAULT_CTF_URL)).strip() or DEFAULT_CTF_URL
    contact_email = str(site_content.get("contact_email", DEFAULT_CONTACT_EMAIL)).strip() or DEFAULT_CONTACT_EMAIL
    application_form_ro = (
        str(site_content.get("application_form_ro_url", DEFAULT_APPLICATION_FORM_RO_URL)).strip()
        or DEFAULT_APPLICATION_FORM_RO_URL
    )
    application_form_en = (
        str(site_content.get("application_form_en_url", DEFAULT_APPLICATION_FORM_EN_URL)).strip()
        or DEFAULT_APPLICATION_FORM_EN_URL
    )
    return {
        "main_url": main_url,
        "ctf_url": ctf_url,
        "contact_email": contact_email,
        "application_form_ro_url": application_form_ro,
        "application_form_en_url": application_form_en,
    }


def extract_listed_member_names(members_data: dict[str, Any]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    def add_name(raw: Any) -> None:
        if raw is None:
            return
        name = str(raw).strip()
        if not name:
            return
        key = name.casefold()
        if key in seen:
            return
        seen.add(key)
        names.append(name)

    founder = members_data.get("founder")
    if isinstance(founder, dict):
        add_name(founder.get("name"))

    candidate_lists: list[Any] = []
    for key in ("team", "members", "team_members", "core_team"):
        value = members_data.get(key)
        if isinstance(value, list):
            candidate_lists.append(value)

    for member_list in candidate_lists:
        for item in member_list:
            if isinstance(item, dict):
                add_name(item.get("name"))

    return names


def build_aegis_lab_ask_context() -> str:
    members_data = load_json_object(MAIN_SITE_MEMBERS_PATH)
    site_content = load_json_object(MAIN_SITE_CONTENT_PATH)
    uptime_sites = load_json_list(UPTIME_SITES_PATH)

    founder = members_data.get("founder")
    team_list = members_data.get("team") if isinstance(members_data.get("team"), list) else []
    founder_name = ""
    if isinstance(founder, dict):
        founder_name = str(founder.get("name", "")).strip()

    member_names = extract_listed_member_names(members_data)

    total_members = len(member_names)
    team_member_count = max(len(member_names) - (1 if founder_name else 0), 0)
    team_roles: list[str] = []
    for member in team_list:
        if not isinstance(member, dict):
            continue
        role = str(member.get("role", "")).strip()
        if role and role not in team_roles:
            team_roles.append(role)

    links = load_team_links(site_content)
    main_url = links["main_url"].rstrip("/") + "/"
    ctf_url = links["ctf_url"]
    contact_email = links["contact_email"]
    application_form_ro_url = links["application_form_ro_url"]
    application_form_en_url = links["application_form_en_url"]
    school_address = str(site_content.get("school_address", "")).strip()
    maps_url = str(site_content.get("google_maps_url", "")).strip()
    home_intro = str(site_content.get("home_intro", "")).strip()
    about_intro = str(site_content.get("about_intro", "")).strip()

    ctf_challenge_catalog: list[dict[str, Any]] = [
        {"name": "Cookie Jar", "category": "Web", "value": 100},
        {"name": "SQL Rookie", "category": "Web", "value": 150},
        {"name": "Template Leak", "category": "Web", "value": 220},
        {"name": "SSRF Notes", "category": "Web", "value": 300},
        {"name": "IDOR Vault", "category": "Web", "value": 180},
        {"name": "Ping Commander", "category": "Web", "value": 200},
        {"name": "File Viewer v2", "category": "Web", "value": 220},
        {"name": "License Check", "category": "Reverse", "value": 100},
        {"name": "XOR Strings", "category": "Reverse", "value": 160},
        {"name": "Jump Maze", "category": "Reverse", "value": 240},
        {"name": "Patch Me", "category": "Reverse", "value": 320},
        {"name": "Stack Smash 101", "category": "Pwn", "value": 120},
        {"name": "Format Frenzy", "category": "Pwn", "value": 190},
        {"name": "GOTcha", "category": "Pwn", "value": 270},
        {"name": "ROP Warmup", "category": "Pwn", "value": 360},
        {"name": "Caesar Returns", "category": "Crypto", "value": 100},
        {"name": "Repeating Key", "category": "Crypto", "value": 170},
        {"name": "Broken RSA", "category": "Crypto", "value": 260},
        {"name": "Hash Oracle", "category": "Crypto", "value": 330},
        {"name": "Suspicious PNG", "category": "Forensics", "value": 100},
        {"name": "Browser Trail", "category": "Forensics", "value": 160},
        {"name": "Memory Whisper", "category": "Forensics", "value": 250},
        {"name": "Log Poison", "category": "Forensics", "value": 320},
    ]

    challenge_hint_map: dict[str, list[str]] = {
        "Cookie Jar": [
            "Check how session/role is represented in browser cookies.",
            "Try changing client-side state and then refresh protected pages.",
        ],
        "SQL Rookie": [
            "Treat the login form as an input-validation problem, not just credentials.",
            "Observe how quote characters and boolean logic affect responses.",
        ],
        "Template Leak": [
            "Look at how user input is rendered back to the page.",
            "Test harmless template expressions and compare output carefully.",
        ],
        "SSRF Notes": [
            "Find any feature where the server fetches a URL for you.",
            "Pivot from external URLs to internal addresses step by step.",
        ],
        "IDOR Vault": [
            "Watch identifiers in requests and try neighboring values.",
            "Check whether authorization is enforced per object, not just per login.",
        ],
        "Ping Commander": [
            "Study how command input is passed to the backend.",
            "Try subtle payload variations to probe filtering behavior.",
        ],
        "File Viewer v2": [
            "Focus on path handling and normalization edge cases.",
            "Try traversal patterns and encoded separators to test boundaries.",
        ],
        "License Check": [
            "Trace the local validation branch before patching anything.",
        ],
        "XOR Strings": [
            "Look for repeating byte patterns and recover the XOR key first.",
        ],
        "Jump Maze": [
            "Build a control-flow map; indirect jumps are the main obstacle.",
        ],
        "Patch Me": [
            "Find one critical conditional and patch the smallest possible bytes.",
        ],
        "Stack Smash 101": [
            "Find the exact overflow offset, then control the return pointer.",
        ],
        "Format Frenzy": [
            "Use the format primitive first for leaks, then for controlled writes.",
        ],
        "GOTcha": [
            "Inspect GOT/PLT resolution and target a function pointer overwrite.",
        ],
        "ROP Warmup": [
            "Collect reliable gadgets and chain a minimal first-stage payload.",
        ],
        "Caesar Returns": [
            "Test shift patterns and validate with frequency/common-word checks.",
        ],
        "Repeating Key": [
            "Estimate key length first; decryption gets easier after that.",
        ],
        "Broken RSA": [
            "Inspect public parameters for weak setup before brute forcing anything.",
        ],
        "Hash Oracle": [
            "Compare oracle outputs across controlled input mutations.",
        ],
        "Suspicious PNG": [
            "Inspect PNG chunks/metadata before deeper steganography tools.",
        ],
        "Browser Trail": [
            "Timeline the browser artifacts (history/cache/downloads) for pivots.",
        ],
        "Memory Whisper": [
            "Start with memory strings and then correlate suspicious structures.",
        ],
        "Log Poison": [
            "Trace unusual log entries by source, encoding, and timestamp.",
        ],
    }

    challenge_lines: list[str] = []
    challenge_hint_lines: list[str] = []
    core_lines: list[str] = []
    for site in uptime_sites:
        if not isinstance(site, dict):
            continue
        category = str(site.get("category", "")).strip()
        name = str(site.get("name", "")).strip()
        url = str(site.get("url", "")).strip()
        if not name or not url:
            continue
        line = f"- {name}: {url}"
        if category == "CTF Web Challenges":
            challenge_lines.append(line)
        elif category == "Core Websites":
            core_lines.append(line)

    category_to_names: dict[str, list[str]] = {}
    for entry in ctf_challenge_catalog:
        category = str(entry.get("category", "")).strip()
        name = str(entry.get("name", "")).strip()
        if not category or not name:
            continue
        category_to_names.setdefault(category, []).append(name)

    catalog_lines: list[str] = []
    for category in ["Web", "Reverse", "Pwn", "Crypto", "Forensics"]:
        names = category_to_names.get(category, [])
        if not names:
            continue
        catalog_lines.append(f"- {category} ({len(names)}): {', '.join(names)}")

    for entry in ctf_challenge_catalog:
        name = str(entry.get("name", "")).strip()
        category = str(entry.get("category", "")).strip()
        value = entry.get("value")
        if not name:
            continue
        hints = challenge_hint_map.get(name, [])
        if hints:
            hint_text = " | ".join([f"H{i + 1}: {hint}" for i, hint in enumerate(hints[:2])])
            challenge_hint_lines.append(f"- {name} [{category}, {value} pts]: {hint_text}")

    lines = [
        "Aegis Lab internal knowledge base (latest local project data):",
        "",
        "Identity:",
        "- Team name: Aegis Lab.",
        "- Type: High school cybersecurity team.",
        "- Team training cadence: weekly meetings and regular practical CTF practice.",
        "- Platform cadence: new challenges are published monthly on the team CTF website.",
        "",
        "Core links:",
        f"- Main website: {main_url}",
        f"- CTF website: {ctf_url}",
        f"- Members page: {main_url}members",
        f"- Events page: {main_url}events",
        f"- About page: {main_url}about",
        f"- Team CTF website: {ctf_url}",
        "",
        "Website context:",
        "- Main site includes team presentation, about page, members, events, and team CTF section.",
        "- CTF site is the team platform used for practical challenge training.",
        "",
        "Join links:",
        f"- Application form (RO): {application_form_ro_url}",
        f"- Application form (EN / international): {application_form_en_url}",
        f"- Contact email: {contact_email}",
    ]

    if core_lines:
        lines.extend(["", "Monitored core websites:"])
        lines.extend(core_lines)

    if challenge_lines:
        lines.extend(["", "CTF web challenge endpoints:"])
        lines.extend(challenge_lines)
    if catalog_lines:
        lines.extend(["", "CTF challenge categories currently on the platform:"])
        lines.extend(catalog_lines)
    if challenge_hint_lines:
        lines.extend(["", "CTF challenge tiny hints (non-spoiler):"])
        lines.extend(challenge_hint_lines)

    lines.extend(
        [
            "",
            "Team profile:",
            f"- Total listed members: {total_members} (Founder: {1 if founder_name else 0}, Team Members: {team_member_count}).",
            f"- Founder: {founder_name or 'Not specified'}",
            f"- Listed members (names): {', '.join(member_names) if member_names else 'No listed members'}",
            f"- Focus roles present: {', '.join(team_roles) if team_roles else 'Not specified'}",
            f"- Contact email: {contact_email}",
        ]
    )

    if school_address:
        lines.append(f"- School/team address: {school_address}")
    if maps_url:
        lines.append(f"- Map link: {maps_url}")
    if home_intro:
        lines.append(f"- Home intro summary: {home_intro}")
    if about_intro:
        lines.append(f"- About summary: {about_intro}")

    lines.extend(
        [
            "",
            "Behavior rules for answers:",
            "- Prefer these facts for team-specific questions (members, links, pages, websites, and scope).",
            "- If a requested fact is not in this knowledge base, say it is not currently available instead of guessing.",
            "- For member count questions, use the exact count above.",
            "- Do not claim the platform has only web challenges; it includes multiple categories listed above.",
            "- Use tiny hints only (non-spoiler) for challenge help unless the user explicitly asks for more detail.",
            "- For join/apply/recruit questions, always include both RO and EN application form links plus contact email.",
            "- Keep answers practical, precise, and short by default (2-4 sentences or a very short bullet list).",
        ]
    )
    return "\n".join(lines)


@dataclass
class BotConfig:
    token: str
    openai_api_key: Optional[str]
    openai_model: str
    openai_max_output_tokens: int
    target_guild_id: Optional[int]
    enable_message_content_intent: bool
    event_manager_role_id: int
    events_page_url: str


class AegisLabBot(discord.Client):
    def __init__(self, config: BotConfig) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.messages = True
        intents.message_content = config.enable_message_content_intent
        super().__init__(intents=intents)

        self.config = config
        self.tree = app_commands.CommandTree(self)
        self.http_session: Optional[aiohttp.ClientSession] = None
        self._commands_registered = False
        self._synced_command_ids: dict[str, int] = {}
        self._metadata_cleanup_done = False
        self._event_meta_lock = asyncio.Lock()
        self._event_meta_path = Path(__file__).resolve().parent / EVENT_META_DB_FILENAME
        self._event_meta: dict[str, dict[str, Any]] = {}

    async def setup_hook(self) -> None:
        timeout = aiohttp.ClientTimeout(total=60)
        self.http_session = aiohttp.ClientSession(timeout=timeout)
        self._load_event_meta_db()

        self._register_commands()
        await self._sync_commands()

    async def _sync_commands(self) -> None:
        try:
            if self.config.target_guild_id:
                guild = discord.Object(id=self.config.target_guild_id)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                LOGGER.info(
                    "Synced %s command(s) to guild %s",
                    len(synced),
                    self.config.target_guild_id,
                )
            else:
                synced = await self.tree.sync()
                LOGGER.info("Synced %s global command(s)", len(synced))
            self._synced_command_ids = {
                command.name: command.id
                for command in synced
                if isinstance(getattr(command, "id", None), int) and int(command.id) > 0
            }
        except Exception:  # noqa: BLE001
            LOGGER.exception("Failed to sync slash commands")

    def _command_mention(self, name: str, fallback_id: Optional[int] = None) -> str:
        command_id = self._synced_command_ids.get(name)
        if isinstance(command_id, int) and command_id > 0:
            return slash_mention(name, command_id)
        if isinstance(fallback_id, int) and fallback_id > 0:
            return slash_mention(name, fallback_id)
        return f"`/{name}`"

    def _load_event_meta_db(self) -> None:
        if not self._event_meta_path.exists():
            self._event_meta = {}
            return

        try:
            raw = json.loads(self._event_meta_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._event_meta = {str(k): v for k, v in raw.items() if isinstance(v, dict)}
            else:
                self._event_meta = {}
        except Exception:  # noqa: BLE001
            LOGGER.exception("Failed to load %s; starting with empty event metadata", self._event_meta_path)
            self._event_meta = {}

    async def _persist_event_meta_db_locked(self) -> None:
        payload = json.dumps(self._event_meta, ensure_ascii=True, indent=2)
        self._event_meta_path.write_text(payload + "\n", encoding="utf-8")

    def _normalize_event_meta(self, raw: dict[str, Any], fallback_place: str) -> dict[str, Any]:
        raw_mode = normalize_optional_text(raw.get("mode")) or EVENT_MODE_ONSITE
        try:
            mode = normalize_event_mode(raw_mode)
        except ValueError:
            mode = EVENT_MODE_ONSITE

        place = normalize_optional_text(raw.get("place")) or fallback_place or "Aegis Lab"
        map_url = normalize_optional_text(raw.get("map_url"))
        online_url = normalize_optional_text(raw.get("online_url"))

        if mode == EVENT_MODE_ONLINE:
            place = "Online"

        return {
            "mode": mode,
            "place": place,
            "map_url": map_url,
            "online_url": online_url,
        }

    async def _set_event_meta(self, event_id: int, meta: dict[str, Any], fallback_place: str = "Aegis Lab") -> None:
        normalized = self._normalize_event_meta(meta, fallback_place=fallback_place)
        async with self._event_meta_lock:
            self._event_meta[str(event_id)] = normalized
            await self._persist_event_meta_db_locked()

    async def _delete_event_meta(self, event_id: int) -> None:
        key = str(event_id)
        async with self._event_meta_lock:
            if key in self._event_meta:
                self._event_meta.pop(key, None)
                await self._persist_event_meta_db_locked()

    async def _resolve_event_meta(self, event: discord.ScheduledEvent) -> dict[str, Any]:
        fallback_place = normalize_optional_text(event.location) or "Aegis Lab"
        key = str(event.id)

        async with self._event_meta_lock:
            stored = self._event_meta.get(key)
        if isinstance(stored, dict):
            return self._normalize_event_meta(stored, fallback_place=fallback_place)

        # Backward compatibility: migrate old metadata that was appended in descriptions.
        parsed = parse_event_meta(event.description)
        if isinstance(parsed, dict):
            normalized = self._normalize_event_meta(parsed, fallback_place=fallback_place)
            await self._set_event_meta(event.id, normalized, fallback_place=fallback_place)

            clean_desc = strip_event_meta(event.description) or None
            if clean_desc != (event.description or None):
                try:
                    await event.edit(
                        description=clean_desc,
                        reason="Remove internal metadata from event description",
                    )
                except Exception:  # noqa: BLE001
                    LOGGER.exception("Failed to clean legacy metadata from event %s description", event.id)

            return normalized

        inferred_mode = EVENT_MODE_ONLINE if fallback_place.lower() == "online" else EVENT_MODE_ONSITE
        fallback_meta = {
            "mode": inferred_mode,
            "place": "Online" if inferred_mode == EVENT_MODE_ONLINE else fallback_place,
            "map_url": None,
            "online_url": None,
        }
        return self._normalize_event_meta(fallback_meta, fallback_place=fallback_place)

    async def _cleanup_legacy_event_metadata(self) -> None:
        target_guilds: list[discord.Guild] = []
        if self.config.target_guild_id:
            guild = self.get_guild(self.config.target_guild_id)
            if guild is not None:
                target_guilds.append(guild)
        else:
            target_guilds.extend(self.guilds)

        for guild in target_guilds:
            try:
                events = await guild.fetch_scheduled_events()
            except Exception:  # noqa: BLE001
                LOGGER.exception("Failed to fetch scheduled events for metadata cleanup in guild %s", guild.id)
                continue

            for event in events:
                if parse_event_meta(event.description):
                    await self._resolve_event_meta(event)

    async def _user_has_role(self, interaction: discord.Interaction, role_id: int) -> bool:
        guild = interaction.guild
        if guild is None or interaction.user is None:
            return False

        member: Optional[discord.Member] = interaction.user if isinstance(interaction.user, discord.Member) else None
        if member is None:
            try:
                member = await guild.fetch_member(interaction.user.id)
            except Exception:  # noqa: BLE001
                LOGGER.exception("Failed to fetch member %s for role check", interaction.user.id)
                return False

        return any(role.id == role_id for role in member.roles)

    async def on_ready(self) -> None:
        LOGGER.info("Logged in as %s (%s)", self.user, self.user.id if self.user else "unknown")
        if not self.config.enable_message_content_intent:
            LOGGER.warning(
                "ENABLE_MESSAGE_CONTENT_INTENT is false. "
                "Mention/!ask message replies are disabled; slash /ask still works."
            )
        if not self._metadata_cleanup_done:
            self._metadata_cleanup_done = True
            try:
                await self._cleanup_legacy_event_metadata()
            except Exception:  # noqa: BLE001
                LOGGER.exception("Legacy event metadata cleanup failed")

    def _extract_question_from_message(self, message: discord.Message) -> Optional[str]:
        content = (message.content or "").strip()
        if not content or not self.user:
            return None

        if content.lower().startswith("!ask "):
            question = content[5:].strip()
            return question or None

        mention = f"<@{self.user.id}>"
        mention_nick = f"<@!{self.user.id}>"
        if content.startswith(mention):
            question = content[len(mention) :].strip()
            return question or None
        if content.startswith(mention_nick):
            question = content[len(mention_nick) :].strip()
            return question or None
        return None

    async def on_message(self, message: discord.Message) -> None:
        if not self.config.enable_message_content_intent:
            return
        if message.author.bot:
            return
        if not self.config.openai_api_key:
            return

        question = self._extract_question_from_message(message)
        if not question:
            return

        try:
            async with message.channel.typing():
                answer = await self.ask_openai(question)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("OpenAI message request failed: %s", exc)
            await message.reply("I could not process that right now. Try again in a moment.", mention_author=False)
            return

        if not answer:
            answer = "I could not generate an answer for that."

        for index, chunk in enumerate(split_for_discord(answer, chunk_size=1900)):
            if index == 0:
                await message.reply(chunk, mention_author=False)
            else:
                await message.channel.send(chunk)

    async def close(self) -> None:
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
        await super().close()

    def _register_commands(self) -> None:
        if self._commands_registered:
            return
        self._commands_registered = True

        @self.tree.command(name="info", description="Show available bot commands")
        async def info(interaction: discord.Interaction) -> None:
            embed = discord.Embed(
                title="Aegis Lab Info & Commands",
                color=discord.Color.blurple(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.description = "\n".join(
                [
                    "Aegis Lab **Main Website** - [Link](https://aegislab.ro/)",
                    "Aegis Lab **CTF Website** - [Link](https://ctf.aegislab.ro/)",
                    "",
                    "**Commands**",
                    f"{self._command_mention('info', INFO_COMMAND_ID)} - Show this command list.",
                    f"{self._command_mention('socials')} - Show Aegis Lab social links.",
                    f"{self._command_mention('events', EVENTS_COMMAND_ID)} `[limit]` - List upcoming server events.",
                    f"{self._command_mention('calendar')} `[month] [year]` - Show monthly calendar with event days.",
                    f"{self._command_mention('ask', ASK_COMMAND_ID)} `<question>` - Ask the Aegis Lab assistant.",
                ]
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="socials", description="Show Aegis Lab social platforms")
        async def socials(interaction: discord.Interaction) -> None:
            embed = discord.Embed(
                title="Aegis Lab Socials",
                color=discord.Color.blurple(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.description = "\n".join(
                [
                    "Connect with Aegis Lab:",
                    "",
                    "- Contact (Email): [Link](mailto:contact@aegislab.ro)",
                    "- YouTube: [Link](https://www.youtube.com/@AegisLabTeam)",
                    "- Instagram: [Link](https://www.instagram.com/aegislab_team/)",
                    "- LinkedIn: [Link](https://www.linkedin.com/company/aegis-labteam/)",
                ]
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="events", description="List upcoming server events")
        @app_commands.describe(limit="How many upcoming events to show (1-20)")
        async def events(interaction: discord.Interaction, limit: app_commands.Range[int, 1, 20] = 10) -> None:
            guild = interaction.guild
            if guild is None:
                await interaction.response.send_message("Use this command inside your Discord server.", ephemeral=True)
                return

            await interaction.response.defer(thinking=True)

            try:
                scheduled = await guild.fetch_scheduled_events()
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Failed to fetch scheduled events: %s", exc)
                await interaction.followup.send("Could not fetch scheduled events.", ephemeral=True)
                return

            now = datetime.now(timezone.utc)
            upcoming = [
                event
                for event in scheduled
                if event.start_time and event.start_time >= now and event.status == discord.EventStatus.scheduled
            ]
            upcoming.sort(key=lambda event: event.start_time)

            if not upcoming:
                await interaction.followup.send("No upcoming scheduled events found.")
                return

            embeds: list[discord.Embed] = []
            for event in upcoming[:limit]:
                meta = await self._resolve_event_meta(event)
                details = [
                    f"More information you can find on the Aegis Lab Website: [Events Page]({self.config.events_page_url})",
                    "",
                    f"Date: `{ro_date_text(event.start_time)}`",
                    f"Time: `{ro_time_text(event.start_time)}`",
                ]
                if event.end_time:
                    details.append(f"Ends: `{ro_time_text(event.end_time)}`")

                if meta["mode"] == EVENT_MODE_ONLINE:
                    if meta["online_url"]:
                        details.append(f"Online: [Join Link]({meta['online_url']})")
                    else:
                        details.append("Online: Meeting link will be provided soon.")
                else:
                    place = meta["place"] or "Aegis Lab"
                    if meta["map_url"]:
                        details.append(f"On-site: `{place}` | [Location Link]({meta['map_url']})")
                    else:
                        details.append(f"On-site: `{place}`")

                details.append(f"Status: `{format_event_status(event.status)}`")
                details.append(f"Event ID: `{event.id}`")

                base_desc = strip_public_event_info(strip_event_meta(event.description), self.config.events_page_url)
                if base_desc:
                    details.append("")
                    details.append(f"Event Description: {truncate(base_desc, 250)}")

                event_embed = discord.Embed(
                    title=f"{event.name}",
                    description="\n".join(details),
                    color=discord.Color.blue(),
                    timestamp=now,
                )
                embeds.append(event_embed)

            for idx in range(0, len(embeds), 10):
                await interaction.followup.send(embeds=embeds[idx : idx + 10])

        @self.tree.command(name="calendar", description="Show monthly calendar and event days")
        @app_commands.describe(month="Month number (1-12)", year="Year (e.g. 2026)")
        async def calendar_view(
            interaction: discord.Interaction,
            month: Optional[app_commands.Range[int, 1, 12]] = None,
            year: Optional[app_commands.Range[int, 2000, 2100]] = None,
        ) -> None:
            guild = interaction.guild
            if guild is None:
                await interaction.response.send_message("Use this command inside your Discord server.", ephemeral=True)
                return

            await interaction.response.defer(thinking=True)

            now = datetime.now(timezone.utc)
            selected_month = month or now.month
            selected_year = year or now.year

            try:
                scheduled = await guild.fetch_scheduled_events()
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Failed to fetch events for calendar: %s", exc)
                await interaction.followup.send("Could not fetch events for calendar.", ephemeral=True)
                return

            month_events = [
                event
                for event in scheduled
                if event.start_time and event.status != discord.EventStatus.cancelled
                and to_ro(event.start_time).year == selected_year
                and to_ro(event.start_time).month == selected_month
            ]
            month_events.sort(key=lambda event: event.start_time)

            marked_days = {to_ro(event.start_time).day for event in month_events if event.start_time}
            cal_text = render_calendar(selected_year, selected_month, marked_days)

            embed = discord.Embed(
                title=f"{guild.name} | {calendar.month_name[selected_month]} {selected_year}",
                description=f"```text\n{cal_text}\n```\n`[DD]*` marks days with scheduled events.",
                color=discord.Color.dark_teal(),
                timestamp=now,
            )

            if month_events:
                lines = []
                for event in month_events[:12]:
                    lines.append(
                        f"`{ro_month_day_text(event.start_time)}` {ro_time_text(event.start_time)} - **{event.name}**"
                    )
                if len(month_events) > 12:
                    lines.append(f"... and {len(month_events) - 12} more event(s)")
                embed.add_field(name="Events This Month", value="\n".join(lines), inline=False)
            else:
                embed.add_field(name="Events This Month", value="No scheduled events in this month.", inline=False)

            await interaction.followup.send(embed=embed)

        @self.tree.command(name="addevent", description="Create a scheduled server event (Events Manager role only)")
        @app_commands.describe(
            title="Event title",
            year="Start year in Romania timezone (e.g. 2026)",
            month="Start month in Romania timezone (1-12)",
            day="Start day in Romania timezone (1-31)",
            hour="Start hour in Romania timezone (0-23)",
            minute="Start minute in Romania timezone (0-59)",
            duration_minutes="Event duration in minutes",
            mode="Event mode: onsite or online",
            description="Optional event description",
            location_name="On-site place name (default: Aegis Lab)",
            location_link="On-site location link (Google Maps etc.)",
            online_link="Online meeting link",
        )
        async def addevent(
            interaction: discord.Interaction,
            title: app_commands.Range[str, 1, 100],
            year: app_commands.Range[int, 2024, 2100],
            month: app_commands.Range[int, 1, 12],
            day: app_commands.Range[int, 1, 31],
            hour: app_commands.Range[int, 0, 23],
            minute: app_commands.Range[int, 0, 59],
            duration_minutes: app_commands.Range[int, 15, 1440],
            mode: str = EVENT_MODE_ONSITE,
            description: Optional[app_commands.Range[str, 1, 1000]] = None,
            location_name: app_commands.Range[str, 1, 100] = "Aegis Lab",
            location_link: Optional[app_commands.Range[str, 1, 500]] = None,
            online_link: Optional[app_commands.Range[str, 1, 500]] = None,
        ) -> None:
            guild = interaction.guild
            if guild is None:
                await interaction.response.send_message("Use this command inside your Discord server.", ephemeral=True)
                return

            await interaction.response.defer(thinking=True, ephemeral=True)

            allowed = await self._user_has_role(interaction, self.config.event_manager_role_id)
            if not allowed:
                await interaction.followup.send(
                    "You need the `Aegis Lab Events Manager` role to use this command.",
                    ephemeral=True,
                )
                return

            try:
                start_dt = ro_input_to_utc(int(year), int(month), int(day), int(hour), int(minute))
            except ValueError as exc:
                await interaction.followup.send(f"Invalid date/time: {exc}", ephemeral=True)
                return

            now_utc = datetime.now(timezone.utc)
            if start_dt <= now_utc:
                await interaction.followup.send(
                    "Start time must be in the future (Ora Romaniei).",
                    ephemeral=True,
                )
                return

            try:
                normalized_mode = normalize_event_mode(mode)
                normalized_location_link = normalize_http_url(location_link)
                normalized_online_link = normalize_http_url(online_link)
            except ValueError as exc:
                await interaction.followup.send(str(exc), ephemeral=True)
                return

            end_dt = start_dt + timedelta(minutes=int(duration_minutes))
            display_location = location_name.strip() if normalized_mode == EVENT_MODE_ONSITE else "Online"
            event_meta = {
                "mode": normalized_mode,
                "place": location_name.strip(),
                "map_url": normalized_location_link,
                "online_url": normalized_online_link,
            }
            clean_description = build_public_event_description(description, self.config.events_page_url)

            try:
                event = await guild.create_scheduled_event(
                    name=title.strip(),
                    start_time=start_dt,
                    end_time=end_dt,
                    description=clean_description,
                    entity_type=discord.EntityType.external,
                    privacy_level=discord.PrivacyLevel.guild_only,
                    location=display_location,
                    reason=f"Created by {interaction.user} via /addevent",
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Failed to create scheduled event: %s", exc)
                await interaction.followup.send(
                    "Could not create the event. Check bot permissions (`Manage Events`) and try again.",
                    ephemeral=True,
                )
                return

            await self._set_event_meta(event.id, event_meta, fallback_place=location_name.strip())

            await interaction.followup.send(
                (
                    f"Created event **{event.name}**\\n"
                    f"Date: `{ro_date_text(event.start_time)}`\\n"
                    f"Time: `{ro_time_text(event.start_time)}`\\n"
                    f"Ends: `{ro_time_text(event.end_time)}`\\n"
                    f"Mode: `{normalized_mode}`\\n"
                    f"Event ID: `{event.id}`\\n"
                    "It will now appear in `/events` and `/calendar`."
                ),
                ephemeral=True,
            )

        @self.tree.command(name="deleteevent", description="Delete a scheduled event (Events Manager role only)")
        @app_commands.describe(event_id="Event ID from /events")
        async def deleteevent(interaction: discord.Interaction, event_id: app_commands.Range[str, 17, 22]) -> None:
            guild = interaction.guild
            if guild is None:
                await interaction.response.send_message("Use this command inside your Discord server.", ephemeral=True)
                return

            await interaction.response.defer(thinking=True, ephemeral=True)

            allowed = await self._user_has_role(interaction, self.config.event_manager_role_id)
            if not allowed:
                await interaction.followup.send(
                    "You need the `Aegis Lab Events Manager` role to use this command.",
                    ephemeral=True,
                )
                return

            event_id_clean = event_id.strip()
            if not event_id_clean.isdigit():
                await interaction.followup.send("Event ID must contain only digits.", ephemeral=True)
                return

            try:
                event_id_int = int(event_id_clean)
                event = await guild.fetch_scheduled_event(event_id_int)
            except Exception:
                await interaction.followup.send("Event not found for that ID.", ephemeral=True)
                return

            try:
                event_name = event.name
                await event.delete(reason=f"Deleted by {interaction.user} via /deleteevent")
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Failed to delete event %s: %s", event_id, exc)
                await interaction.followup.send(
                    "Could not delete the event. Check bot permissions (`Manage Events`).",
                    ephemeral=True,
                )
                return

            await self._delete_event_meta(event_id_int)
            await interaction.followup.send(f"Deleted event `{event_name}` (`{event_id_int}`).", ephemeral=True)

        @self.tree.command(name="editevent", description="Edit a scheduled event (Events Manager role only)")
        @app_commands.describe(
            event_id="Event ID from /events",
            title="New title",
            year="New start year in Romania timezone",
            month="New start month in Romania timezone (1-12)",
            day="New start day in Romania timezone (1-31)",
            hour="New start hour in Romania timezone (0-23)",
            minute="New start minute in Romania timezone (0-59)",
            duration_minutes="New duration in minutes",
            mode="onsite or online",
            description="New description text",
            location_name="New on-site place name",
            location_link="New on-site location link",
            online_link="New online meeting link",
        )
        async def editevent(
            interaction: discord.Interaction,
            event_id: app_commands.Range[str, 17, 22],
            title: Optional[app_commands.Range[str, 1, 100]] = None,
            year: Optional[app_commands.Range[int, 2024, 2100]] = None,
            month: Optional[app_commands.Range[int, 1, 12]] = None,
            day: Optional[app_commands.Range[int, 1, 31]] = None,
            hour: Optional[app_commands.Range[int, 0, 23]] = None,
            minute: Optional[app_commands.Range[int, 0, 59]] = None,
            duration_minutes: Optional[app_commands.Range[int, 15, 1440]] = None,
            mode: Optional[str] = None,
            description: Optional[app_commands.Range[str, 1, 1000]] = None,
            location_name: Optional[app_commands.Range[str, 1, 100]] = None,
            location_link: Optional[app_commands.Range[str, 1, 500]] = None,
            online_link: Optional[app_commands.Range[str, 1, 500]] = None,
        ) -> None:
            guild = interaction.guild
            if guild is None:
                await interaction.response.send_message("Use this command inside your Discord server.", ephemeral=True)
                return

            await interaction.response.defer(thinking=True, ephemeral=True)

            allowed = await self._user_has_role(interaction, self.config.event_manager_role_id)
            if not allowed:
                await interaction.followup.send(
                    "You need the `Aegis Lab Events Manager` role to use this command.",
                    ephemeral=True,
                )
                return

            event_id_clean = event_id.strip()
            if not event_id_clean.isdigit():
                await interaction.followup.send("Event ID must contain only digits.", ephemeral=True)
                return

            try:
                event_id_int = int(event_id_clean)
                event = await guild.fetch_scheduled_event(event_id_int)
            except Exception:
                await interaction.followup.send("Event not found for that ID.", ephemeral=True)
                return

            try:
                normalized_mode = normalize_event_mode(mode) if mode is not None else None
                normalized_location_link = normalize_http_url(location_link) if location_link is not None else None
                normalized_online_link = normalize_http_url(online_link) if online_link is not None else None
            except ValueError as exc:
                await interaction.followup.send(str(exc), ephemeral=True)
                return

            existing_meta = await self._resolve_event_meta(event)
            base_desc = strip_public_event_info(strip_event_meta(event.description), self.config.events_page_url)

            start_source_utc = event.start_time or datetime.now(timezone.utc)
            start_source_local = to_ro(start_source_utc)
            new_year = int(year) if year is not None else start_source_local.year
            new_month = int(month) if month is not None else start_source_local.month
            new_day = int(day) if day is not None else start_source_local.day
            new_hour = int(hour) if hour is not None else start_source_local.hour
            new_minute = int(minute) if minute is not None else start_source_local.minute

            try:
                new_start_dt = ro_input_to_utc(new_year, new_month, new_day, new_hour, new_minute)
            except ValueError as exc:
                await interaction.followup.send(f"Invalid date/time: {exc}", ephemeral=True)
                return

            if duration_minutes is not None:
                new_duration = int(duration_minutes)
            elif event.end_time and event.start_time:
                new_duration = int(max(15, (event.end_time - event.start_time).total_seconds() // 60))
            else:
                new_duration = 60
            new_end_dt = new_start_dt + timedelta(minutes=new_duration)

            final_mode = normalized_mode or existing_meta["mode"]
            final_place = (location_name.strip() if location_name else existing_meta["place"] or "Aegis Lab")
            final_map_url = normalized_location_link if location_link is not None else existing_meta.get("map_url")
            final_online_url = normalized_online_link if online_link is not None else existing_meta.get("online_url")
            final_description = description if description is not None else base_desc

            updated_meta = {
                "mode": final_mode,
                "place": final_place,
                "map_url": final_map_url,
                "online_url": final_online_url,
            }
            updated_description = build_public_event_description(final_description, self.config.events_page_url)
            updated_location = final_place if final_mode == EVENT_MODE_ONSITE else "Online"

            try:
                updated_event = await event.edit(
                    name=(title.strip() if title else event.name),
                    start_time=new_start_dt,
                    end_time=new_end_dt,
                    description=updated_description,
                    location=updated_location,
                    reason=f"Edited by {interaction.user} via /editevent",
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Failed to edit event %s: %s", event_id_int, exc)
                await interaction.followup.send(
                    "Could not edit the event. Check bot permissions (`Manage Events`) and values.",
                    ephemeral=True,
                )
                return

            await self._set_event_meta(updated_event.id, updated_meta, fallback_place=final_place)

            await interaction.followup.send(
                (
                    f"Updated event **{updated_event.name}** (`{updated_event.id}`)\\n"
                    f"Date: `{ro_date_text(updated_event.start_time)}`\\n"
                    f"Time: `{ro_time_text(updated_event.start_time)}`\\n"
                    f"Mode: `{final_mode}`\\n"
                    "Changes are now visible in `/events` and `/calendar`."
                ),
                ephemeral=True,
            )

        @self.tree.command(name="ask", description="Ask Aegis Lab assistant (OpenAI)")
        @app_commands.describe(question="Your question")
        async def ask(interaction: discord.Interaction, question: app_commands.Range[str, 1, 1500]) -> None:
            if not self.config.openai_api_key:
                await interaction.response.send_message(
                    "OpenAI is not configured. Set OPENAI_API_KEY in the bot environment.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(thinking=True)

            try:
                answer = await self.ask_openai(question)
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("OpenAI request failed: %s", exc)
                await interaction.followup.send("OpenAI request failed right now. Please try again.", ephemeral=True)
                return

            if not answer:
                answer = "I could not generate an answer for that."

            chunks = split_for_discord(answer, chunk_size=1900)
            for index, chunk in enumerate(chunks):
                if index == 0:
                    await interaction.followup.send(chunk)
                else:
                    await interaction.followup.send(chunk)

    async def ask_openai(self, question: str) -> str:
        if not self.http_session:
            raise RuntimeError("HTTP session is not initialized")
        if not self.config.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is missing")

        quick_answer = self._rule_based_answer(question)
        if quick_answer:
            return quick_answer

        team_context = build_aegis_lab_ask_context()
        payload = {
            "model": self.config.openai_model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are the Aegis Lab Discord assistant for a high school cybersecurity team. "
                                "Answer clearly and practically. Default to short replies (2-4 sentences). "
                                "Only expand if the user explicitly asks for details. "
                                "When describing Aegis Lab, always use first-person team voice (we/our), not third person (they/their).\n\n"
                                f"{team_context}"
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": question}],
                },
            ],
            "max_output_tokens": self.config.openai_max_output_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.config.openai_api_key}",
            "Content-Type": "application/json",
        }

        async with self.http_session.post("https://api.openai.com/v1/responses", json=payload, headers=headers) as resp:
            raw = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"OpenAI API error {resp.status}: {raw[:300]}")

            data = json.loads(raw)
            return extract_openai_text(data)

    def _rule_based_answer(self, question: str) -> Optional[str]:
        normalized = " ".join(question.lower().split())

        # Avoid hijacking member-count/profile questions.
        count_terms = (
            "how many members",
            "number of members",
            "members are in",
            "members does",
            "who is in the team",
            "team members",
            "founder",
        )
        if any(term in normalized for term in count_terms):
            return None

        join_terms = (
            "how to join",
            "how can i join",
            "how do i join",
            "join aegis",
            "join aegis lab",
            "join the team",
            "apply",
            "application",
            "application form",
            "recruit",
            "recruitment",
            "become a member",
        )
        team_terms = ("aegis", "aegis lab", "team")

        if not any(term in normalized for term in join_terms):
            return None
        if not any(term in normalized for term in team_terms):
            return None

        site_content = load_json_object(MAIN_SITE_CONTENT_PATH)
        links = load_team_links(site_content)
        return (
            "To join Aegis Lab:\n"
            f"- Application form (RO): {links['application_form_ro_url']}\n"
            f"- Application form (EN / international): {links['application_form_en_url']}\n"
            f"- Contact: {links['contact_email']}"
        )


def load_config() -> BotConfig:
    load_dotenv()

    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN is required")

    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip() or None
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
    openai_max_output_tokens = env_int("OPENAI_MAX_OUTPUT_TOKENS", 500, minimum=50)
    target_guild_id = env_optional_int("TARGET_GUILD_ID", minimum=1)
    enable_message_content_intent = env_bool("ENABLE_MESSAGE_CONTENT_INTENT", True)
    event_manager_role_id = env_int(
        "EVENT_MANAGER_ROLE_ID",
        DEFAULT_EVENT_MANAGER_ROLE_ID,
        minimum=1,
    )
    events_page_url = os.getenv("EVENTS_PAGE_URL", DEFAULT_EVENTS_PAGE_URL).strip() or DEFAULT_EVENTS_PAGE_URL

    return BotConfig(
        token=token,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        openai_max_output_tokens=openai_max_output_tokens,
        target_guild_id=target_guild_id,
        enable_message_content_intent=enable_message_content_intent,
        event_manager_role_id=event_manager_role_id,
        events_page_url=events_page_url,
    )


def main() -> None:
    configure_logging()
    config = load_config()
    bot = AegisLabBot(config)
    try:
        bot.run(config.token)
    except discord.errors.PrivilegedIntentsRequired:
        if not config.enable_message_content_intent:
            raise

        LOGGER.warning(
            "Message Content Intent is not enabled in Discord Developer Portal. "
            "Restarting in slash-only mode (no mention/!ask message replies)."
        )
        fallback_config = BotConfig(
            token=config.token,
            openai_api_key=config.openai_api_key,
            openai_model=config.openai_model,
            openai_max_output_tokens=config.openai_max_output_tokens,
            target_guild_id=config.target_guild_id,
            enable_message_content_intent=False,
            event_manager_role_id=config.event_manager_role_id,
            events_page_url=config.events_page_url,
        )
        fallback_bot = AegisLabBot(fallback_config)
        fallback_bot.run(fallback_config.token)


if __name__ == "__main__":
    main()

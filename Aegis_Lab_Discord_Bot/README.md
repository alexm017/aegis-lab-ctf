# Aegis Lab Discord Bot

Discord bot for your cybersecurity team server with:
- `/events` to list upcoming server scheduled events
- `/calendar` to show a monthly event calendar
- `/socials` to show team social platform links
- `/addevent`, `/editevent`, `/deleteevent` for event management (role-gated)
- `/ask` to answer custom questions using OpenAI
- Message replies in any channel when users mention the bot or use `!ask ...`

## Important Security Note
Use the **Bot Token** from Discord Bot settings to run the bot.
Do **not** use Client Secret as bot runtime auth.

If your Client Secret was shared, regenerate it in Discord Developer Portal:
- `OAuth2 -> Reset Secret`

## 1) Invite the Bot
Using your Application ID `1483068475651002389`:

```text
https://discord.com/oauth2/authorize?client_id=1483068475651002389&scope=bot%20applications.commands
```

Grant at least these permissions:
- View Channels
- Send Messages
- Read Message History
- Use Slash Commands

## 2) Install
```bash
cd /home/alexhkit2/HACKTHEBOX/MACHINES/eCPTX/History_Websites/2026/ZeroSec_CTF/Aegis_Lab_Discord_Bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3) Configure
```bash
cp .env.example .env
```

Edit `.env`:
- `DISCORD_BOT_TOKEN` (required)
- `OPENAI_API_KEY` (required for `/ask` and mention replies)
- `OPENAI_MODEL` (default `gpt-4.1-mini`)
- `OPENAI_MAX_OUTPUT_TOKENS` (default `500`)
- `TARGET_GUILD_ID` (optional, use your server ID for instant slash command sync)
- `ENABLE_MESSAGE_CONTENT_INTENT` (set `true` for `@bot ...` and `!ask ...` in any channel)
- `EVENT_MANAGER_ROLE_ID` (role allowed to use `/addevent`, `/editevent`, `/deleteevent`)
- `EVENTS_PAGE_URL` (link shown in `/events` as “More information...”)

Also enable this in Discord Developer Portal for your bot:
- `Bot -> Privileged Gateway Intents -> Message Content Intent` (ON)

## 4) Run
```bash
source .venv/bin/activate
python bot.py
```

## Commands
- `/events [limit]`
- `/calendar [month] [year]`
- `/socials`
- `/addevent title year month day hour minute duration_minutes [mode] [description] [location_name] [location_link] [online_link]`
- `/editevent event_id [title] [year] [month] [day] [hour] [minute] [duration_minutes] [mode] [description] [location_name] [location_link] [online_link]`
- `/deleteevent event_id`
- `/ask <question>`

Time input for `/addevent` and `/editevent` is interpreted as Romania local time (Europe/Bucharest).

## Ask in Any Channel
The bot answers in any channel when:
- You mention it: `@Aegis Lab how do I harden SSH?`
- You use prefix: `!ask how to detect phishing domains`

Event management commands are restricted to members with the role ID from `EVENT_MANAGER_ROLE_ID`.

# 3xui-shop (Replit)

Telegram bot for selling VPN subscriptions, integrated with the 3X-UI panel.
Original project: https://github.com/snoups/3xui-shop

## How it runs on Replit

- Language: Python 3.12
- Entry point: `python -m app`
- Port: `5000` (aiohttp webhook server, host `0.0.0.0`)
- Workflow: `Start application`
- Telegram webhook URL is auto-derived from `REPLIT_DEV_DOMAIN` if `BOT_DOMAIN` is not set (see `app/config.py`).

## Replit-specific changes

- `app/__main__.py`: replaced `RedisStorage` with in-memory FSM (`MemoryStorage`) and a `fakeredis` instance for tasks that expect a Redis client. This removes the external Redis dependency from `docker-compose.yml`.
- `app/config.py`: `BOT_DOMAIN` falls back to `REPLIT_DEV_DOMAIN` when unset.
- `app/data/plans.json` is created from `plans.example.json` on first setup.
- Locale `.mo` files are compiled from `.po` (Babel `pybabel compile`).

## Required secrets

- `BOT_TOKEN` — Telegram bot token (from @BotFather)
- `BOT_DEV_ID` — Telegram numeric user ID of the developer/owner
- `BOT_SUPPORT_ID` — Telegram numeric user ID for support contact
- `XUI_USERNAME`, `XUI_PASSWORD` — credentials for the 3X-UI panel

Optional env vars: `BOT_PORT` (default 5000), `BOT_DOMAIN`, `LOG_LEVEL`,
plus payment‑gateway variables (`YOOKASSA_*`, `CRYPTOMUS_*`, `HELEKET_*`, `YOOMONEY_*`).

## Project layout

- `app/` — bot application (handlers, services, tasks, db, locales)
- `app/data/` — runtime data (SQLite DB, `plans.json`)
- `app/locales/` — i18n catalogs (`bot.po` / `bot.mo`)
- `scripts/` — helper shell scripts (logs, migrations, translations)

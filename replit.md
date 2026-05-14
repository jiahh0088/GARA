# GARA Discord Bot

All-in-One Economy, Casino, Clan & Fame Discord bot. Built in Python with per-guild economy, casino games, a clan competition system, fame/aura system, VC activity rewards, and an in-game shop.

## Run & Operate

- **Bot entry point:** `python main.py`
- **Workflow:** `GARA Discord Bot` (console output)
- **Required secret:** `DISCORD_TOKEN` — your Discord bot token from the Developer Portal
- **Database:** SQLite (`gara.db`) — created automatically on first run

## Stack

- Python 3.11
- `discord.py` 2.x — bot framework
- `aiosqlite` — async SQLite database
- `flask` — keep-alive web server (health check endpoint)

## Where things live

- `main.py` — entire bot: config, DB, events, commands, Flask health check
- `gara.db` — SQLite database (auto-created, not committed)

## Features

- **Economy:** `.balance`, `.deposit`, `.withdraw`, `.give`, `.daily`, `.work`, `.rob`, `.leaderboard`
- **Casino:** `.slots <bet>`, `.mines start/pick/cashout/all <bet>`
- **Fame:** `.fame`, `.boost @user`, `.neg @user`, `.famous`
- **Clans:** `.clans`, `.clanstats`, `.joinclan`, `.leaveclan`, `.mygold`, `.createclan` (admin)
- **Shop:** `.shop`, `.buy <item>`
- **VC Activity:** Automatic role rewards based on voice channel hours
- **Admin:** `.givemoney`, `.takemoney`, `.setprefix`, `.setcurrency`, `.spin`, `.lockcycle`
- **Help:** `.help` (paginated button UI)
- **Battle:** `.battle @user`
- **Stats:** `.stats`

## Bot Prefix

Default: `.` (configurable per-guild with `.setprefix`)

## Architecture decisions

- Single-file bot (`main.py`) for straightforward Railway/Replit deployment
- Per-guild isolation: all economy data keyed by `(user_id, guild_id)`
- SQLite with aiosqlite for zero-dependency async persistence
- Flask keep-alive thread uses `PORT` env var (defaults to 3000) to avoid port conflicts
- Admin check: guild Administrators OR IDs listed in `GaraConfig.ADMIN_IDS`

## User preferences

- Single-file Python deployment (no splitting into cogs unless asked)

## Gotchas

- PyNaCl not installed — voice features disabled (expected, no voice commands used)
- `gara.db` is created in the working directory; on Railway, use a volume mount to persist it
- The Flask health page is at the root path `/` on the PORT the bot binds to

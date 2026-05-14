"""
═══════════════════════════════════════════════════════════════════════════════
  G A R A   D I S C O R D   B O T  — FULL FEATURE BUILD
  All-in-One Economy, Casino, Clan & Fame System
  Theme: Black/Dark | Brand: GARA
  Prefix: Per-guild configurable (default: .)
  Currency: Gara Coins (GC)
  Single-file deployment for Railway/Replit
═══════════════════════════════════════════════════════════════════════════════
"""

import discord
from discord.ext import commands, tasks
from discord.ui import View, Button, Select
import asyncio
import json
import random
import os
import datetime
from datetime import timedelta
from typing import Optional, Dict, List
import aiosqlite
from flask import Flask, jsonify
from threading import Thread
import logging
import difflib
import time

# ══════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("gara")

# ══════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════

class GaraConfig:
    BOT_NAME = "GARA"
    BOT_AVATAR_URL = ""
    EMBED_COLOR = 0x000000
    EMBED_COLOR_ACCENT = 0x1a1a1a
    EMBED_COLOR_SUCCESS = 0x00FF88
    EMBED_COLOR_FAIL = 0xFF0044
    EMBED_COLOR_WARN = 0xFFAA00

    PREFIX = "."
    CURRENCY_NAME = "Gara Coins"
    CURRENCY_ABBREV = "GC"
    CURRENCY_SYMBOL = "💎"

    STARTING_BALANCE = 1000
    STARTING_VAULT = 0
    DAILY_REWARD_MIN = 100
    DAILY_REWARD_MAX = 500
    WORK_COOLDOWN_HOURS = 4
    WORK_REWARD_MIN = 50
    WORK_REWARD_MAX = 200
    ROB_CHANCE = 0.4
    ROB_COOLDOWN_HOURS = 2

    SLOTS_EMOJIS = ["💎", "🔥", "👑", "💰", "🎯", "🎲"]
    SLOTS_JACKPOT_MULTIPLIER = 10
    SLOTS_MATCH_MULTIPLIER = 3

    FAME_AURA_START = 0
    BOOST_COOLDOWN_HOURS = 1
    NEG_COOLDOWN_HOURS = 1

    # Tier system defaults (hours, daily_coins, gamble_mult, name)
    DEFAULT_TIERS = [
        {"name": "Tier 1",    "hours": 1,  "daily": 10000,   "mult": 1.0},
        {"name": "Tier 2",    "hours": 5,  "daily": 50000,   "mult": 1.2},
        {"name": "Protected", "hours": 25, "daily": 0,       "mult": 1.5},
        {"name": "Tier X",    "hours": 35, "daily": 1000000, "mult": 2.0},
        {"name": "VIP",       "hours": 55, "daily": 5000000, "mult": 2.5},
    ]

    VC_TIER_ROLES = ["Tier 1", "Tier 2", "Protected", "Tier X", "VIP"]

    CLAN_INACTIVITY_DAYS = 7
    CLAN_DAILY_PENALTY_PERCENT = 10
    CLAN_GOLD_POOL_DAILY = 100000

    DEFAULT_CLAN_MULTS = [2.5, 2.0, 1.5]  # top 3 clans

    MULT_SHOP_PRICE = 4_000_000
    MUTE_BASE_PRICE = 150_000

    CRASH_DEFAULT_MAX = 10.0
    MESSAGE_EARN_GC = 1
    MESSAGE_EARN_COOLDOWN = 30
    VC_EARN_PER_MIN = 2

    ADMIN_IDS: List[int] = []

    TRIVIA_QUESTIONS = [
        ("What is 7 × 8?", "56"),
        ("What planet is closest to the Sun?", "mercury"),
        ("How many sides does a hexagon have?", "6"),
        ("What is the chemical symbol for gold?", "au"),
        ("What year did World War II end?", "1945"),
        ("What is the capital of France?", "paris"),
        ("How many continents are there?", "7"),
        ("What is the fastest land animal?", "cheetah"),
        ("How many bones in the adult human body?", "206"),
        ("What gas do plants absorb?", "carbon dioxide"),
    ]


# ══════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════

class Database:
    def __init__(self, db_path="gara.db"):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER, guild_id INTEGER,
                    balance INTEGER DEFAULT 0, vault INTEGER DEFAULT 0,
                    aura INTEGER DEFAULT 0, impact INTEGER DEFAULT 1,
                    last_work TEXT, last_rob TEXT, last_daily TEXT,
                    last_boost TEXT, last_neg TEXT,
                    vc_hours REAL DEFAULT 0, vc_join_time TEXT,
                    weekly_messages INTEGER DEFAULT 0,
                    weekly_vc_minutes INTEGER DEFAULT 0,
                    total_messages INTEGER DEFAULT 0,
                    last_message_earn TEXT,
                    mult_bought INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            # Add columns that might not exist in older DB
            for col, defn in [
                ("weekly_messages", "INTEGER DEFAULT 0"),
                ("weekly_vc_minutes", "INTEGER DEFAULT 0"),
                ("total_messages", "INTEGER DEFAULT 0"),
                ("last_message_earn", "TEXT"),
                ("mult_bought", "INTEGER DEFAULT 0"),
            ]:
                try:
                    await db.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
                except Exception:
                    pass

            await db.execute("""
                CREATE TABLE IF NOT EXISTS clans (
                    clan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT, role_id INTEGER, guild_id INTEGER,
                    gold INTEGER DEFAULT 0,
                    weekly_messages INTEGER DEFAULT 0,
                    weekly_vc_minutes INTEGER DEFAULT 0,
                    total_messages INTEGER DEFAULT 0,
                    last_active TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name, guild_id)
                )
            """)
            for col, defn in [
                ("weekly_messages", "INTEGER DEFAULT 0"),
                ("weekly_vc_minutes", "INTEGER DEFAULT 0"),
                ("total_messages", "INTEGER DEFAULT 0"),
            ]:
                try:
                    await db.execute(f"ALTER TABLE clans ADD COLUMN {col} {defn}")
                except Exception:
                    pass

            await db.execute("""
                CREATE TABLE IF NOT EXISTS clan_members (
                    user_id INTEGER, clan_id INTEGER, guild_id INTEGER,
                    personal_gold INTEGER DEFAULT 0,
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, clan_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS daily_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    clan_id INTEGER, date TEXT,
                    message_count INTEGER DEFAULT 0,
                    percentage REAL DEFAULT 0,
                    UNIQUE(clan_id, date)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    user_id INTEGER, guild_id INTEGER, item_id TEXT, quantity INTEGER DEFAULT 1,
                    PRIMARY KEY (user_id, guild_id, item_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS mines_games (
                    user_id INTEGER, guild_id INTEGER,
                    bet INTEGER, grid TEXT, revealed TEXT,
                    multiplier REAL DEFAULT 1.0, active INTEGER DEFAULT 1,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS server_settings (
                    guild_id INTEGER PRIMARY KEY,
                    prefix TEXT DEFAULT '.',
                    currency_name TEXT DEFAULT 'Gara Coins',
                    currency_abbrev TEXT DEFAULT 'GC',
                    log_channel INTEGER DEFAULT 0,
                    roles_channel INTEGER DEFAULT 0,
                    roles_msg_id INTEGER DEFAULT 0,
                    activity_channel INTEGER DEFAULT 0,
                    activity_msg_id INTEGER DEFAULT 0,
                    clan_channel INTEGER DEFAULT 0,
                    clan_msg_id INTEGER DEFAULT 0,
                    blank_ui_channel INTEGER DEFAULT 0,
                    blank_ui_msg_id INTEGER DEFAULT 0,
                    blank_ui_title TEXT DEFAULT '',
                    blank_ui_desc TEXT DEFAULT '',
                    blank_ui_color TEXT DEFAULT '000000',
                    random_vc INTEGER DEFAULT 0,
                    vc_blacklist TEXT DEFAULT '[]',
                    crash_max_mult REAL DEFAULT 10.0,
                    giveaway_channel INTEGER DEFAULT 0,
                    giveaway_prize TEXT DEFAULT '',
                    clan_mults TEXT DEFAULT '[2.5, 2.0, 1.5]',
                    shop_roles TEXT DEFAULT '[]',
                    tier_config TEXT DEFAULT '[]',
                    rich_roles TEXT DEFAULT '[]',
                    last_weekly_reset TEXT DEFAULT ''
                )
            """)
            # Add new columns for older DBs
            for col, defn in [
                ("roles_channel", "INTEGER DEFAULT 0"),
                ("roles_msg_id", "INTEGER DEFAULT 0"),
                ("activity_channel", "INTEGER DEFAULT 0"),
                ("activity_msg_id", "INTEGER DEFAULT 0"),
                ("clan_channel", "INTEGER DEFAULT 0"),
                ("clan_msg_id", "INTEGER DEFAULT 0"),
                ("blank_ui_channel", "INTEGER DEFAULT 0"),
                ("blank_ui_msg_id", "INTEGER DEFAULT 0"),
                ("blank_ui_title", "TEXT DEFAULT ''"),
                ("blank_ui_desc", "TEXT DEFAULT ''"),
                ("blank_ui_color", "TEXT DEFAULT '000000'"),
                ("random_vc", "INTEGER DEFAULT 0"),
                ("vc_blacklist", "TEXT DEFAULT '[]'"),
                ("crash_max_mult", "REAL DEFAULT 10.0"),
                ("giveaway_channel", "INTEGER DEFAULT 0"),
                ("giveaway_prize", "TEXT DEFAULT ''"),
                ("clan_mults", "TEXT DEFAULT '[2.5, 2.0, 1.5]'"),
                ("shop_roles", "TEXT DEFAULT '[]'"),
                ("tier_config", "TEXT DEFAULT '[]'"),
                ("rich_roles", "TEXT DEFAULT '[]'"),
                ("last_weekly_reset", "TEXT DEFAULT ''"),
            ]:
                try:
                    await db.execute(f"ALTER TABLE server_settings ADD COLUMN {col} {defn}")
                except Exception:
                    pass

            await db.execute("""
                CREATE TABLE IF NOT EXISTS giveaways (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER, channel_id INTEGER, msg_id INTEGER,
                    prize TEXT, end_time TEXT, active INTEGER DEFAULT 1
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS clan_wars (
                    war_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    attacker_clan_id INTEGER, defender_clan_id INTEGER,
                    attacker_score INTEGER DEFAULT 0, defender_score INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    started_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_users_guild ON users(guild_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_clan_members_user ON clan_members(user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_giveaways_guild ON giveaways(guild_id, active)")
            await db.commit()
            logger.info("Database initialized")

    # ── User helpers ──

    async def get_user(self, user_id: int, guild_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM users WHERE user_id=? AND guild_id=?", (user_id, guild_id)
            ) as c:
                row = await c.fetchone()
                if not row:
                    await db.execute(
                        "INSERT INTO users (user_id,guild_id,balance,vault) VALUES (?,?,?,?)",
                        (user_id, guild_id, GaraConfig.STARTING_BALANCE, GaraConfig.STARTING_VAULT),
                    )
                    await db.commit()
                    return {"user_id": user_id, "guild_id": guild_id,
                            "balance": GaraConfig.STARTING_BALANCE, "vault": GaraConfig.STARTING_VAULT,
                            "aura": 0, "impact": 1, "vc_hours": 0.0,
                            "weekly_messages": 0, "weekly_vc_minutes": 0,
                            "total_messages": 0, "mult_bought": 0}
                cols = [d[0] for d in c.description]
                return dict(zip(cols, row))

    async def update_user(self, user_id: int, guild_id: int, **kwargs):
        async with aiosqlite.connect(self.db_path) as db:
            sets = ", ".join(f"{k}=?" for k in kwargs)
            vals = list(kwargs.values()) + [user_id, guild_id]
            await db.execute(f"UPDATE users SET {sets} WHERE user_id=? AND guild_id=?", vals)
            await db.commit()

    async def add_balance(self, user_id: int, guild_id: int, amount: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance=balance+? WHERE user_id=? AND guild_id=?",
                (amount, user_id, guild_id),
            )
            await db.commit()

    async def sub_balance(self, user_id: int, guild_id: int, amount: int):
        async with aiosqlite.connect(self.db_path) as db:
            c = await db.execute(
                "UPDATE users SET balance=balance-? WHERE user_id=? AND guild_id=? AND balance>=?",
                (amount, user_id, guild_id, amount),
            )
            await db.commit()
            return c.rowcount > 0

    async def move_to_vault(self, user_id: int, guild_id: int, amount: int):
        async with aiosqlite.connect(self.db_path) as db:
            c = await db.execute(
                "UPDATE users SET balance=balance-?,vault=vault+? WHERE user_id=? AND guild_id=? AND balance>=?",
                (amount, amount, user_id, guild_id, amount),
            )
            await db.commit()
            return c.rowcount > 0

    async def move_from_vault(self, user_id: int, guild_id: int, amount: int):
        async with aiosqlite.connect(self.db_path) as db:
            c = await db.execute(
                "UPDATE users SET balance=balance+?,vault=vault-? WHERE user_id=? AND guild_id=? AND vault>=?",
                (amount, amount, user_id, guild_id, amount),
            )
            await db.commit()
            return c.rowcount > 0

    async def transfer_balance(self, from_id: int, to_id: int, guild_id: int, amount: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("BEGIN IMMEDIATE")
            c = await db.execute(
                "UPDATE users SET balance=balance-? WHERE user_id=? AND guild_id=? AND balance>=?",
                (amount, from_id, guild_id, amount),
            )
            if c.rowcount == 0:
                await db.execute("ROLLBACK")
                return False
            await db.execute(
                "UPDATE users SET balance=balance+? WHERE user_id=? AND guild_id=?",
                (amount, to_id, guild_id),
            )
            await db.execute("COMMIT")
            return True

    async def rob_balance(self, robber_id, target_id, guild_id, stolen, fine, success):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("BEGIN IMMEDIATE")
            now = datetime.datetime.now().isoformat()
            if success:
                c = await db.execute(
                    "UPDATE users SET balance=balance-? WHERE user_id=? AND guild_id=? AND balance>=?",
                    (stolen, target_id, guild_id, stolen),
                )
                if c.rowcount == 0:
                    await db.execute("ROLLBACK")
                    return False
                await db.execute(
                    "UPDATE users SET balance=balance+?,last_rob=? WHERE user_id=? AND guild_id=?",
                    (stolen, now, robber_id, guild_id),
                )
            else:
                await db.execute(
                    "UPDATE users SET balance=MAX(0,balance-?),last_rob=? WHERE user_id=? AND guild_id=?",
                    (fine, now, robber_id, guild_id),
                )
            await db.execute("COMMIT")
            return True

    async def boost_user(self, booster_id, target_id, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.datetime.now().isoformat()
            await db.execute("UPDATE users SET aura=aura+1 WHERE user_id=? AND guild_id=?", (target_id, guild_id))
            await db.execute("UPDATE users SET last_boost=? WHERE user_id=? AND guild_id=?", (now, booster_id, guild_id))
            await db.commit()

    async def neg_user(self, negger_id, target_id, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.datetime.now().isoformat()
            await db.execute("UPDATE users SET aura=MAX(0,aura-1) WHERE user_id=? AND guild_id=?", (target_id, guild_id))
            await db.execute("UPDATE users SET last_neg=? WHERE user_id=? AND guild_id=?", (now, negger_id, guild_id))
            await db.commit()

    async def get_leaderboard(self, guild_id: int, limit: int = 10):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT user_id,balance+vault as total FROM users WHERE guild_id=? ORDER BY total DESC LIMIT ?",
                (guild_id, limit),
            ) as c:
                return await c.fetchall()

    async def get_fame_leaderboard(self, guild_id: int, limit: int = 10):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT user_id,aura,impact FROM users WHERE guild_id=? ORDER BY aura DESC,impact DESC LIMIT ?",
                (guild_id, limit),
            ) as c:
                return await c.fetchall()

    # ── Clan helpers ──

    async def get_clan(self, clan_id=None, name=None, guild_id=None):
        async with aiosqlite.connect(self.db_path) as db:
            if clan_id:
                async with db.execute("SELECT * FROM clans WHERE clan_id=?", (clan_id,)) as c:
                    row = await c.fetchone()
                    if row:
                        return dict(zip([d[0] for d in c.description], row))
            elif name and guild_id:
                async with db.execute("SELECT * FROM clans WHERE name=? AND guild_id=?", (name, guild_id)) as c:
                    row = await c.fetchone()
                    if row:
                        return dict(zip([d[0] for d in c.description], row))
            return None

    async def get_user_clan(self, user_id: int, guild_id: int = None):
        async with aiosqlite.connect(self.db_path) as db:
            if guild_id:
                async with db.execute("""
                    SELECT c.* FROM clans c
                    JOIN clan_members cm ON c.clan_id=cm.clan_id
                    WHERE cm.user_id=? AND cm.guild_id=?
                """, (user_id, guild_id)) as c:
                    row = await c.fetchone()
                    if row:
                        return dict(zip([d[0] for d in c.description], row))
            return None

    async def get_clan_leaderboard(self, guild_id: int, limit: int = 10):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM clans WHERE guild_id=? ORDER BY gold DESC LIMIT ?", (guild_id, limit)
            ) as c:
                rows = await c.fetchall()
                cols = [d[0] for d in c.description]
                return [dict(zip(cols, r)) for r in rows]

    async def get_clan_members(self, clan_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id FROM clan_members WHERE clan_id=?", (clan_id,)) as c:
                return [r[0] for r in await c.fetchall()]

    # ── Mines helpers ──

    async def get_mines_game(self, user_id: int, guild_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM mines_games WHERE user_id=? AND guild_id=? AND active=1",
                (user_id, guild_id),
            ) as c:
                row = await c.fetchone()
                if row:
                    return dict(zip([d[0] for d in c.description], row))
                return None

    async def create_mines_game(self, user_id, guild_id, bet, grid):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO mines_games(user_id,guild_id,bet,grid,revealed,multiplier,active) VALUES(?,?,?,?,?,?,?)",
                (user_id, guild_id, bet, json.dumps(grid), json.dumps([]), 1.0, 1),
            )
            await db.commit()

    async def update_mines_game(self, user_id, guild_id, revealed, multiplier):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE mines_games SET revealed=?,multiplier=? WHERE user_id=? AND guild_id=?",
                (json.dumps(revealed), multiplier, user_id, guild_id),
            )
            await db.commit()

    async def delete_mines_game(self, user_id, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM mines_games WHERE user_id=? AND guild_id=?", (user_id, guild_id))
            await db.commit()

    # ── Server settings ──

    async def get_settings(self, guild_id: int) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM server_settings WHERE guild_id=?", (guild_id,)) as c:
                row = await c.fetchone()
                if not row:
                    return {}
                return dict(zip([d[0] for d in c.description], row))

    async def set_setting(self, guild_id: int, **kwargs):
        async with aiosqlite.connect(self.db_path) as db:
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" for _ in kwargs)
            updates = ", ".join(f"{k}=excluded.{k}" for k in kwargs)
            vals = [guild_id] + list(kwargs.values())
            await db.execute(
                f"INSERT INTO server_settings(guild_id,{cols}) VALUES(?,{placeholders}) "
                f"ON CONFLICT(guild_id) DO UPDATE SET {updates}",
                vals,
            )
            await db.commit()

    # ── Giveaway helpers ──

    async def create_giveaway(self, guild_id, channel_id, msg_id, prize, end_time):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO giveaways(guild_id,channel_id,msg_id,prize,end_time,active) VALUES(?,?,?,?,?,1)",
                (guild_id, channel_id, msg_id, prize, end_time),
            )
            await db.commit()

    async def get_active_giveaways(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM giveaways WHERE active=1") as c:
                rows = await c.fetchall()
                cols = [d[0] for d in c.description]
                return [dict(zip(cols, r)) for r in rows]

    async def close_giveaway(self, giveaway_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE giveaways SET active=0 WHERE id=?", (giveaway_id,))
            await db.commit()


# ══════════════════════════════════════════
# BOT SETUP
# ══════════════════════════════════════════

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

async def prefix_callable(bot_obj, message):
    if not message.guild:
        return GaraConfig.PREFIX
    s = bot_obj.guild_settings.get(message.guild.id, {})
    return s.get("prefix", GaraConfig.PREFIX)

bot = commands.Bot(command_prefix=prefix_callable, intents=intents, help_command=None)
bot.guild_settings: Dict[int, dict] = {}
bot.leaderboard_messages: Dict[int, object] = {}
bot.lockcycles: Dict[int, dict] = {}
bot.active_crashes: Dict[int, dict] = {}   # user_id -> crash state
bot._last_cmd_time: Dict[int, float] = {}   # rate limiting
db = Database()


def get_gs(guild_id, key, default=None):
    return bot.guild_settings.get(guild_id, {}).get(key, default)

def get_currency_name(guild_id):
    return get_gs(guild_id, "currency_name", GaraConfig.CURRENCY_NAME)

def get_currency_abbrev(guild_id):
    return get_gs(guild_id, "currency_abbrev", GaraConfig.CURRENCY_ABBREV)

def get_prefix_for_guild(guild_id):
    return get_gs(guild_id, "prefix", GaraConfig.PREFIX)

def get_tiers(guild_id):
    raw = get_gs(guild_id, "tier_config", "[]")
    try:
        t = json.loads(raw) if isinstance(raw, str) else raw
        if t:
            return t
    except Exception:
        pass
    return GaraConfig.DEFAULT_TIERS

def get_clan_mults(guild_id):
    raw = get_gs(guild_id, "clan_mults", "[2.5,2.0,1.5]")
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return GaraConfig.DEFAULT_CLAN_MULTS

def is_admin(ctx):
    if ctx.author.id in GaraConfig.ADMIN_IDS:
        return True
    if ctx.guild and ctx.author.guild_permissions.administrator:
        return True
    if ctx.guild and ctx.author.guild_permissions.manage_guild:
        return True
    return False


async def get_user_tier(guild_id: int, vc_hours: float):
    tiers = get_tiers(guild_id)
    current = None
    for t in sorted(tiers, key=lambda x: x["hours"]):
        if vc_hours >= t["hours"]:
            current = t
    return current


async def get_effective_mult(user_id: int, guild_id: int):
    """Stacking: tier_mult × personal_mult × clan_rank_mult"""
    user = await db.get_user(user_id, guild_id)
    vc_hours = user.get("vc_hours", 0)
    tier = await get_user_tier(guild_id, vc_hours)
    tier_mult = tier["mult"] if tier else 1.0

    personal_mult = 2.5 if user.get("mult_bought", 0) else 1.0

    clan = await db.get_user_clan(user_id, guild_id)
    clan_mult = 1.0
    if clan:
        clans = await db.get_clan_leaderboard(guild_id, 3)
        mults = get_clan_mults(guild_id)
        for i, c in enumerate(clans):
            if c["clan_id"] == clan["clan_id"] and i < len(mults):
                clan_mult = mults[i]
                break

    return tier_mult * personal_mult * clan_mult


# ══════════════════════════════════════════
# EMBED BUILDER
# ══════════════════════════════════════════

def gara_embed(title=None, description=None, color=None, thumbnail=None, footer=None, guild_id=None):
    embed = discord.Embed(
        title=f"**{title}**" if title else None,
        description=description,
        color=color if color is not None else GaraConfig.EMBED_COLOR,
    )
    embed.set_author(name=GaraConfig.BOT_NAME, icon_url=GaraConfig.BOT_AVATAR_URL or None)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    c_name = get_currency_name(guild_id) if guild_id else GaraConfig.CURRENCY_NAME
    c_abbrev = get_currency_abbrev(guild_id) if guild_id else GaraConfig.CURRENCY_ABBREV
    embed.set_footer(
        text=footer or f"{GaraConfig.BOT_NAME} • {c_name} ({c_abbrev})",
        icon_url=GaraConfig.BOT_AVATAR_URL or None,
    )
    return embed


# ══════════════════════════════════════════
# VIEWS
# ══════════════════════════════════════════

# ── Mines Button Grid ──

class MinesView(View):
    def __init__(self, user_id, guild_id, bet, grid, revealed, multiplier):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.guild_id = guild_id
        self.bet = bet
        self.grid = grid
        self.revealed = revealed
        self.multiplier = multiplier
        self.message = None
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()
        for i in range(9):
            is_rev = i in self.revealed
            if is_rev:
                label = "💎"
                style = discord.ButtonStyle.success
                disabled = True
            else:
                label = str(i + 1)
                style = discord.ButtonStyle.secondary
                disabled = False
            btn = Button(label=label, style=style, disabled=disabled, row=i // 3)
            btn.custom_id = f"mine_{i}"
            btn.callback = self._make_callback(i)
            self.add_item(btn)
        co = Button(label=f"Cash Out ({int(self.bet * self.multiplier):,})", style=discord.ButtonStyle.primary, row=3)
        co.callback = self.cashout_callback
        self.add_item(co)

    def _make_callback(self, index):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("Not your game!", ephemeral=True)
                return
            game = await db.get_mines_game(self.user_id, self.guild_id)
            if not game:
                await interaction.response.send_message("Game expired.", ephemeral=True)
                return
            grid = json.loads(game["grid"])
            revealed = json.loads(game["revealed"])
            if index in revealed:
                await interaction.response.send_message("Already revealed!", ephemeral=True)
                return
            revealed.append(index)
            if grid[index] == "💣":
                await db.delete_mines_game(self.user_id, self.guild_id)
                grid_str = self._grid_str(grid, revealed, explode=index)
                embed = gara_embed(
                    title="💥 BOOM! You hit a mine!",
                    description=f"Lost **{self.bet:,}** {get_currency_abbrev(self.guild_id)}\n\n{grid_str}",
                    color=GaraConfig.EMBED_COLOR_FAIL, guild_id=self.guild_id,
                )
                for item in self.children:
                    item.disabled = True
                await interaction.response.edit_message(embed=embed, view=self)
                self.stop()
            else:
                new_mult = game["multiplier"] * 1.25
                await db.update_mines_game(self.user_id, self.guild_id, revealed, new_mult)
                self.revealed = revealed
                self.multiplier = new_mult
                self.grid = grid
                potential = int(self.bet * new_mult)
                grid_str = self._grid_str(grid, revealed)
                embed = gara_embed(
                    title="✅ Safe!",
                    description=f"Multiplier: **{new_mult:.2f}x** | Potential: **{potential:,}** {get_currency_abbrev(self.guild_id)}\n\n{grid_str}",
                    color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=self.guild_id,
                )
                self._build_buttons()
                await interaction.response.edit_message(embed=embed, view=self)
        return callback

    async def cashout_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        game = await db.get_mines_game(self.user_id, self.guild_id)
        if not game:
            await interaction.response.send_message("No active game.", ephemeral=True)
            return
        winnings = int(game["bet"] * game["multiplier"])
        await db.delete_mines_game(self.user_id, self.guild_id)
        await db.add_balance(self.user_id, self.guild_id, winnings)
        embed = gara_embed(
            title="💰 Cashed Out!",
            description=f"Bet: **{game['bet']:,}** | Mult: **{game['multiplier']:.2f}x**\nWon: **{winnings:,}** {get_currency_abbrev(self.guild_id)}!",
            color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=self.guild_id,
        )
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    def _grid_str(self, grid, revealed, explode=None):
        icons = []
        for i in range(9):
            if i == explode:
                icons.append("💥")
            elif i in revealed:
                icons.append("💎")
            else:
                icons.append("⬛")
        return f"{icons[0]}{icons[1]}{icons[2]}\n{icons[3]}{icons[4]}{icons[5]}\n{icons[6]}{icons[7]}{icons[8]}"


# ── Blackjack ──

DECK = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"] * 4

def card_value(hand):
    val = 0
    aces = 0
    for c in hand:
        if c in ("J","Q","K"):
            val += 10
        elif c == "A":
            aces += 1
            val += 11
        else:
            val += int(c)
    while val > 21 and aces:
        val -= 10
        aces -= 1
    return val

def hand_str(hand):
    return " ".join(f"`{c}`" for c in hand)

class BlackjackView(View):
    def __init__(self, ctx, bet, deck, player, dealer):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.bet = bet
        self.deck = deck
        self.player = player
        self.dealer = dealer

    def make_embed(self, done=False, result=""):
        dealer_show = hand_str(self.dealer) if done else f"`{self.dealer[0]}` `?`"
        desc = (
            f"**Your hand:** {hand_str(self.player)} = **{card_value(self.player)}**\n"
            f"**Dealer:** {dealer_show}"
        )
        if done:
            desc += f"\n\n{result}"
        return gara_embed(title="🃏 Blackjack", description=desc,
                          color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=self.ctx.guild.id)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        self.player.append(self.deck.pop())
        pv = card_value(self.player)
        if pv > 21:
            await db.sub_balance(self.ctx.author.id, self.ctx.guild.id, self.bet)
            for b in self.children:
                b.disabled = True
            await interaction.response.edit_message(
                embed=self.make_embed(True, f"💥 Bust! Lost **{self.bet:,}** {get_currency_abbrev(self.ctx.guild.id)}"),
                view=self)
            self.stop()
        else:
            await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.danger)
    async def stand(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        while card_value(self.dealer) < 17:
            self.dealer.append(self.deck.pop())
        pv = card_value(self.player)
        dv = card_value(self.dealer)
        abbrev = get_currency_abbrev(self.ctx.guild.id)
        if dv > 21 or pv > dv:
            mult = await get_effective_mult(self.ctx.author.id, self.ctx.guild.id)
            winnings = int(self.bet * mult)
            await db.add_balance(self.ctx.author.id, self.ctx.guild.id, winnings)
            result = f"✅ You win **{winnings:,}** {abbrev}! (×{mult:.2f})"
            color = GaraConfig.EMBED_COLOR_SUCCESS
        elif pv == dv:
            await db.add_balance(self.ctx.author.id, self.ctx.guild.id, self.bet)
            result = f"🤝 Push! Got **{self.bet:,}** {abbrev} back."
            color = GaraConfig.EMBED_COLOR_WARN
        else:
            await db.sub_balance(self.ctx.author.id, self.ctx.guild.id, self.bet)
            result = f"❌ Dealer wins. Lost **{self.bet:,}** {abbrev}."
            color = GaraConfig.EMBED_COLOR_FAIL
        for b in self.children:
            b.disabled = True
        embed = self.make_embed(True, result)
        embed.color = color
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


# ── Crash ──

class CrashView(View):
    def __init__(self, user_id, guild_id, bet, msg_ref):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.guild_id = guild_id
        self.bet = bet
        self.msg_ref = msg_ref
        self.cashed = False

    @discord.ui.button(label="🚀 Cash Out", style=discord.ButtonStyle.success)
    async def cashout(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        state = bot.active_crashes.get(self.user_id)
        if not state or state.get("crashed"):
            await interaction.response.send_message("Game already over.", ephemeral=True)
            return
        mult = state["mult"]
        state["cashed"] = True
        self.cashed = True
        winnings = int(self.bet * mult)
        await db.add_balance(self.user_id, self.guild_id, winnings)
        bot.active_crashes.pop(self.user_id, None)
        button.disabled = True
        abbrev = get_currency_abbrev(self.guild_id)
        embed = gara_embed(
            title="🚀 Cashed Out!",
            description=f"Cashed at **{mult:.2f}x** — won **{winnings:,}** {abbrev}!",
            color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=self.guild_id,
        )
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


# ── Coin Flip ──

class CoinFlipView(View):
    def __init__(self, ctx, bet):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.bet = bet

    @discord.ui.button(label="🪙 Heads", style=discord.ButtonStyle.primary)
    async def heads(self, interaction, button):
        await self._resolve(interaction, "heads")

    @discord.ui.button(label="🪙 Tails", style=discord.ButtonStyle.secondary)
    async def tails(self, interaction, button):
        await self._resolve(interaction, "tails")

    async def _resolve(self, interaction, choice):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        result = random.choice(["heads", "tails"])
        abbrev = get_currency_abbrev(self.ctx.guild.id)
        for b in self.children:
            b.disabled = True
        if choice == result:
            mult = await get_effective_mult(self.ctx.author.id, self.ctx.guild.id)
            win = int(self.bet * mult)
            await db.add_balance(self.ctx.author.id, self.ctx.guild.id, win)
            embed = gara_embed(title=f"🪙 {result.title()}! You win!",
                               description=f"Won **{win:,}** {abbrev}! (×{mult:.2f})",
                               color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=self.ctx.guild.id)
        else:
            await db.sub_balance(self.ctx.author.id, self.ctx.guild.id, self.bet)
            embed = gara_embed(title=f"🪙 {result.title()}! You lose.",
                               description=f"Lost **{self.bet:,}** {abbrev}.",
                               color=GaraConfig.EMBED_COLOR_FAIL, guild_id=self.ctx.guild.id)
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


# ── TicTacToe ──

class TTTView(View):
    def __init__(self, ctx, opponent, clan_reward):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.opponent = opponent
        self.clan_reward = clan_reward
        self.board = [" "] * 9
        self.current = ctx.author
        self.symbols = {ctx.author.id: "❌", opponent.id: "⭕"}
        self._build()

    def _build(self):
        self.clear_items()
        for i in range(9):
            label = self.board[i] if self.board[i] != " " else "‌"  # zero-width
            disabled = self.board[i] != " "
            btn = Button(label=label if self.board[i] != " " else str(i+1),
                         style=discord.ButtonStyle.secondary if self.board[i] == " " else
                               discord.ButtonStyle.danger if self.board[i] == "❌" else discord.ButtonStyle.primary,
                         disabled=disabled, row=i//3)
            btn.callback = self._make_cb(i)
            self.add_item(btn)

    def _make_cb(self, idx):
        async def cb(interaction: discord.Interaction):
            if interaction.user.id != self.current.id:
                await interaction.response.send_message("Not your turn!", ephemeral=True)
                return
            sym = self.symbols[self.current.id]
            self.board[idx] = sym
            winner_sym = self._check_win()
            if winner_sym:
                winner = self.current
                loser = self.opponent if winner == self.ctx.author else self.ctx.author
                clan = await db.get_user_clan(winner.id, self.ctx.guild.id)
                if clan:
                    async with aiosqlite.connect(db.db_path) as conn:
                        await conn.execute("UPDATE clans SET gold=gold+? WHERE clan_id=?",
                                           (self.clan_reward, clan["clan_id"]))
                        await conn.commit()
                self._build()
                for item in self.children:
                    item.disabled = True
                embed = gara_embed(title="Tic-Tac-Toe",
                                   description=f"{winner.mention} wins! Clan earns **{self.clan_reward:,}** gold!",
                                   color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=self.ctx.guild.id)
                await interaction.response.edit_message(embed=embed, view=self)
                self.stop()
                return
            if " " not in self.board:
                self._build()
                embed = gara_embed(title="Tic-Tac-Toe", description="It's a draw!",
                                   color=GaraConfig.EMBED_COLOR_WARN, guild_id=self.ctx.guild.id)
                await interaction.response.edit_message(embed=embed, view=self)
                self.stop()
                return
            self.current = self.opponent if self.current == self.ctx.author else self.ctx.author
            self._build()
            embed = gara_embed(title="Tic-Tac-Toe",
                               description=f"{self.current.mention}'s turn ({self.symbols[self.current.id]})",
                               color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=self.ctx.guild.id)
            await interaction.response.edit_message(embed=embed, view=self)
        return cb

    def _check_win(self):
        wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
        for a,b,c in wins:
            if self.board[a] == self.board[b] == self.board[c] != " ":
                return self.board[a]
        return None


# ── RPS ──

class RPSView(View):
    picks: Dict[int, str] = {}

    def __init__(self, ctx, opponent, clan_reward):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.opponent = opponent
        self.clan_reward = clan_reward
        self.picks = {}

    async def _pick(self, interaction, choice):
        if interaction.user.id not in (self.ctx.author.id, self.opponent.id):
            await interaction.response.send_message("Not a participant!", ephemeral=True)
            return
        self.picks[interaction.user.id] = choice
        await interaction.response.send_message(f"You picked **{choice}**. Waiting for opponent...", ephemeral=True)
        if len(self.picks) == 2:
            await self._resolve(interaction)

    async def _resolve(self, interaction):
        a_pick = self.picks[self.ctx.author.id]
        o_pick = self.picks[self.opponent.id]
        beats = {"rock": "scissors", "scissors": "paper", "paper": "rock"}
        guild_id = self.ctx.guild.id
        if a_pick == o_pick:
            result = "Draw!"
            color = GaraConfig.EMBED_COLOR_WARN
            winner = None
        elif beats[a_pick] == o_pick:
            result = f"{self.ctx.author.mention} wins!"
            winner = self.ctx.author
            color = GaraConfig.EMBED_COLOR_SUCCESS
        else:
            result = f"{self.opponent.mention} wins!"
            winner = self.opponent
            color = GaraConfig.EMBED_COLOR_SUCCESS
        if winner:
            clan = await db.get_user_clan(winner.id, guild_id)
            if clan:
                async with aiosqlite.connect(db.db_path) as conn:
                    await conn.execute("UPDATE clans SET gold=gold+? WHERE clan_id=?", (self.clan_reward, clan["clan_id"]))
                    await conn.commit()
        desc = (f"{self.ctx.author.mention}: **{a_pick}** vs {self.opponent.mention}: **{o_pick}**\n\n"
                f"{result}" + (f"\nClan earns **{self.clan_reward:,}** gold!" if winner else ""))
        embed = gara_embed(title="Rock Paper Scissors", description=desc, color=color, guild_id=guild_id)
        for b in self.children:
            b.disabled = True
        await self.ctx.send(embed=embed)
        self.stop()

    @discord.ui.button(label="🪨 Rock", style=discord.ButtonStyle.secondary)
    async def rock(self, i, b): await self._pick(i, "rock")
    @discord.ui.button(label="📄 Paper", style=discord.ButtonStyle.secondary)
    async def paper(self, i, b): await self._pick(i, "paper")
    @discord.ui.button(label="✂️ Scissors", style=discord.ButtonStyle.secondary)
    async def scissors(self, i, b): await self._pick(i, "scissors")


# ── Leaderboard ──

class LeaderboardView(View):
    def __init__(self, ctx, mode="users"):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.mode = mode
        self.message = None

    async def get_embed(self):
        guild_id = self.ctx.guild.id
        if self.mode == "users":
            rows = await db.get_leaderboard(guild_id, 10)
            embed = gara_embed(title="💰 Wealth Leaderboard", color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=guild_id,
                               footer="Active voice only — unmuted and undeafened")
            medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
            desc = ""
            for i, (uid, total) in enumerate(rows):
                member = self.ctx.guild.get_member(uid)
                name = member.display_name if member else f"User {uid}"
                desc += f"{medals[i]} **{name}** — {total:,} {get_currency_abbrev(guild_id)}\n"
            embed.description = desc or "No data yet."
        else:
            clans = await db.get_clan_leaderboard(guild_id, 5)
            mults = get_clan_mults(guild_id)
            embed = gara_embed(title="🏆 Clan Leaderboard", color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=guild_id)
            desc = ""
            medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
            for i, clan in enumerate(clans):
                mult_tag = f"(×{mults[i]})" if i < len(mults) else ""
                desc += f"{medals[i]} **{clan['name']}** — {clan['gold']:,} gold {mult_tag}\n"
            embed.description = desc or "No clans yet."
        return embed

    @discord.ui.button(label="💰 Wealth", style=discord.ButtonStyle.primary)
    async def btn_users(self, interaction, button):
        self.mode = "users"
        embed = await self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🏆 Clans", style=discord.ButtonStyle.secondary)
    async def btn_clans(self, interaction, button):
        self.mode = "clans"
        embed = await self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)


# ── Help ──

class HelpView(View):
    CATEGORIES = [
        {"name": "Economy",  "emoji": "💰", "commands": [
            ("balance [@user]", "Check balance"), ("deposit <amt>", "Deposit to vault"),
            ("withdraw <amt>", "Withdraw from vault"), ("give @user <amt>", "Send coins"),
            ("daily", "Daily reward"), ("work", "Earn coins"),
            ("rob @user", "Try to rob someone"), ("leaderboard", "Wealth top 10"),
            ("profile [@user]", "Full profile card"), ("giveclangold <amt>", "Donate to clan pool"),
        ]},
        {"name": "Casino",   "emoji": "🎰", "commands": [
            ("slots <bet>", "Slot machine"), ("mines <bet>", "Mines button grid"),
            ("blackjack <bet>", "Hit or Stand"), ("crash <bet>", "Crash rocket game"),
            ("coinflip <bet>", "Heads or Tails"),
        ]},
        {"name": "Fame",     "emoji": "⭐", "commands": [
            ("fame [@user]", "Aura profile"), ("boost @user", "Give +1 aura"),
            ("neg @user", "Give -1 aura"), ("famous", "Fame leaderboard"),
        ]},
        {"name": "Clans",    "emoji": "🏰", "commands": [
            ("clans", "Clan leaderboard"), ("clanstats", "Full clan activity"),
            ("joinclan <name>", "Join a clan"), ("leaveclan", "Leave your clan"),
            ("mygold", "Your gold info"), ("tictactoe @user", "Clan mini-game"),
            ("rps @user", "Rock Paper Scissors"), ("highcard @user", "High card draw"),
            ("clanwar <name>", "Declare clan war"), ("warattack <id>", "Attack in war"),
        ]},
        {"name": "Mini-Games","emoji": "🎮", "commands": [
            ("trivia", "Answer a trivia question"), ("numguess", "Guess 1-100"),
            ("diceroll <bet>", "Roll the dice"), ("scramble", "Unscramble a word"),
            ("coinflip <bet>", "Heads or Tails flip"),
        ]},
        {"name": "Shop",     "emoji": "🛒", "commands": [
            ("shop", "View shop"), ("buy <item>", "Purchase an item"),
            ("buy mult", "Buy 2.5× personal multiplier"),
        ]},
        {"name": "Stats",    "emoji": "📊", "commands": [
            ("stats", "Your VC activity"), ("garalb", "Overall activity LB"),
            ("clanlb", "Clan leaderboard"),
        ]},
        {"name": "Admin",    "emoji": "⚙️", "admin_only": True, "commands": [
            ("givemoney @user <amt>", "Give coins"), ("takemoney @user <amt>", "Take coins"),
            ("setprefix <p>", "Change prefix"), ("setcurrency <name> <abbr>", "Change currency"),
            ("setroleschannel #ch", "Post earn roles UI"), ("updaterolesui", "Refresh roles UI"),
            ("setactivitychannel #ch", "Activity LB channel"), ("setclanchannel #ch", "Clan LB channel"),
            ("setblankui #ch", "Post blank embed"), ("editblankui title|desc|color <val>", "Edit blank embed"),
            ("setrandomvc #vc", "Enable random VC redirect"), ("blacklistvc #vc", "Blacklist VC"),
            ("unblacklistvc #vc", "Unblacklist VC"), ("spin", "Nitro spin"),
            ("lockcycle <open> <close> [#ch]", "Lock/unlock schedule"),
            ("settiername <1-5> <name>", "Set tier name"),
            ("settierrole <1-5> @role", "Set tier role"),
            ("settierhours <1-5> <hours>", "Set tier hours"),
            ("settiercoins <1-5> <coins>", "Set tier daily coins"),
            ("setclanmult <1-3> <mult>", "Set clan multiplier"),
            ("setrichrole <1-5> @role", "Map rich role"),
            ("addshoprole @role <price>", "Add role to shop"),
            ("removeshoprole @role", "Remove shop role"),
            ("giveclan <name> <amt>", "Give clan gold"),
            ("giveclangold <amt>", "Donate to clan"),
            ("setgiveaway #ch <prize>", "Weekly auto-giveaway"),
            ("giveaway <duration> <prize>", "Start giveaway"),
            ("setcrashmult <max>", "Set crash ceiling"),
            ("createclan <name> @role", "Create clan"),
        ]},
    ]

    # page = -1  → overview/menu
    # page = 0..N-1 → category index

    def __init__(self, ctx):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.page = -1
        visible = [c for c in self.CATEGORIES if not c.get("admin_only") or is_admin(ctx)]
        self.visible = visible
        self._build()

    def _auth(self, interaction) -> bool:
        return interaction.user.id == self.ctx.author.id

    # ── button builders ──────────────────────────────────────────────────────

    def _build(self):
        self.clear_items()
        if self.page == -1:
            self._build_menu()
        else:
            self._build_browse()

    def _build_menu(self):
        for i, cat in enumerate(self.visible):
            btn = Button(
                label=f"{cat['emoji']} {cat['name']}",
                style=discord.ButtonStyle.primary,
                row=i // 4,
            )
            btn.callback = self._make_jump_cb(i)
            self.add_item(btn)

    def _build_browse(self):
        n = len(self.visible)
        prev_btn = Button(
            label="◀ Prev",
            style=discord.ButtonStyle.secondary,
            disabled=(self.page == 0),
            row=0,
        )
        prev_btn.callback = self._prev
        self.add_item(prev_btn)

        menu_btn = Button(label="☰ Menu", style=discord.ButtonStyle.primary, row=0)
        menu_btn.callback = self._to_menu
        self.add_item(menu_btn)

        next_btn = Button(
            label="Next ▶",
            style=discord.ButtonStyle.secondary,
            disabled=(self.page == n - 1),
            row=0,
        )
        next_btn.callback = self._next
        self.add_item(next_btn)

    # ── callbacks ────────────────────────────────────────────────────────────

    def _make_jump_cb(self, idx):
        async def cb(interaction):
            if not self._auth(interaction):
                await interaction.response.send_message("Not your help menu!", ephemeral=True)
                return
            self.page = idx
            self._build()
            await interaction.response.edit_message(embed=self._cat_embed(), view=self)
        return cb

    async def _prev(self, interaction):
        if not self._auth(interaction):
            await interaction.response.send_message("Not your help menu!", ephemeral=True)
            return
        self.page = max(0, self.page - 1)
        self._build()
        await interaction.response.edit_message(embed=self._cat_embed(), view=self)

    async def _next(self, interaction):
        if not self._auth(interaction):
            await interaction.response.send_message("Not your help menu!", ephemeral=True)
            return
        self.page = min(len(self.visible) - 1, self.page + 1)
        self._build()
        await interaction.response.edit_message(embed=self._cat_embed(), view=self)

    async def _to_menu(self, interaction):
        if not self._auth(interaction):
            await interaction.response.send_message("Not your help menu!", ephemeral=True)
            return
        self.page = -1
        self._build()
        await interaction.response.edit_message(embed=self.main_embed(), view=self)

    # ── embeds ───────────────────────────────────────────────────────────────

    def main_embed(self):
        guild_id = self.ctx.guild.id if self.ctx.guild else None
        cats = "\n".join(f"{c['emoji']} **{c['name']}**" for c in self.visible)
        return gara_embed(
            title="📖 GARA Help",
            description=f"Select a category to browse, or use **◀ Prev / Next ▶** inside any category.\n\n{cats}",
            color=GaraConfig.EMBED_COLOR_ACCENT,
            guild_id=guild_id,
        )

    def _cat_embed(self):
        cat = self.visible[self.page]
        guild_id = self.ctx.guild.id if self.ctx.guild else None
        prefix = get_prefix_for_guild(guild_id)
        cmds = "\n".join(f"`{prefix}{cmd}` — {desc}" for cmd, desc in cat["commands"])
        n = len(self.visible)
        e = gara_embed(
            title=f"{cat['emoji']} {cat['name']}",
            description=cmds or "No commands.",
            color=GaraConfig.EMBED_COLOR_ACCENT,
            guild_id=guild_id,
        )
        e.set_footer(text=f"Category {self.page + 1} of {n}  •  Use ◀ Prev / Next ▶ to browse")
        return e


# ══════════════════════════════════════════
# EVENTS
# ══════════════════════════════════════════

@bot.event
async def on_ready():
    await db.init()
    # Load guild settings
    async with aiosqlite.connect(db.db_path) as conn:
        async with conn.execute("SELECT * FROM server_settings") as c:
            rows = await c.fetchall()
            cols = [d[0] for d in c.description]
            for row in rows:
                d = dict(zip(cols, row))
                bot.guild_settings[d["guild_id"]] = d
    logger.info("═══════════════════════════════════════")
    logger.info(f"  {GaraConfig.BOT_NAME} is online!")
    logger.info(f"  Logged in as: {bot.user}")
    logger.info(f"  Guilds: {len(bot.guilds)}")
    logger.info("═══════════════════════════════════════")
    daily_reset.start()
    vc_payout.start()
    live_leaderboard_update.start()
    lockcycle_task.start()
    giveaway_checker.start()
    weekly_reset_task.start()
    rich_roles_task.start()


@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    uid = message.author.id
    gid = message.guild.id
    now_str = datetime.datetime.now().isoformat()

    # 1 GC per message with 30s cooldown
    user = await db.get_user(uid, gid)
    last_earn = user.get("last_message_earn")
    can_earn = True
    if last_earn:
        try:
            last_dt = datetime.datetime.fromisoformat(last_earn)
            if (datetime.datetime.now() - last_dt).total_seconds() < GaraConfig.MESSAGE_EARN_COOLDOWN:
                can_earn = False
        except Exception:
            pass
    if can_earn:
        await db.add_balance(uid, gid, GaraConfig.MESSAGE_EARN_GC)
        await db.update_user(uid, gid, last_message_earn=now_str,
                             total_messages=(user.get("total_messages") or 0) + 1,
                             weekly_messages=(user.get("weekly_messages") or 0) + 1)
        # Update clan message count
        clan = await db.get_user_clan(uid, gid)
        if clan:
            today = datetime.date.today().isoformat()
            async with aiosqlite.connect(db.db_path) as conn:
                await conn.execute(
                    "INSERT INTO daily_activity(clan_id,date,message_count) VALUES(?,?,1) "
                    "ON CONFLICT(clan_id,date) DO UPDATE SET message_count=message_count+1",
                    (clan["clan_id"], today),
                )
                await conn.execute(
                    "UPDATE clans SET weekly_messages=weekly_messages+1,total_messages=total_messages+1 WHERE clan_id=?",
                    (clan["clan_id"],),
                )
                await conn.commit()

    await bot.process_commands(message)


@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return
    gid = member.guild.id
    uid = member.id
    now_str = datetime.datetime.now().isoformat()

    # Track VC join/leave for hours
    user = await db.get_user(uid, gid)
    vc_join = user.get("vc_join_time")

    def is_active(vs):
        return vs and vs.channel and not vs.deaf and not vs.self_deaf and not vs.mute and not vs.self_mute

    if not is_active(before) and is_active(after):
        # Joined active VC
        await db.update_user(uid, gid, vc_join_time=now_str)
    elif is_active(before) and not is_active(after):
        # Left or became muted/deafened
        if vc_join:
            try:
                joined_dt = datetime.datetime.fromisoformat(vc_join)
                elapsed_hours = (datetime.datetime.now() - joined_dt).total_seconds() / 3600
                current_hours = user.get("vc_hours", 0) or 0
                new_hours = current_hours + elapsed_hours
                elapsed_mins = int(elapsed_hours * 60)
                weekly_vc = (user.get("weekly_vc_minutes") or 0) + elapsed_mins
                await db.update_user(uid, gid, vc_hours=new_hours, vc_join_time=None,
                                     weekly_vc_minutes=weekly_vc)
                # Check for tier rewards
                await check_tier_rewards(member, gid, current_hours, new_hours)
            except Exception as e:
                logger.warning(f"VC tracking error: {e}")

    # Random VC redirect
    settings = await db.get_settings(gid)
    random_vc_id = settings.get("random_vc", 0)
    if random_vc_id and after.channel and after.channel.id == random_vc_id:
        try:
            blacklist_raw = settings.get("vc_blacklist", "[]")
            blacklist = json.loads(blacklist_raw) if isinstance(blacklist_raw, str) else blacklist_raw
            options = [
                ch for ch in member.guild.voice_channels
                if ch.id != random_vc_id and ch.id not in blacklist
            ]
            if options:
                target = random.choice(options)
                await member.move_to(target)
            else:
                try:
                    await member.send("No available voice channels to move to!")
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Random VC error: {e}")


async def check_tier_rewards(member, guild_id, old_hours, new_hours):
    tiers = get_tiers(guild_id)
    for tier in tiers:
        if old_hours < tier["hours"] <= new_hours:
            # Assign role if configured
            role_id = tier.get("role_id")
            if role_id:
                role = member.guild.get_role(role_id)
                if role:
                    try:
                        await member.add_roles(role)
                    except Exception:
                        pass
            # Give reward
            if tier.get("daily", 0) > 0:
                await db.add_balance(member.id, guild_id, tier["daily"])
            logger.info(f"Tier {tier['name']} reached by {member.id}")


@bot.before_invoke
async def global_rate_limit(ctx):
    now = time.monotonic()
    key = ctx.author.id
    last = bot._last_cmd_time.get(key, 0.0)
    if now - last < 1.25:
        raise commands.CommandOnCooldown(
            commands.Cooldown(1, 1.25), 1.25 - (now - last), commands.BucketType.user
        )
    bot._last_cmd_time[key] = now


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        if error.retry_after < 0.2:
            return  # Silently drop only extreme spam
        await ctx.reply(f"⏰ Slow down! Try again in `{error.retry_after:.1f}s`.", delete_after=5)
    elif isinstance(error, commands.CommandNotFound):
        cmd_name = ctx.invoked_with
        all_cmds = [c.name for c in bot.commands] + [a for c in bot.commands for a in c.aliases]
        matches = difflib.get_close_matches(cmd_name, all_cmds, n=1, cutoff=0.5)
        if matches:
            prefix = get_prefix_for_guild(ctx.guild.id if ctx.guild else None)
            await ctx.reply(f"❓ Command not found. Did you mean `{prefix}{matches[0]}`?", delete_after=8)
    elif isinstance(error, commands.MissingRequiredArgument):
        prefix = get_prefix_for_guild(ctx.guild.id if ctx.guild else None)
        await ctx.reply(f"❌ Missing argument: `{error.param.name}`\nUsage: `{prefix}{ctx.command.name} {ctx.command.signature}`", delete_after=10)
    elif isinstance(error, commands.BadArgument):
        await ctx.reply(f"❌ Invalid argument. {error}", delete_after=8)
    elif isinstance(error, commands.MemberNotFound):
        await ctx.reply("❌ Member not found.", delete_after=5)
    else:
        logger.error(f"Unhandled error in {ctx.command}: {error}", exc_info=True)


# ══════════════════════════════════════════
# TASKS
# ══════════════════════════════════════════

@tasks.loop(hours=24)
async def daily_reset():
    await asyncio.sleep(5)
    today = datetime.date.today().isoformat()
    try:
        async with aiosqlite.connect(db.db_path) as conn:
            async with conn.execute("""
                SELECT c.clan_id, c.guild_id, COALESCE(da.message_count,0) as msgs
                FROM clans c
                LEFT JOIN daily_activity da ON c.clan_id=da.clan_id AND da.date=?
                GROUP BY c.clan_id
            """, (today,)) as c:
                clan_data = await c.fetchall()
            total_msgs = sum(d[2] for d in clan_data)
            if total_msgs:
                for clan_id, guild_id, msgs in clan_data:
                    pct = (msgs / total_msgs) * 100
                    gold_earned = int(GaraConfig.CLAN_GOLD_POOL_DAILY * (pct / 100))
                    await conn.execute(
                        "UPDATE clans SET gold=gold+?,last_active=? WHERE clan_id=?",
                        (gold_earned, today, clan_id),
                    )
                    await conn.execute(
                        "UPDATE daily_activity SET percentage=? WHERE clan_id=? AND date=?",
                        (pct, clan_id, today),
                    )
            await conn.commit()
        logger.info("Daily reset done")
    except Exception as e:
        logger.error(f"Daily reset error: {e}", exc_info=True)


@tasks.loop(minutes=1)
async def vc_payout():
    """2 GC/min for unmuted + undeafened VC members"""
    try:
        for guild in bot.guilds:
            for channel in guild.voice_channels:
                for member in channel.members:
                    if (not member.bot and not member.voice.afk
                            and not member.voice.deaf and not member.voice.self_deaf
                            and not member.voice.mute and not member.voice.self_mute):
                        try:
                            await db.add_balance(member.id, guild.id, GaraConfig.VC_EARN_PER_MIN)
                            # Weekly VC tracking
                            user = await db.get_user(member.id, guild.id)
                            wvc = (user.get("weekly_vc_minutes") or 0) + 1
                            await db.update_user(member.id, guild.id, weekly_vc_minutes=wvc)
                            # Clan VC tracking
                            clan = await db.get_user_clan(member.id, guild.id)
                            if clan:
                                async with aiosqlite.connect(db.db_path) as conn:
                                    await conn.execute(
                                        "UPDATE clans SET weekly_vc_minutes=weekly_vc_minutes+1 WHERE clan_id=?",
                                        (clan["clan_id"],),
                                    )
                                    await conn.commit()
                        except Exception as e:
                            logger.warning(f"VC payout error {member.id}: {e}")
    except Exception as e:
        logger.error(f"VC payout loop error: {e}", exc_info=True)


@tasks.loop(minutes=5)
async def live_leaderboard_update():
    """Auto-edit activity and clan leaderboard channels every 5 min"""
    for guild in bot.guilds:
        gid = guild.id
        settings = await db.get_settings(gid)
        if not settings:
            continue

        # Activity leaderboard channel
        act_ch_id = settings.get("activity_channel", 0)
        act_msg_id = settings.get("activity_msg_id", 0)
        if act_ch_id and act_msg_id:
            ch = guild.get_channel(act_ch_id)
            if ch:
                try:
                    msg = await ch.fetch_message(act_msg_id)
                    rows = await db.get_leaderboard(gid, 10)
                    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
                    desc = ""
                    for i, (uid, total) in enumerate(rows):
                        member = guild.get_member(uid)
                        name = member.display_name if member else f"User {uid}"
                        desc += f"{medals[i]} **{name}** — {total:,} {get_currency_abbrev(gid)}\n"
                    embed = gara_embed(title="💰 Activity Leaderboard", description=desc or "No data.",
                                       color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=gid,
                                       footer="Active voice only — unmuted and undeafened")
                    await msg.edit(embed=embed)
                except Exception:
                    pass

        # Clan leaderboard channel
        clan_ch_id = settings.get("clan_channel", 0)
        clan_msg_id = settings.get("clan_msg_id", 0)
        if clan_ch_id and clan_msg_id:
            ch = guild.get_channel(clan_ch_id)
            if ch:
                try:
                    msg = await ch.fetch_message(clan_msg_id)
                    clans = await db.get_clan_leaderboard(gid, 5)
                    mults = get_clan_mults(gid)
                    medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
                    desc = ""
                    for i, clan in enumerate(clans):
                        mult_tag = f"**×{mults[i]}** bonus" if i < len(mults) else ""
                        role = guild.get_role(clan.get("role_id") or 0)
                        role_str = role.mention if role else clan["name"]
                        desc += f"{medals[i]} {role_str} — {clan['gold']:,} gold {mult_tag}\n"
                    embed = gara_embed(title="🏆 Clan Leaderboard (Weekly)", description=desc or "No clans.",
                                       color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=gid)
                    await msg.edit(embed=embed)
                except Exception:
                    pass


@tasks.loop(minutes=1)
async def lockcycle_task():
    now = datetime.datetime.now()
    for channel_id, config in list(bot.lockcycles.items()):
        guild = bot.get_guild(config["guild_id"])
        if not guild:
            continue
        channel = guild.get_channel(channel_id)
        if not channel:
            continue
        oh, om = config["open"]
        ch, cm = config["close"]
        open_time = now.replace(hour=oh, minute=om, second=0, microsecond=0)
        close_time = now.replace(hour=ch, minute=cm, second=0, microsecond=0)
        current = now.replace(second=0, microsecond=0)
        everyone = guild.default_role
        try:
            if current == open_time:
                await channel.set_permissions(everyone, send_messages=True)
                logger.info(f"Unlocked {channel_id}")
            elif current == close_time:
                await channel.set_permissions(everyone, send_messages=False)
                logger.info(f"Locked {channel_id}")
        except Exception as e:
            logger.error(f"Lock error: {e}")


@tasks.loop(hours=1)
async def giveaway_checker():
    active = await db.get_active_giveaways()
    now = datetime.datetime.now()
    for gw in active:
        try:
            end = datetime.datetime.fromisoformat(gw["end_time"])
            if now >= end:
                guild = bot.get_guild(gw["guild_id"])
                if not guild:
                    await db.close_giveaway(gw["id"])
                    continue
                ch = guild.get_channel(gw["channel_id"])
                if not ch:
                    await db.close_giveaway(gw["id"])
                    continue
                try:
                    msg = await ch.fetch_message(gw["msg_id"])
                    # Get entrants from reactions
                    entrants = []
                    for reaction in msg.reactions:
                        if str(reaction.emoji) == "🎉":
                            async for user in reaction.users():
                                if not user.bot:
                                    entrants.append(user)
                    # Top 10 richest get 2 entries
                    rich = await db.get_leaderboard(guild.id, 10)
                    rich_ids = [r[0] for r in rich]
                    weighted = []
                    for u in entrants:
                        weighted.append(u)
                        if u.id in rich_ids:
                            weighted.append(u)
                    if weighted:
                        winner = random.choice(weighted)
                        await ch.send(
                            embed=gara_embed(
                                title="🎉 Giveaway Ended!",
                                description=f"**Prize:** {gw['prize']}\n**Winner:** {winner.mention} 🎊",
                                color=GaraConfig.EMBED_COLOR_SUCCESS,
                            )
                        )
                    else:
                        await ch.send(embed=gara_embed(title="🎉 Giveaway Ended",
                                                        description="No valid entries!",
                                                        color=GaraConfig.EMBED_COLOR_WARN))
                except Exception:
                    pass
                await db.close_giveaway(gw["id"])
        except Exception as e:
            logger.error(f"Giveaway error: {e}")


@tasks.loop(hours=168)  # 7 days
async def weekly_reset_task():
    await asyncio.sleep(10)
    logger.info("Running weekly reset...")
    for guild in bot.guilds:
        gid = guild.id
        settings = await db.get_settings(gid)
        try:
            async with aiosqlite.connect(db.db_path) as conn:
                # Get all clans, split gold equally to members
                async with conn.execute("SELECT * FROM clans WHERE guild_id=?", (gid,)) as c:
                    clans = await c.fetchall()
                    clan_cols = [d[0] for d in c.description]
                for clan_row in clans:
                    clan = dict(zip(clan_cols, clan_row))
                    if clan["gold"] <= 0:
                        continue
                    members = await db.get_clan_members(clan["clan_id"])
                    if not members:
                        continue
                    share = clan["gold"] // len(members)
                    if share <= 0:
                        continue
                    for uid in members:
                        await db.add_balance(uid, gid, share)
                    await conn.execute("UPDATE clans SET gold=0 WHERE clan_id=?", (clan["clan_id"],))

                # Reset weekly counters
                await conn.execute("UPDATE users SET weekly_messages=0,weekly_vc_minutes=0 WHERE guild_id=?", (gid,))
                await conn.execute("UPDATE clans SET weekly_messages=0,weekly_vc_minutes=0 WHERE guild_id=?", (gid,))
                await conn.commit()

            # Post activity LB to channel
            act_ch_id = settings.get("activity_channel", 0)
            if act_ch_id:
                ch = guild.get_channel(act_ch_id)
                if ch:
                    rows = await db.get_leaderboard(gid, 10)
                    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
                    desc = "\n".join(
                        f"{medals[i]} <@{uid}> — {total:,}" for i, (uid, total) in enumerate(rows)
                    )
                    await ch.send(embed=gara_embed(title="📊 Weekly Activity Summary",
                                                   description=desc or "No data.",
                                                   color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=gid))

            # Auto-giveaway
            gw_ch_id = settings.get("giveaway_channel", 0)
            gw_prize = settings.get("giveaway_prize", "")
            if gw_ch_id and gw_prize:
                ch = guild.get_channel(gw_ch_id)
                if ch:
                    end_time = (datetime.datetime.now() + timedelta(days=2)).isoformat()
                    embed = gara_embed(title="🎉 Weekly Giveaway!",
                                       description=f"**Prize:** {gw_prize}\nReact with 🎉 to enter!\nEnds in 48 hours.",
                                       color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=gid)
                    msg = await ch.send(embed=embed)
                    await msg.add_reaction("🎉")
                    await db.create_giveaway(gid, ch.id, msg.id, gw_prize, end_time)

        except Exception as e:
            logger.error(f"Weekly reset error for {gid}: {e}", exc_info=True)


@tasks.loop(hours=24)
async def rich_roles_task():
    """Assign top 5 rich roles daily"""
    for guild in bot.guilds:
        gid = guild.id
        settings = await db.get_settings(gid)
        if not settings:
            continue
        rich_roles_raw = settings.get("rich_roles", "[]")
        try:
            rich_roles = json.loads(rich_roles_raw) if isinstance(rich_roles_raw, str) else rich_roles_raw
        except Exception:
            continue
        if not rich_roles:
            continue
        top = await db.get_leaderboard(gid, 5)
        for i, (uid, _) in enumerate(top):
            if i >= len(rich_roles):
                break
            role_id = rich_roles[i]
            member = guild.get_member(uid)
            role = guild.get_role(role_id)
            if member and role:
                try:
                    await member.add_roles(role)
                except Exception:
                    pass


# ══════════════════════════════════════════
# ECONOMY COMMANDS
# ══════════════════════════════════════════

@bot.command(name="balance", aliases=["bal", "wallet"])
@commands.cooldown(1, 3, commands.BucketType.user)
async def balance_cmd(ctx, member: discord.Member = None):
    target = member or ctx.author
    user = await db.get_user(target.id, ctx.guild.id)
    abbrev = get_currency_abbrev(ctx.guild.id)
    mult = await get_effective_mult(target.id, ctx.guild.id)
    embed = gara_embed(title=f"{target.display_name}'s Balance",
                       color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id,
                       thumbnail=target.display_avatar.url)
    embed.add_field(name="Wallet",  value=f"**{user['balance']:,}** {abbrev}", inline=True)
    embed.add_field(name="Vault",   value=f"**{user['vault']:,}** {abbrev}", inline=True)
    embed.add_field(name="Total",   value=f"**{(user['balance']+user['vault']):,}** {abbrev}", inline=True)
    embed.add_field(name="Multiplier", value=f"×{mult:.2f}", inline=True)
    await ctx.reply(embed=embed)


@bot.command(name="deposit", aliases=["dep"])
@commands.cooldown(1, 2, commands.BucketType.user)
async def deposit_cmd(ctx, amount: str):
    user = await db.get_user(ctx.author.id, ctx.guild.id)
    amt = user["balance"] if amount.lower() == "all" else int(amount.replace(",",""))
    if amt <= 0:
        return await ctx.reply("Amount must be positive!")
    if not await db.move_to_vault(ctx.author.id, ctx.guild.id, amt):
        return await ctx.reply("Insufficient wallet balance!")
    await ctx.reply(embed=gara_embed(title="Deposited",
        description=f"Moved **{amt:,}** {get_currency_abbrev(ctx.guild.id)} to vault.",
        color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))


@bot.command(name="withdraw", aliases=["with"])
@commands.cooldown(1, 2, commands.BucketType.user)
async def withdraw_cmd(ctx, amount: str):
    user = await db.get_user(ctx.author.id, ctx.guild.id)
    amt = user["vault"] if amount.lower() == "all" else int(amount.replace(",",""))
    if amt <= 0:
        return await ctx.reply("Amount must be positive!")
    if not await db.move_from_vault(ctx.author.id, ctx.guild.id, amt):
        return await ctx.reply("Insufficient vault balance!")
    await ctx.reply(embed=gara_embed(title="Withdrew",
        description=f"Moved **{amt:,}** {get_currency_abbrev(ctx.guild.id)} to wallet.",
        color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))


@bot.command(name="give", aliases=["pay","send"])
@commands.cooldown(1, 3, commands.BucketType.user)
async def give_cmd(ctx, member: discord.Member, amount: int):
    if member.bot or member.id == ctx.author.id:
        return await ctx.reply("Invalid target!")
    if amount <= 0:
        return await ctx.reply("Amount must be positive!")
    if not await db.transfer_balance(ctx.author.id, member.id, ctx.guild.id, amount):
        return await ctx.reply("Insufficient balance!")
    await ctx.reply(embed=gara_embed(title="Transfer Complete",
        description=f"Sent **{amount:,}** {get_currency_abbrev(ctx.guild.id)} to {member.mention}!",
        color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))


@bot.command(name="daily")
@commands.cooldown(1, 1, commands.BucketType.user)
async def daily_cmd(ctx):
    user = await db.get_user(ctx.author.id, ctx.guild.id)
    last = user.get("last_daily")
    if last:
        dt = datetime.datetime.fromisoformat(last)
        if datetime.datetime.now() - dt < timedelta(days=1):
            remaining = timedelta(days=1) - (datetime.datetime.now() - dt)
            h, rem = divmod(int(remaining.total_seconds()), 3600)
            m = rem // 60
            return await ctx.reply(f"Come back in **{h}h {m}m**!")
    reward = random.randint(GaraConfig.DAILY_REWARD_MIN, GaraConfig.DAILY_REWARD_MAX)
    mult = await get_effective_mult(ctx.author.id, ctx.guild.id)
    total = int(reward * mult)
    await db.add_balance(ctx.author.id, ctx.guild.id, total)
    await db.update_user(ctx.author.id, ctx.guild.id, last_daily=datetime.datetime.now().isoformat())
    embed = gara_embed(title="Daily Reward",
        description=f"Claimed **{total:,}** {get_currency_abbrev(ctx.guild.id)}! (×{mult:.2f} mult)",
        color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id)
    await ctx.reply(embed=embed)


@bot.command(name="work")
@commands.cooldown(1, 1, commands.BucketType.user)
async def work_cmd(ctx):
    user = await db.get_user(ctx.author.id, ctx.guild.id)
    last = user.get("last_work")
    if last:
        dt = datetime.datetime.fromisoformat(last)
        if datetime.datetime.now() - dt < timedelta(hours=GaraConfig.WORK_COOLDOWN_HOURS):
            remaining = timedelta(hours=GaraConfig.WORK_COOLDOWN_HOURS) - (datetime.datetime.now() - dt)
            return await ctx.reply(f"Work again in **{int(remaining.total_seconds()//60)} min**!")
    jobs = ["delivered packages","mined crypto","traded stocks","streamed games",
            "fixed bugs","designed logos","wrote code","hacked the mainframe","flipped burgers","walked dogs"]
    base = random.randint(GaraConfig.WORK_REWARD_MIN, GaraConfig.WORK_REWARD_MAX)
    mult = await get_effective_mult(ctx.author.id, ctx.guild.id)
    earned = int(base * mult)
    await db.add_balance(ctx.author.id, ctx.guild.id, earned)
    await db.update_user(ctx.author.id, ctx.guild.id, last_work=datetime.datetime.now().isoformat())
    await ctx.reply(embed=gara_embed(title="Work Complete",
        description=f"You {random.choice(jobs)} and earned **{earned:,}** {get_currency_abbrev(ctx.guild.id)}! (×{mult:.2f})",
        color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))


@bot.command(name="rob")
@commands.cooldown(1, 1, commands.BucketType.user)
async def rob_cmd(ctx, member: discord.Member):
    if member.bot or member.id == ctx.author.id:
        return await ctx.reply("Can't rob that user!")
    user = await db.get_user(ctx.author.id, ctx.guild.id)
    target = await db.get_user(member.id, ctx.guild.id)
    last = user.get("last_rob")
    if last:
        dt = datetime.datetime.fromisoformat(last)
        if datetime.datetime.now() - dt < timedelta(hours=GaraConfig.ROB_COOLDOWN_HOURS):
            remaining = timedelta(hours=GaraConfig.ROB_COOLDOWN_HOURS) - (datetime.datetime.now() - dt)
            return await ctx.reply(f"Wait **{int(remaining.total_seconds()//60)} min**!")
    if target["balance"] < 100:
        return await ctx.reply("They're too broke to rob!")
    success = random.random() < GaraConfig.ROB_CHANCE
    if success:
        stolen = random.randint(int(target["balance"] * 0.1), int(target["balance"] * 0.3))
        await db.rob_balance(ctx.author.id, member.id, ctx.guild.id, stolen, 0, True)
        embed = gara_embed(title="🔫 Robbery Successful!",
            description=f"Stole **{stolen:,}** {get_currency_abbrev(ctx.guild.id)} from {member.mention}!",
            color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id)
    else:
        fine = random.randint(50, max(50, min(500, user["balance"])))
        await db.rob_balance(ctx.author.id, member.id, ctx.guild.id, 0, fine, False)
        embed = gara_embed(title="🚔 Caught!",
            description=f"You were caught and fined **{fine:,}** {get_currency_abbrev(ctx.guild.id)}!",
            color=GaraConfig.EMBED_COLOR_FAIL, guild_id=ctx.guild.id)
    await ctx.reply(embed=embed)


@bot.command(name="leaderboard", aliases=["lb","rich","top"])
@commands.cooldown(1, 3, commands.BucketType.user)
async def leaderboard_cmd(ctx):
    view = LeaderboardView(ctx, mode="users")
    embed = await view.get_embed()
    msg = await ctx.send(embed=embed, view=view)
    view.message = msg


@bot.command(name="garalb")
@commands.cooldown(1, 5, commands.BucketType.user)
async def garalb_cmd(ctx):
    rows = await db.get_leaderboard(ctx.guild.id, 10)
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    desc = ""
    for i, (uid, total) in enumerate(rows):
        member = ctx.guild.get_member(uid)
        name = member.display_name if member else f"<@{uid}>"
        user_data = await db.get_user(uid, ctx.guild.id)
        wm = user_data.get("weekly_messages", 0)
        wv = user_data.get("weekly_vc_minutes", 0)
        desc += f"{medals[i]} **{name}** — {total:,} GC | {wm} msgs | {wv} VC mins\n"
    embed = gara_embed(title="📊 Overall Activity Leaderboard",
                       description=desc or "No data.", color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id,
                       footer="Active voice only — unmuted and undeafened")
    await ctx.reply(embed=embed)


@bot.command(name="clanlb")
@commands.cooldown(1, 5, commands.BucketType.user)
async def clanlb_cmd(ctx):
    clans = await db.get_clan_leaderboard(ctx.guild.id, 10)
    mults = get_clan_mults(ctx.guild.id)
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    desc = ""
    for i, clan in enumerate(clans):
        mult_tag = f"**×{mults[i]}**" if i < len(mults) else ""
        role = ctx.guild.get_role(clan.get("role_id") or 0)
        role_str = role.mention if role else f"**{clan['name']}**"
        desc += f"{medals[i]} {role_str} — {clan['gold']:,} gold | {clan.get('weekly_messages',0)} msgs {mult_tag}\n"
    embed = gara_embed(title="🏰 Clan Leaderboard",
                       description=desc or "No clans.", color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id)
    await ctx.reply(embed=embed)


@bot.command(name="profile")
@commands.cooldown(1, 5, commands.BucketType.user)
async def profile_cmd(ctx, member: discord.Member = None):
    target = member or ctx.author
    user = await db.get_user(target.id, ctx.guild.id)
    abbrev = get_currency_abbrev(ctx.guild.id)
    total_wealth = user["balance"] + user["vault"]
    mult = await get_effective_mult(target.id, ctx.guild.id)
    tier = await get_user_tier(ctx.guild.id, user.get("vc_hours", 0))
    clan = await db.get_user_clan(target.id, ctx.guild.id)

    lb = await db.get_leaderboard(ctx.guild.id, 100)
    lb_rank = next((i+1 for i, (uid, _) in enumerate(lb) if uid == target.id), "N/A")

    embed = gara_embed(title=f"🪪 {target.display_name}'s Profile",
                       color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id,
                       thumbnail=target.display_avatar.url)
    embed.add_field(name="💰 Wallet",       value=f"{user['balance']:,} {abbrev}", inline=True)
    embed.add_field(name="🏦 Vault",        value=f"{user['vault']:,} {abbrev}", inline=True)
    embed.add_field(name="📊 Total",        value=f"{total_wealth:,} {abbrev}", inline=True)
    embed.add_field(name="⭐ Aura",         value=str(user.get("aura", 0)), inline=True)
    embed.add_field(name="🎙️ VC Hours",    value=f"{user.get('vc_hours', 0):.1f}h", inline=True)
    embed.add_field(name="💬 Messages",     value=str(user.get("total_messages", 0)), inline=True)
    embed.add_field(name="🏅 Tier",         value=tier["name"] if tier else "None", inline=True)
    embed.add_field(name="🏆 LB Rank",      value=f"#{lb_rank}", inline=True)
    embed.add_field(name="✨ Multiplier",   value=f"×{mult:.2f}", inline=True)
    embed.add_field(name="🏰 Clan",         value=clan["name"] if clan else "None", inline=True)
    embed.add_field(name="📈 Weekly Msgs",  value=str(user.get("weekly_messages", 0)), inline=True)
    embed.add_field(name="🎙️ Weekly VC",   value=f"{user.get('weekly_vc_minutes', 0)} min", inline=True)
    await ctx.reply(embed=embed)


@bot.command(name="giveclangold")
@commands.cooldown(1, 5, commands.BucketType.user)
async def giveclangold_cmd(ctx, amount: int):
    if amount <= 0:
        return await ctx.reply("Amount must be positive!")
    clan = await db.get_user_clan(ctx.author.id, ctx.guild.id)
    if not clan:
        return await ctx.reply("You're not in a clan!")
    if not await db.sub_balance(ctx.author.id, ctx.guild.id, amount):
        return await ctx.reply("Insufficient balance!")
    async with aiosqlite.connect(db.db_path) as conn:
        await conn.execute("UPDATE clans SET gold=gold+? WHERE clan_id=?", (amount, clan["clan_id"]))
        await conn.commit()
    await ctx.reply(embed=gara_embed(title="Clan Donation",
        description=f"Donated **{amount:,}** to **{clan['name']}**'s gold pool!",
        color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))


# ══════════════════════════════════════════
# CASINO COMMANDS
# ══════════════════════════════════════════

@bot.command(name="slots")
@commands.cooldown(1, 3, commands.BucketType.user)
async def slots_cmd(ctx, bet: int):
    user = await db.get_user(ctx.author.id, ctx.guild.id)
    if bet <= 0 or bet > user["balance"]:
        return await ctx.reply("Invalid bet!")
    emojis = GaraConfig.SLOTS_EMOJIS
    result = [random.choice(emojis) for _ in range(3)]
    mult = await get_effective_mult(ctx.author.id, ctx.guild.id)
    if result[0] == result[1] == result[2]:
        winnings = int(bet * GaraConfig.SLOTS_JACKPOT_MULTIPLIER * mult)
        title = "🎰 JACKPOT!"
        color = GaraConfig.EMBED_COLOR_SUCCESS
    elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
        winnings = int(bet * GaraConfig.SLOTS_MATCH_MULTIPLIER * mult)
        title = "🎰 Winner!"
        color = GaraConfig.EMBED_COLOR_SUCCESS
    else:
        winnings = -bet
        title = "🎰 No luck..."
        color = GaraConfig.EMBED_COLOR_FAIL
    await db.add_balance(ctx.author.id, ctx.guild.id, winnings)
    abbrev = get_currency_abbrev(ctx.guild.id)
    embed = gara_embed(title=title, description=f"**{' | '.join(result)}**", color=color, guild_id=ctx.guild.id)
    embed.add_field(name="Bet", value=f"{bet:,}", inline=True)
    embed.add_field(name="Result", value=f"{winnings:+,} {abbrev}", inline=True)
    embed.add_field(name="Balance", value=f"{user['balance']+winnings:,}", inline=True)
    await ctx.reply(embed=embed)


@bot.command(name="mines")
@commands.cooldown(1, 3, commands.BucketType.user)
async def mines_cmd(ctx, bet: int):
    user = await db.get_user(ctx.author.id, ctx.guild.id)
    if bet <= 0 or bet > user["balance"]:
        return await ctx.reply("Invalid bet!")
    existing = await db.get_mines_game(ctx.author.id, ctx.guild.id)
    if existing:
        return await ctx.reply("You already have an active Mines game!")
    grid = ["💎"] * 6 + ["💣"] * 3
    random.shuffle(grid)
    await db.sub_balance(ctx.author.id, ctx.guild.id, bet)
    await db.create_mines_game(ctx.author.id, ctx.guild.id, bet, grid)
    view = MinesView(ctx.author.id, ctx.guild.id, bet, grid, [], 1.0)
    embed = gara_embed(
        title="💎 Mines",
        description=f"Bet: **{bet:,}** {get_currency_abbrev(ctx.guild.id)}\nClick tiles to reveal. Hit a 💣 and you lose!\n\n⬛⬛⬛\n⬛⬛⬛\n⬛⬛⬛",
        color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id,
    )
    msg = await ctx.reply(embed=embed, view=view)
    view.message = msg


@bot.command(name="blackjack", aliases=["bj"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def blackjack_cmd(ctx, bet: int):
    user = await db.get_user(ctx.author.id, ctx.guild.id)
    if bet <= 0 or bet > user["balance"]:
        return await ctx.reply("Invalid bet!")
    deck = DECK.copy()
    random.shuffle(deck)
    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]
    view = BlackjackView(ctx, bet, deck, player, dealer)
    if card_value(player) == 21:
        mult = await get_effective_mult(ctx.author.id, ctx.guild.id)
        winnings = int(bet * 1.5 * mult)
        await db.add_balance(ctx.author.id, ctx.guild.id, winnings)
        embed = view.make_embed(True, f"🃏 Blackjack! Won **{winnings:,}** {get_currency_abbrev(ctx.guild.id)}!")
        embed.color = GaraConfig.EMBED_COLOR_SUCCESS
        return await ctx.reply(embed=embed)
    await ctx.reply(embed=view.make_embed(), view=view)


@bot.command(name="crash")
@commands.cooldown(1, 5, commands.BucketType.user)
async def crash_cmd(ctx, bet: int):
    user = await db.get_user(ctx.author.id, ctx.guild.id)
    if bet <= 0 or bet > user["balance"]:
        return await ctx.reply("Invalid bet!")
    if ctx.author.id in bot.active_crashes:
        return await ctx.reply("You already have an active Crash game!")
    settings = await db.get_settings(ctx.guild.id)
    max_mult = settings.get("crash_max_mult", GaraConfig.CRASH_DEFAULT_MAX) or GaraConfig.CRASH_DEFAULT_MAX
    await db.sub_balance(ctx.author.id, ctx.guild.id, bet)
    # Determine crash point: exponential distribution weighted low
    crash_at = round(random.uniform(1.0, max_mult) * random.uniform(0.5, 1.0), 2)
    crash_at = max(1.01, crash_at)
    state = {"mult": 1.0, "crashed": False, "cashed": False, "crash_at": crash_at}
    bot.active_crashes[ctx.author.id] = state
    embed = gara_embed(title="🚀 Crash — 1.00×",
                       description=f"Bet: **{bet:,}** {get_currency_abbrev(ctx.guild.id)}\nCash out before it crashes!",
                       color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id)
    view = CrashView(ctx.author.id, ctx.guild.id, bet, None)
    msg = await ctx.reply(embed=embed, view=view)
    view.msg_ref = msg

    async def tick():
        tick_val = 0.05
        while not state["crashed"] and not state["cashed"]:
            await asyncio.sleep(2)
            state["mult"] = round(state["mult"] + tick_val, 2)
            tick_val = min(tick_val * 1.05, 1.0)
            if state["mult"] >= state["crash_at"]:
                state["crashed"] = True
                bot.active_crashes.pop(ctx.author.id, None)
                crash_embed = gara_embed(title=f"💥 CRASHED at {state['mult']:.2f}×",
                                         description=f"Lost **{bet:,}** {get_currency_abbrev(ctx.guild.id)}!",
                                         color=GaraConfig.EMBED_COLOR_FAIL, guild_id=ctx.guild.id)
                for item in view.children:
                    item.disabled = True
                try:
                    await msg.edit(embed=crash_embed, view=view)
                except Exception:
                    pass
                view.stop()
                return
            if not state["cashed"]:
                new_embed = gara_embed(title=f"🚀 Crash — {state['mult']:.2f}×",
                                        description=f"Bet: **{bet:,}** {get_currency_abbrev(ctx.guild.id)}\nCash out before it crashes!",
                                        color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id)
                try:
                    await msg.edit(embed=new_embed, view=view)
                except Exception:
                    state["crashed"] = True
                    return

    asyncio.create_task(tick())


@bot.command(name="coinflip", aliases=["cf","flip"])
@commands.cooldown(1, 3, commands.BucketType.user)
async def coinflip_cmd(ctx, bet: int):
    user = await db.get_user(ctx.author.id, ctx.guild.id)
    if bet <= 0 or bet > user["balance"]:
        return await ctx.reply("Invalid bet!")
    view = CoinFlipView(ctx, bet)
    embed = gara_embed(title="🪙 Coin Flip", description="Pick Heads or Tails!",
                       color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id)
    await ctx.reply(embed=embed, view=view)


# ══════════════════════════════════════════
# FAME COMMANDS
# ══════════════════════════════════════════

@bot.command(name="fame")
@commands.cooldown(1, 3, commands.BucketType.user)
async def fame_cmd(ctx, member: discord.Member = None):
    target = member or ctx.author
    user = await db.get_user(target.id, ctx.guild.id)
    embed = gara_embed(title=f"⭐ {target.display_name}'s Fame",
                       color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id,
                       thumbnail=target.display_avatar.url)
    embed.add_field(name="Aura",   value=f"**{user['aura']}**", inline=True)
    embed.add_field(name="Impact", value=f"**{user['impact']}**", inline=True)
    msg = await ctx.reply(embed=embed)
    await msg.add_reaction("⬆️")
    await msg.add_reaction("⬇️")


@bot.command(name="boost")
@commands.cooldown(1, 1, commands.BucketType.user)
async def boost_cmd(ctx, member: discord.Member):
    if member.id == ctx.author.id:
        return await ctx.reply("Can't boost yourself!")
    user = await db.get_user(ctx.author.id, ctx.guild.id)
    last = user.get("last_boost")
    if last:
        dt = datetime.datetime.fromisoformat(last)
        if datetime.datetime.now() - dt < timedelta(hours=GaraConfig.BOOST_COOLDOWN_HOURS):
            remaining = timedelta(hours=GaraConfig.BOOST_COOLDOWN_HOURS) - (datetime.datetime.now() - dt)
            return await ctx.reply(f"Wait **{int(remaining.total_seconds()//60)} min**!")
    target = await db.get_user(member.id, ctx.guild.id)
    await db.boost_user(ctx.author.id, member.id, ctx.guild.id)
    await ctx.reply(embed=gara_embed(title="⬆️ Boosted!",
        description=f"You boosted {member.mention}'s aura to **{target['aura']+1}**!",
        color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))


@bot.command(name="neg")
@commands.cooldown(1, 1, commands.BucketType.user)
async def neg_cmd(ctx, member: discord.Member):
    if member.id == ctx.author.id:
        return await ctx.reply("Can't neg yourself!")
    user = await db.get_user(ctx.author.id, ctx.guild.id)
    last = user.get("last_neg")
    if last:
        dt = datetime.datetime.fromisoformat(last)
        if datetime.datetime.now() - dt < timedelta(hours=GaraConfig.NEG_COOLDOWN_HOURS):
            remaining = timedelta(hours=GaraConfig.NEG_COOLDOWN_HOURS) - (datetime.datetime.now() - dt)
            return await ctx.reply(f"Wait **{int(remaining.total_seconds()//60)} min**!")
    target = await db.get_user(member.id, ctx.guild.id)
    await db.neg_user(ctx.author.id, member.id, ctx.guild.id)
    await ctx.reply(embed=gara_embed(title="⬇️ Negged!",
        description=f"Negged {member.mention}! Their aura: **{max(0,target['aura']-1)}**.",
        color=GaraConfig.EMBED_COLOR_FAIL, guild_id=ctx.guild.id))


@bot.command(name="famous")
@commands.cooldown(1, 5, commands.BucketType.user)
async def famous_cmd(ctx):
    rows = await db.get_fame_leaderboard(ctx.guild.id, 10)
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    desc = ""
    for i, (uid, aura, impact) in enumerate(rows):
        member = ctx.guild.get_member(uid)
        name = member.display_name if member else f"<@{uid}>"
        desc += f"{medals[i]} **{name}** — Aura: {aura} | Impact: {impact}\n"
    await ctx.reply(embed=gara_embed(title="⭐ Most Famous",
        description=desc or "No data.", color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id))


# ══════════════════════════════════════════
# SHOP
# ══════════════════════════════════════════

@bot.command(name="shop", aliases=["store"])
@commands.cooldown(1, 3, commands.BucketType.user)
async def shop_cmd(ctx):
    prefix = get_prefix_for_guild(ctx.guild.id)
    abbrev = get_currency_abbrev(ctx.guild.id)
    embed = gara_embed(title="🛒 Shop", color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id)
    embed.add_field(name="🔇 Mute",
                    value=f"Timeout someone 5 min.\n**{GaraConfig.MUTE_BASE_PRICE:,}** {abbrev} or 10% wealth\n`{prefix}buy mute @user`",
                    inline=False)
    embed.add_field(name="✨ 2.5× Multiplier",
                    value=f"Personal stacking multiplier.\n**{GaraConfig.MULT_SHOP_PRICE:,}** {abbrev} or 20% total wealth\n`{prefix}buy mult`",
                    inline=False)
    # Custom shop roles
    settings = await db.get_settings(ctx.guild.id)
    shop_roles_raw = settings.get("shop_roles", "[]")
    try:
        shop_roles = json.loads(shop_roles_raw) if isinstance(shop_roles_raw, str) else shop_roles_raw
    except Exception:
        shop_roles = []
    for item in shop_roles:
        role = ctx.guild.get_role(item["role_id"])
        if role:
            embed.add_field(name=f"🎭 {role.name}",
                            value=f"**{item['price']:,}** {abbrev}\n`{prefix}buy role {role.id}`",
                            inline=False)
    await ctx.reply(embed=embed)


@bot.command(name="buy")
@commands.cooldown(1, 3, commands.BucketType.user)
async def buy_cmd(ctx, item: str, target: discord.Member = None):
    abbrev = get_currency_abbrev(ctx.guild.id)
    user = await db.get_user(ctx.author.id, ctx.guild.id)
    total_wealth = user["balance"] + user["vault"]

    if item.lower() == "mute":
        if not target:
            return await ctx.reply(f"Usage: `.buy mute @user`")
        price = max(GaraConfig.MUTE_BASE_PRICE, int(total_wealth * 0.1))
        if not await db.sub_balance(ctx.author.id, ctx.guild.id, price):
            return await ctx.reply(f"Need **{price:,}** {abbrev}!")
        try:
            await target.timeout(timedelta(minutes=5), reason=f"Shop mute by {ctx.author.display_name}")
            await ctx.reply(embed=gara_embed(title="🔇 Muted!",
                description=f"{target.mention} muted for 5 min! Cost: **{price:,}** {abbrev}",
                color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))
        except discord.Forbidden:
            await db.add_balance(ctx.author.id, ctx.guild.id, price)
            await ctx.reply("Missing permissions to mute! Refunded.")

    elif item.lower() == "mult":
        price = max(GaraConfig.MULT_SHOP_PRICE, int(total_wealth * 0.2))
        if user.get("mult_bought", 0):
            return await ctx.reply("You already have the 2.5× multiplier!")
        if not await db.sub_balance(ctx.author.id, ctx.guild.id, price):
            return await ctx.reply(f"Need **{price:,}** {abbrev}!")
        await db.update_user(ctx.author.id, ctx.guild.id, mult_bought=1)
        await ctx.reply(embed=gara_embed(title="✨ Multiplier Purchased!",
            description=f"You now have a permanent **2.5×** personal multiplier!",
            color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))

    elif item.lower() == "role":
        if not target:
            return await ctx.reply("Specify a role ID.")
        # target is actually role_id passed as second arg, handle it
        settings = await db.get_settings(ctx.guild.id)
        try:
            shop_roles = json.loads(settings.get("shop_roles", "[]"))
        except Exception:
            shop_roles = []
        role_item = next((r for r in shop_roles if str(r["role_id"]) == str(target.id)), None)
        if not role_item:
            return await ctx.reply("Role not in shop!")
        if not await db.sub_balance(ctx.author.id, ctx.guild.id, role_item["price"]):
            return await ctx.reply(f"Need **{role_item['price']:,}** {abbrev}!")
        role = ctx.guild.get_role(role_item["role_id"])
        if role:
            await ctx.author.add_roles(role)
        await ctx.reply(embed=gara_embed(title="Purchase Complete",
            description=f"You bought {role.mention if role else 'role'}!",
            color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))
    else:
        await ctx.reply(f"Unknown item `{item}`. Check `.shop`.")


# ══════════════════════════════════════════
# CLAN COMMANDS
# ══════════════════════════════════════════

@bot.command(name="clans")
@commands.cooldown(1, 5, commands.BucketType.user)
async def clans_cmd(ctx):
    clans = await db.get_clan_leaderboard(ctx.guild.id, 10)
    mults = get_clan_mults(ctx.guild.id)
    embed = gara_embed(title="🏆 Clan Leaderboard", color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id)
    if not clans:
        embed.description = "No clans yet! Admins can create them with `.createclan`"
    else:
        desc = ""
        for i, clan in enumerate(clans):
            mult_tag = f" **×{mults[i]}**" if i < len(mults) else ""
            desc += f"**{i+1}. {clan['name']}** — {clan['gold']:,} gold{mult_tag}\n"
        embed.description = desc
    await ctx.reply(embed=embed)


@bot.command(name="clanstats")
@commands.cooldown(1, 5, commands.BucketType.user)
async def clanstats_cmd(ctx):
    today = datetime.date.today().isoformat()
    async with aiosqlite.connect(db.db_path) as conn:
        async with conn.execute("""
            SELECT c.name, c.gold, c.weekly_messages, c.weekly_vc_minutes,
                   COALESCE(da.message_count,0) as today_msgs, c.role_id
            FROM clans c
            LEFT JOIN daily_activity da ON c.clan_id=da.clan_id AND da.date=?
            WHERE c.guild_id=?
            ORDER BY c.gold DESC
        """, (today, ctx.guild.id)) as c:
            rows = await c.fetchall()
    mults = get_clan_mults(ctx.guild.id)
    embed = gara_embed(title="🏰 Full Clan Stats", color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id,
                       footer="Active voice only — unmuted and undeafened")
    for i, (name, gold, w_msgs, w_vc, today_msgs, role_id) in enumerate(rows):
        role = ctx.guild.get_role(role_id)
        mention = role.mention if role else name
        mult_str = f" ×{mults[i]}" if i < len(mults) else ""
        embed.add_field(
            name=f"{i+1}. {name}{mult_str}",
            value=f"{mention}\n💰 {gold:,} gold | 💬 {w_msgs} w-msgs | 🎙 {w_vc} w-VC | Today: {today_msgs} msgs",
            inline=False,
        )
    if not rows:
        embed.description = "No clans found."
    await ctx.reply(embed=embed)


@bot.command(name="joinclan")
@commands.cooldown(1, 5, commands.BucketType.user)
async def joinclan_cmd(ctx, *, clan_name: str):
    clan = await db.get_clan(name=clan_name, guild_id=ctx.guild.id)
    if not clan:
        return await ctx.reply("Clan not found!")
    existing = await db.get_user_clan(ctx.author.id, ctx.guild.id)
    if existing:
        return await ctx.reply(f"Leave your current clan first! (`{get_prefix_for_guild(ctx.guild.id)}leaveclan`)")
    async with aiosqlite.connect(db.db_path) as conn:
        await conn.execute(
            "INSERT INTO clan_members(user_id,clan_id,guild_id,personal_gold) VALUES(?,?,?,0)",
            (ctx.author.id, clan["clan_id"], ctx.guild.id),
        )
        await conn.commit()
    role = ctx.guild.get_role(clan.get("role_id") or 0)
    if role:
        try:
            await ctx.author.add_roles(role)
        except Exception:
            pass
    await ctx.reply(embed=gara_embed(title="Clan Joined!",
        description=f"You joined **{clan['name']}**!", color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))


@bot.command(name="leaveclan")
@commands.cooldown(1, 5, commands.BucketType.user)
async def leaveclan_cmd(ctx):
    clan = await db.get_user_clan(ctx.author.id, ctx.guild.id)
    if not clan:
        return await ctx.reply("You're not in a clan!")
    async with aiosqlite.connect(db.db_path) as conn:
        await conn.execute("DELETE FROM clan_members WHERE user_id=? AND clan_id=?",
                           (ctx.author.id, clan["clan_id"]))
        await conn.commit()
    role = ctx.guild.get_role(clan.get("role_id") or 0)
    if role:
        try:
            await ctx.author.remove_roles(role)
        except Exception:
            pass
    await ctx.reply(embed=gara_embed(title="Left Clan",
        description=f"You left **{clan['name']}**.", color=GaraConfig.EMBED_COLOR_WARN, guild_id=ctx.guild.id))


@bot.command(name="mygold")
@commands.cooldown(1, 3, commands.BucketType.user)
async def mygold_cmd(ctx):
    user = await db.get_user(ctx.author.id, ctx.guild.id)
    clan = await db.get_user_clan(ctx.author.id, ctx.guild.id)
    abbrev = get_currency_abbrev(ctx.guild.id)
    embed = gara_embed(title="Your Gold", color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id)
    embed.add_field(name="Wallet", value=f"**{user['balance']:,}** {abbrev}", inline=True)
    if clan:
        embed.add_field(name=f"Clan: {clan['name']}", value=f"**{clan['gold']:,}** total gold", inline=True)
        members = await db.get_clan_members(clan["clan_id"])
        if members:
            share = clan["gold"] // len(members)
            embed.add_field(name="Your Share", value=f"**{share:,}** {abbrev}", inline=True)
    else:
        embed.add_field(name="Clan", value="Not in a clan", inline=True)
    await ctx.reply(embed=embed)


# ── Clan Mini-Games ──

@bot.command(name="tictactoe", aliases=["ttt"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def ttt_cmd(ctx, opponent: discord.Member):
    if opponent.bot or opponent.id == ctx.author.id:
        return await ctx.reply("Invalid opponent!")
    view = TTTView(ctx, opponent, 15000)
    embed = gara_embed(title="Tic-Tac-Toe",
                       description=f"{ctx.author.mention} ❌ vs {opponent.mention} ⭕\n{ctx.author.mention}'s turn!",
                       color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id)
    await ctx.reply(embed=embed, view=view)


@bot.command(name="rps")
@commands.cooldown(1, 5, commands.BucketType.user)
async def rps_cmd(ctx, opponent: discord.Member):
    if opponent.bot or opponent.id == ctx.author.id:
        return await ctx.reply("Invalid opponent!")
    view = RPSView(ctx, opponent, 15000)
    embed = gara_embed(title="Rock Paper Scissors",
                       description=f"{ctx.author.mention} vs {opponent.mention}\nBoth pick secretly!",
                       color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id)
    await ctx.reply(embed=embed, view=view)


@bot.command(name="highcard")
@commands.cooldown(1, 5, commands.BucketType.user)
async def highcard_cmd(ctx, opponent: discord.Member):
    if opponent.bot or opponent.id == ctx.author.id:
        return await ctx.reply("Invalid opponent!")
    values = list(range(2, 15))  # 2-14 (14=Ace)
    names = {11:"J",12:"Q",13:"K",14:"A"}
    a_val = random.choice(values)
    b_val = random.choice(values)
    a_name = names.get(a_val, str(a_val))
    b_name = names.get(b_val, str(b_val))
    CLAN_REWARD = 15000
    if a_val > b_val:
        winner = ctx.author
        loser = opponent
    elif b_val > a_val:
        winner = opponent
        loser = ctx.author
    else:
        winner = None
    if winner:
        clan = await db.get_user_clan(winner.id, ctx.guild.id)
        if clan:
            async with aiosqlite.connect(db.db_path) as conn:
                await conn.execute("UPDATE clans SET gold=gold+? WHERE clan_id=?", (CLAN_REWARD, clan["clan_id"]))
                await conn.commit()
        result = f"{winner.mention} wins with **{a_name if winner==ctx.author else b_name}**!\nClan earns **{CLAN_REWARD:,}** gold!"
        color = GaraConfig.EMBED_COLOR_SUCCESS
    else:
        result = "It's a draw!"
        color = GaraConfig.EMBED_COLOR_WARN
    embed = gara_embed(title="🃏 High Card",
                       description=f"{ctx.author.mention}: `{a_name}` vs {opponent.mention}: `{b_name}`\n\n{result}",
                       color=color, guild_id=ctx.guild.id)
    await ctx.reply(embed=embed)


# ── Clan Wars ──

@bot.command(name="clanwar")
@commands.cooldown(1, 10, commands.BucketType.user)
async def clanwar_cmd(ctx, *, clan_name: str):
    attacker_clan = await db.get_user_clan(ctx.author.id, ctx.guild.id)
    if not attacker_clan:
        return await ctx.reply("You're not in a clan!")
    defender_clan = await db.get_clan(name=clan_name, guild_id=ctx.guild.id)
    if not defender_clan:
        return await ctx.reply("Clan not found!")
    if attacker_clan["clan_id"] == defender_clan["clan_id"]:
        return await ctx.reply("Can't war your own clan!")
    async with aiosqlite.connect(db.db_path) as conn:
        await conn.execute(
            "INSERT INTO clan_wars(guild_id,attacker_clan_id,defender_clan_id) VALUES(?,?,?)",
            (ctx.guild.id, attacker_clan["clan_id"], defender_clan["clan_id"]),
        )
        await conn.commit()
        async with conn.execute("SELECT last_insert_rowid()") as c:
            war_id = (await c.fetchone())[0]
    await ctx.reply(embed=gara_embed(title="⚔️ Clan War Declared!",
        description=f"**{attacker_clan['name']}** vs **{defender_clan['name']}**\nWar ID: `{war_id}`\nUse `.warattack {war_id}` to battle!",
        color=GaraConfig.EMBED_COLOR_WARN, guild_id=ctx.guild.id))


@bot.command(name="warattack")
@commands.cooldown(1, 10, commands.BucketType.user)
async def warattack_cmd(ctx, war_id: int):
    user_clan = await db.get_user_clan(ctx.author.id, ctx.guild.id)
    if not user_clan:
        return await ctx.reply("You're not in a clan!")
    async with aiosqlite.connect(db.db_path) as conn:
        async with conn.execute("SELECT * FROM clan_wars WHERE war_id=? AND status='active'", (war_id,)) as c:
            war = await c.fetchone()
    if not war:
        return await ctx.reply("War not found or already ended!")
    user = await db.get_user(ctx.author.id, ctx.guild.id)
    power = random.randint(100, 1000) + user["aura"] * 10 + random.randint(1, 500)
    async with aiosqlite.connect(db.db_path) as conn:
        war_cols = ["war_id","guild_id","attacker_clan_id","defender_clan_id","attacker_score","defender_score","status","started_at"]
        war_data = dict(zip(war_cols, war))
        if user_clan["clan_id"] == war_data["attacker_clan_id"]:
            await conn.execute("UPDATE clan_wars SET attacker_score=attacker_score+? WHERE war_id=?", (power, war_id))
        else:
            await conn.execute("UPDATE clan_wars SET defender_score=defender_score+? WHERE war_id=?", (power, war_id))
        # Check if war should end (5 attacks total)
        async with conn.execute("SELECT attacker_score,defender_score FROM clan_wars WHERE war_id=?", (war_id,)) as c:
            scores = await c.fetchone()
        await conn.commit()
    embed = gara_embed(title=f"⚔️ War Attack! +{power} power",
                       description=f"Attacker: **{scores[0]:,}** vs Defender: **{scores[1]:,}**",
                       color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id)
    await ctx.reply(embed=embed)


# ══════════════════════════════════════════
# MINI-GAMES
# ══════════════════════════════════════════

@bot.command(name="trivia")
@commands.cooldown(1, 10, commands.BucketType.user)
async def trivia_cmd(ctx):
    q, answer = random.choice(GaraConfig.TRIVIA_QUESTIONS)
    embed = gara_embed(title="🧠 Trivia",
                       description=f"{q}\n\nYou have **15 seconds** to answer!",
                       color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id)
    await ctx.reply(embed=embed)
    def check(m):
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
    try:
        msg = await bot.wait_for("message", timeout=15.0, check=check)
        if msg.content.lower().strip() == answer.lower():
            reward = random.randint(100, 500)
            await db.add_balance(ctx.author.id, ctx.guild.id, reward)
            clan = await db.get_user_clan(ctx.author.id, ctx.guild.id)
            if clan:
                async with aiosqlite.connect(db.db_path) as conn:
                    await conn.execute("UPDATE clans SET gold=gold+500 WHERE clan_id=?", (clan["clan_id"],))
                    await conn.commit()
            await ctx.reply(embed=gara_embed(title="✅ Correct!",
                description=f"Won **{reward:,}** {get_currency_abbrev(ctx.guild.id)}! Clan +500 gold.",
                color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))
        else:
            await ctx.reply(embed=gara_embed(title="❌ Wrong!",
                description=f"Answer: **{answer}**", color=GaraConfig.EMBED_COLOR_FAIL, guild_id=ctx.guild.id))
    except asyncio.TimeoutError:
        await ctx.reply(embed=gara_embed(title="⏰ Time's Up!",
            description=f"Answer: **{answer}**", color=GaraConfig.EMBED_COLOR_WARN, guild_id=ctx.guild.id))


@bot.command(name="numguess")
@commands.cooldown(1, 10, commands.BucketType.user)
async def numguess_cmd(ctx):
    number = random.randint(1, 100)
    await ctx.reply(embed=gara_embed(title="🔢 Number Guess",
        description="Guess a number between **1 and 100**! You have **3 tries**.",
        color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id))
    def check(m):
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
    for attempt in range(3):
        try:
            msg = await bot.wait_for("message", timeout=20.0, check=check)
            try:
                guess = int(msg.content)
            except ValueError:
                await ctx.reply("Please enter a number!", delete_after=3)
                continue
            if guess == number:
                reward = (3 - attempt) * 200
                await db.add_balance(ctx.author.id, ctx.guild.id, reward)
                await ctx.reply(embed=gara_embed(title="✅ Correct!",
                    description=f"The number was **{number}**! Won **{reward:,}** {get_currency_abbrev(ctx.guild.id)}!",
                    color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))
                return
            hint = "higher ↑" if guess < number else "lower ↓"
            remaining = 2 - attempt
            await ctx.reply(f"Wrong! Go **{hint}**. {remaining} tries left." if remaining else "Wrong! Reveal coming...")
        except asyncio.TimeoutError:
            break
    await ctx.reply(embed=gara_embed(title="❌ Game Over",
        description=f"The number was **{number}**.", color=GaraConfig.EMBED_COLOR_FAIL, guild_id=ctx.guild.id))


@bot.command(name="diceroll", aliases=["dice"])
@commands.cooldown(1, 5, commands.BucketType.user)
async def diceroll_cmd(ctx, bet: int):
    user = await db.get_user(ctx.author.id, ctx.guild.id)
    if bet <= 0 or bet > user["balance"]:
        return await ctx.reply("Invalid bet!")
    player_roll = random.randint(1, 6) + random.randint(1, 6)
    house_roll = random.randint(1, 6) + random.randint(1, 6)
    abbrev = get_currency_abbrev(ctx.guild.id)
    if player_roll > house_roll:
        mult = await get_effective_mult(ctx.author.id, ctx.guild.id)
        win = int(bet * mult)
        await db.add_balance(ctx.author.id, ctx.guild.id, win)
        result = f"You win **{win:,}** {abbrev}!"
        color = GaraConfig.EMBED_COLOR_SUCCESS
    elif player_roll < house_roll:
        await db.sub_balance(ctx.author.id, ctx.guild.id, bet)
        result = f"Lost **{bet:,}** {abbrev}."
        color = GaraConfig.EMBED_COLOR_FAIL
    else:
        result = "Push! No coins lost."
        color = GaraConfig.EMBED_COLOR_WARN
    embed = gara_embed(title="🎲 Dice Roll",
        description=f"🎲 You: **{player_roll}** | House: **{house_roll}**\n{result}",
        color=color, guild_id=ctx.guild.id)
    await ctx.reply(embed=embed)


SCRAMBLE_WORDS = ["discord","economy","casino","balance","deposit","leaderboard",
                  "multiplier","giveaway","gambling","champion","treasure","phantom"]

@bot.command(name="scramble")
@commands.cooldown(1, 10, commands.BucketType.user)
async def scramble_cmd(ctx):
    word = random.choice(SCRAMBLE_WORDS)
    scrambled = list(word)
    random.shuffle(scrambled)
    scrambled_str = "".join(scrambled)
    await ctx.reply(embed=gara_embed(title="🔤 Word Scramble",
        description=f"Unscramble: **`{scrambled_str}`**\n20 seconds!",
        color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id))
    def check(m):
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
    try:
        msg = await bot.wait_for("message", timeout=20.0, check=check)
        if msg.content.lower().strip() == word:
            reward = len(word) * 50
            await db.add_balance(ctx.author.id, ctx.guild.id, reward)
            await ctx.reply(embed=gara_embed(title="✅ Correct!",
                description=f"Word: **{word}** — Won **{reward:,}** {get_currency_abbrev(ctx.guild.id)}!",
                color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))
        else:
            await ctx.reply(embed=gara_embed(title="❌ Wrong!",
                description=f"Word was: **{word}**", color=GaraConfig.EMBED_COLOR_FAIL, guild_id=ctx.guild.id))
    except asyncio.TimeoutError:
        await ctx.reply(embed=gara_embed(title="⏰ Time's Up!",
            description=f"Word was: **{word}**", color=GaraConfig.EMBED_COLOR_WARN, guild_id=ctx.guild.id))


# ══════════════════════════════════════════
# GIVEAWAY
# ══════════════════════════════════════════

def parse_duration(s: str) -> Optional[timedelta]:
    s = s.lower().strip()
    try:
        if s.endswith("d"):
            return timedelta(days=int(s[:-1]))
        if s.endswith("h"):
            return timedelta(hours=int(s[:-1]))
        if s.endswith("m"):
            return timedelta(minutes=int(s[:-1]))
    except Exception:
        pass
    return None


@bot.command(name="giveaway")
@commands.cooldown(1, 10, commands.BucketType.user)
async def giveaway_cmd(ctx, duration: str, *, prize: str):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    delta = parse_duration(duration)
    if not delta:
        return await ctx.reply("Invalid duration! Use e.g. `1d`, `2h`, `30m`")
    end_time = (datetime.datetime.now() + delta).isoformat()
    embed = gara_embed(title="🎉 Giveaway!",
        description=f"**Prize:** {prize}\nReact with 🎉 to enter!\nEnds: **{duration}** from now.",
        color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id)
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")
    await db.create_giveaway(ctx.guild.id, ctx.channel.id, msg.id, prize, end_time)
    await ctx.message.delete(delay=2)


# ══════════════════════════════════════════
# STATS
# ══════════════════════════════════════════

@bot.command(name="stats")
@commands.cooldown(1, 5, commands.BucketType.user)
async def stats_cmd(ctx, member: discord.Member = None):
    target = member or ctx.author
    user = await db.get_user(target.id, ctx.guild.id)
    hours = user.get("vc_hours", 0) or 0
    tiers = get_tiers(ctx.guild.id)
    tier = await get_user_tier(ctx.guild.id, hours)
    sorted_tiers = sorted(tiers, key=lambda x: x["hours"])
    next_tier = next((t for t in sorted_tiers if t["hours"] > hours), None)
    embed = gara_embed(title=f"📊 {target.display_name}'s Stats",
                       color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id,
                       thumbnail=target.display_avatar.url,
                       footer="Active voice only — unmuted and undeafened")
    embed.add_field(name="VC Hours",       value=f"**{hours:.1f}h**", inline=True)
    embed.add_field(name="Current Tier",   value=tier["name"] if tier else "None", inline=True)
    if next_tier:
        embed.add_field(name="Next Tier",  value=f"**{next_tier['name']}** in {next_tier['hours']-hours:.1f}h", inline=True)
    else:
        embed.add_field(name="Status",     value="**MAX TIER**", inline=True)
    embed.add_field(name="Weekly Msgs",    value=str(user.get("weekly_messages", 0)), inline=True)
    embed.add_field(name="Weekly VC",      value=f"{user.get('weekly_vc_minutes',0)} min", inline=True)
    await ctx.reply(embed=embed)


# ══════════════════════════════════════════
# BATTLE
# ══════════════════════════════════════════

@bot.command(name="battle")
@commands.cooldown(1, 5, commands.BucketType.user)
async def battle_cmd(ctx, opponent: discord.Member):
    if opponent.bot or opponent.id == ctx.author.id:
        return await ctx.reply("Invalid opponent!")
    user = await db.get_user(ctx.author.id, ctx.guild.id)
    opp = await db.get_user(opponent.id, ctx.guild.id)
    bet = min(user["balance"] // 10, opp["balance"] // 10, 10000)
    if bet <= 0:
        return await ctx.reply("One of you doesn't have enough to battle!")
    # Fully randomized: 100-1000 base + aura×10 + 1-500 bonus
    u_power = random.randint(100, 1000) + user["aura"] * 10 + random.randint(1, 500)
    o_power = random.randint(100, 1000) + opp["aura"] * 10 + random.randint(1, 500)
    abbrev = get_currency_abbrev(ctx.guild.id)
    if u_power > o_power:
        winner, loser = ctx.author, opponent
        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute("UPDATE users SET balance=balance+? WHERE user_id=? AND guild_id=?", (bet, ctx.author.id, ctx.guild.id))
            await conn.execute("UPDATE users SET balance=MAX(0,balance-?) WHERE user_id=? AND guild_id=?", (bet, opponent.id, ctx.guild.id))
            await conn.commit()
        color = GaraConfig.EMBED_COLOR_SUCCESS
    elif o_power > u_power:
        winner, loser = opponent, ctx.author
        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute("UPDATE users SET balance=balance+? WHERE user_id=? AND guild_id=?", (bet, opponent.id, ctx.guild.id))
            await conn.execute("UPDATE users SET balance=MAX(0,balance-?) WHERE user_id=? AND guild_id=?", (bet, ctx.author.id, ctx.guild.id))
            await conn.commit()
        color = GaraConfig.EMBED_COLOR_FAIL
    else:
        winner = loser = None
        color = GaraConfig.EMBED_COLOR_WARN
    embed = gara_embed(title="⚔️ Battle!", color=color, guild_id=ctx.guild.id)
    if winner:
        embed.description = f"**{winner.mention}** defeated {loser.mention}!\n**{bet:,}** {abbrev} transferred!"
    else:
        embed.description = "It's a draw! No coins moved."
    embed.add_field(name=ctx.author.display_name,  value=f"Power: {u_power:,}", inline=True)
    embed.add_field(name=opponent.display_name, value=f"Power: {o_power:,}", inline=True)
    await ctx.reply(embed=embed)


# ══════════════════════════════════════════
# HELP
# ══════════════════════════════════════════

@bot.command(name="help")
@commands.cooldown(1, 3, commands.BucketType.user)
async def help_cmd(ctx):
    view = HelpView(ctx)
    await ctx.reply(embed=view.main_embed(), view=view)


# ══════════════════════════════════════════
# ADMIN COMMANDS
# ══════════════════════════════════════════

@bot.command(name="givemoney", aliases=["addmoney"])
@commands.cooldown(1, 1, commands.BucketType.user)
async def givemoney_cmd(ctx, member: discord.Member, amount: int):
    if not is_admin(ctx):
        return await ctx.reply("No permission!")
    await db.add_balance(member.id, ctx.guild.id, amount)
    await ctx.reply(embed=gara_embed(title="Admin Transfer",
        description=f"Gave **{amount:,}** {get_currency_abbrev(ctx.guild.id)} to {member.mention}!",
        color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))


@bot.command(name="takemoney", aliases=["removemoney"])
@commands.cooldown(1, 1, commands.BucketType.user)
async def takemoney_cmd(ctx, member: discord.Member, amount: int):
    if not is_admin(ctx):
        return await ctx.reply("No permission!")
    await db.sub_balance(member.id, ctx.guild.id, amount)
    await ctx.reply(embed=gara_embed(title="Admin Deduction",
        description=f"Took **{amount:,}** {get_currency_abbrev(ctx.guild.id)} from {member.mention}!",
        color=GaraConfig.EMBED_COLOR_WARN, guild_id=ctx.guild.id))


@bot.command(name="setprefix")
@commands.cooldown(1, 1, commands.BucketType.user)
async def setprefix_cmd(ctx, new_prefix: str):
    if not is_admin(ctx):
        return await ctx.reply("No permission!")
    if len(new_prefix) > 5:
        return await ctx.reply("Max 5 chars!")
    await db.set_setting(ctx.guild.id, prefix=new_prefix)
    bot.guild_settings.setdefault(ctx.guild.id, {})["prefix"] = new_prefix
    await ctx.reply(embed=gara_embed(title="Prefix Updated",
        description=f"New prefix: `{new_prefix}`", color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))


@bot.command(name="setcurrency")
@commands.cooldown(1, 1, commands.BucketType.user)
async def setcurrency_cmd(ctx, name: str, abbrev: str):
    if not is_admin(ctx):
        return await ctx.reply("No permission!")
    await db.set_setting(ctx.guild.id, currency_name=name, currency_abbrev=abbrev)
    s = bot.guild_settings.setdefault(ctx.guild.id, {})
    s["currency_name"] = name
    s["currency_abbrev"] = abbrev
    await ctx.reply(embed=gara_embed(title="Currency Updated",
        description=f"Now: **{name}** ({abbrev})", color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))


@bot.command(name="createclan")
@commands.cooldown(1, 1, commands.BucketType.user)
async def createclan_cmd(ctx, name: str, role: discord.Role):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    async with aiosqlite.connect(db.db_path) as conn:
        try:
            await conn.execute(
                "INSERT INTO clans(name,role_id,guild_id,last_active) VALUES(?,?,?,?)",
                (name, role.id, ctx.guild.id, datetime.date.today().isoformat()),
            )
            await conn.commit()
        except Exception:
            return await ctx.reply("A clan with that name already exists!")
    await ctx.reply(embed=gara_embed(title="Clan Created",
        description=f"Clan **{name}** ({role.mention}) created!",
        color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))


@bot.command(name="giveclan")
@commands.cooldown(1, 1, commands.BucketType.user)
async def giveclan_cmd(ctx, clan_name: str, amount: int):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    clan = await db.get_clan(name=clan_name, guild_id=ctx.guild.id)
    if not clan:
        return await ctx.reply("Clan not found!")
    async with aiosqlite.connect(db.db_path) as conn:
        await conn.execute("UPDATE clans SET gold=gold+? WHERE clan_id=?", (amount, clan["clan_id"]))
        await conn.commit()
    await ctx.reply(embed=gara_embed(title="Clan Gold Given",
        description=f"Gave **{amount:,}** gold to **{clan_name}**!",
        color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))


@bot.command(name="setroleschannel")
@commands.cooldown(1, 1, commands.BucketType.user)
async def setroleschannel_cmd(ctx, channel: discord.TextChannel):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    tiers = get_tiers(ctx.guild.id)
    sorted_tiers = sorted(tiers, key=lambda x: x["hours"], reverse=True)  # Inverted: highest first
    abbrev = get_currency_abbrev(ctx.guild.id)
    desc = ""
    for t in sorted_tiers:
        desc += f"**{t['name']}** — {t['hours']}h | {t['daily']:,} {abbrev}/day | ×{t['mult']}\n"
    embed = gara_embed(title="🏅 Earn Roles",
                       description=desc,
                       color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id,
                       footer="Active voice time only — unmuted and undeafened")
    msg = await channel.send(embed=embed)
    await db.set_setting(ctx.guild.id, roles_channel=channel.id, roles_msg_id=msg.id)
    await ctx.reply(f"Roles UI posted in {channel.mention}!")


@bot.command(name="updaterolesui")
@commands.cooldown(1, 1, commands.BucketType.user)
async def updaterolesui_cmd(ctx):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    settings = await db.get_settings(ctx.guild.id)
    ch_id = settings.get("roles_channel", 0)
    msg_id = settings.get("roles_msg_id", 0)
    if not ch_id or not msg_id:
        return await ctx.reply("No roles channel set! Use `.setroleschannel #channel` first.")
    ch = ctx.guild.get_channel(ch_id)
    if not ch:
        return await ctx.reply("Roles channel not found!")
    try:
        msg = await ch.fetch_message(msg_id)
        tiers = get_tiers(ctx.guild.id)
        sorted_tiers = sorted(tiers, key=lambda x: x["hours"], reverse=True)
        abbrev = get_currency_abbrev(ctx.guild.id)
        desc = ""
        for t in sorted_tiers:
            desc += f"**{t['name']}** — {t['hours']}h | {t['daily']:,} {abbrev}/day | ×{t['mult']}\n"
        embed = gara_embed(title="🏅 Earn Roles", description=desc,
                           color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id,
                           footer="Active voice time only — unmuted and undeafened")
        await msg.edit(embed=embed)
        await ctx.reply("✅ Roles UI updated!")
    except Exception as e:
        await ctx.reply(f"Failed: {e}")


@bot.command(name="setactivitychannel")
@commands.cooldown(1, 1, commands.BucketType.user)
async def setactivitychannel_cmd(ctx, channel: discord.TextChannel):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    embed = gara_embed(title="💰 Activity Leaderboard",
                       description="Loading...", color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id,
                       footer="Active voice only — unmuted and undeafened")
    msg = await channel.send(embed=embed)
    await db.set_setting(ctx.guild.id, activity_channel=channel.id, activity_msg_id=msg.id)
    bot.guild_settings.setdefault(ctx.guild.id, {}).update({"activity_channel": channel.id, "activity_msg_id": msg.id})
    await ctx.reply(f"Activity LB channel set to {channel.mention}!")


@bot.command(name="setclanchannel")
@commands.cooldown(1, 1, commands.BucketType.user)
async def setclanchannel_cmd(ctx, channel: discord.TextChannel):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    embed = gara_embed(title="🏆 Clan Leaderboard",
                       description="Loading...", color=GaraConfig.EMBED_COLOR_ACCENT, guild_id=ctx.guild.id)
    msg = await channel.send(embed=embed)
    await db.set_setting(ctx.guild.id, clan_channel=channel.id, clan_msg_id=msg.id)
    bot.guild_settings.setdefault(ctx.guild.id, {}).update({"clan_channel": channel.id, "clan_msg_id": msg.id})
    await ctx.reply(f"Clan LB channel set to {channel.mention}!")


@bot.command(name="setblankui")
@commands.cooldown(1, 1, commands.BucketType.user)
async def setblankui_cmd(ctx, channel: discord.TextChannel):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    embed = discord.Embed(description="\u200b", color=0x000000)
    msg = await channel.send(embed=embed)
    await db.set_setting(ctx.guild.id, blank_ui_channel=channel.id, blank_ui_msg_id=msg.id,
                         blank_ui_title="", blank_ui_desc="", blank_ui_color="000000")
    await ctx.reply(f"Blank UI posted in {channel.mention}!")


@bot.command(name="editblankui")
@commands.cooldown(1, 1, commands.BucketType.user)
async def editblankui_cmd(ctx, field: str, *, value: str):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    settings = await db.get_settings(ctx.guild.id)
    ch_id = settings.get("blank_ui_channel", 0)
    msg_id = settings.get("blank_ui_msg_id", 0)
    if not ch_id or not msg_id:
        return await ctx.reply("No blank UI set! Use `.setblankui #channel` first.")
    ch = ctx.guild.get_channel(ch_id)
    if not ch:
        return await ctx.reply("Channel not found!")
    try:
        msg = await ch.fetch_message(msg_id)
        title = settings.get("blank_ui_title", "")
        desc = settings.get("blank_ui_desc", "")
        color_hex = settings.get("blank_ui_color", "000000")
        field = field.lower()
        if field == "title":
            title = value
            await db.set_setting(ctx.guild.id, blank_ui_title=title)
        elif field == "description":
            desc = value
            await db.set_setting(ctx.guild.id, blank_ui_desc=desc)
        elif field == "color":
            color_hex = value.lstrip("#")
            await db.set_setting(ctx.guild.id, blank_ui_color=color_hex)
        else:
            return await ctx.reply("Field must be `title`, `description`, or `color`.")
        try:
            color_int = int(color_hex, 16)
        except Exception:
            color_int = 0
        embed = discord.Embed(title=title or None, description=desc or "\u200b", color=color_int)
        await msg.edit(embed=embed)
        await ctx.reply("✅ Blank UI updated!")
    except Exception as e:
        await ctx.reply(f"Failed: {e}")


@bot.command(name="setrandomvc")
@commands.cooldown(1, 1, commands.BucketType.user)
async def setrandomvc_cmd(ctx, channel: discord.VoiceChannel):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    await db.set_setting(ctx.guild.id, random_vc=channel.id)
    bot.guild_settings.setdefault(ctx.guild.id, {})["random_vc"] = channel.id
    await ctx.reply(f"Random VC set to **{channel.name}**! Members who join will be moved to a random other VC.")


@bot.command(name="blacklistvc")
@commands.cooldown(1, 1, commands.BucketType.user)
async def blacklistvc_cmd(ctx, channel: discord.VoiceChannel):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    settings = await db.get_settings(ctx.guild.id)
    try:
        bl = json.loads(settings.get("vc_blacklist", "[]"))
    except Exception:
        bl = []
    if channel.id not in bl:
        bl.append(channel.id)
    await db.set_setting(ctx.guild.id, vc_blacklist=json.dumps(bl))
    await ctx.reply(f"**{channel.name}** blacklisted from random VC redirects.")


@bot.command(name="unblacklistvc")
@commands.cooldown(1, 1, commands.BucketType.user)
async def unblacklistvc_cmd(ctx, channel: discord.VoiceChannel):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    settings = await db.get_settings(ctx.guild.id)
    try:
        bl = json.loads(settings.get("vc_blacklist", "[]"))
    except Exception:
        bl = []
    bl = [c for c in bl if c != channel.id]
    await db.set_setting(ctx.guild.id, vc_blacklist=json.dumps(bl))
    await ctx.reply(f"**{channel.name}** removed from VC blacklist.")


@bot.command(name="lockcycle")
@commands.cooldown(1, 1, commands.BucketType.user)
async def lockcycle_cmd(ctx, open_time: str, close_time: str, channel: discord.TextChannel = None):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    target = channel or ctx.channel
    def parse_time(s):
        s = s.upper().strip()
        if not (s.endswith("AM") or s.endswith("PM")):
            return None, "You must include AM or PM (e.g. 9:00AM, 10:00PM)"
        is_pm = s.endswith("PM")
        time_part = s[:-2]
        try:
            h, m = map(int, time_part.split(":"))
        except Exception:
            return None, "Use format HH:MM AM/PM"
        if is_pm and h != 12:
            h += 12
        if not is_pm and h == 12:
            h = 0
        if not (0 <= h <= 23 and 0 <= m <= 59):
            return None, "Invalid time"
        return (h, m), None
    open_parsed, err = parse_time(open_time)
    if err:
        return await ctx.reply(f"❌ Open time: {err}")
    close_parsed, err = parse_time(close_time)
    if err:
        return await ctx.reply(f"❌ Close time: {err}")
    bot.lockcycles[target.id] = {"open": open_parsed, "close": close_parsed, "guild_id": ctx.guild.id}
    embed = gara_embed(title="🔒 Lock Cycle Set",
        description=f"Channel: {target.mention}\nOpens: **{open_time}** | Locks: **{close_time}**",
        color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id)
    await ctx.reply(embed=embed)


@bot.command(name="setclanmult")
@commands.cooldown(1, 1, commands.BucketType.user)
async def setclanmult_cmd(ctx, rank: int, mult: float):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    if rank not in (1, 2, 3):
        return await ctx.reply("Rank must be 1, 2, or 3.")
    mults = get_clan_mults(ctx.guild.id)
    while len(mults) < 3:
        mults.append(1.0)
    mults[rank - 1] = mult
    await db.set_setting(ctx.guild.id, clan_mults=json.dumps(mults))
    bot.guild_settings.setdefault(ctx.guild.id, {})["clan_mults"] = json.dumps(mults)
    await ctx.reply(embed=gara_embed(title="Clan Multiplier Updated",
        description=f"Rank {rank} clan multiplier: **×{mult}**",
        color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id))


@bot.command(name="settiername")
@commands.cooldown(1, 1, commands.BucketType.user)
async def settiername_cmd(ctx, tier_num: int, *, name: str):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    if not 1 <= tier_num <= 5:
        return await ctx.reply("Tier must be 1-5.")
    tiers = get_tiers(ctx.guild.id)
    tiers[tier_num - 1]["name"] = name
    await db.set_setting(ctx.guild.id, tier_config=json.dumps(tiers))
    bot.guild_settings.setdefault(ctx.guild.id, {})["tier_config"] = json.dumps(tiers)
    await ctx.reply(f"Tier {tier_num} renamed to **{name}**.")


@bot.command(name="settierrole")
@commands.cooldown(1, 1, commands.BucketType.user)
async def settierrole_cmd(ctx, tier_num: int, role: discord.Role):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    if not 1 <= tier_num <= 5:
        return await ctx.reply("Tier must be 1-5.")
    tiers = get_tiers(ctx.guild.id)
    tiers[tier_num - 1]["role_id"] = role.id
    await db.set_setting(ctx.guild.id, tier_config=json.dumps(tiers))
    bot.guild_settings.setdefault(ctx.guild.id, {})["tier_config"] = json.dumps(tiers)
    await ctx.reply(f"Tier {tier_num} role set to {role.mention}.")


@bot.command(name="settierhours")
@commands.cooldown(1, 1, commands.BucketType.user)
async def settierhours_cmd(ctx, tier_num: int, hours: float):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    if not 1 <= tier_num <= 5:
        return await ctx.reply("Tier must be 1-5.")
    tiers = get_tiers(ctx.guild.id)
    tiers[tier_num - 1]["hours"] = hours
    await db.set_setting(ctx.guild.id, tier_config=json.dumps(tiers))
    bot.guild_settings.setdefault(ctx.guild.id, {})["tier_config"] = json.dumps(tiers)
    await ctx.reply(f"Tier {tier_num} hours set to **{hours}h**.")


@bot.command(name="settiercoins")
@commands.cooldown(1, 1, commands.BucketType.user)
async def settiercoins_cmd(ctx, tier_num: int, coins: int):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    if not 1 <= tier_num <= 5:
        return await ctx.reply("Tier must be 1-5.")
    tiers = get_tiers(ctx.guild.id)
    tiers[tier_num - 1]["daily"] = coins
    await db.set_setting(ctx.guild.id, tier_config=json.dumps(tiers))
    bot.guild_settings.setdefault(ctx.guild.id, {})["tier_config"] = json.dumps(tiers)
    await ctx.reply(f"Tier {tier_num} daily coins set to **{coins:,}**.")


@bot.command(name="setrichrole")
@commands.cooldown(1, 1, commands.BucketType.user)
async def setrichrole_cmd(ctx, rank: int, role: discord.Role):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    if not 1 <= rank <= 5:
        return await ctx.reply("Rank must be 1-5.")
    settings = await db.get_settings(ctx.guild.id)
    try:
        rich_roles = json.loads(settings.get("rich_roles", "[]"))
    except Exception:
        rich_roles = []
    while len(rich_roles) < 5:
        rich_roles.append(0)
    rich_roles[rank - 1] = role.id
    await db.set_setting(ctx.guild.id, rich_roles=json.dumps(rich_roles))
    await ctx.reply(f"Rich role rank {rank} set to {role.mention}.")


@bot.command(name="addshoprole")
@commands.cooldown(1, 1, commands.BucketType.user)
async def addshoprole_cmd(ctx, role: discord.Role, price: int):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    settings = await db.get_settings(ctx.guild.id)
    try:
        shop_roles = json.loads(settings.get("shop_roles", "[]"))
    except Exception:
        shop_roles = []
    if len(shop_roles) >= 5:
        return await ctx.reply("Maximum 5 shop roles!")
    shop_roles = [r for r in shop_roles if r["role_id"] != role.id]
    shop_roles.append({"role_id": role.id, "price": price})
    await db.set_setting(ctx.guild.id, shop_roles=json.dumps(shop_roles))
    await ctx.reply(f"Added {role.mention} to shop for **{price:,}** {get_currency_abbrev(ctx.guild.id)}!")


@bot.command(name="removeshoprole")
@commands.cooldown(1, 1, commands.BucketType.user)
async def removeshoprole_cmd(ctx, role: discord.Role):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    settings = await db.get_settings(ctx.guild.id)
    try:
        shop_roles = json.loads(settings.get("shop_roles", "[]"))
    except Exception:
        shop_roles = []
    shop_roles = [r for r in shop_roles if r["role_id"] != role.id]
    await db.set_setting(ctx.guild.id, shop_roles=json.dumps(shop_roles))
    await ctx.reply(f"Removed {role.mention} from shop.")


@bot.command(name="setgiveaway")
@commands.cooldown(1, 1, commands.BucketType.user)
async def setgiveaway_cmd(ctx, channel: discord.TextChannel, *, prize: str):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    await db.set_setting(ctx.guild.id, giveaway_channel=channel.id, giveaway_prize=prize)
    await ctx.reply(f"Weekly auto-giveaway set in {channel.mention} with prize: **{prize}**.")


@bot.command(name="setcrashmult")
@commands.cooldown(1, 1, commands.BucketType.user)
async def setcrashmult_cmd(ctx, max_mult: float):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    if max_mult < 2.0:
        return await ctx.reply("Min crash ceiling is 2.0×")
    await db.set_setting(ctx.guild.id, crash_max_mult=max_mult)
    bot.guild_settings.setdefault(ctx.guild.id, {})["crash_max_mult"] = max_mult
    await ctx.reply(f"Crash max multiplier set to **{max_mult}×**.")


@bot.command(name="spin")
@commands.cooldown(1, 1, commands.BucketType.user)
async def spin_cmd(ctx):
    if not is_admin(ctx):
        return await ctx.reply("Admin only!")
    clans = await db.get_clan_leaderboard(ctx.guild.id, 1)
    if not clans:
        return await ctx.reply("No clans active!")
    winning_clan = clans[0]
    members = await db.get_clan_members(winning_clan["clan_id"])
    if not members:
        return await ctx.reply("No members in winning clan!")
    winner_id = random.choice(members)
    winner = ctx.guild.get_member(winner_id)
    mention = winner.mention if winner else f"<@{winner_id}>"
    embed = gara_embed(title="🎰 Nitro Spin!",
        description=f"Winning Clan: **{winning_clan['name']}**\n🎉 Winner: {mention}\n\n**Discord Nitro Classic** prize!",
        color=GaraConfig.EMBED_COLOR_SUCCESS, guild_id=ctx.guild.id)
    await ctx.reply(embed=embed)
    async with aiosqlite.connect(db.db_path) as conn:
        await conn.execute("UPDATE clans SET gold=0 WHERE guild_id=?", (ctx.guild.id,))
        await conn.commit()


# ══════════════════════════════════════════
# FLASK WEB DASHBOARD
# ══════════════════════════════════════════

flask_app = Flask("")

@flask_app.route("/")
def dashboard():
    server_count = len(bot.guilds) if bot.is_ready() else 0
    user_count = sum(g.member_count for g in bot.guilds) if bot.is_ready() else 0
    return f"""<!DOCTYPE html>
<html>
<head>
  <title>GARA Bot Dashboard</title>
  <meta http-equiv="refresh" content="30">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #000; color: #fff; font-family: 'Courier New', monospace; padding: 30px; }}
    h1 {{ color: #00FF88; font-size: 2.5em; margin-bottom: 10px; }}
    .subtitle {{ color: #888; margin-bottom: 30px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px,1fr)); gap: 16px; margin-bottom: 30px; }}
    .card {{ background: #0a0a0a; border: 1px solid #1a1a1a; border-radius: 8px; padding: 20px; }}
    .card h3 {{ color: #00FF88; font-size: 0.85em; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }}
    .card .val {{ font-size: 2em; font-weight: bold; }}
    .status {{ color: #00FF88; }}
    footer {{ color: #444; font-size: 0.8em; margin-top: 30px; }}
  </style>
</head>
<body>
  <h1>⬡ GARA</h1>
  <p class="subtitle">Live Bot Dashboard — auto-refreshes every 30s</p>
  <div class="grid">
    <div class="card"><h3>Status</h3><div class="val status">● ONLINE</div></div>
    <div class="card"><h3>Servers</h3><div class="val">{server_count}</div></div>
    <div class="card"><h3>Users</h3><div class="val">{user_count:,}</div></div>
    <div class="card"><h3>Prefix</h3><div class="val">{GaraConfig.PREFIX}</div></div>
    <div class="card"><h3>Currency</h3><div class="val">{GaraConfig.CURRENCY_NAME}</div></div>
  </div>
  <footer>GARA Discord Bot • {GaraConfig.BOT_NAME} • Active voice only — unmuted and undeafened</footer>
</body>
</html>"""

@flask_app.route("/health")
def health():
    return jsonify({"status": "ok", "bot": GaraConfig.BOT_NAME, "guilds": len(bot.guilds)})


def run_flask():
    port = int(os.environ.get("PORT", 3000))
    flask_app.run(host="0.0.0.0", port=port, use_reloader=False)

def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()


# ══════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════

if __name__ == "__main__":
    keep_alive()
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        print("ERROR: DISCORD_TOKEN not set!")
        print("  Railway: Variables → Add DISCORD_TOKEN")
        print("  Replit: Secrets → Add DISCORD_TOKEN")
    else:
        bot.run(TOKEN)

from __future__ import annotations

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    guild_id INTEGER NOT NULL, key TEXT NOT NULL, value TEXT,
    PRIMARY KEY (guild_id, key)
);
CREATE TABLE IF NOT EXISTS warns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL, reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS levels (
    guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    xp INTEGER NOT NULL DEFAULT 0, level INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);
CREATE TABLE IF NOT EXISTS sub_hashes (
    guild_id INTEGER NOT NULL, hash TEXT NOT NULL, user_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, hash)
);
CREATE TABLE IF NOT EXISTS economy (
    guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    balance INTEGER NOT NULL DEFAULT 0,
    last_daily REAL NOT NULL DEFAULT 0, last_work REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL, guild_id INTEGER, channel_id INTEGER,
    remind_at REAL NOT NULL, text TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str = "data.db"):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.path)
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()

    # ---------- ayarlar ----------
    async def get(self, guild_id: int, key: str, default=None):
        async with self.conn.execute(
            "SELECT value FROM settings WHERE guild_id=? AND key=?", (guild_id, key)
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row and row[0] is not None else default

    async def get_int(self, guild_id: int, key: str, default=None):
        v = await self.get(guild_id, key)
        try:
            return int(v) if v is not None else default
        except ValueError:
            return default

    async def get_prefix(self, guild_id: int, prefix: str) -> dict:
        async with self.conn.execute(
            "SELECT key, value FROM settings WHERE guild_id=? AND key LIKE ?",
            (guild_id, prefix + "%"),
        ) as cur:
            rows = await cur.fetchall()
        return {k: v for k, v in rows}

    async def set(self, guild_id: int, key: str, value):
        if value is None:
            await self.conn.execute(
                "DELETE FROM settings WHERE guild_id=? AND key=?", (guild_id, key)
            )
        else:
            await self.conn.execute(
                "INSERT INTO settings (guild_id, key, value) VALUES (?,?,?) "
                "ON CONFLICT(guild_id, key) DO UPDATE SET value=excluded.value",
                (guild_id, key, str(value)),
            )
        await self.conn.commit()

    # ---------- uyarılar ----------
    async def add_warn(self, guild_id, user_id, mod_id, reason) -> int:
        await self.conn.execute(
            "INSERT INTO warns (guild_id, user_id, moderator_id, reason) VALUES (?,?,?,?)",
            (guild_id, user_id, mod_id, reason),
        )
        await self.conn.commit()
        return await self.count_warns(guild_id, user_id)

    async def count_warns(self, guild_id, user_id) -> int:
        async with self.conn.execute(
            "SELECT COUNT(*) FROM warns WHERE guild_id=? AND user_id=?", (guild_id, user_id)
        ) as cur:
            return (await cur.fetchone())[0]

    async def get_warns(self, guild_id, user_id):
        async with self.conn.execute(
            "SELECT id, moderator_id, reason, created_at FROM warns "
            "WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 15",
            (guild_id, user_id),
        ) as cur:
            return await cur.fetchall()

    async def delete_warn(self, guild_id, warn_id) -> int:
        cur = await self.conn.execute(
            "DELETE FROM warns WHERE guild_id=? AND id=?", (guild_id, warn_id)
        )
        await self.conn.commit()
        return cur.rowcount

    async def clear_warns(self, guild_id, user_id) -> int:
        cur = await self.conn.execute(
            "DELETE FROM warns WHERE guild_id=? AND user_id=?", (guild_id, user_id)
        )
        await self.conn.commit()
        return cur.rowcount

    # ---------- seviye ----------
    async def get_level(self, guild_id, user_id):
        async with self.conn.execute(
            "SELECT xp, level FROM levels WHERE guild_id=? AND user_id=?", (guild_id, user_id)
        ) as cur:
            row = await cur.fetchone()
        return (row[0], row[1]) if row else (0, 0)

    async def set_level(self, guild_id, user_id, xp, level):
        await self.conn.execute(
            "INSERT INTO levels (guild_id, user_id, xp, level) VALUES (?,?,?,?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET xp=excluded.xp, level=excluded.level",
            (guild_id, user_id, xp, level),
        )
        await self.conn.commit()

    async def top_levels(self, guild_id, limit=10):
        async with self.conn.execute(
            "SELECT user_id, xp, level FROM levels WHERE guild_id=? "
            "ORDER BY level DESC, xp DESC LIMIT ?",
            (guild_id, limit),
        ) as cur:
            return await cur.fetchall()

    async def get_rank(self, guild_id, user_id) -> int:
        xp, level = await self.get_level(guild_id, user_id)
        async with self.conn.execute(
            "SELECT COUNT(*) + 1 FROM levels WHERE guild_id=? AND "
            "(level > ? OR (level = ? AND xp > ?))",
            (guild_id, level, level, xp),
        ) as cur:
            return (await cur.fetchone())[0]

    # ---------- abone görsel hash ----------
    async def get_hash_owner(self, guild_id, h):
        async with self.conn.execute(
            "SELECT user_id FROM sub_hashes WHERE guild_id=? AND hash=?", (guild_id, h)
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row else None

    async def add_hash(self, guild_id, h, user_id):
        await self.conn.execute(
            "INSERT OR IGNORE INTO sub_hashes (guild_id, hash, user_id) VALUES (?,?,?)",
            (guild_id, h, user_id),
        )
        await self.conn.commit()

    # ---------- ekonomi ----------
    async def get_eco(self, guild_id, user_id):
        async with self.conn.execute(
            "SELECT balance, last_daily, last_work FROM economy WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ) as cur:
            row = await cur.fetchone()
        return tuple(row) if row else (0, 0.0, 0.0)

    async def add_balance(self, guild_id, user_id, amount) -> int:
        await self.conn.execute(
            "INSERT INTO economy (guild_id, user_id, balance) VALUES (?,?,?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET balance = balance + excluded.balance",
            (guild_id, user_id, amount),
        )
        await self.conn.commit()
        return (await self.get_eco(guild_id, user_id))[0]

    async def set_eco_time(self, guild_id, user_id, column, value):
        if column not in ("last_daily", "last_work"):
            raise ValueError(column)
        await self.conn.execute(
            f"INSERT INTO economy (guild_id, user_id, {column}) VALUES (?,?,?) "
            f"ON CONFLICT(guild_id, user_id) DO UPDATE SET {column}=excluded.{column}",
            (guild_id, user_id, value),
        )
        await self.conn.commit()

    async def top_balances(self, guild_id, limit=10):
        async with self.conn.execute(
            "SELECT user_id, balance FROM economy WHERE guild_id=? ORDER BY balance DESC LIMIT ?",
            (guild_id, limit),
        ) as cur:
            return await cur.fetchall()

    # ---------- hatırlatıcı ----------
    async def add_reminder(self, user_id, guild_id, channel_id, remind_at, text) -> int:
        cur = await self.conn.execute(
            "INSERT INTO reminders (user_id, guild_id, channel_id, remind_at, text) VALUES (?,?,?,?,?)",
            (user_id, guild_id, channel_id, remind_at, text),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def due_reminders(self, now):
        async with self.conn.execute(
            "SELECT id, user_id, guild_id, channel_id, text FROM reminders WHERE remind_at <= ?", (now,)
        ) as cur:
            return await cur.fetchall()

    async def delete_reminder(self, rid):
        await self.conn.execute("DELETE FROM reminders WHERE id=?", (rid,))
        await self.conn.commit()

    async def user_reminders(self, user_id):
        async with self.conn.execute(
            "SELECT id, remind_at, text FROM reminders WHERE user_id=? ORDER BY remind_at LIMIT 10", (user_id,)
        ) as cur:
            return await cur.fetchall()

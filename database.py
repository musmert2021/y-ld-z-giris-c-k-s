"""Asenkron SQLite katmanı."""

import datetime

import aiosqlite

SETTING_KEYS = {
    "log_channel_id",
    "welcome_channel_id",
    "autorole_id",
    "ticket_category_id",
    "ticket_staff_role_id",
    "levelup_channel_id",
    "levelup_enabled",
    "welcome_card_enabled",
    "welcome_background_hex",
    "antiraid_enabled",
    "antiraid_esik",
    "antiraid_pencere",
    "stats_channel_id",
    "stats_message_id",
}


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                log_channel_id INTEGER
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                reason TEXT,
                moderator_id INTEGER,
                timestamp TEXT
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_config (
                key TEXT PRIMARY KEY,
                value INTEGER
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_threads (
                guild_id INTEGER PRIMARY KEY,
                thread_id INTEGER,
                name TEXT,
                invite TEXT
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS levels (
                guild_id INTEGER,
                user_id INTEGER,
                xp INTEGER DEFAULT 0,
                seviye INTEGER DEFAULT 0,
                son_mesaj_ts REAL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS level_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                seviye INTEGER,
                role_id INTEGER
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                message_id INTEGER,
                prize TEXT,
                winners_count INTEGER,
                end_time TEXT,
                host_id INTEGER,
                ended INTEGER DEFAULT 0
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS giveaway_entries (
                giveaway_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (giveaway_id, user_id)
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS reaction_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                message_id INTEGER,
                emoji TEXT,
                role_id INTEGER,
                label TEXT
            )
        """)

        for col in SETTING_KEYS - {"log_channel_id"}:
            try:
                await self.conn.execute(
                    f"ALTER TABLE guild_settings ADD COLUMN {col} INTEGER"
                )
            except aiosqlite.OperationalError:
                pass
        for col in ("welcome_background_hex",):
            try:
                await self.conn.execute(
                    f"ALTER TABLE guild_settings ADD COLUMN {col} TEXT"
                )
            except aiosqlite.OperationalError:
                pass
        await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def get_settings(self, guild_id: int) -> dict:
        async with self.conn.execute(
            "SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else {}

    async def set_setting(self, guild_id: int, key: str, value):
        if key not in SETTING_KEYS:
            raise ValueError(f"Geçersiz ayar: {key}")
        await self.conn.execute(
            "INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)",
            (guild_id,),
        )
        await self.conn.execute(
            f"UPDATE guild_settings SET {key} = ? WHERE guild_id = ?",
            (value, guild_id),
        )
        await self.conn.commit()

    async def get_global(self, key: str):
        async with self.conn.execute(
            "SELECT value FROM bot_config WHERE key = ?", (key,)
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row else None

    async def set_global(self, key: str, value):
        await self.conn.execute(
            "INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)", (key, value)
        )
        await self.conn.commit()

    async def add_warning(self, guild_id, user_id, reason, moderator_id) -> int:
        await self.conn.execute(
            "INSERT INTO warnings (guild_id, user_id, reason, moderator_id, timestamp)"
            " VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, reason, moderator_id, str(datetime.datetime.now())),
        )
        await self.conn.commit()
        return await self.count_warnings(guild_id, user_id)

    async def count_warnings(self, guild_id, user_id) -> int:
        async with self.conn.execute(
            "SELECT COUNT(*) FROM warnings WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ) as cur:
            return (await cur.fetchone())[0]

    async def get_warnings(self, guild_id, user_id, limit=20):
        async with self.conn.execute(
            "SELECT id, reason, moderator_id, timestamp FROM warnings"
            " WHERE guild_id = ? AND user_id = ? ORDER BY id DESC LIMIT ?",
            (guild_id, user_id, limit),
        ) as cur:
            return await cur.fetchall()

    async def delete_warning(self, guild_id, warning_id) -> bool:
        cur = await self.conn.execute(
            "DELETE FROM warnings WHERE id = ? AND guild_id = ?",
            (warning_id, guild_id),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def clear_warnings(self, guild_id, user_id) -> int:
        cur = await self.conn.execute(
            "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        await self.conn.commit()
        return cur.rowcount

    async def get_guild_thread(self, guild_id: int):
        async with self.conn.execute(
            "SELECT * FROM guild_threads WHERE guild_id = ?", (guild_id,)
        ) as cur:
            return await cur.fetchone()

    async def set_guild_thread(self, guild_id, thread_id, name, invite):
        await self.conn.execute(
            "INSERT OR REPLACE INTO guild_threads (guild_id, thread_id, name, invite)"
            " VALUES (?, ?, ?, ?)",
            (guild_id, thread_id, name, invite),
        )
        await self.conn.commit()

    async def list_guild_threads(self):
        async with self.conn.execute(
            "SELECT * FROM guild_threads ORDER BY name COLLATE NOCASE"
        ) as cur:
            return await cur.fetchall()

    async def delete_guild_thread_by_thread(self, thread_id):
        await self.conn.execute(
            "DELETE FROM guild_threads WHERE thread_id = ?", (thread_id,)
        )
        await self.conn.commit()

    async def get_level(self, guild_id, user_id):
        async with self.conn.execute(
            "SELECT * FROM levels WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ) as cur:
            row = await cur.fetchone()
        return row

    async def add_xp(self, guild_id, user_id, miktar, simdi):
        row = await self.get_level(guild_id, user_id)
        if row is None:
            await self.conn.execute(
                "INSERT INTO levels (guild_id, user_id, xp, seviye, son_mesaj_ts)"
                " VALUES (?, ?, ?, 0, ?)",
                (guild_id, user_id, miktar, simdi),
            )
            await self.conn.commit()
            return miktar, 0
        yeni_xp = row["xp"] + miktar
        await self.conn.execute(
            "UPDATE levels SET xp = ?, son_mesaj_ts = ? WHERE guild_id = ? AND user_id = ?",
            (yeni_xp, simdi, guild_id, user_id),
        )
        await self.conn.commit()
        return yeni_xp, row["seviye"]

    async def set_level(self, guild_id, user_id, seviye):
        await self.conn.execute(
            "UPDATE levels SET seviye = ? WHERE guild_id = ? AND user_id = ?",
            (seviye, guild_id, user_id),
        )
        await self.conn.commit()

    async def leaderboard(self, guild_id, limit=10):
        async with self.conn.execute(
            "SELECT * FROM levels WHERE guild_id = ? ORDER BY xp DESC LIMIT ?",
            (guild_id, limit),
        ) as cur:
            return await cur.fetchall()

    async def rank(self, guild_id, user_id) -> int:
        async with self.conn.execute(
            "SELECT COUNT(*) + 1 FROM levels WHERE guild_id = ? AND xp > ("
            " SELECT xp FROM levels WHERE guild_id = ? AND user_id = ?)",
            (guild_id, guild_id, user_id),
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row else 1

    async def add_level_role(self, guild_id, seviye, role_id):
        await self.conn.execute(
            "INSERT INTO level_roles (guild_id, seviye, role_id) VALUES (?, ?, ?)",
            (guild_id, seviye, role_id),
        )
        await self.conn.commit()

    async def remove_level_role(self, guild_id, seviye):
        cur = await self.conn.execute(
            "DELETE FROM level_roles WHERE guild_id = ? AND seviye = ?",
            (guild_id, seviye),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def list_level_roles(self, guild_id):
        async with self.conn.execute(
            "SELECT * FROM level_roles WHERE guild_id = ? ORDER BY seviye",
            (guild_id,),
        ) as cur:
            return await cur.fetchall()

    async def create_giveaway(self, guild_id, channel_id, message_id, prize,
                              winners_count, end_time, host_id) -> int:
        cur = await self.conn.execute(
            "INSERT INTO giveaways (guild_id, channel_id, message_id, prize,"
            " winners_count, end_time, host_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (guild_id, channel_id, message_id, prize, winners_count,
             end_time, host_id),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def get_giveaway_by_message(self, message_id):
        async with self.conn.execute(
            "SELECT * FROM giveaways WHERE message_id = ?", (message_id,)
        ) as cur:
            return await cur.fetchone()

    async def active_giveaways(self):
        async with self.conn.execute(
            "SELECT * FROM giveaways WHERE ended = 0"
        ) as cur:
            return await cur.fetchall()

    async def end_giveaway(self, giveaway_id):
        await self.conn.execute(
            "UPDATE giveaways SET ended = 1 WHERE id = ?", (giveaway_id,)
        )
        await self.conn.commit()

    async def add_giveaway_entry(self, giveaway_id, user_id) -> bool:
        try:
            await self.conn.execute(
                "INSERT INTO giveaway_entries (giveaway_id, user_id) VALUES (?, ?)",
                (giveaway_id, user_id),
            )
            await self.conn.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def remove_giveaway_entry(self, giveaway_id, user_id):
        await self.conn.execute(
            "DELETE FROM giveaway_entries WHERE giveaway_id = ? AND user_id = ?",
            (giveaway_id, user_id),
        )
        await self.conn.commit()

    async def giveaway_entry_count(self, giveaway_id) -> int:
        async with self.conn.execute(
            "SELECT COUNT(*) FROM giveaway_entries WHERE giveaway_id = ?",
            (giveaway_id,),
        ) as cur:
            return (await cur.fetchone())[0]

    async def giveaway_entrants(self, giveaway_id):
        async with self.conn.execute(
            "SELECT user_id FROM giveaway_entries WHERE giveaway_id = ?",
            (giveaway_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [r[0] for r in rows]

    async def add_reaction_role(self, guild_id, message_id, emoji, role_id, label):
        await self.conn.execute(
            "INSERT INTO reaction_roles (guild_id, message_id, emoji, role_id, label)"
            " VALUES (?, ?, ?, ?, ?)",
            (guild_id, message_id, emoji, role_id, label),
        )
        await self.conn.commit()

    async def get_reaction_roles(self, message_id):
        async with self.conn.execute(
            "SELECT * FROM reaction_roles WHERE message_id = ?", (message_id,)
        ) as cur:
            return await cur.fetchall()

    async def all_reaction_role_panels(self):
        async with self.conn.execute(
            "SELECT DISTINCT guild_id, message_id FROM reaction_roles"
        ) as cur:
            return await cur.fetchall()

    async def delete_reaction_panel(self, message_id):
        await self.conn.execute(
            "DELETE FROM reaction_roles WHERE message_id = ?", (message_id,)
        )
        await self.conn.commit()

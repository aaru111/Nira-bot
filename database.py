import asyncpg
import os
from typing import Optional, List, Any

DATABASE_URL: Optional[str] = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set.")


class Database:

    def __init__(self) -> None:
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self) -> None:
        try:
            # Initialize the connection pool
            self.pool = await asyncpg.create_pool(dsn=DATABASE_URL,
                                                  min_size=1,
                                                  max_size=10)
            await self.create_tables()
        except Exception as e:
            print(f"Error initializing database pool: {e}")
            raise

    async def create_tables(self) -> None:
        create_guild_prefixes_table: str = """
        CREATE TABLE IF NOT EXISTS guild_prefixes(
            guild_id BIGINT PRIMARY KEY,
            prefix VARCHAR(10) NOT NULL DEFAULT '.'
        );
        """
        create_reaction_roles_table: str = """
        CREATE TABLE IF NOT EXISTS reaction_roles(
            guild_id BIGINT,
            message_id BIGINT,
            role_id BIGINT,
            channel_id BIGINT,
            emoji TEXT,
            color TEXT,
            custom_id TEXT,
            link TEXT,
            PRIMARY KEY(guild_id, message_id, role_id)
        );
        """
        create_tracked_messages_table: str = """
        CREATE TABLE IF NOT EXISTS tracked_messages(
            message_id BIGINT PRIMARY KEY
        );
        """
        create_anilist_tokens_table: str = """
        CREATE TABLE IF NOT EXISTS anilist_tokens(
            user_id BIGINT PRIMARY KEY,
            access_token TEXT NOT NULL
        );
        """
        create_player_stats_table: str = """
        CREATE TABLE IF NOT EXISTS player_stats(
            player_id BIGINT PRIMARY KEY,
            player_name TEXT NOT NULL,
            games_played INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0
        );
        """
        create_ticket_panels_table: str = """
        CREATE TABLE IF NOT EXISTS ticket_panels(
            id BIGINT PRIMARY KEY,
            channel_id BIGINT NOT NULL,
            guild_id BIGINT NOT NULL,
            limit_per_user INTEGER DEFAULT 1,
            panel_title TEXT NOT NULL,
            panel_description TEXT NOT NULL,
            panel_moderators BIGINT[] DEFAULT ARRAY[]::BIGINT[],
            deleted BOOLEAN DEFAULT FALSE
        );
        """

        create_tickets_table: str = """
        CREATE TABLE IF NOT EXISTS tickets(
            panel_id BIGINT REFERENCES ticket_panels(id),
            ticket_id BIGINT PRIMARY KEY,
            ticket_creator BIGINT NOT NULL,
            closed BOOLEAN DEFAULT FALSE
        );
        """
        try:
            if self.pool is None:
                raise ValueError("Database pool is not initialized")
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(create_guild_prefixes_table)
                    await conn.execute(create_reaction_roles_table)
                    await conn.execute(create_tracked_messages_table)
                    await conn.execute(create_anilist_tokens_table)
                    await conn.execute(create_player_stats_table)
                    await conn.execute(create_ticket_panels_table)
                    await conn.execute(create_tickets_table)
        except asyncpg.UniqueViolationError as e:
            print(f"Unique violation error while creating tables: {e}")
            raise
        except asyncpg.DuplicateObjectError as e:
            print(f"Duplicate object error while creating tables: {e}")
            raise
        except Exception as e:
            print(f"Error creating tables: {e}")
            raise

    async def execute(self, query: str, *params: Any) -> None:
        if self.pool is None:
            raise ValueError("Database pool is not initialized")
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(query, *params)
        except asyncpg.UniqueViolationError as e:
            print(f"Unique violation error while executing query: {e}")
            raise
        except Exception as e:
            print(f"Error executing query: {e}")
            raise

    async def fetch(self, query: str, *params: Any) -> List[asyncpg.Record]:
        if self.pool is None:
            raise ValueError("Database pool is not initialized")
        try:
            async with self.pool.acquire() as conn:
                return await conn.fetch(query, *params)
        except Exception as e:
            print(f"Error fetching data: {e}")
            raise

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()


# Instantiate a global database object
db: Database = Database()

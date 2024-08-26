# database.py

import asyncpg
import os

DATABASE_URL = os.getenv('DATABASE_URL')


class Database:

    def __init__(self):
        self.pool = None

    async def initialize(self):
        # Initialize the connection pool
        self.pool = await asyncpg.create_pool(dsn=DATABASE_URL,
                                              min_size=1,
                                              max_size=10)
        await self.create_tables()

    async def create_tables(self):
        create_reaction_roles_table = """
        CREATE TABLE IF NOT EXISTS reaction_roles (
            guild_id TEXT,
            message_id TEXT,
            role_id TEXT,
            channel_id TEXT,
            emoji TEXT,
            color TEXT,
            custom_id TEXT,
            link TEXT,
            PRIMARY KEY (guild_id, message_id, role_id)
        );
        """
        create_tracked_messages_table = """
        CREATE TABLE IF NOT EXISTS tracked_messages (
            message_id TEXT PRIMARY KEY
        );
        """
        async with self.pool.acquire() as conn:
            await conn.execute(create_reaction_roles_table)
            await conn.execute(create_tracked_messages_table)

    async def execute(self, query: str, *params):
        async with self.pool.acquire() as conn:
            await conn.execute(query, *params)

    async def fetch(self, query: str, *params):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *params)

    async def close(self):
        await self.pool.close()


# Instantiate a global database object
db = Database()

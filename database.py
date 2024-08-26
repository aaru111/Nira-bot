import asyncpg
import os

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set.")


class Database:

    def __init__(self):
        self.pool = None

    async def initialize(self):
        try:
            # Initialize the connection pool
            self.pool = await asyncpg.create_pool(dsn=DATABASE_URL,
                                                  min_size=1,
                                                  max_size=10)
            await self.create_tables()
        except Exception as e:
            print(f"Error initializing database pool: {e}")
            raise

    async def create_tables(self):
        create_reaction_roles_table = """
        CREATE TABLE IF NOT EXISTS reaction_roles(
            guild_id TEXT,
            message_id TEXT,
            role_id TEXT,
            channel_id TEXT,
            emoji TEXT,
            color TEXT,
            custom_id TEXT,
            link TEXT,
            PRIMARY KEY(guild_id, message_id, role_id)
        );
        """
        create_tracked_messages_table = """
        CREATE TABLE IF NOT EXISTS tracked_messages(
            message_id TEXT PRIMARY KEY
        );
        """
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(create_reaction_roles_table)
                    await conn.execute(create_tracked_messages_table)
        except Exception as e:
            print(f"Error creating tables: {e}")
            raise

    async def execute(self, query: str, *params) -> None:
        try:    
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(query, *params)
        except Exception as e:
            print(f"Error executing query: {e}")
            raise

    async def fetch(self, query: str, *params) -> list:
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
db = Database()

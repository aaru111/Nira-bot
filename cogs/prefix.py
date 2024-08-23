import discord
from discord import app_commands
from discord.ext import commands
import asyncpg
from abc import ABC, abstractmethod
import os


class DatabaseManager(ABC):

    @abstractmethod
    async def get_prefix(self, guild_id: int) -> str:
        pass

    @abstractmethod
    async def set_prefix(self, guild_id: int, prefix: str) -> None:
        pass


class PostgreSQLManager(DatabaseManager):

    def __init__(self):
        self.pool = None

    async def initialize(self):
        db_url = os.environ['DATABASE_URL']
        self.pool = await asyncpg.create_pool(db_url)
        await self.create_table()

    async def create_table(self):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS guild_prefixes (
                    guild_id BIGINT PRIMARY KEY,
                    prefix VARCHAR(10) NOT NULL
                )
            ''')

    async def get_prefix(self, guild_id: int) -> str:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT prefix FROM guild_prefixes WHERE guild_id = $1',
                guild_id)
            return row['prefix'] if row else '.'

    async def set_prefix(self, guild_id: int, prefix: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''
                INSERT INTO guild_prefixes (guild_id, prefix)
                VALUES ($1, $2)
                ON CONFLICT (guild_id) DO UPDATE SET prefix = $2
            ''', guild_id, prefix)


class PrefixCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.db_manager = PostgreSQLManager()

    async def cog_load(self):
        await self.db_manager.initialize()

    @staticmethod
    def is_valid_prefix(prefix: str) -> bool:
        return len(prefix) <= 10 and not any(char.isspace() for char in prefix)

    @app_commands.command(
        name='prefix',
        description='Change or view the bot prefix for this server')
    @app_commands.describe(
        new_prefix='The new prefix to set (leave empty to view current prefix)'
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def change_prefix(self,
                            interaction: discord.Interaction,
                            new_prefix: str = None):
        if new_prefix is None:
            current_prefix = await self.db_manager.get_prefix(
                interaction.guild.id)
            await interaction.response.send_message(
                f"The current prefix is: `{current_prefix}`")
            return

        if not self.is_valid_prefix(new_prefix):
            await interaction.response.send_message(
                "Invalid prefix. It must be 10 characters or less and contain no spaces.",
                ephemeral=True)
            return

        await self.db_manager.set_prefix(interaction.guild.id, new_prefix)
        self.bot.command_prefix = commands.when_mentioned_or(new_prefix)
        await interaction.response.send_message(
            f"Prefix updated to: `{new_prefix}`")

    @change_prefix.error
    async def change_prefix_error(self, interaction: discord.Interaction,
                                  error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need 'Manage Server' permissions to change the prefix.",
                ephemeral=True)

    async def get_prefix(self, message: discord.Message) -> str:
        if message.guild:
            return await self.db_manager.get_prefix(message.guild.id)
        return '.'  # Default prefix for DMs


async def setup(bot):
    cog = PrefixCog(bot)
    await bot.add_cog(cog)
    bot.get_prefix = cog.get_prefix

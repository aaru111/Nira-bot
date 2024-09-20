import discord
from discord.ext import commands
from typing import Optional, List
from database import db, Database


class Premium(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.db: Database = db

    async def cog_load(self) -> None:
        await self.create_tables()

    async def create_tables(self) -> None:
        query: str = """
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            is_premium BOOLEAN DEFAULT FALSE
        );
        """
        await self.db.execute(query)

    @commands.command()
    @commands.is_owner()
    async def set_premium(self, ctx: commands.Context,
                          user: discord.Member) -> None:
        """Set a user as premium (Owner only)"""
        query: str = """
        INSERT INTO users (user_id, is_premium)
        VALUES ($1, TRUE)
        ON CONFLICT (user_id)
        DO UPDATE SET is_premium = TRUE;
        """
        await self.db.execute(query, user.id)
        await ctx.send(f"{user.mention} is now a premium user!")

    @commands.command()
    @commands.is_owner()
    async def remove_premium(self, ctx: commands.Context,
                             user: discord.Member) -> None:
        """Remove premium status from a user (Owner only)"""
        query: str = """
        INSERT INTO users (user_id, is_premium)
        VALUES ($1, FALSE)
        ON CONFLICT (user_id)
        DO UPDATE SET is_premium = FALSE;
        """
        await self.db.execute(query, user.id)
        await ctx.send(f"{user.mention} is no longer a premium user.")

    @commands.command()
    @commands.is_owner()
    async def list_premium(self, ctx: commands.Context) -> None:
        """List all premium users (Owner only)"""
        query: str = "SELECT user_id FROM users WHERE is_premium = TRUE;"
        results: List[asyncpg.Record] = await self.db.fetch(query)
        if not results:
            await ctx.send("There are no premium users.")
            return

        premium_users: List[str] = []
        for row in results:
            user: Optional[discord.User] = self.bot.get_user(row['user_id'])
            if user:
                premium_users.append(
                    f"{user.name}#{user.discriminator} (ID: {user.id})")
            else:
                premium_users.append(f"Unknown User (ID: {row['user_id']})")

        premium_list: str = "\n".join(premium_users)
        await ctx.send(f"Premium Users:\n{premium_list}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Premium(bot))

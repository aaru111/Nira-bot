import discord
from discord.ext import commands
from typing import Optional, List
from database import db, Database
import asyncpg


class Premium(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.db: Database = db

    async def cog_load(self) -> None:
        await db.initialize()
        await self.create_tables()

    async def create_tables(self) -> None:
        query: str = """
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            is_premium BOOLEAN DEFAULT FALSE
        );
        """
        await self.db.execute(query)

    async def is_premium(self, user_id: int) -> bool:
        if user_id == self.bot.owner_id:
            return True
        query: str = "SELECT is_premium FROM users WHERE user_id = $1;"
        result = await self.db.fetchval(query, user_id)
        return bool(result)

    @commands.command()
    @commands.is_owner()
    async def set_premium(self, ctx: commands.Context,
                          user: discord.Member) -> None:
        """Set a user as premium (Owner only)"""
        if user.id == self.bot.owner_id:
            await ctx.send(
                f"{user.mention} is already a premium user as the bot owner!")
            return
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
        if user.id == self.bot.owner_id:
            await ctx.send("Cannot remove premium status from the bot owner.")
            return
        query: str = """
        DELETE FROM users WHERE user_id = $1;
        """
        await self.db.execute(query, user.id)
        await ctx.send(f"{user.mention} is no longer a premium user.")

    @commands.command()
    @commands.is_owner()
    async def list_premium(self, ctx: commands.Context) -> None:
        """List all premium users (Owner only)"""
        query: str = "SELECT user_id FROM users WHERE is_premium = TRUE;"
        results: List[asyncpg.Record] = await self.db.fetch(query)

        premium_users: List[str] = []
        if self.bot.user:
            premium_users.append(
                f"{self.bot.user.name} (Bot Owner, ID: {self.bot.owner_id})")
        for row in results:
            user: Optional[discord.User] = self.bot.get_user(row['user_id'])
            if user:
                premium_users.append(f"{user.name} (ID: {user.id})")
            else:
                premium_users.append(f"Unknown User (ID: {row['user_id']})")

        premium_list: str = "\n".join(premium_users)

        embed = discord.Embed(title="Premium Users",
                              description=premium_list,
                              color=discord.Color.gold())
        await ctx.send(embed=embed)

    @commands.command()
    async def premium_status(self,
                             ctx: commands.Context,
                             user: Optional[discord.Member] = None) -> None:
        """Check premium status of a user"""
        target_user = user or ctx.author
        is_premium = await self.is_premium(target_user.id)
        status = "is" if is_premium else "is not"
        await ctx.send(f"{target_user.mention} {status} a premium user.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Premium(bot))

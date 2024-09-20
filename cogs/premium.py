import discord
from discord.ext import commands
from discord import app_commands
from database import db


class Premium(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await self.create_tables()

    async def create_tables(self):
        query = """
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            is_premium BOOLEAN DEFAULT FALSE
        );
        """
        await db.execute(query)

    @commands.command()
    @commands.is_owner()
    async def set_premium(self, ctx, user: discord.Member):
        """Set a user as premium (Owner only)"""
        query = """
        INSERT INTO users (user_id, is_premium)
        VALUES ($1, TRUE)
        ON CONFLICT (user_id)
        DO UPDATE SET is_premium = TRUE;
        """
        await db.execute(query, user.id)
        await ctx.send(f"{user.mention} is now a premium user!")

    @commands.command()
    @commands.is_owner()
    async def remove_premium(self, ctx, user: discord.Member):
        """Remove premium status from a user (Owner only)"""
        query = """
        INSERT INTO users (user_id, is_premium)
        VALUES ($1, FALSE)
        ON CONFLICT (user_id)
        DO UPDATE SET is_premium = FALSE;
        """
        await db.execute(query, user.id)
        await ctx.send(f"{user.mention} is no longer a premium user.")

    @commands.command()
    @commands.is_owner()
    async def list_premium(self, ctx):
        """List all premium users (Owner only)"""
        query = "SELECT user_id FROM users WHERE is_premium = TRUE;"
        results = await db.fetch(query)

        if not results:
            await ctx.send("There are no premium users.")
            return

        premium_users = []
        for row in results:
            user = self.bot.get_user(row['user_id'])
            if user:
                premium_users.append(
                    f"{user.name}#{user.discriminator} (ID: {user.id})")
            else:
                premium_users.append(f"Unknown User (ID: {row['user_id']})")

        premium_list = "\n".join(premium_users)
        await ctx.send(f"Premium Users:\n{premium_list}")


async def setup(bot):
    await bot.add_cog(Premium(bot))

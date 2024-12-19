import discord
from discord.ext import commands
from datetime import datetime, timedelta
import pytz
from typing import Optional
from helpers.database import db


class StreakSystem(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.messages_required = 2
        self.bot.loop.create_task(self.setup_database())

    async def setup_database(self):
        create_streaks_table = """
        CREATE TABLE IF NOT EXISTS user_streaks(
            user_id BIGINT PRIMARY KEY,
            streak_count INTEGER DEFAULT 0,
            last_streak_date DATE DEFAULT CURRENT_DATE,
            messages_today INTEGER DEFAULT 0,
            streak_updated_today BOOLEAN DEFAULT FALSE
        );
        """
        try:
            await db.execute(create_streaks_table)
        except Exception as e:
            print(f"Error setting up database: {e}")

    async def get_user_streak(
            self, user_id: int) -> tuple[int, Optional[datetime], int, bool]:
        query = """
        SELECT streak_count, last_streak_date, messages_today, streak_updated_today
        FROM user_streaks 
        WHERE user_id = $1;
        """
        result = await db.fetch(query, user_id)
        if result:
            return (result[0]['streak_count'], result[0]['last_streak_date'],
                    result[0]['messages_today'],
                    result[0]['streak_updated_today'])
        return 0, None, 0, False

    async def update_user_streak(self, user_id: int, streak_count: int,
                                 messages_today: int, streak_updated: bool):
        query = """
        INSERT INTO user_streaks (user_id, streak_count, last_streak_date, messages_today, streak_updated_today)
        VALUES ($1, $2, CURRENT_DATE, $3, $4)
        ON CONFLICT (user_id) 
        DO UPDATE SET 
            streak_count = $2,
            last_streak_date = CURRENT_DATE,
            messages_today = $3,
            streak_updated_today = $4;
        """
        await db.execute(query, user_id, streak_count, messages_today,
                         streak_updated)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        user_id = message.author.id
        streak_count, last_streak_date, messages_today, streak_updated_today = await self.get_user_streak(
            user_id)

        utc_now = datetime.now(pytz.UTC)
        current_date = utc_now.date()

        if last_streak_date and current_date > last_streak_date:
            messages_today = 0
            streak_updated_today = False

        if streak_updated_today:
            return

        messages_today += 1

        if messages_today >= self.messages_required:
            if last_streak_date is None or (current_date - last_streak_date
                                            <= timedelta(days=1)):
                streak_count += 1
                streak_updated_today = True
                await message.channel.send(
                    f"🔥 **{message.author.name}** has reached their daily message goal! "
                    f"Current streak: {streak_count} days!")
            else:
                streak_count = 1
                streak_updated_today = True
                await message.channel.send(
                    f"🔥 **{message.author.name}** has started a new streak!")

        await self.update_user_streak(user_id, streak_count, messages_today,
                                      streak_updated_today)

    @commands.hybrid_command(name="streak",
                             description="Check your current streak")
    async def check_streak(self, ctx: commands.Context):
        streak_count, _, _, _ = await self.get_user_streak(ctx.author.id)

        utc_now = datetime.now(pytz.UTC)
        next_message_time = utc_now.replace(
            hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        next_message_timestamp = int(next_message_time.timestamp())

        embed = discord.Embed(title="🔥 Streak Status",
                              color=discord.Color.blue())
        embed.add_field(name="Current Streak",
                        value=f"{streak_count} days",
                        inline=False)
        embed.add_field(name="Next Eligible Message Time",
                        value=f"<t:{next_message_timestamp}:R>",
                        inline=False)

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="leaderboard",
                             description="View the streak leaderboard")
    async def streak_leaderboard(self, ctx: commands.Context):
        query = """
        SELECT user_id, streak_count 
        FROM user_streaks 
        ORDER BY streak_count DESC 
        LIMIT 10;
        """
        results = await db.fetch(query)

        if not results:
            await ctx.send("No streaks recorded yet!")
            return

        embed = discord.Embed(title="🏆 Streak Leaderboard",
                              color=discord.Color.gold())

        for idx, record in enumerate(results, 1):
            user = self.bot.get_user(record['user_id'])
            user_name = user.name if user else f"User {record['user_id']}"
            embed.add_field(name=f"#{idx} {user_name}",
                            value=f"{record['streak_count']} days",
                            inline=False)

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(StreakSystem(bot))

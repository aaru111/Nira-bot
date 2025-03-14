from discord.ext import commands
from collections import defaultdict
import time
import random


class CheeseCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = defaultdict(dict)
        self.cooldown_time = 5
        self.trigger_words = [
            "cheese", "cheddar", "gouda", "brie", "parmesan", "mozzarella",
            "paneer", "cream cheese", "ricotta", "feta"
        ]
        self.cheese_emojis = ["🧀", "🍕"]
        self.enabled_guilds = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user or not message.guild:
            return

        guild_id = message.guild.id

        if not self.enabled_guilds.get(guild_id, True):
            return

        message_lower = message.content.lower()
        if any(word in message_lower for word in self.trigger_words):
            channel_id = message.channel.id

            current_time = time.time()
            last_time = self.cooldowns[guild_id].get(channel_id, 0)

            if current_time - last_time < self.cooldown_time:
                return

            try:
                chosen_emoji = random.choice(self.cheese_emojis)
                await message.add_reaction(chosen_emoji)
                self.cooldowns[guild_id][channel_id] = current_time
            except:
                pass

    @commands.hybrid_command(name="togglecheese",
                             description="Toggle cheese reactions on/off")
    @commands.has_permissions(manage_guild=True)
    async def togglecheese(self, ctx):
        guild_id = ctx.guild.id
        self.enabled_guilds[guild_id] = not self.enabled_guilds.get(
            guild_id, True)
        status = "enabled" if self.enabled_guilds[guild_id] else "disabled"
        await ctx.send(f"Cheese reactions {status} for this server!")

    @togglecheese.error
    async def togglecheese_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "You need 'Manage Server' permission to use this command!")


async def setup(bot):
    await bot.add_cog(CheeseCog(bot))

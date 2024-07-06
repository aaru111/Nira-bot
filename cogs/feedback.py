import discord
from discord.ext import commands
import logging
import json
from pathlib import Path
from main import Bot

# Set up logging
logger = logging.getLogger('discord')

CONFIG_FILE = Path('config.json')


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)


# Define the embed color
EMBED_COLOR = 0x2f3131


class Feedback(commands.Cog):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.config = load_config()

    @commands.command(name='feedback')
    async def feedback(self, ctx: commands.Context, *, message: str):
        # Send a confirmation message to the user
        embed = discord.Embed(
            title="Feedback Received",
            description=
            "Thank you for your feedback! Our team will review it soon.",
            color=EMBED_COLOR)
        await ctx.send(embed=embed)

        # Log the feedback
        logger.info(
            f"Feedback from {ctx.author} (ID: {ctx.author.id}) in {ctx.guild} (ID: {ctx.guild.id}): {message}"
        )

        # Optionally, send the feedback to a specific channel
        feedback_channel_id = self.config.get('feedback_channel_id')
        if feedback_channel_id:
            feedback_channel = self.bot.get_channel(feedback_channel_id)
            if feedback_channel:
                feedback_embed = discord.Embed(title="New Feedback",
                                               description=message,
                                               color=EMBED_COLOR)
                feedback_embed.add_field(
                    name="User",
                    value=f"{ctx.author} (ID: {ctx.author.id})",
                    inline=False)
                feedback_embed.add_field(
                    name="Guild",
                    value=f"{ctx.guild.name} (ID: {ctx.guild.id})",
                    inline=False)
                feedback_message = await feedback_channel.send(
                    embed=feedback_embed)

                # Add thumbs up and thumbs down reactions for voting
                await feedback_message.add_reaction('👍')
                await feedback_message.add_reaction('👎')
            else:
                await ctx.send(
                    "```py\nError: Feedback channel not found. Please set a valid feedback channel using the setfeedbackchannel command.```"
                )
        else:
            await ctx.send(
                "```py\nError: Feedback channel is not set. Please set a feedback channel using the setfeedbackchannel command.```"
            )

    @commands.command(name='setfeedbackchannel')
    @commands.has_permissions(administrator=True)
    async def set_feedback_channel(self, ctx: commands.Context,
                                   channel: discord.TextChannel):
        self.config['feedback_channel_id'] = channel.id
        save_config(self.config)
        await ctx.send(f"Feedback channel has been set to {channel.mention}")

    @commands.command(name='getfeedbackchannel')
    @commands.has_permissions(administrator=True)
    async def get_feedback_channel(self, ctx: commands.Context):
        feedback_channel_id = self.config.get('feedback_channel_id')
        if feedback_channel_id:
            channel = self.bot.get_channel(feedback_channel_id)
            if channel:
                await ctx.send(
                    f"The current feedback channel is {channel.mention}")
            else:
                await ctx.send(
                    "```py\nError: The saved feedback channel ID is invalid. Please set a new feedback channel using the setfeedbackchannel command.```"
                )
        else:
            await ctx.send(
                "```py\nFeedback channel is not set. Please set a feedback channel using the setfeedbackchannel command.```"
            )

    @commands.command(name='removefeedbackchannel')
    @commands.has_permissions(administrator=True)
    async def remove_feedback_channel(self, ctx: commands.Context):
        if 'feedback_channel_id' in self.config:
            del self.config['feedback_channel_id']
            save_config(self.config)
            await ctx.send("Feedback channel has been removed.")
        else:
            await ctx.send("```py\nFeedback channel is not set.```")


async def setup(bot: commands.Bot):
    await bot.add_cog(Feedback(bot))

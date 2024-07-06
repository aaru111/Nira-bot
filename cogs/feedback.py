import discord
from discord.ext import commands
from discord import app_commands
import logging
import json
from pathlib import Path
from discord.ui import Modal, TextInput, View, Button

# Set up logging
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

CONFIG_FILE = Path('config.json')


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        CONFIG_FILE.touch()
        return {}


def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)


# Define the embed color
EMBED_COLOR = 0x2f3131


class FeedbackModal(Modal):

    def __init__(self, bot, config):
        super().__init__(title="Feedback Form")
        self.bot = bot
        self.config = config
        self.add_item(
            TextInput(label="Subject",
                      style=discord.TextStyle.short,
                      placeholder="Brief summary of your feedback"))
        self.add_item(
            TextInput(label="Details",
                      style=discord.TextStyle.long,
                      placeholder="Detailed feedback"))

    async def on_submit(self, interaction: discord.Interaction):
        subject = self.children[0].value
        details = self.children[1].value
        user = interaction.user
        guild = interaction.guild

        embed = discord.Embed(
            title="Feedback Received",
            description=
            "Thank you for your feedback! Our team will review it soon.",
            color=EMBED_COLOR)
        await interaction.response.send_message(embed=embed)

        logger.info(
            f"Feedback from {user} (ID: {user.id}) in {guild.name if guild else 'Direct Message'} (ID: {guild.id if guild else 'N/A'}) - Subject: {subject}, Details: {details}"
        )

        feedback_channel_id = self.config.get('feedback_channel_id')
        if feedback_channel_id:
            feedback_channel = self.bot.get_channel(feedback_channel_id)
            if feedback_channel:
                feedback_embed = discord.Embed(
                    title="New Feedback",
                    description=
                    f"**Subject:** {subject}\n\n**Details:** {details}",
                    color=EMBED_COLOR)
                feedback_embed.add_field(name="User",
                                         value=f"{user} (ID: {user.id})",
                                         inline=False)
                feedback_embed.add_field(
                    name="Guild",
                    value=
                    f"{interaction.guild.name if interaction.guild else 'Direct Message'} (ID: {interaction.guild.id if interaction.guild else 'N/A'})",  # Corrected line
                    inline=False)
                feedback_embed.set_footer(text="Upvotes: 0 | Downvotes: 0")

                feedback_view = FeedbackView(self.bot)
                feedback_message = await feedback_channel.send(
                    embed=feedback_embed, view=feedback_view)

                feedback_view.feedback_message = feedback_message
            else:
                await interaction.followup.send(
                    "```py\nError: Feedback channel not found. Please set a valid feedback channel using the setfeedbackchannel command.```"
                )
        else:
            await interaction.followup.send(
                "```py\nError: Feedback channel is not set. Please set a feedback channel using the setfeedbackchannel command.```"
            )


class FeedbackView(View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.feedback_message = None
        self.upvotes = 0
        self.downvotes = 0

    @discord.ui.button(label="Upvote", style=discord.ButtonStyle.green)
    async def upvote_button(self, interaction: discord.Interaction,
                            button: Button):
        self.upvotes += 1
        if self.feedback_message:  # Check if feedback_message is set
            await self.update_feedback_message(interaction)

    @discord.ui.button(label="Downvote", style=discord.ButtonStyle.red)
    async def downvote_button(self, interaction: discord.Interaction,
                              button: Button):
        self.downvotes += 1
        if self.feedback_message:  # Check if feedback_message is set
            await self.update_feedback_message(interaction)

    async def update_feedback_message(self, interaction: discord.Interaction):
        if self.feedback_message:  # Check if feedback_message is set
            feedback_embed = self.feedback_message.embeds[0]
            feedback_embed.set_footer(
                text=f"Upvotes: {self.upvotes} | Downvotes: {self.downvotes}")
            await self.feedback_message.edit(embed=feedback_embed, view=self)
            await interaction.response.defer(
            )  # Use defer() instead of defer_update()


class Feedback(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = load_config()

    @app_commands.command(name='feedback', description='Submit your feedback')
    async def feedback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            FeedbackModal(self.bot, self.config))

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
                if isinstance(channel, discord.TextChannel):
                    await ctx.send(
                        f"The current feedback channel is {channel.mention}")
                else:
                    await ctx.send(
                        "The current feedback channel is a private channel.")
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

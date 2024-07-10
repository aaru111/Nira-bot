import discord
from discord.ext import commands
from discord import app_commands
import logging
import json
from pathlib import Path
from discord.ui import Modal, TextInput, View, Button
from typing import Optional
from datetime import datetime  # Import datetime for timestamp

# Set up logging for the bot
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# Define the path to the configuration file
CONFIG_FILE = Path('config.json')


# Function to load the configuration from the file
def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        CONFIG_FILE.touch()
        return {}


# Function to save the configuration to the file
def save_config(config: dict):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)


# Define the color for embeds
EMBED_COLOR = 0x2b2d31


# Modal class for feedback submission
class FeedbackModal(Modal):

    def __init__(self, bot: commands.Bot, config: dict):
        super().__init__(title="Feedback Form")
        self.bot = bot
        self.config = config
        # Add input fields for subject and details
        self.add_item(
            TextInput(label="Subject",
                      style=discord.TextStyle.short,
                      placeholder="Brief summary of your feedback"))
        self.add_item(
            TextInput(label="Details",
                      style=discord.TextStyle.long,
                      placeholder="Detailed feedback"))

    # Event that runs when the form is submitted
    async def on_submit(self, interaction: discord.Interaction):
        subject = self.children[0].value
        details = self.children[1].value
        user = interaction.user
        guild = interaction.guild

        # Create an embed to confirm feedback submission to the user
        embed = discord.Embed(
            title="Feedback Received",
            description=
            "Thank you for your feedback! Our team will review it soon.",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow())
        embed.set_footer(text=f"Initiated by {user}")
        await interaction.response.send_message(embed=embed)

        # Log the feedback submission
        logger.info(
            f"Feedback from {user} (ID: {user.id}) in {guild.name if guild else 'Direct Message'} (ID: {guild.id if guild else 'N/A'}) - Subject: {subject}, Details: {details}"
        )

        # Get the feedback channel ID from the configuration
        feedback_channel_id = self.config.get('feedback_channel_id')
        if feedback_channel_id:
            feedback_channel = self.bot.get_channel(feedback_channel_id)
            if feedback_channel:
                # Create an embed to post in the feedback channel
                feedback_embed = discord.Embed(
                    title=f"{subject}",
                    description=f"**Details:** {details}",
                    color=EMBED_COLOR,
                    timestamp=discord.utils.utcnow())
                feedback_embed.add_field(name="Upvote Meter",
                                         value="────────── 0.0%",
                                         inline=False)
                feedback_embed.add_field(name="Downvote Meter",
                                         value="────────── 0.0%",
                                         inline=False)
                feedback_embed.set_footer(text=f"Initiated by {user}",
                                          icon_url=user.avatar)

                # Create a view for the feedback message with upvote/downvote buttons
                feedback_view = FeedbackView(self.bot)
                feedback_message = await feedback_channel.send(
                    embed=feedback_embed, view=feedback_view)

                # Create a discussion thread for the feedback
                thread = await feedback_message.create_thread(name=subject)
                await thread.send(
                    f"**Details:** {details}\n\n*Submitted by {user}*")

                # Store the feedback message and user ID in the view
                feedback_view.feedback_message = feedback_message
                feedback_view.user_id = user.id
            else:
                await interaction.followup.send(
                    "```py\nError: Feedback channel not found. Please set a valid feedback channel using the setup wizard.```",
                    ephemeral=True)
        else:
            await interaction.followup.send(
                "```py\nError: Feedback channel is not set. Please set a feedback channel using the setup wizard.```",
                ephemeral=True)


# Modal class for setting feedback channel
class SetFeedbackChannelModal(Modal):

    def __init__(self, bot: commands.Bot, config: dict, setup_view):
        super().__init__(title="Set Feedback Channel")
        self.bot = bot
        self.config = config
        self.setup_view = setup_view
        # Add input field for channel ID
        self.add_item(
            TextInput(label="Channel ID",
                      style=discord.TextStyle.short,
                      placeholder="Enter the ID of the feedback channel"))

    async def on_submit(self, interaction: discord.Interaction):
        channel_id = self.children[0].value
        try:
            channel_id = int(channel_id)
            channel = self.bot.get_channel(channel_id)
            if channel:
                # Set the feedback channel in the configuration
                self.config['feedback_channel_id'] = channel_id
                save_config(self.config)
                await interaction.response.send_message(
                    f"Feedback channel has been set to {channel.mention}",
                    ephemeral=True)
                # Update the embed with the new channel info
                await self.setup_view.update_embed(
                    interaction, channel_mention=channel.mention)
            else:
                await interaction.response.send_message(
                    "```py\nError: Channel not found. Please enter a valid channel ID.```",
                    ephemeral=True)
        except ValueError:
            await interaction.response.send_message(
                "```py\nError: Invalid channel ID. Please enter a valid channel ID.```",
                ephemeral=True)


# View class to handle upvote/downvote buttons for feedback
class FeedbackView(View):

    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.feedback_message: Optional[discord.Message] = None
        self.upvotes = 0
        self.downvotes = 0
        self.user_votes = {}  # Track user votes

    @discord.ui.button(label="Upvote",
                       style=discord.ButtonStyle.green,
                       emoji="📈")
    async def upvote_button(self, interaction: discord.Interaction,
                            button: Button):
        user_id = interaction.user.id
        previous_vote = self.user_votes.get(user_id)

        if previous_vote == "upvote":
            # User is removing their upvote
            self.upvotes -= 1
            del self.user_votes[user_id]
        else:
            # User is changing or adding an upvote
            if previous_vote == "downvote":
                self.downvotes -= 1
            self.upvotes += 1
            self.user_votes[user_id] = "upvote"

        await self.update_feedback_message(interaction)

    @discord.ui.button(label="Downvote",
                       style=discord.ButtonStyle.red,
                       emoji="📉")
    async def downvote_button(self, interaction: discord.Interaction,
                              button: Button):
        user_id = interaction.user.id
        previous_vote = self.user_votes.get(user_id)

        if previous_vote == "downvote":
            # User is removing their downvote
            self.downvotes -= 1
            del self.user_votes[user_id]
        else:
            # User is changing or adding a downvote
            if previous_vote == "upvote":
                self.upvotes -= 1
            self.downvotes += 1
            self.user_votes[user_id] = "downvote"

        await self.update_feedback_message(interaction)

    # Update the feedback message embed with the latest vote counts and percentages
    async def update_feedback_message(self, interaction: discord.Interaction):
        if self.feedback_message:
            total_votes = self.upvotes + self.downvotes
            upvote_percentage = (self.upvotes /
                                 total_votes) * 100 if total_votes > 0 else 0
            downvote_percentage = (self.downvotes /
                                   total_votes) * 100 if total_votes > 0 else 0
            upvote_bar = '█' * int(upvote_percentage // 10) + ' ' * (
                10 - int(upvote_percentage // 10))
            downvote_bar = '█' * int(downvote_percentage // 10) + ' ' * (
                10 - int(downvote_percentage // 10))

            feedback_embed = self.feedback_message.embeds[0]
            feedback_embed.set_footer(
                text=
                f"Initiated by {interaction.guild.get_member(self.user_id)}\nUpvotes: {self.upvotes} ({upvote_percentage:.1f}%) | Downvotes: {self.downvotes} ({downvote_percentage:.1f}%)"
            )

            # Update the existing fields for upvote and downvote meters
            feedback_embed.set_field_at(
                0,
                name="Upvotes",
                value=f"{upvote_bar} {upvote_percentage:.1f}%",
                inline=False)
            feedback_embed.set_field_at(
                1,
                name="Downvotes",
                value=f"{downvote_bar} {downvote_percentage:.1f}%",
                inline=False)

            await self.feedback_message.edit(embed=feedback_embed, view=self)
            await interaction.response.defer()


# View class for the feedback setup buttons
class FeedbackSetupView(View):

    def __init__(self, bot: commands.Bot, config: dict):
        super().__init__(timeout=None)
        self.bot = bot
        self.config = config

    @discord.ui.button(label="Set Channel",
                       style=discord.ButtonStyle.primary,
                       emoji="🔧")
    async def set_channel(self, interaction: discord.Interaction,
                          button: Button):
        await interaction.response.send_modal(
            SetFeedbackChannelModal(self.bot, self.config, self))

    @discord.ui.button(label="Remove Channel",
                       style=discord.ButtonStyle.danger,
                       emoji="🗑️")
    async def remove_channel(self, interaction: discord.Interaction,
                             button: Button):
        if 'feedback_channel_id' in self.config:
            del self.config['feedback_channel_id']
            save_config(self.config)
            await interaction.response.send_message(
                "Feedback channel has been removed.", ephemeral=True)
            # Update the embed to reflect removal of the channel
            await self.update_embed(interaction)
        else:
            await interaction.response.send_message(
                "```py\nFeedback channel is not set.```", ephemeral=True)

    # Add a method to update the embed with the current channel info
    async def update_embed(self,
                           interaction: discord.Interaction,
                           channel_mention: Optional[str] = None):
        feedback_channel_id = self.config.get('feedback_channel_id')
        if not channel_mention:
            channel_mention = "Not set"
            if feedback_channel_id and (
                    channel := self.bot.get_channel(feedback_channel_id)):
                channel_mention = channel.mention

        embed = discord.Embed(
            title="Configure Feedback Settings",
            description=
            f"Use the buttons below to configure the feedback settings.\n\n**Current Feedback Channel:** {channel_mention}",
            color=EMBED_COLOR)
        await interaction.edit_original_response(embed=embed, view=self)


# Cog class to handle feedback commands
class Feedback(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = load_config()

    @app_commands.command(name='feedback', description='Submit your feedback')
    @app_commands.guild_only()
    async def feedback(self, interaction: discord.Interaction):
        # Show the feedback modal to the user
        await interaction.response.send_modal(
            FeedbackModal(self.bot, self.config))

    @app_commands.command(name='feedback_setup',
                          description='Configure feedback settings')
    @commands.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def feedback_setup(self, interaction: discord.Interaction):
        view = FeedbackSetupView(self.bot, self.config)
        await interaction.response.send_message(
            "Configuring feedback settings...", ephemeral=True)
        await view.update_embed(interaction)


# Function to set up the feedback cog
async def setup(bot: commands.Bot):
    await bot.add_cog(Feedback(bot))

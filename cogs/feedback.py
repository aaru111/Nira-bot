import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Modal, TextInput, Button
import json
import os
import aiohttp


class FeedbackModal(Modal):

    def __init__(self, feedback_type):
        super().__init__(title=f"{feedback_type} Feedback Form")
        self.feedback_type = feedback_type

        self.add_item(
            TextInput(label="Your feedback", style=discord.TextStyle.long))

    async def on_submit(self, interaction: discord.Interaction):
        feedback = self.children[0].value
        await interaction.response.send_message(
            f"Thank you for your feedback: {feedback}", ephemeral=True)

        guild_id = interaction.guild.id
        if not os.path.exists('feedback_channels.json'):
            with open('feedback_channels.json', 'w') as f:
                json.dump({}, f)

        with open('feedback_channels.json', 'r') as f:
            feedback_channels = json.load(f)

        if str(guild_id) in feedback_channels:
            channel_id = feedback_channels[str(guild_id)]
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                embed = discord.Embed(title=f"Feedback: {self.feedback_type}",
                                      description=feedback,
                                      color=discord.Color.blue())
                embed.add_field(name="Upvotes", value="0", inline=True)
                embed.add_field(name="Downvotes", value="0", inline=True)
                embed.add_field(name="Progress",
                                value="▓▓▓▓▓▓▓▓▓▓ 0%",
                                inline=False)

                view = FeedbackVoteView()
                await channel.send(embed=embed, view=view)
            else:
                await interaction.response.send_message(
                    "Feedback channel not found.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Feedback channel is not set up.", ephemeral=True)


class FeedbackDropdown(Select):

    def __init__(self):
        options = [
            discord.SelectOption(label="Bug Report",
                                 description="Report a bug in the bot"),
            discord.SelectOption(label="Feature Request",
                                 description="Request a new feature"),
            discord.SelectOption(label="General Feedback",
                                 description="Give general feedback")
        ]
        super().__init__(placeholder="Choose a feedback type...",
                         min_values=1,
                         max_values=1,
                         options=options,
                         custom_id="feedback_dropdown")

    async def callback(self, interaction: discord.Interaction):
        selected_option = self.values[0]
        await interaction.response.send_modal(FeedbackModal(selected_option))


class FeedbackView(View):

    def __init__(self):
        super().__init__(
            timeout=None)  # Persistent views should have no timeout
        self.add_item(FeedbackDropdown())


class FeedbackVoteButton(Button):

    def __init__(self, label, style, custom_id):
        super().__init__(label=label, style=style, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        message = interaction.message
        embed = message.embeds[0]

        upvotes = int(embed.fields[0].value)
        downvotes = int(embed.fields[1].value)

        if self.custom_id == "upvote_button":
            upvotes += 1
        elif self.custom_id == "downvote_button":
            downvotes += 1

        total_votes = upvotes + downvotes
        upvote_percentage = int(
            (upvotes / total_votes) * 100) if total_votes > 0 else 0

        embed.set_field_at(0, name="Upvotes", value=str(upvotes), inline=True)
        embed.set_field_at(1,
                           name="Downvotes",
                           value=str(downvotes),
                           inline=True)
        embed.set_field_at(
            2,
            name="Progress",
            value=
            f"▓{'▓' * (upvote_percentage // 10)}{'░' * (10 - (upvote_percentage // 10))} {upvote_percentage}%",
            inline=False)

        await interaction.response.edit_message(embed=embed, view=self.view)


class FeedbackVoteView(View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(
            FeedbackVoteButton(label="Upvote",
                               style=discord.ButtonStyle.success,
                               custom_id="upvote_button"))
        self.add_item(
            FeedbackVoteButton(label="Downvote",
                               style=discord.ButtonStyle.danger,
                               custom_id="downvote_button"))


class FeedbackSetupDropdown(Select):

    def __init__(self, cog):
        self.cog = cog
        options = [
            discord.SelectOption(
                label="Add Channel",
                description="Set the channel for feedback logs"),
            discord.SelectOption(label="Remove Channel",
                                 description="Remove the feedback channel")
        ]
        super().__init__(placeholder="Choose an option...",
                         min_values=1,
                         max_values=1,
                         options=options,
                         custom_id="feedback_setup_dropdown")

    async def callback(self, interaction: discord.Interaction):
        selected_option = self.values[0]

        if selected_option == "Add Channel":
            await interaction.response.send_message(
                "Please mention the channel you want to set for feedback logs.",
                ephemeral=True)
        elif selected_option == "Remove Channel":
            guild_id = str(interaction.guild.id)
            if os.path.exists('feedback_channels.json'):
                with open('feedback_channels.json', 'r') as f:
                    feedback_channels = json.load(f)

                if guild_id in feedback_channels:
                    del feedback_channels[guild_id]
                    with open('feedback_channels.json', 'w') as f:
                        json.dump(feedback_channels, f, indent=4)
                    await interaction.response.send_message(
                        "Feedback channel has been removed.", ephemeral=True)
                else:
                    await interaction.response.send_message(
                        "Feedback channel is not set up.", ephemeral=True)
            else:
                await interaction.response.send_message(
                    "Feedback channel is not set up.", ephemeral=True)


class FeedbackSetupView(View):

    def __init__(self, cog):
        super().__init__(timeout=None)
        self.add_item(FeedbackSetupDropdown(cog))


class Feedback(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.bot.add_view(FeedbackView())  # Register the persistent view
        self.bot.add_view(
            FeedbackVoteView())  # Register the persistent vote view
        self.bot.add_view(
            FeedbackSetupView(self))  # Register the persistent setup view

    async def close(self):
        await self.session.close()

    @app_commands.command(name="feedback",
                          description="Send feedback using a dropdown")
    async def feedback(self, interaction: discord.Interaction):
        """Send feedback using a dropdown"""
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command cannot be used in DMs.", ephemeral=True)
            return

        view = FeedbackView()
        await interaction.response.send_message(
            "Please select the type of feedback:", view=view, ephemeral=True)

    @app_commands.command(
        name="feedback_setup",
        description="Set or remove the channel for feedback logs (Admin only)")
    @app_commands.default_permissions(manage_channels=True)
    async def feedback_setup(self, interaction: discord.Interaction):
        """Set or remove the channel for feedback logs (Admin only)"""
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command cannot be used in DMs.", ephemeral=True)
            return

        view = FeedbackSetupView(self)
        await interaction.response.send_message("Please choose an option:",
                                                view=view,
                                                ephemeral=True)

    @feedback_setup.error
    async def feedback_setup_error(self, interaction: discord.Interaction,
                                   error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You do not have the necessary permissions to use this command.",
                ephemeral=True)
        else:
            await interaction.response.send_message(
                "An error occurred. Please try again.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return

        if message.reference and message.reference.resolved and isinstance(
                message.reference.resolved, discord.Message):
            referenced_message = message.reference.resolved

            if referenced_message.author == self.bot.user:
                await self.handle_add_channel(message, referenced_message)

    async def handle_add_channel(self, message, referenced_message):
        if "Please mention the channel you want to set for feedback logs." in referenced_message.content:
            if len(message.channel_mentions) > 0:
                channel = message.channel_mentions[0]
                guild_id = str(message.guild.id)

                feedback_channels = {}
                if os.path.exists('feedback_channels.json'):
                    with open('feedback_channels.json', 'r') as f:
                        feedback_channels = json.load(f)

                feedback_channels[guild_id] = channel.id

                with open('feedback_channels.json', 'w') as f:
                    json.dump(feedback_channels, f, indent=4)

                await message.reply(
                    f"Feedback channel has been set to {channel.mention}",
                    mention_author=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Feedback(bot))

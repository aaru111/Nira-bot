import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Modal, TextInput, Button
import json
import os
import aiohttp
from datetime import datetime


class FeedbackModal(Modal):

    def __init__(self, feedback_type):
        super().__init__(title=f"{feedback_type} Feedback Form")
        self.feedback_type = feedback_type

        self.add_item(
            TextInput(label="Feedback Title", style=discord.TextStyle.short))
        self.add_item(
            TextInput(label="Your feedback", style=discord.TextStyle.long))

    async def on_submit(self, interaction: discord.Interaction):
        title = self.children[0].value
        feedback = self.children[1].value
        await interaction.response.send_message(
            f"Thank you for your feedback: {title}", ephemeral=True)

        guild_id = str(interaction.guild.id)
        if not os.path.exists('feedback_channels.json'):
            with open('feedback_channels.json', 'w') as f:
                json.dump({}, f)

        with open('feedback_channels.json', 'r') as f:
            feedback_channels = json.load(f)

        if guild_id in feedback_channels:
            channel_id = feedback_channels[guild_id]
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                embed = discord.Embed(title=title,
                                      description=feedback,
                                      color=discord.Color.blue())
                embed.add_field(name="Upvotes", value="0", inline=True)
                embed.add_field(name="Downvotes", value="0", inline=True)
                embed.add_field(name="Upvote Progress",
                                value="░░░░░░░░░░ 0%",
                                inline=False)
                embed.add_field(name="Downvote Progress",
                                value="░░░░░░░░░░ 0%",
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
            discord.SelectOption(label="Bug Report 🐞",
                                 description="Report a bug in the bot"),
            discord.SelectOption(label="Feature Request ✨",
                                 description="Request a new feature"),
            discord.SelectOption(label="General Feedback 💬",
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

    def __init__(self, label, emoji, style, custom_id):
        super().__init__(label=label,
                         emoji=emoji,
                         style=style,
                         custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        message = interaction.message
        embed = message.embeds[0]

        upvotes = int(embed.fields[0].value)
        downvotes = int(embed.fields[1].value)
        upvoters = embed.fields[4].value.split(
            ", ") if embed.fields[4].value != "None" else []
        downvoters = embed.fields[5].value.split(
            ", ") if embed.fields[5].value != "None" else []

        user_mention = interaction.user.mention

        if self.custom_id == "upvote_button":
            if user_mention in downvoters:
                downvotes -= 1
                downvoters.remove(user_mention)
            if user_mention not in upvoters:
                upvotes += 1
                upvoters.append(user_mention)
        elif self.custom_id == "downvote_button":
            if user_mention in upvoters:
                upvotes -= 1
                upvoters.remove(user_mention)
            if user_mention not in downvoters:
                downvotes += 1
                downvoters.append(user_mention)
        elif self.custom_id == "show_votes_button":
            await interaction.response.send_message(
                f"Upvoted by: {', '.join(upvoters) if upvoters else 'None'}\nDownvoted by: {', '.join(downvoters) if downvoters else 'None'}",
                ephemeral=True)
            return

        total_votes = upvotes + downvotes
        upvote_percentage = int(
            (upvotes / total_votes) * 100) if total_votes > 0 else 0
        downvote_percentage = int(
            (downvotes / total_votes) * 100) if total_votes > 0 else 0

        embed.set_field_at(0, name="Upvotes", value=str(upvotes), inline=True)
        embed.set_field_at(1,
                           name="Downvotes",
                           value=str(downvotes),
                           inline=True)
        embed.set_field_at(
            2,
            name="Upvote Progress",
            value=
            f"▓{'▓' * (upvote_percentage // 10)}{'░' * (10 - (upvote_percentage // 10))} {upvote_percentage}%",
            inline=False)
        embed.set_field_at(
            3,
            name="Downvote Progress",
            value=
            f"▓{'▓' * (downvote_percentage // 10)}{'░' * (10 - (downvote_percentage // 10))} {downvote_percentage}%",
            inline=False)

        await interaction.response.edit_message(embed=embed, view=self.view)


class FeedbackVoteView(View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(
            FeedbackVoteButton(label="Upvote",
                               emoji="👍",
                               style=discord.ButtonStyle.success,
                               custom_id="upvote_button"))
        self.add_item(
            FeedbackVoteButton(label="Show Votes",
                               emoji="🗳️",
                               style=discord.ButtonStyle.secondary,
                               custom_id="show_votes_button"))
        self.add_item(
            FeedbackVoteButton(label="Downvote",
                               emoji="👎",
                               style=discord.ButtonStyle.danger,
                               custom_id="downvote_button"))


class RemoveChannelButton(Button):

    def __init__(self, cog):
        super().__init__(label="Remove Channel",
                         emoji="❌",
                         style=discord.ButtonStyle.danger)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        if os.path.exists('feedback_channels.json'):
            with open('feedback_channels.json', 'r') as f:
                feedback_channels = json.load(f)

            if guild_id in feedback_channels:
                del feedback_channels[guild_id]
                with open('feedback_channels.json', 'w') as f:
                    json.dump(feedback_channels, f, indent=4)
                embed = interaction.message.embeds[0]
                embed.description = "No feedback channel set."
                embed.set_footer(
                    text=
                    f"Powered By Nira • Requested By {interaction.user} • {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                    icon_url=interaction.user.avatar.url)
                await interaction.response.edit_message(embed=embed, view=None)
            else:
                await interaction.response.send_message(
                    "Feedback channel is not set up.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Feedback channel is not set up.", ephemeral=True)


class Feedback(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.bot.add_view(FeedbackView())  # Register the persistent view
        self.bot.add_view(
            FeedbackVoteView())  # Register the persistent vote view

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
    @app_commands.default_permissions(administrator=True)
    async def feedback_setup(self,
                             interaction: discord.Interaction,
                             channel: discord.TextChannel = None):
        """Set or remove the channel for feedback logs (Admin only)"""
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command cannot be used in DMs.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)

        feedback_channels = {}
        if os.path.exists('feedback_channels.json'):
            with open('feedback_channels.json', 'r') as f:
                feedback_channels = json.load(f)

        if channel:
            feedback_channels[guild_id] = channel.id

            with open('feedback_channels.json', 'w') as f:
                json.dump(feedback_channels, f, indent=4)

            embed = discord.Embed(
                title="Feedback Channel Set",
                description=
                f"Feedback channel has been set to {channel.mention}.",
                color=discord.Color.green())
            embed.set_footer(
                text=
                f"Powered By Nira • Requested By {interaction.user} • {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                icon_url=interaction.user.avatar.url)
            embed.set_author(name=self.bot.user.name,
                             icon_url=self.bot.user.avatar.url)
            embed.add_field(
                name="Usage",
                value="Use `/feedback_setup` to set feedback channel.",
                inline=False)
            view = View()
            view.add_item(RemoveChannelButton(self))

            await interaction.response.send_message(embed=embed,
                                                    view=view,
                                                    ephemeral=True)
        else:
            embed = discord.Embed(
                title="Feedback Channel Not Set",
                description="No feedback channel has been set.",
                color=discord.Color.red())
            embed.set_footer(
                text=
                f"Powered By Nira • Requested By {interaction.user} • {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                icon_url=interaction.user.avatar.url)
            embed.set_author(name=self.bot.user.name,
                             icon_url=self.bot.user.avatar.url)
            embed.add_field(
                name="Usage",
                value=
                "Use `/feedback_setup <channel>` to set feedback channel.",
                inline=False)
            view = View()
            view.add_item(RemoveChannelButton(self))

            await interaction.response.send_message(embed=embed,
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


async def setup(bot: commands.Bot) -> None:
    cog = Feedback(bot)
    await bot.add_cog(cog)

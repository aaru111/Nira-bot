import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, Optional
import asyncio
from loguru import logger

vote_tracking: Dict[int, Dict[int,
                              bool]] = {}  # {message_id: {user_id: voted_up}}
latest_suggestion_id: Dict[int, int] = {}  # {channel_id: message_id}


class SuggestionModal(discord.ui.Modal, title="Create a Suggestion"):

    def __init__(self):
        super().__init__()

        self.type = discord.ui.TextInput(
            label="Suggestion Type",
            placeholder="Feature Request / Bug Report / Improvement",
            required=True,
            max_length=50)
        self.topic = discord.ui.TextInput(
            label="Topic",
            placeholder="Brief topic of your suggestion",
            required=True,
            max_length=100)
        self.description = discord.ui.TextInput(
            label="Description",
            placeholder="Detailed explanation of your suggestion...",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=1000)

        self.add_item(self.type)
        self.add_item(self.topic)
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()


class SuggestionButtons(discord.ui.View):

    def __init__(self, bot, *, is_latest: bool = False):
        super().__init__(timeout=None)
        self.bot = bot
        self.up_votes = 0
        self.down_votes = 0
        self.is_latest = is_latest

        if not self.is_latest:

            self.remove_item(self.new_suggestion)

    @discord.ui.button(label="Upvote (0)",
                       style=discord.ButtonStyle.green,
                       custom_id="suggestion_upvote")
    async def upvote(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        message_id = interaction.message.id
        user_id = interaction.user.id

        if message_id not in vote_tracking:
            vote_tracking[message_id] = {}

        if user_id in vote_tracking[message_id]:
            if vote_tracking[message_id][user_id]:
                self.up_votes -= 1
                del vote_tracking[message_id][user_id]
            else:
                self.down_votes -= 1
                vote_tracking[message_id][user_id] = True
                self.up_votes += 1
        else:
            vote_tracking[message_id][user_id] = True
            self.up_votes += 1

        button.label = f"Upvote ({self.up_votes})"
        self.children[1].label = f"Downvote ({self.down_votes})"

        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Downvote (0)",
                       style=discord.ButtonStyle.red,
                       custom_id="suggestion_downvote")
    async def downvote(self, interaction: discord.Interaction,
                       button: discord.ui.Button):
        message_id = interaction.message.id
        user_id = interaction.user.id

        if message_id not in vote_tracking:
            vote_tracking[message_id] = {}

        if user_id in vote_tracking[message_id]:
            if not vote_tracking[message_id][user_id]:
                self.down_votes -= 1
                del vote_tracking[message_id][user_id]
            else:
                self.up_votes -= 1
                vote_tracking[message_id][user_id] = False
                self.down_votes += 1
        else:
            vote_tracking[message_id][user_id] = False
            self.down_votes += 1

        self.children[0].label = f"Upvote ({self.up_votes})"
        button.label = f"Downvote ({self.down_votes})"

        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="New Suggestion",
                       style=discord.ButtonStyle.blurple,
                       custom_id="new_suggestion")
    async def new_suggestion(self, interaction: discord.Interaction,
                             button: discord.ui.Button):
        modal = SuggestionModal()
        await interaction.response.send_modal(modal)

        try:
            await modal.wait()

            if interaction.channel.id in latest_suggestion_id:
                try:
                    old_message = await interaction.channel.fetch_message(
                        latest_suggestion_id[interaction.channel.id])
                    old_view = SuggestionButtons(self.bot, is_latest=False)

                    for child in self.children:
                        if "upvote" in child.custom_id:
                            old_view.up_votes = int(
                                child.label.split("(")[1].strip(")"))
                        elif "downvote" in child.custom_id:
                            old_view.down_votes = int(
                                child.label.split("(")[1].strip(")"))
                    await old_message.edit(view=old_view)
                except discord.NotFound:
                    pass

            embed = discord.Embed(title=f"New Suggestion: {modal.topic}",
                                  color=discord.Color.blue())
            embed.add_field(name="Type", value=modal.type.value, inline=False)
            embed.add_field(name="Description",
                            value=modal.description.value,
                            inline=False)
            embed.set_footer(text=f"Suggested by {interaction.user}",
                             icon_url=interaction.user.display_avatar.url)

            new_view = SuggestionButtons(self.bot, is_latest=True)
            message = await interaction.channel.send(embed=embed,
                                                     view=new_view)

            latest_suggestion_id[interaction.channel.id] = message.id

            await message.create_thread(
                name=f"Discussion: {modal.topic.value[:50]}",
                auto_archive_duration=1440)

        except asyncio.TimeoutError:
            pass


class InitialSuggestionView(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="New Suggestion",
                       style=discord.ButtonStyle.blurple,
                       custom_id="initial_suggestion")
    async def create_suggestion(self, interaction: discord.Interaction,
                                button: discord.ui.Button):
        modal = SuggestionModal()
        await interaction.response.send_modal(modal)

        try:
            await modal.wait()

            embed = discord.Embed(title=f"New Suggestion: {modal.topic}",
                                  color=discord.Color.blue())
            embed.add_field(name="Type", value=modal.type.value, inline=False)
            embed.add_field(name="Description",
                            value=modal.description.value,
                            inline=False)
            embed.set_footer(text=f"Suggested by {interaction.user}",
                             icon_url=interaction.user.display_avatar.url)

            await interaction.message.delete()

            new_view = SuggestionButtons(self.bot, is_latest=True)
            message = await interaction.channel.send(embed=embed,
                                                     view=new_view)

            latest_suggestion_id[interaction.channel.id] = message.id

            await message.create_thread(
                name=f"Discussion: {modal.topic.value[:50]}",
                auto_archive_duration=1440)

        except asyncio.TimeoutError:
            pass


class Suggestion(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="setupsuggestions",
                             description="Set up a suggestion channel")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(channel="The channel to set up for suggestions")
    async def setup_suggestions(self,
                                ctx: commands.Context,
                                channel: Optional[discord.TextChannel] = None):
        target_channel = channel or ctx.channel

        embed = discord.Embed(
            title="💡 Suggestions",
            description="Click the button below to submit a new suggestion!",
            color=discord.Color.blue())

        await target_channel.send(embed=embed,
                                  view=InitialSuggestionView(self.bot))
        await ctx.send(
            f"Suggestion system has been set up in {target_channel.mention}!",
            ephemeral=True)


async def setup(bot):
    await bot.add_cog(Suggestion(bot))

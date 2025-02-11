import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, Optional
import asyncio
from helpers import database

db = database.db

vote_tracking: Dict[int, Dict[int, bool]] = {}
latest_suggestion_id: Dict[int, int] = {}
suggestion_statuses = {
    "pending": {
        "name": "⏳ Pending",
        "color": discord.Color.blue()
    },
    "approved": {
        "name": "✅ Approved",
        "color": discord.Color.green()
    },
    "rejected": {
        "name": "❌ Rejected",
        "color": discord.Color.red()
    },
    "implemented": {
        "name": "✨ Implemented",
        "color": discord.Color.gold()
    },
    "under_review": {
        "name": "🔍 Under Review",
        "color": discord.Color.orange()
    }
}


class ModSetupModal(discord.ui.Modal, title="Add Moderator"):
    target = discord.ui.TextInput(
        label="Role/User ID",
        placeholder="Enter role or user ID to add as moderator",
        required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            target_id = int(self.target.value)
        except ValueError:
            return await interaction.response.send_message(
                "Invalid ID format!", ephemeral=True)

        guild = interaction.guild
        target = guild.get_role(target_id) or guild.get_member(target_id)

        if not target:
            return await interaction.response.send_message(
                "Role/user not found!", ephemeral=True)

        if isinstance(target, discord.Role):
            if target.permissions.kick_members:
                await db.execute(
                    "INSERT INTO suggestion_mods (guild_id, mod_id, is_role) VALUES ($1, $2, $3) ON CONFLICT (guild_id, mod_id) DO NOTHING",
                    interaction.guild_id, target_id, True)
                await interaction.response.send_message(
                    f"Added role {target.name} as moderator!", ephemeral=True)
            else:
                await interaction.response.send_message(
                    "Role must have Kick Members permission!", ephemeral=True)
        elif isinstance(target, discord.Member):
            if target.guild_permissions.kick_members:
                await db.execute(
                    "INSERT INTO suggestion_mods (guild_id, mod_id, is_role) VALUES ($1, $2, $3) ON CONFLICT (guild_id, mod_id) DO NOTHING",
                    interaction.guild_id, target_id, False)
                await interaction.response.send_message(
                    f"Added user {target.display_name} as moderator!",
                    ephemeral=True)
            else:
                await interaction.response.send_message(
                    "User must have Kick Members permission!", ephemeral=True)


class ModSetupView(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def get_mods_embed(self, guild_id):
        records = await db.fetch(
            "SELECT mod_id, is_role FROM suggestion_mods WHERE guild_id = $1",
            guild_id)
        guild = self.bot.get_guild(guild_id)

        description = "**Current Moderators:**\n"
        for record in records:
            mod_id = record['mod_id']
            is_role = record['is_role']

            if is_role:
                target = guild.get_role(mod_id)
                type_str = "(Role)"
            else:
                target = guild.get_member(mod_id)
                type_str = "(User)"

            if target:
                description += f"- {target.mention} {type_str}\n"
            else:
                description += f"- Unknown ID: {mod_id} {type_str}\n"

        embed = discord.Embed(title="Moderator Setup",
                              description=description,
                              color=discord.Color.blurple())
        embed.add_field(
            name="Instructions",
            value="Click the button below to add moderators/roles. "
            "They must have at least Kick Members permission.\n"
            "Administrators automatically have full access.",
            inline=False)
        return embed

    @discord.ui.button(label="Add Moderator",
                       style=discord.ButtonStyle.blurple)
    async def add_moderator(self, interaction: discord.Interaction,
                            button: discord.ui.Button):
        modal = ModSetupModal()
        await interaction.response.send_modal(modal)
        await modal.wait()

        embed = await self.get_mods_embed(interaction.guild_id)
        await interaction.edit_original_response(embed=embed)


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


class StatusSelect(discord.ui.Select):

    def __init__(self, bot, current_status):
        self.bot = bot
        options = [
            discord.SelectOption(label=status["name"], value=status_key)
            for status_key, status in suggestion_statuses.items()
        ]
        super().__init__(
            placeholder=
            f"Current Status: {suggestion_statuses[current_status]['name']}",
            options=options,
            custom_id="status_select")

    async def callback(self, interaction: discord.Interaction):
        if not await is_mod(interaction):
            return await interaction.response.send_message(
                "You don't have permission to do this!", ephemeral=True)

        new_status = self.values[0]
        status_info = suggestion_statuses[new_status]

        embed = interaction.message.embeds[0]
        embed.color = status_info["color"]

        existing_fields = {field.name: field.value for field in embed.fields}
        existing_fields["Status"] = status_info["name"]

        embed.clear_fields()
        for name, value in existing_fields.items():
            embed.add_field(name=name, value=value, inline=False)

        await interaction.message.edit(embed=embed)
        await interaction.response.defer()


async def is_mod(interaction: discord.Interaction):
    if interaction.user.guild_permissions.administrator:
        return True

    records = await db.fetch(
        "SELECT mod_id, is_role FROM suggestion_mods WHERE guild_id = $1",
        interaction.guild_id)

    user_roles = [role.id for role in interaction.user.roles]
    user_id = interaction.user.id

    for record in records:
        mod_id = record['mod_id']
        is_role = record['is_role']

        if is_role:
            if mod_id in user_roles:
                return True
        else:
            if mod_id == user_id:
                return True

    return False


class SuggestionButtons(discord.ui.View):

    def __init__(self, bot, *, is_latest: bool = False):
        super().__init__(timeout=None)
        self.bot = bot
        self.up_votes = 0
        self.down_votes = 0
        self.is_latest = is_latest
        self.add_item(StatusSelect(bot, "pending"))

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

            embed = discord.Embed(title=f"New Suggestion: {modal.topic.value}",
                                  color=discord.Color.blue())
            embed.add_field(name="Type", value=modal.type.value, inline=False)
            embed.add_field(name="Description",
                            value=modal.description.value,
                            inline=False)
            embed.add_field(name="Status",
                            value=suggestion_statuses["pending"]["name"],
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

            embed = discord.Embed(title=f"New Suggestion: {modal.topic.value}",
                                  color=discord.Color.blue())
            embed.add_field(name="Type", value=modal.type.value, inline=False)
            embed.add_field(name="Description",
                            value=modal.description.value,
                            inline=False)
            embed.add_field(name="Status",
                            value=suggestion_statuses["pending"]["name"],
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

    @commands.hybrid_group(name="suggestions")
    async def suggestions_group(self, ctx):
        pass

    @suggestions_group.command(name="mod setup",
                               description="Setup suggestion moderators")
    @commands.has_permissions(administrator=True)
    async def mod_setup(self, ctx: commands.Context):
       
        await db.execute("""
            CREATE TABLE IF NOT EXISTS suggestion_mods (
                guild_id BIGINT,
                mod_id BIGINT,
                is_role BOOLEAN NOT NULL,
                PRIMARY KEY (guild_id, mod_id)
            )
        """)

        view = ModSetupView(self.bot)
        embed = await view.get_mods_embed(ctx.guild.id)
        await ctx.send(embed=embed, view=view, ephemeral=True)

    @commands.hybrid_command(name="setup suggestions",
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

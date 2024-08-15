import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import random
import string
import asyncio
from typing import Dict, Any, Set, List
from abc import ABC, abstractmethod

# File paths for storing data
DATA_PATH = "data/reaction_roles.json"
TRACKED_MESSAGES_PATH = "data/tracked_messages.json"
RATE_LIMIT_INTERVAL = 2
RATE_LIMIT_CLEANUP_INTERVAL = 60


class RolesyncCooldown:

    def __init__(self, rate, per):
        self.rate = rate
        self.per = per
        self.last_used = {}

    def __call__(self, ctx):
        now = ctx.message.created_at.timestamp()
        bucket = ctx.guild.id if ctx.guild else ctx.author.id
        if bucket in self.last_used:
            last = self.last_used[bucket]
            if now - last < self.per:
                raise commands.CommandOnCooldown(
                    cooldown=commands.Cooldown(self.rate, self.per),
                    retry_after=self.per - (now - last),
                    type=commands.BucketType.guild)
        self.last_used[bucket] = now
        return True


class NavigationView(discord.ui.View):

    def __init__(self, cog: 'ReactionRole', guild: discord.Guild,
                 channel: discord.TextChannel):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild = guild
        self.channel = channel
        self.current_page = 0
        self.message_ids = self.get_message_ids()

    def get_message_ids(self) -> List[str]:
        return ['overview'] + [
            message_id for message_id, roles_data in self.cog.reaction_roles[
                str(self.guild.id)].items()
            if roles_data[0]['channel_id'] == str(self.channel.id)
        ]

    def update_button_state(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(
            self.message_ids) - 1

    @discord.ui.button(label="Previous",
                       style=discord.ButtonStyle.primary,
                       row=1)
    async def prev_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
        self.update_button_state()
        await self.update_embed(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, row=1)
    async def next_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        if self.current_page < len(self.message_ids) - 1:
            self.current_page += 1
        self.update_button_state()
        await self.update_embed(interaction)

    async def update_embed(self, interaction: discord.Interaction):
        if self.current_page == 0:
            embed = await self.cog.create_channel_reaction_roles_embed(
                self.guild, self.channel)
        else:
            message_id = self.message_ids[self.current_page]
            embed = await self.cog.create_message_reaction_roles_embed(
                self.guild, self.channel, message_id)

        await interaction.response.edit_message(embed=embed, view=self)


class ChannelSelect(discord.ui.Select):

    def __init__(self, cog: 'ReactionRole',
                 options: List[discord.SelectOption]):
        super().__init__(placeholder="Select a channel", options=options)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(self.values[0])
        channel = interaction.guild.get_channel(channel_id)
        if channel:
            view = NavigationView(self.cog, interaction.guild, channel)
            overview_embed = await self.cog.create_channel_reaction_roles_embed(
                interaction.guild, channel)
            await interaction.response.edit_message(embed=overview_embed,
                                                    view=view)


class ChannelSelectView(discord.ui.View):

    def __init__(self, cog: 'ReactionRole',
                 options: List[discord.SelectOption]):
        super().__init__()
        self.add_item(ChannelSelect(cog, options))


class ColorChoice(app_commands.Choice):
    """Defines color choices for reaction role buttons."""
    Red = app_commands.Choice(name="Red", value="red")
    Green = app_commands.Choice(name="Green", value="green")
    Blurple = app_commands.Choice(name="Blurple", value="blurple")
    Gray = app_commands.Choice(name="Gray", value="gray")


class ColorMapping:
    """Maps color names to Discord button styles."""
    MAPPING = {
        "red": discord.ButtonStyle.danger,
        "green": discord.ButtonStyle.success,
        "blurple": discord.ButtonStyle.primary,
        "gray": discord.ButtonStyle.secondary
    }

    @classmethod
    def get_style(cls, color: str) -> discord.ButtonStyle:
        """Get the Discord button style for a given color name."""
        return cls.MAPPING.get(color.lower(), discord.ButtonStyle.primary)


class DataManager(ABC):
    """Abstract base class for data management operations."""

    @staticmethod
    @abstractmethod
    def load_data(file_path: str) -> Any:
        """Load data from a file."""
        pass

    @staticmethod
    @abstractmethod
    def save_data(file_path: str, data: Any) -> None:
        """Save data to a file."""
        pass


class JsonDataManager(DataManager):

    @staticmethod
    def load_data(file_path: str) -> Any:
        """Load JSON data from a file."""
        try:
            with open(file_path, "r") as file:
                return json.load(file)
        except (json.JSONDecodeError, FileNotFoundError):
            return {} if file_path == DATA_PATH else []

    @staticmethod
    def save_data(file_path: str, data: Any) -> None:
        """Save data to a JSON file."""
        with open(file_path, "w") as file:
            json.dump(data, file, indent=4)


class FileManager:
    """Manages file operations for the bot."""

    @staticmethod
    def ensure_data_files_exist():
        """Create necessary directories and files if they don't exist."""
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(TRACKED_MESSAGES_PATH), exist_ok=True)
        for file_path in [DATA_PATH, TRACKED_MESSAGES_PATH]:
            if not os.path.exists(file_path):
                JsonDataManager.save_data(file_path,
                                          {} if file_path == DATA_PATH else [])


class ReactionRoleManager:
    """Manages reaction role operations, reducing code duplication."""

    def __init__(self, cog: commands.Cog):
        self.cog = cog

    async def add_buttons_to_message(self, message: discord.Message,
                                     roles_data: List[Dict[str, Any]]):
        """Add reaction role buttons to a message."""
        guild = message.guild
        view = discord.ui.View(timeout=None)

        for role_data in roles_data:
            role = guild.get_role(int(role_data['role_id']))
            emoji = role_data['emoji']
            color = discord.ButtonStyle(int(role_data['color']))
            custom_id = role_data['custom_id']
            link = role_data.get('link')

            if link:
                button = discord.ui.Button(label="Click here",
                                           url=link,
                                           emoji=emoji)
            else:
                button = discord.ui.Button(style=color,
                                           emoji=emoji,
                                           custom_id=custom_id)

            button.callback = self.create_button_callback(role)
            view.add_item(button)

        await message.edit(view=view)

    def create_button_callback(self, role: discord.Role):

        async def button_callback(interaction: discord.Interaction):
            if not self.cog.check_rate_limit(interaction.user.id):
                await interaction.response.send_message(
                    "You're doing that too fast. Please wait a moment.",
                    ephemeral=True)
                return

            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message(
                    f"Role {role.name} removed!", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(
                    f"Role {role.name} assigned!", ephemeral=True)

        return button_callback

    async def handle_message_deletion(self, message: discord.Message):
        """Handle message deletion events."""
        guild_id = str(message.guild.id)
        message_id = str(message.id)
        if guild_id in self.cog.reaction_roles and message_id in self.cog.reaction_roles[
                guild_id]:
            self.cog.delete_reaction_role(guild_id, message_id)


class ReactionRole(commands.Cog):
    """A Discord bot cog for managing reaction roles."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.role_manager = ReactionRoleManager(self)
        FileManager.ensure_data_files_exist()
        self.reaction_roles: Dict[str, Dict[str, List[Dict[
            str, Any]]]] = JsonDataManager.load_data(DATA_PATH)
        self.tracked_messages: Set[int] = set(
            JsonDataManager.load_data(TRACKED_MESSAGES_PATH))
        self.bot.loop.create_task(self.setup_reaction_roles())
        self.rate_limit_dict: Dict[int, float] = {}
        self.bot.loop.create_task(self.cleanup_rate_limit_dict())

    def check_rate_limit(self, user_id: int) -> bool:
        """Check if a user has exceeded the rate limit for button clicks."""
        current_time = asyncio.get_event_loop().time()
        if user_id in self.rate_limit_dict:
            last_time = self.rate_limit_dict[user_id]
            if current_time - last_time < RATE_LIMIT_INTERVAL:
                return False
        self.rate_limit_dict[user_id] = current_time
        return True

    async def cleanup_rate_limit_dict(self):
        """Periodically cleanup the rate limit dictionary to prevent memory leaks."""
        while not self.bot.is_closed():
            current_time = asyncio.get_event_loop().time()
            self.rate_limit_dict = {
                user_id: last_time
                for user_id, last_time in self.rate_limit_dict.items()
                if current_time - last_time < RATE_LIMIT_INTERVAL
            }
            await asyncio.sleep(RATE_LIMIT_CLEANUP_INTERVAL)

    def save_reaction_roles(self):
        """Save the current reaction roles data to file."""
        JsonDataManager.save_data(DATA_PATH, self.reaction_roles)

    def save_tracked_messages(self):
        """Save the current tracked messages to file."""
        JsonDataManager.save_data(TRACKED_MESSAGES_PATH,
                                  list(self.tracked_messages))

    async def setup_reaction_roles(self):
        """Setup reaction roles when the bot starts."""
        await self.bot.wait_until_ready()
        to_delete = []
        for guild_id, messages in self.reaction_roles.items():
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                to_delete.append(guild_id)
                continue
            for message_id, roles_data in messages.items():
                channel = self.bot.get_channel(int(
                    roles_data[0]['channel_id']))
                if channel:
                    try:
                        message = await channel.fetch_message(int(message_id))
                        await self.role_manager.add_buttons_to_message(
                            message, roles_data)
                        self.tracked_messages.add(int(message_id))
                    except discord.NotFound:
                        to_delete.append((guild_id, message_id))
                await asyncio.sleep(0.1)  # Avoid rate limiting

        await asyncio.sleep(30)
        for entry in to_delete:
            if isinstance(entry, tuple):
                guild_id, message_id = entry
                self.delete_reaction_role(guild_id, message_id)
            else:
                del self.reaction_roles[entry]
        self.save_reaction_roles()
        self.save_tracked_messages()

    def delete_reaction_role(self, guild_id: str, message_id: str):
        """Delete a reaction role from the saved data."""
        if guild_id in self.reaction_roles and message_id in self.reaction_roles[
                guild_id]:
            del self.reaction_roles[guild_id][message_id]
            if not self.reaction_roles[guild_id]:
                del self.reaction_roles[guild_id]
        self.save_reaction_roles()
        self.tracked_messages.discard(int(message_id))
        self.save_tracked_messages()

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Event listener for channel deletions."""
        guild_id = str(channel.guild.id)
        if guild_id in self.reaction_roles:
            messages_to_delete = [
                message_id for message_id, roles_data in
                self.reaction_roles[guild_id].items()
                if roles_data[0]['channel_id'] == str(channel.id)
            ]
            for message_id in messages_to_delete:
                self.delete_reaction_role(guild_id, message_id)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Event listener for message deletions."""
        await self.role_manager.handle_message_deletion(message)

    async def get_emoji_choices(
            self, interaction: discord.Interaction
    ) -> List[app_commands.Choice[str]]:
        """Get a list of custom emoji choices for the guild."""
        return [
            app_commands.Choice(name=emoji.name, value=str(emoji.id))
            for emoji in interaction.guild.emojis
        ][:25]

    @app_commands.command(name="reaction-role",
                          description="Add a reaction role to a message")
    @app_commands.describe(
        message_link="The message link or ID to add the reaction role to",
        role="The role to assign",
        emoji="The custom emoji to use on the button",
        color="The color of the button (optional, default is blurple)",
        link="A URL to make the button a link button (optional)")
    @app_commands.choices(color=[
        ColorChoice.Red, ColorChoice.Green, ColorChoice.Blurple,
        ColorChoice.Gray
    ])
    async def reaction_role(self,
                            interaction: discord.Interaction,
                            message_link: str,
                            role: discord.Role,
                            emoji: str,
                            color: str = None,
                            link: str = None):
        """Command to add a reaction role to a message."""
        await interaction.response.defer(ephemeral=True)
        try:
            message_id, channel_id = self.parse_message_link(
                message_link, interaction.channel.id)
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                raise ValueError("Channel not found.")
            message = await channel.fetch_message(message_id)
            color = ColorMapping.get_style(color if color else "blurple")
            emoji_obj = discord.utils.get(interaction.guild.emojis,
                                          id=int(emoji))
            if not emoji_obj:
                raise ValueError("Invalid emoji selected.")
            guild_id = str(interaction.guild.id)
            message_id = str(message.id)

            if guild_id not in self.reaction_roles:
                self.reaction_roles[guild_id] = {}
            if message_id not in self.reaction_roles[guild_id]:
                self.reaction_roles[guild_id][message_id] = []

            existing_role = next(
                (role_data
                 for role_data in self.reaction_roles[guild_id][message_id]
                 if role_data["role_id"] == str(role.id)), None)

            if existing_role:
                custom_id = existing_role["custom_id"]
                existing_role.update({
                    "channel_id": str(channel.id),
                    "emoji": str(emoji_obj),
                    "color": color.value,
                    "link": link
                })
            else:
                custom_id = ''.join(
                    random.choices(string.ascii_letters + string.digits, k=20))
                new_role_data = {
                    "role_id": str(role.id),
                    "channel_id": str(channel.id),
                    "emoji": str(emoji_obj),
                    "color": color.value,
                    "custom_id": custom_id,
                    "link": link
                }
                self.reaction_roles[guild_id][message_id].append(new_role_data)

            self.save_reaction_roles()
            await self.role_manager.add_buttons_to_message(
                message, self.reaction_roles[guild_id][message_id])
            self.tracked_messages.add(int(message_id))
            self.save_tracked_messages()
            await interaction.followup.send(
                "Reaction role added or updated successfully!", ephemeral=True)
        except (ValueError, discord.NotFound, discord.HTTPException) as e:
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

    @reaction_role.autocomplete('emoji')
    async def emoji_autocomplete(
            self, interaction: discord.Interaction,
            current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete function for custom emoji selection."""
        return await self.get_emoji_choices(interaction)

    @staticmethod
    def parse_message_link(message_link: str,
                           default_channel_id: int) -> tuple[int, int]:
        """Parse a message link or ID to get message and channel IDs."""
        if "/" in message_link:
            message_id = int(message_link.split("/")[-1])
            channel_id = int(message_link.split("/")[-2])
        else:
            message_id = int(message_link)
            channel_id = default_channel_id
        return message_id, channel_id

    @app_commands.command(
        name="reaction-role-summary",
        description=
        "Show a summary of all configured reaction roles and sync data")
    @app_commands.checks.cooldown(1,
                                  10.0,
                                  key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reaction_role_summary(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        invalid_entries = await self.sync_reaction_roles()
        guild_id = str(interaction.guild.id)

        if guild_id not in self.reaction_roles or not self.reaction_roles[
                guild_id]:
            await interaction.followup.send(
                "No reaction roles configured in this server.", ephemeral=True)
            return

        channel_ids = {
            int(roles_data[0]['channel_id'])
            for roles_data in self.reaction_roles[guild_id].values()
        }
        options = [
            discord.SelectOption(
                label=interaction.guild.get_channel(channel_id).name,
                value=str(channel_id)) for channel_id in channel_ids
            if interaction.guild.get_channel(channel_id)
        ]

        if not options:
            await interaction.followup.send(
                "No valid channels with reaction roles found.", ephemeral=True)
            return

        view = ChannelSelectView(self, options)
        embed = discord.Embed(
            title="📊__**Reaction Roles Summary**__",
            description=
            "```yaml\nSelect a channel below to view its configured reaction roles:```",
            color=discord.Color.blurple())
        embed.add_field(
            name="📌__Total Channels__",
            value=f"```css\n{len(options)} channel(s) with reaction roles```",
            inline=False)
        embed.add_field(
            name="ℹ️__How to Use__",
            value=(
                "1️⃣ Choose a channel from the dropdown menu\n"
                "2️⃣ View the overview and reaction roles for that channel\n"
                "3️⃣ Use navigation buttons to browse multiple messages\n"
                "4️⃣ Manage roles using the `/reaction-role` command"),
            inline=False)
        embed.add_field(
            name="🔄__Sync Results__",
            value=
            f"```diff\n{'+' if invalid_entries > 0 else '-'}{invalid_entries} invalid entries removed```",
            inline=False)
        embed.set_thumbnail(
            url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.set_footer(
            text=
            f"Requested by {interaction.user} | Server: {interaction.guild.name}",
            icon_url=interaction.user.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @reaction_role_summary.error
    async def reaction_role_summary_error(self,
                                          interaction: discord.Interaction,
                                          error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds.",
                ephemeral=True)
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You don't have the required permissions to use this command.",
                ephemeral=True)
        else:
            await interaction.response.send_message(
                "An error occurred while executing this command.",
                ephemeral=True)

    async def sync_reaction_roles(self) -> int:
        """Sync reaction roles data with current server state."""
        to_delete = []
        for guild_id, messages in self.reaction_roles.items():
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                to_delete.append(guild_id)
                continue
            for message_id, roles_data in messages.items():
                channel = self.bot.get_channel(int(
                    roles_data[0]['channel_id']))
                if channel:
                    try:
                        await channel.fetch_message(int(message_id))
                    except discord.NotFound:
                        to_delete.append((guild_id, message_id))
                        self.tracked_messages.discard(int(message_id))
                else:
                    to_delete.append((guild_id, message_id))
                    self.tracked_messages.discard(int(message_id))

        for entry in to_delete:
            if isinstance(entry, tuple):
                guild_id, message_id = entry
                self.delete_reaction_role(guild_id, message_id)
            else:
                del self.reaction_roles[entry]

        self.save_reaction_roles()
        self.save_tracked_messages()
        return len(to_delete)

    async def create_message_reaction_roles_embed(
            self, guild: discord.Guild, channel: discord.TextChannel,
            message_id: str) -> discord.Embed:
        embed = discord.Embed(
            title=f"🎭__Reaction Roles in #{channel.name}__",
            description="```yaml\nConfigured reaction roles for message:```",
            color=discord.Color.blurple())
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        guild_id = str(guild.id)

        if guild_id not in self.reaction_roles or message_id not in self.reaction_roles[
                guild_id]:
            embed.add_field(name="Error",
                            value="No reaction roles found for this message.",
                            inline=False)
            return embed

        roles_data = self.reaction_roles[guild_id][message_id]
        message_link = f"https://discord.com/channels/{guild_id}/{channel.id}/{message_id}"
        field_value = f"[🔗 Jump to Message]({message_link})\n\n"

        for role_data in roles_data:
            role = guild.get_role(int(role_data['role_id']))
            emoji = role_data['emoji']
            field_value += f"{emoji} {role.mention if role else 'Unknown Role'}\n"

        embed.add_field(name=f"📝__Message ID: {message_id}__",
                        value=field_value,
                        inline=False)
        embed.set_footer(
            text=f"Use /reaction-role to add or modify roles • {guild.name}",
            icon_url=guild.icon.url if guild.icon else None)
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def create_channel_reaction_roles_embed(
            self, guild: discord.Guild,
            channel: discord.TextChannel) -> discord.Embed:
        embed = discord.Embed(
            title=f"🎭__Reaction Roles in #{channel.name}__",
            description=
            "```yaml\nOverview of reaction roles in this channel:```",
            color=discord.Color.blurple())
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        guild_id = str(guild.id)
        channel_id = str(channel.id)

        message_count = sum(
            1 for roles_data in self.reaction_roles.get(guild_id, {}).values()
            if roles_data[0]['channel_id'] == channel_id)
        role_count = sum(
            len(roles_data)
            for roles_data in self.reaction_roles.get(guild_id, {}).values()
            if roles_data[0]['channel_id'] == channel_id)

        embed.add_field(
            name="📊__Summary__",
            value=
            f"```css\nTotal Messages: {message_count}\nTotal Roles: {role_count}```",
            inline=False)
        embed.set_footer(
            text=f"Use the navigation buttons to view details • {guild.name}",
            icon_url=guild.icon.url if guild.icon else None)
        embed.timestamp = discord.utils.utcnow()
        return embed


async def setup(bot: commands.Bot) -> None:
    """Setup the ReactionRole cog."""
    await bot.add_cog(ReactionRole(bot))

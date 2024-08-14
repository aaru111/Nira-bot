import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import random
import string
import asyncio
from typing import Dict, Any, Set, List, Optional
from abc import ABC, abstractmethod

# File paths for storing data
DATA_PATH = "data/reaction_roles.json"
TRACKED_MESSAGES_PATH = "data/tracked_messages.json"


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
    """Concrete implementation of DataManager for JSON files."""

    @staticmethod
    def load_data(file_path: str) -> Any:
        """Load JSON data from a file."""
        with open(file_path, "r") as file:
            return json.load(file)

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
    """
    Manages reaction role operations, reducing code duplication.
    """

    def __init__(self, cog: commands.Cog):
        self.cog = cog

    async def add_buttons_to_message(self,
                                     message: discord.Message,
                                     role_id: str,
                                     emoji: str,
                                     color: discord.ButtonStyle,
                                     custom_id: str,
                                     link: Optional[str] = None):
        """Add reaction role buttons to a message."""
        guild = message.guild
        role = guild.get_role(int(role_id))

        view = discord.ui.View(timeout=None)

        if link:
            button = discord.ui.Button(label="Click here",
                                       url=link,
                                       emoji=emoji)
        else:
            button = discord.ui.Button(style=color,
                                       emoji=emoji,
                                       custom_id=custom_id)

            async def button_callback(interaction: discord.Interaction):
                """Callback function for button clicks."""
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

            button.callback = button_callback

        view.add_item(button)
        await message.edit(view=view)

    async def handle_message_deletion(self, message: discord.Message):
        """Handle message deletion events."""
        guild_id = str(message.guild.id)
        message_id = str(message.id)

        if guild_id in self.cog.reaction_roles and message_id in self.cog.reaction_roles[guild_id]:
            self.cog.delete_reaction_role(guild_id, message_id)


class ReactionRole(commands.Cog):
    """
    A Discord bot cog for managing reaction roles.

    This cog allows users to create reaction roles, where clicking a button
    assigns or removes a specific role from a user.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.role_manager = ReactionRoleManager(self)
        FileManager.ensure_data_files_exist()
        self.reaction_roles: Dict[str, Dict[str, Any]] = JsonDataManager.load_data(DATA_PATH)
        self.tracked_messages: Set[int] = set(JsonDataManager.load_data(TRACKED_MESSAGES_PATH))
        self.bot.loop.create_task(self.setup_reaction_roles())
        self.rate_limit_dict: Dict[int, float] = {}

    def save_reaction_roles(self):
        """Save the current reaction roles data to file."""
        JsonDataManager.save_data(DATA_PATH, self.reaction_roles)

    def save_tracked_messages(self):
        """Save the current tracked messages to file."""
        JsonDataManager.save_data(TRACKED_MESSAGES_PATH, list(self.tracked_messages))

    async def setup_reaction_roles(self):
        """
        Set up reaction roles when the bot starts.

        This method retrieves all saved reaction roles and adds the corresponding
        buttons to the messages.
        """
        await self.bot.wait_until_ready()
        to_delete = []

        for guild_id, messages in self.reaction_roles.items():
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                to_delete.append(guild_id)
                continue

            for message_id, details in messages.items():
                channel = self.bot.get_channel(int(details['channel_id']))
                if channel:
                    try:
                        message = await channel.fetch_message(int(message_id))
                        color = discord.ButtonStyle(int(details['color']))
                        await self.role_manager.add_buttons_to_message(
                            message, details['role_id'], details['emoji'],
                            color, details['custom_id'], details.get('link'))
                        self.tracked_messages.add(int(message_id))
                    except discord.NotFound:
                        to_delete.append((guild_id, message_id))
                    await asyncio.sleep(0.1)  # Avoid rate limiting

        # Clean up deleted messages after a delay
        await asyncio.sleep(30)
        for entry in to_delete:
            if isinstance(entry, tuple):
                guild_id, message_id = entry
                self.delete_reaction_role(guild_id, message_id)
            else:
                del self.reaction_roles[entry]
        self.save_reaction_roles()
        self.save_tracked_messages()

        # Start periodic check for deleted messages
        self.bot.loop.create_task(self.periodic_check())

    def delete_reaction_role(self, guild_id: str, message_id: str):
        """Delete a reaction role from the saved data."""
        if guild_id in self.reaction_roles and message_id in self.reaction_roles[guild_id]:
            del self.reaction_roles[guild_id][message_id]
            if not self.reaction_roles[guild_id]:
                del self.reaction_roles[guild_id]
            self.save_reaction_roles()
            self.tracked_messages.discard(int(message_id))
            self.save_tracked_messages()
            print(f"Deleted reaction role info for message ID: {message_id}")

    async def periodic_check(self):
        """Periodically check for deleted messages and clean up data."""
        while not self.bot.is_closed():
            to_delete = []
            for guild_id, messages in list(self.reaction_roles.items()):
                for message_id, details in list(messages.items()):
                    channel = self.bot.get_channel(int(details['channel_id']))
                    if channel:
                        try:
                            await channel.fetch_message(int(message_id))
                        except discord.NotFound:
                            to_delete.append((guild_id, message_id))

            for guild_id, message_id in to_delete:
                self.delete_reaction_role(guild_id, str(message_id))

            await asyncio.sleep(300)  # Check every 5 minutes

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
        ][:25]  # Discord limits choices to 25

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

            custom_id = ''.join(
                random.choices(string.ascii_letters + string.digits, k=20))

            emoji_obj = discord.utils.get(interaction.guild.emojis,
                                          id=int(emoji))
            if not emoji_obj:
                raise ValueError("Invalid emoji selected.")

            await self.role_manager.add_buttons_to_message(message, str(role.id),
                                                           str(emoji_obj), color, custom_id,
                                                           link)

            self.update_reaction_roles(interaction.guild.id,
                                       message.id, role.id, channel.id,
                                       str(emoji_obj), color, custom_id, link)

            await interaction.followup.send(
                "Reaction role added successfully!", ephemeral=True)
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

    def update_reaction_roles(self, guild_id: int, message_id: int,
                              role_id: int, channel_id: int, emoji: str,
                              color: discord.ButtonStyle, custom_id: str,
                              link: Optional[str]):
        """Update the stored reaction role data."""
        guild_id_str = str(guild_id)
        message_id_str = str(message_id)

        if guild_id_str not in self.reaction_roles:
            self.reaction_roles[guild_id_str] = {}

        self.reaction_roles[guild_id_str][message_id_str] = {
            "role_id": str(role_id),
            "channel_id": str(channel_id),
            "emoji": emoji,
            "color": color.value,
            "custom_id": custom_id,
            "link": link
        }
        self.save_reaction_roles()

        self.tracked_messages.add(message_id)
        self.save_tracked_messages()

    def check_rate_limit(self, user_id: int) -> bool:
        """Check if a user has exceeded the rate limit for button clicks."""
        current_time = asyncio.get_event_loop().time()
        if user_id in self.rate_limit_dict:
            last_time = self.rate_limit_dict[user_id]
            if current_time - last_time < 2:
                return False
        self.rate_limit_dict[user_id] = current_time
        return True

    @app_commands.command(name="reaction-role-summary",
                          description="Show a summary of all configured reaction roles")
    async def reaction_role_summary(self, interaction: discord.Interaction):
        """Command to show a summary of all configured reaction roles."""
        guild_id = str(interaction.guild.id)
        if guild_id not in self.reaction_roles or not self.reaction_roles[guild_id]:
            await interaction.response.send_message("No reaction roles configured in this server.", ephemeral=True)
            return

        embed = discord.Embed(title="Reaction Roles Summary",
                              description="Here are the configured reaction roles:",
                              color=discord.Color.blurple())
        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)

        for message_id, details in self.reaction_roles[guild_id].items():
            channel = interaction.guild.get_channel(int(details['channel_id']))
            if not channel:
                continue

            message_link = f"https://discord.com/channels/{guild_id}/{details['channel_id']}/{message_id}"
            role = interaction.guild.get_role(int(details['role_id']))
            emoji = details['emoji']

            embed.add_field(
                name=f"Message ID: {message_id}",
                value=f"**Role:** {role.mention}\n"
                      f"**Emoji:** {emoji}\n"
                      f"**Channel:** {channel.mention}\n"
                      f"[Message Link]({message_link})",
                inline=False
            )

        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Set up the ReactionRole cog."""
    await bot.add_cog(ReactionRole(bot))

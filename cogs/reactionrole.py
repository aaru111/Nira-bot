import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json
import os
import random

CONFIG_FILE = "reaction_roles.json"

SUGGESTED_EMOJIS = ["👍", "👎", "❤️", "😂", "🔥", "🎉", "❗", "✅", "🔔", "⭐"]

class ReactionRoleButton(discord.ui.Button):
    """
    A button that assigns/removes a role when clicked.
    """
    def __init__(self, role_id: int, emoji: str, colour: discord.ButtonStyle):
        super().__init__(style=colour, emoji=emoji, custom_id=str(role_id))
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        """
        Handles the button click, adding/removing the role to/from the user.
        """
        guild = interaction.guild
        role = guild.get_role(self.role_id)
        user = interaction.user

        try:
            if role in user.roles:
                await user.remove_roles(role)
                await interaction.response.send_message(embed=discord.Embed(
                    title="Role Removed",
                    description=f"You have been removed from the role: **{role.name}**",
                    color=discord.Color.red()), ephemeral=True)
            else:
                await user.add_roles(role)
                await interaction.response.send_message(embed=discord.Embed(
                    title="Role Assigned",
                    description=f"You have been assigned the role: **{role.name}**",
                    color=discord.Color.green()), ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(embed=discord.Embed(
                title="Permission Error",
                description="I do not have permission to manage roles.",
                color=discord.Color.red()), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description=f"An error occurred: {e}",
                color=discord.Color.red()), ephemeral=True)

class ReactionRoleView(discord.ui.View):
    """
    A view containing buttons to assign/remove roles.
    """
    def __init__(self, buttons: list[ReactionRoleButton] = None):
        super().__init__(timeout=None)
        if buttons:
            for button in buttons:
                self.add_item(button)

class ReactionRole(commands.Cog):
    """
    A Cog for handling reaction role commands.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.load_config()

    async def close(self):
        """
        Closes the aiohttp session.
        """
        await self.session.close()

    @commands.Cog.listener()
    async def on_shutdown(self):
        await self.close()

    @commands.Cog.listener()
    async def on_disconnect(self):
        await self.close()

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Checks if the messages stored in the config file exist when the bot starts up.
        """
        await self.check_messages()

    async def check_messages(self):
        """
        Verifies if messages in the config file still exist and deletes their entries if they don't.
        """
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)

            for guild_id, messages in config.copy().items():
                guild = self.bot.get_guild(int(guild_id))
                if guild:
                    for message_id in list(messages.keys()):
                        try:
                            channel_id, message_id = map(int, message_id.split("-"))
                            channel = guild.get_channel(channel_id)
                            if channel:
                                await channel.fetch_message(message_id)
                        except (discord.NotFound, discord.Forbidden):
                            self.delete_message_from_config(guild_id, f"{channel_id}-{message_id}")

    def load_config(self):
        """
        Loads the reaction roles configuration from the JSON file.
        """
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                for guild_id, messages in config.items():
                    for message_id, buttons in messages.items():
                        channel_id, message_id = map(int, message_id.split("-"))
                        view = ReactionRoleView()
                        for button in buttons:
                            role_id = button["role_id"]
                            emoji = button.get("emoji", "🔘")
                            colour = getattr(discord.ButtonStyle, button["colour"])
                            view.add_item(ReactionRoleButton(role_id, emoji, colour))
                        self.bot.add_view(view, message_id=int(message_id))

    def save_config(self, guild_id, channel_id, message_id, button):
        """
        Saves the reaction roles configuration to the JSON file.
        """
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
        else:
            config = {}

        if str(guild_id) not in config:
            config[str(guild_id)] = {}

        message_key = f"{channel_id}-{message_id}"

        if message_key not in config[str(guild_id)]:
            config[str(guild_id)][message_key] = []

        config[str(guild_id)][message_key].append(button)

        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)

    def delete_message_from_config(self, guild_id, message_key):
        """
        Deletes a message configuration from the JSON file.
        """
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)

            if str(guild_id) in config and message_key in config[str(guild_id)]:
                del config[str(guild_id)][message_key]
                if not config[str(guild_id)]:
                    del config[str(guild_id)]

                with open(CONFIG_FILE, "w") as f:
                    json.dump(config, f, indent=4)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        """
        Event listener for when a message is deleted.
        """
        message_key = f"{payload.channel_id}-{payload.message_id}"
        self.delete_message_from_config(payload.guild_id, message_key)

    @app_commands.command(
        name="reaction_role",
        description="Assign buttons to a message for role assignment or remove them.")
    async def reaction_role(self, interaction: discord.Interaction, message_link: str = None, role: discord.Role = None, emoji: str = None, colour: str = None, remove: str = None):
        """
        Command to add or remove reaction role buttons to/from a specified message.

        Parameters:
            interaction (discord.Interaction): The interaction object.
            message_link (str): The link to the message.
            role (discord.Role): The role to assign/remove.
            emoji (str): The emoji for the button.
            colour (str): The colour of the button.
            remove (str): The link to the message from which to remove reaction roles.
        """
        try:
            if remove:
                # Parse message link to get channel ID and message ID
                parts = remove.split('/')
                channel_id = int(parts[-2])
                message_id = int(parts[-1])
                channel = self.bot.get_channel(channel_id)
                message = await channel.fetch_message(message_id)

                # Remove the reaction roles
                self.delete_message_from_config(interaction.guild.id, f"{channel_id}-{message_id}")
                await message.edit(view=None)
                await interaction.response.send_message(embed=discord.Embed(
                    title="Reaction Roles Removed",
                    description=f"Reaction roles have been removed from [this message]({remove})",
                    color=discord.Color.blue()), ephemeral=True)
                return

            if not message_link or not role:
                await interaction.response.send_message(embed=discord.Embed(
                    title="Missing Parameters",
                    description="Please provide both a message link and a role.",
                    color=discord.Color.red()), ephemeral=True)
                return

            # Parse message link to get channel ID and message ID
            parts = message_link.split('/')
            channel_id = int(parts[-2])
            message_id = int(parts[-1])
            channel = self.bot.get_channel(channel_id)
            message = await channel.fetch_message(message_id)

            # Determine button colour
            if colour is None:
                colour = random.choice(["red", "green", "blurple", "grey"])
            colour_map = {
                "red": discord.ButtonStyle.red,
                "green": discord.ButtonStyle.green,
                "blurple": discord.ButtonStyle.blurple,
                "grey": discord.ButtonStyle.grey
            }
            button_colour = colour_map.get(colour, discord.ButtonStyle.grey)

            # Default emoji if not provided
            if emoji is None:
                emoji = random.choice(SUGGESTED_EMOJIS)

            # Create a new button
            button = ReactionRoleButton(role.id, emoji, button_colour)

            # Create or update the view
            view = discord.ui.View(timeout=None)
            if message.components:
                for action_row in message.components:
                    for item in action_row.children:
                        view.add_item(ReactionRoleButton(int(item.custom_id), str(item.emoji), item.style))
            view.add_item(button)

            # Register the view globally
            self.bot.add_view(view, message_id=message_id)

            # Save the button configuration
            self.save_config(interaction.guild.id, channel_id, message_id, {
                "role_id": role.id,
                "emoji": emoji,
                "colour": colour
            })

            await message.edit(view=view)
            await interaction.response.send_message(embed=discord.Embed(
                title="Reaction Role Added",
                description=f"Reaction role has been added to [this message]({message_link})",
                color=discord.Color.blue()), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description=f"An error occurred: {e}",
                color=discord.Color.red()), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    """
    Setup function to add the ReactionRole cog to the bot.

    Parameters:
        bot (commands.Bot): The bot instance.
    """
    await bot.add_cog(ReactionRole(bot))

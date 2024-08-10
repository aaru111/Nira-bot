import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import random
import string
import asyncio

DATA_PATH = "data/reaction_roles.json"


class ReactionRole(commands.Cog):

    def __init__(self, bot):
        """Initializes the ReactionRole Cog"""
        self.bot = bot
        self.reaction_roles = self.load_reaction_roles()
        self.tracked_messages = set()  # To track messages with reaction roles
        self.bot.loop.create_task(self.setup_reaction_roles())

    def load_reaction_roles(self):
        """Loads the reaction roles from the JSON file"""
        if not os.path.exists(DATA_PATH):
            return {}
        with open(DATA_PATH, "r") as file:
            return json.load(file)

    def save_reaction_roles(self):
        """Saves the reaction roles to the JSON file"""
        with open(DATA_PATH, "w") as file:
            json.dump(self.reaction_roles, file, indent=4)

    async def setup_reaction_roles(self):
        """Sets up reaction roles for messages when the bot starts"""
        await self.bot.wait_until_ready()
        to_delete = []

        for guild_id, messages in list(self.reaction_roles.items()):
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                to_delete.append(guild_id)
                continue

            for message_id, details in list(messages.items()):
                channel = self.bot.get_channel(int(details['channel_id']))
                if channel:
                    try:
                        # Fetch the message to ensure it still exists
                        message = await channel.fetch_message(int(message_id))
                        color = discord.ButtonStyle(int(details['color']))
                        await self.add_buttons_to_message(
                            message, details['role_id'], details['emoji'],
                            color, details['custom_id'])
                        self.tracked_messages.add(
                            message.id)  # Track this message
                    except discord.NotFound:
                        to_delete.append((guild_id, message_id))
                    await asyncio.sleep(0.1)

        # Clean up invalid entries
        for entry in to_delete:
            if isinstance(entry, tuple):  # Message deletion
                guild_id, message_id = entry
                self.delete_reaction_role(guild_id, message_id)
            else:  # Guild deletion
                del self.reaction_roles[entry]
        self.save_reaction_roles()

    def delete_reaction_role(self, guild_id, message_id):
        """Helper function to delete a reaction role from the JSON file"""
        if guild_id in self.reaction_roles and message_id in self.reaction_roles[
                guild_id]:
            del self.reaction_roles[guild_id][message_id]
            if not self.reaction_roles[
                    guild_id]:  # If no more messages in guild, delete guild entry
                del self.reaction_roles[guild_id]
            self.save_reaction_roles()
            print(f"Deleted reaction role info for message ID: {message_id}")

    async def add_buttons_to_message(self, message, role_id, emoji, color,
                                     custom_id):
        """Adds buttons to the message"""
        guild = message.guild
        role = guild.get_role(int(role_id))
        button = discord.ui.Button(style=color,
                                   emoji=emoji,
                                   custom_id=custom_id)

        async def button_callback(interaction: discord.Interaction):
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message(
                    f"Role {role.name} removed!", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(
                    f"Role {role.name} assigned!", ephemeral=True)

        button.callback = button_callback

        view = discord.ui.View(timeout=None)
        view.add_item(button)
        await message.edit(view=view)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Listener that runs when a message is deleted"""
        guild_id = str(message.guild.id)
        message_id = str(message.id)

        # Check if the deleted message had a reaction role associated with it
        if guild_id in self.reaction_roles and message_id in self.reaction_roles[
                guild_id]:
            self.delete_reaction_role(guild_id, message_id)
            if message.id in self.tracked_messages:
                self.tracked_messages.remove(message.id)

    @app_commands.command(name="reaction-role",
                          description="Add a reaction role to a message")
    @app_commands.describe(
        message_link="The message link or ID to add the reaction role to",
        role="The role to assign",
        emoji="The emoji to use on the button (optional)",
        color="The color of the button")
    async def reaction_role(self,
                            interaction: discord.Interaction,
                            message_link: str,
                            role: discord.Role,
                            color: discord.ButtonStyle,
                            emoji: str = None):
        """Command to add a reaction role to a message"""
        await interaction.response.defer(ephemeral=True)

        # Parse the message link to get message and channel IDs
        if "/" in message_link:
            message_id = int(message_link.split("/")[-1])
            channel_id = int(message_link.split("/")[-2])
        else:
            message_id = int(message_link)
            channel_id = interaction.channel.id

        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.followup.send("Channel not found.",
                                            ephemeral=True)
            return

        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            await interaction.followup.send("Message not found.",
                                            ephemeral=True)
            return

        # Use a random emoji if none is provided
        if not emoji:
            emoji = random.choice(['😀', '🎉', '🔥', '👍', '❤️'])

        custom_id = ''.join(
            random.choices(string.ascii_letters + string.digits, k=20))
        await self.add_buttons_to_message(message, role.id, emoji, color,
                                          custom_id)

        # Save the reaction role info
        guild_id = str(interaction.guild.id)
        if guild_id not in self.reaction_roles:
            self.reaction_roles[guild_id] = {}

        self.reaction_roles[guild_id][str(message_id)] = {
            "channel_id": str(channel_id),
            "role_id": str(role.id),
            "emoji": emoji,
            "color": str(color.value),
            "custom_id": custom_id
        }
        self.save_reaction_roles()

        # Track the message for future deletions
        self.tracked_messages.add(message.id)

        await interaction.followup.send("Reaction role added successfully!",
                                        ephemeral=True)


async def setup(bot):
    """Sets up the ReactionRole cog"""
    await bot.add_cog(ReactionRole(bot))

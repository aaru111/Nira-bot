import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import random
import string

DATA_PATH = "data/reaction_roles.json"


class ReactionRole(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.reaction_roles = self.load_reaction_roles()
        self.bot.loop.create_task(self.setup_reaction_roles())

    def load_reaction_roles(self):
        if not os.path.exists(DATA_PATH):
            return {}
        with open(DATA_PATH, "r") as file:
            return json.load(file)

    def save_reaction_roles(self):
        with open(DATA_PATH, "w") as file:
            json.dump(self.reaction_roles, file, indent=4)

    async def setup_reaction_roles(self):
        await self.bot.wait_until_ready()
        to_delete = []

        for guild_id, messages in self.reaction_roles.items():
            for message_id, details in list(messages.items()):
                channel = self.bot.get_channel(int(details['channel_id']))
                if channel is not None:
                    try:
                        message = await channel.fetch_message(int(message_id))
                        color = discord.ButtonStyle(int(details['color']))
                        await self.add_buttons_to_message(
                            message, details['role_id'], details['emoji'],
                            color, details['custom_id'])
                    except discord.NotFound:
                        to_delete.append((guild_id, message_id))

        for guild_id, message_id in to_delete:
            if message_id in self.reaction_roles[guild_id]:
                del self.reaction_roles[guild_id][message_id]
            if not self.reaction_roles[guild_id]:
                del self.reaction_roles[guild_id]

        self.save_reaction_roles()

    async def add_buttons_to_message(self, message, role_id, emoji, color,
                                     custom_id):
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
    async def on_ready(self):
        to_delete = []
        for guild_id, messages in list(self.reaction_roles.items()):
            for message_id in list(messages.keys()):
                channel = self.bot.get_channel(
                    int(messages[message_id]['channel_id']))
                try:
                    await channel.fetch_message(message_id)
                except discord.NotFound:
                    to_delete.append((guild_id, message_id))

        for guild_id, message_id in to_delete:
            if guild_id in self.reaction_roles and message_id in self.reaction_roles[
                    guild_id]:
                del self.reaction_roles[guild_id][message_id]
                if not self.reaction_roles[guild_id]:
                    del self.reaction_roles[guild_id]

        self.save_reaction_roles()

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        guild_id = str(message.guild.id)
        message_id = str(message.id)

        if guild_id in self.reaction_roles and message_id in self.reaction_roles[
                guild_id]:
            del self.reaction_roles[guild_id][message_id]
            if not self.reaction_roles[guild_id]:
                del self.reaction_roles[guild_id]
            self.save_reaction_roles()

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
        await interaction.response.defer(ephemeral=True)

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

        if not emoji:
            emoji = random.choice(['😀', '🎉', '🔥', '👍', '❤️'])

        custom_id = ''.join(
            random.choices(string.ascii_letters + string.digits, k=20))
        await self.add_buttons_to_message(message, role.id, emoji, color,
                                          custom_id)

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

        await interaction.followup.send("Reaction role added successfully!",
                                        ephemeral=True)

    @app_commands.command(
        name="reaction-role-summary",
        description="Show a summary of all configured reaction roles")
    async def reaction_role_summary(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)

        if guild_id not in self.reaction_roles or not self.reaction_roles[
                guild_id]:
            await interaction.response.send_message(
                "No reaction roles configured in this server.", ephemeral=True)
            return

        embed = discord.Embed(title="Reaction Roles Summary",
                              color=discord.Color.blue())
        for message_id, details in self.reaction_roles[guild_id].items():
            channel = interaction.guild.get_channel(int(details['channel_id']))
            message_url = f"https://discord.com/channels/{interaction.guild.id}/{channel.id}/{message_id}"
            embed.add_field(
                name=f"Channel: {channel.name}",
                value=
                f"[Message](<{message_url}>)\nRole: <@&{details['role_id']}>\nEmoji: {details['emoji']}",
                inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(ReactionRole(bot))

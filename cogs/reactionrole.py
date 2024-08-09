import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json
import os
import random
import asyncio

CONFIG_FILE = "data/reaction_roles.json"  # Updated path to be inside the /data folder

SUGGESTED_EMOJIS = ["👍", "👎", "❤️", "😂", "🔥", "🎉", "❗", "✅", "🔔", "⭐"]


class ReactionRoleButton(discord.ui.Button):

    def __init__(self, role_id: int, emoji: str, colour: discord.ButtonStyle):
        super().__init__(style=colour, emoji=emoji, custom_id=str(role_id))
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        role = guild.get_role(self.role_id)
        user = interaction.user

        try:
            if role in user.roles:
                await user.remove_roles(role)
                await interaction.response.send_message(embed=discord.Embed(
                    title="Role Removed",
                    description=
                    f"You have been removed from the role: **{role.name}**",
                    color=discord.Color.red()),
                                                        ephemeral=True)
            else:
                await user.add_roles(role)
                await interaction.response.send_message(embed=discord.Embed(
                    title="Role Assigned",
                    description=
                    f"You have been assigned the role: **{role.name}**",
                    color=discord.Color.green()),
                                                        ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(embed=discord.Embed(
                title="Permission Error",
                description="I do not have permission to manage roles.",
                color=discord.Color.red()),
                                                    ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description=f"An error occurred: {e}",
                color=discord.Color.red()),
                                                    ephemeral=True)


class ReactionRoleView(discord.ui.View):

    def __init__(self, buttons: list[ReactionRoleButton] = None):
        super().__init__(timeout=None)
        if buttons:
            for button in buttons:
                self.add_item(button)


class ReactionRole(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.load_config()

    async def close(self):
        await self.session.close()

    @commands.Cog.listener()
    async def on_shutdown(self):
        await self.close()

    @commands.Cog.listener()
    async def on_disconnect(self):
        await self.close()

    @commands.Cog.listener()
    async def on_ready(self):
        await self.check_messages()

    async def check_messages(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)

            for guild_id, messages in config.copy().items():
                guild = self.bot.get_guild(int(guild_id))
                if guild:
                    for message_id in list(messages.keys()):
                        try:
                            channel_id, message_id = map(
                                int, message_id.split("-"))
                            channel = guild.get_channel(channel_id)
                            if channel:
                                await channel.fetch_message(message_id)
                        except (discord.NotFound, discord.Forbidden):
                            self.delete_message_from_config(
                                guild_id, f"{channel_id}-{message_id}")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                for guild_id, messages in config.items():
                    for message_id, buttons in messages.items():
                        channel_id, message_id = map(int,
                                                     message_id.split("-"))
                        view = ReactionRoleView()
                        for button in buttons:
                            role_id = button["role_id"]
                            emoji = button.get("emoji", "🔘")
                            colour = getattr(discord.ButtonStyle,
                                             button["colour"],
                                             discord.ButtonStyle.grey)
                            view.add_item(
                                ReactionRoleButton(role_id, emoji, colour))
                        self.bot.add_view(view, message_id=int(message_id))

    def save_config(self, guild_id, channel_id, message_id, button):
        config = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)

        guild_id_str = str(guild_id)
        if guild_id_str not in config:
            config[guild_id_str] = {}

        message_key = f"{channel_id}-{message_id}"
        if message_key not in config[guild_id_str]:
            config[guild_id_str][message_key] = []

        config[guild_id_str][message_key].append(button)

        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)

    def delete_message_from_config(self, guild_id, message_key):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)

            guild_id_str = str(guild_id)
            if guild_id_str in config and message_key in config[guild_id_str]:
                del config[guild_id_str][message_key]
                if not config[guild_id_str]:
                    del config[guild_id_str]

                with open(CONFIG_FILE, "w") as f:
                    json.dump(config, f, indent=4)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        message_key = f"{payload.channel_id}-{payload.message_id}"
        self.delete_message_from_config(payload.guild_id, message_key)

    @app_commands.command(
        name="reaction_role",
        description=
        "Assign buttons to a message for role assignment or remove them.")
    async def reaction_role(self,
                            interaction: discord.Interaction,
                            message_link: str = None,
                            role: discord.Role = None,
                            emoji: str = None,
                            colour: str = None,
                            remove: str = None):
        try:
            if remove:
                parts = remove.split('/')
                channel_id = int(parts[-2])
                message_id = int(parts[-1])
                channel = self.bot.get_channel(channel_id)
                message = await channel.fetch_message(message_id)

                self.delete_message_from_config(interaction.guild.id,
                                                f"{channel_id}-{message_id}")
                await message.edit(view=None)
                await interaction.response.send_message(embed=discord.Embed(
                    title="Reaction Roles Removed",
                    description=
                    f"Reaction roles have been removed from [this message]({remove})",
                    color=discord.Color.blue()),
                                                        ephemeral=True)
                return

            if not message_link or not role:
                await interaction.response.send_message(embed=discord.Embed(
                    title="Missing Parameters",
                    description=
                    "Please provide both a message link and a role.",
                    color=discord.Color.red()),
                                                        ephemeral=True)
                return

            parts = message_link.split('/')
            channel_id = int(parts[-2])
            message_id = int(parts[-1])
            channel = self.bot.get_channel(channel_id)
            message = await channel.fetch_message(message_id)

            colour_map = {
                "red": discord.ButtonStyle.red,
                "green": discord.ButtonStyle.green,
                "blurple": discord.ButtonStyle.blurple,
                "grey": discord.ButtonStyle.grey
            }
            button_colour = colour_map.get(colour, discord.ButtonStyle.grey)

            if emoji is None:
                emoji = random.choice(SUGGESTED_EMOJIS)

            button = ReactionRoleButton(role.id, emoji, button_colour)

            view = discord.ui.View(timeout=None)
            if message.components:
                for action_row in message.components:
                    for item in action_row.children:
                        view.add_item(
                            ReactionRoleButton(int(item.custom_id),
                                               str(item.emoji), item.style))
            view.add_item(button)

            self.bot.add_view(view, message_id=message_id)

            self.save_config(interaction.guild.id, channel_id, message_id, {
                "role_id": role.id,
                "emoji": emoji,
                "colour": colour
            })

            await message.edit(view=view)
            await interaction.response.send_message(embed=discord.Embed(
                title="Reaction Role Added",
                description=
                f"Reaction role has been added to [this message]({message_link})",
                color=discord.Color.blue()),
                                                    ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description=f"An error occurred: {e}",
                color=discord.Color.red()),
                                                    ephemeral=True)

    @app_commands.command(
        name="reaction_role_summary",
        description="Show a summary of reaction roles set in this server.")
    async def reaction_role_summary(self, interaction: discord.Interaction):
        try:
            if not os.path.exists(CONFIG_FILE):
                await interaction.response.send_message(embed=discord.Embed(
                    title="No Reaction Roles",
                    description=
                    "No reaction roles have been set up in this server.",
                    color=discord.Color.red()),
                                                        ephemeral=True)
                return

            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)

            guild_id_str = str(interaction.guild.id)
            if guild_id_str not in config:
                await interaction.response.send_message(embed=discord.Embed(
                    title="No Reaction Roles",
                    description=
                    "No reaction roles have been set up in this server.",
                    color=discord.Color.red()),
                                                        ephemeral=True)
                return

            messages = config[guild_id_str]
            message_keys = list(messages.keys())
            total_pages = len(message_keys)
            current_page = 0

            async def get_embed(page_number):
                embed = discord.Embed(
                    title="Reaction Roles Summary",
                    description="List of reaction roles set up in this server:",
                    color=discord.Color.blue())
                embed.set_thumbnail(url=interaction.guild.icon.url)

                start_index = page_number * 5
                end_index = start_index + 5
                page_keys = message_keys[start_index:end_index]

                for message_key in page_keys:
                    channel_id, message_id = map(int, message_key.split("-"))
                    channel = interaction.guild.get_channel(channel_id)
                    message = await channel.fetch_message(message_id)

                    embed.add_field(
                        name=f"Message: [Link]({message.jump_url})",
                        value="\n".join([
                            f"{str(button['emoji'])} - <@&{button['role_id']}>"
                            for button in messages[message_key]
                        ]),
                        inline=False)

                embed.set_footer(text=f"Page {page_number + 1}/{total_pages}")

                return embed

            async def paginate(page_number):
                embed = await get_embed(page_number)
                components = []

                if total_pages > 1:
                    if page_number > 0:
                        components.append(
                            discord.ui.Button(
                                label="Previous",
                                custom_id="previous",
                                style=discord.ButtonStyle.primary))
                    if page_number < total_pages - 1:
                        components.append(
                            discord.ui.Button(
                                label="Next",
                                custom_id="next",
                                style=discord.ButtonStyle.primary))

                view = discord.ui.View()
                for component in components:
                    view.add_item(component)

                message = await interaction.response.send_message(embed=embed,
                                                                  view=view)

                def check(interaction):
                    return interaction.message.id == message.id and interaction.user == interaction.user

                try:
                    interaction_response = await self.bot.wait_for(
                        'interaction', timeout=120, check=check)
                    if interaction_response.custom_id == "previous" and page_number > 0:
                        await paginate(page_number - 1)
                    elif interaction_response.custom_id == "next" and page_number < total_pages - 1:
                        await paginate(page_number + 1)
                except asyncio.TimeoutError:
                    await message.edit(view=None)

            await paginate(current_page)

        except Exception as e:
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description=f"An error occurred: {e}",
                color=discord.Color.red()),
                                                    ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReactionRole(bot))

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import random
from urllib.parse import urlparse
import webcolors
import logging
import io

from .modules.embedmod import (AuthorModal, BodyModal, ImagesModal,
                               FooterModal, ScheduleModal, create_embed_view)
from .modules.embedtemp import get_template, templates
from .utils.custom_colors import custom_colors


class EmbedCreator(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.embed_object = None

    async def cog_unload(self):
        """Cleanup resources when the cog is unloaded."""
        await self.session.close()

    @commands.hybrid_command(
        name="stealembed",
        description="Get the code of an embed to use with the embed creator")
    @app_commands.describe(
        message="The message link or ID containing the embed")
    async def stealembed(self, ctx: commands.Context, message: str):
        try:

            if "discord.com/channels/" in message:
                try:

                    parts = message.split('/')
                    guild_id = int(parts[-3])
                    channel_id = int(parts[-2])
                    message_id = int(parts[-1])

                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        channel = await self.bot.fetch_channel(channel_id)

                    message = await channel.fetch_message(message_id)
                except (IndexError, ValueError):
                    await ctx.send("Invalid message link format!",
                                   ephemeral=True)
                    return
                except discord.NotFound:
                    await ctx.send("Couldn't find that message or channel!",
                                   ephemeral=True)
                    return
            else:

                try:
                    message_id = int(message)
                    message = await ctx.channel.fetch_message(message_id)
                except ValueError:
                    await ctx.send(
                        "Please provide a valid message ID or link!",
                        ephemeral=True)
                    return
                except discord.NotFound:
                    await ctx.send(
                        "Couldn't find that message in this channel!",
                        ephemeral=True)
                    return

            if not message.embeds:
                await ctx.send("That message doesn't contain any embeds!",
                               ephemeral=True)
                return

            embed = message.embeds[0]

            embed_dict = embed.to_dict()

            def format_dict(d, indent=0):
                formatted = "{"
                for key, value in d.items():
                    formatted += f'\n{" " * (indent + 4)}"{key}": '
                    if isinstance(value, dict):
                        formatted += format_dict(value, indent + 4)
                    elif isinstance(value, list):
                        if not value:
                            formatted += "[]"
                        else:
                            formatted += "[\n"
                            for item in value:
                                if isinstance(item, dict):
                                    formatted += f'{" " * (indent + 8)}{format_dict(item, indent + 8)},\n'
                                else:
                                    formatted += f'{" " * (indent + 8)}"{item}",\n'
                            formatted += f'{" " * (indent + 4)}]'
                    elif isinstance(value, str):

                        escaped_value = value.replace('"', '\\"')
                        formatted += f'"{escaped_value}"'
                    elif value is None:
                        formatted += "null"
                    else:
                        formatted += f"{value}"
                    formatted += ","
                formatted = formatted.rstrip(",")
                formatted += f'\n{" " * indent}}}'
                return formatted

            formatted_code = format_dict(embed_dict)

            file = discord.File(io.StringIO(formatted_code),
                                filename="embed_code.txt")

            instructions = discord.Embed(
                title="Embed Code Stolen!",
                description=(
                    "**To use this embed:**\n"
                    "1. Open and copy the code from the attached file\n"
                    "2. Use `/embed`\n"
                    "3. Click the Import button\n"
                    "4. Paste the code\n\n"
                    "**Preview of the embed is shown below** ↓"),
                color=discord.Color.green())

            await ctx.send(embeds=[instructions, embed],
                           file=file,
                           ephemeral=True)

        except discord.Forbidden:
            await ctx.send("I don't have permission to see that message!",
                           ephemeral=True)
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(
        name="embed",
        description="Create a custom embed message interactively.")
    @app_commands.choices(template=[
        app_commands.Choice(name=name.capitalize(), value=name)
        for name in templates.keys()
    ])
    async def embed(self,
                    interaction: discord.Interaction,
                    template: str = None) -> None:
        try:
            if template:
                self.embed_object = get_template(template)
                content = f"Here's your {template.capitalize()} template. You can now edit it using the options below."
            else:
                self.embed_object = discord.Embed(
                    title="🛠️ Embed Configuration Preview",
                    description=
                    ("```yaml\n"
                     "Please select an option from the dropdown below to begin configuring your embed.\n\n"
                     "Current Options:\n"
                     "- Author: Set the author of the embed.\n"
                     "- Body: Edit the main content of the embed.\n"
                     "- Images: Add an image or thumbnail.\n"
                     "- Footer: Configure the footer of the embed.\n"
                     "- Schedule Embed: Set a time to automatically send the embed.\n\n"
                     "Once you're satisfied, use the buttons below to send or reset the embed.\n"
                     "```"),
                    color=discord.Color.from_rgb(
                        *random.choice(list(custom_colors.values()))),
                    timestamp=discord.utils.utcnow())
                self.embed_object.set_footer(
                    text=f"Command initiated by {interaction.user.name}",
                    icon_url=interaction.user.avatar.url
                    if interaction.user.avatar else None)
                content = "Welcome to the Embed Creator. Please use the options below to configure your embed."

            view = create_embed_view(self.embed_object, self.bot)

            await interaction.response.send_message(content=content,
                                                    embed=self.embed_object,
                                                    view=view,
                                                    ephemeral=True)
        except Exception as e:
            logging.error(f"Error in embed command: {str(e)}")
            await interaction.response.send_message(
                "An error occurred while creating the embed. Please try again.",
                ephemeral=True)

    async def dropdown_callback(self,
                                interaction: discord.Interaction) -> None:
        value = interaction.data["values"][0] if isinstance(
            interaction.data, dict) and "values" in interaction.data else None
        if value == "author":
            await interaction.response.send_modal(
                AuthorModal(self.embed_object, self.bot, is_edit=True))
        elif value == "body":
            await interaction.response.send_modal(
                BodyModal(self.embed_object, self.bot, is_edit=True))
        elif value == "images":
            await interaction.response.send_modal(
                ImagesModal(self.embed_object, self.bot, is_edit=True))
        elif value == "footer":
            await interaction.response.send_modal(
                FooterModal(self.embed_object, self.bot, is_edit=True))
        elif value == "schedule":
            await interaction.response.send_modal(
                ScheduleModal(self.embed_object, self.bot,
                              interaction.channel))

    def is_valid_url(self, url: str) -> bool:
        """Validate if a given string is a properly formatted URL."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False

    def is_valid_hex_color(self, color: str) -> bool:
        """Check if a given string is a valid hex color code."""
        if color.startswith("#"):
            color = color[1:]
        return len(color) == 6 and all(c in "0123456789ABCDEFabcdef"
                                       for c in color)

    def get_color_from_name(self, name: str) -> discord.Color:
        """Convert a color name to a Discord Color object, with custom colors support."""
        try:
            # Check if color name is in custom colors
            if name in custom_colors:
                rgb = custom_colors[name]
                return discord.Color.from_rgb(*rgb)
            # Normalize the name by replacing spaces with hyphens
            name = name.replace(" ", "-")
            rgb = webcolors.name_to_rgb(name)
            return discord.Color.from_rgb(rgb.red, rgb.green, rgb.blue)
        except ValueError:
            return discord.Color.default()


async def setup(bot: commands.Bot) -> None:
    """Setup the EmbedCreator cog."""
    await bot.add_cog(EmbedCreator(bot))

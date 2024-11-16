import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import random
from urllib.parse import urlparse
import webcolors
import re

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

        await self.session.close()

    def convert_emoji_string(self, content: str) -> str:
        """Convert custom emoji strings to proper Discord emoji format."""
        if not content:
            return content

        # First, handle already formatted Discord emojis
        def replace_formatted_emoji(match):
            emoji_name = match.group(1)
            emoji_id = match.group(2)
            is_animated = match.group(0).startswith('<a:')
            return f"<{'a' if is_animated else ''}:{emoji_name}:{emoji_id}>"

        # Then, handle simple :emoji_name: format
        def replace_simple_emoji(match):
            emoji_name = match.group(1)
            # Search for the emoji in all guilds the bot has access to
            for guild in self.bot.guilds:
                emoji = discord.utils.get(guild.emojis, name=emoji_name)
                if emoji:
                    return str(
                        emoji
                    )  # This will return the proper Discord emoji format
            return f":{emoji_name}:"  # Return original format if emoji not found

        # Pattern for formatted Discord emojis
        formatted_pattern = r'<(?:a?):([^:]+):(\d+)>'
        # Pattern for simple emoji format
        simple_pattern = r':([^:\s]+):'

        # First replace any already formatted emojis
        content = re.sub(formatted_pattern, replace_formatted_emoji, content)
        # Then handle simple format
        content = re.sub(simple_pattern, replace_simple_emoji, content)

        return content

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

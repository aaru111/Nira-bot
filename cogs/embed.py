import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Modal, TextInput, Button
import aiohttp
from urllib.parse import urlparse
import webcolors
import random
from utils.custom_colors import custom_colors  # Import custom colors
from utils.helpembed import get_help_embed
import asyncio
import re
from datetime import datetime, timedelta


class BaseView(View):

    def __init__(self,
                 bot: commands.Bot,
                 embed: discord.Embed = None,
                 current_page: int = 1,
                 total_pages: int = 10):
        super().__init__(timeout=None)
        self.bot = bot
        self.embed = embed
        self.current_page = current_page
        self.total_pages = total_pages

    def add_navigation_buttons(self):
        if self.current_page > 1:
            self.add_item(PreviousButton(self.current_page, self.total_pages))
        if self.current_page < self.total_pages:
            self.add_item(NextButton(self.current_page, self.total_pages))
        self.add_item(JumpToPageButton())

    def add_embed_buttons(self):
        self.add_item(SendButton(self.embed))
        self.add_item(SendToButton(self.embed))
        self.add_item(ResetButton(self.embed))
        self.add_item(FieldsButton())
        self.add_item(PlusButton(self.embed))
        self.add_item(MinusButton(self.embed))
        self.add_item(HelpButton())
        self.add_item(EditFieldButton(self.embed, self.bot))


class EmbedCreator(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.embed_object = None  # Initialize embed_object as None
    
    @app_commands.command(
        name="embed",
        description="Create a custom embed message interactively.")
    async def embed(self, interaction: discord.Interaction) -> None:
        self.embed_object = discord.Embed(
            description="",
            color=discord.Color.from_rgb(
                *random.choice(list(custom_colors.values()))))
        view = create_embed_view(self.embed_object, self.bot)
    
        preview_embed = discord.Embed(
            title="🛠️ Embed Configuration Preview.",
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
        preview_embed.set_footer(
            text=f"Command initiated by {interaction.user.name}",
            icon_url=interaction.user.avatar.url)
    
        await interaction.response.send_message(embed=preview_embed,
                                                view=view,
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
                ScheduleModal(self.embed_object, self.bot))

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


class AuthorModal(Modal):

    def __init__(self,
                 embed: discord.Embed,
                 bot: commands.Bot,
                 is_edit: bool = False):
        super().__init__(title="Configure Author")
        self.embed = embed
        self.bot = bot  # Pass bot as an argument
        self.is_edit = is_edit
        self.author = TextInput(label="Author Name",
                                default=self.embed.author.name
                                if is_edit and self.embed.author else None)
        self.author_url = TextInput(label="Author URL",
                                    required=False,
                                    default=self.embed.author.url
                                    if is_edit and self.embed.author else None)
        self.author_icon_url = TextInput(
            label="Author Icon URL",
            required=False,
            default=self.embed.author.icon_url
            if is_edit and self.embed.author else None)
        self.add_item(self.author)
        self.add_item(self.author_url)
        self.add_item(self.author_icon_url)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle the submission of the author modal."""
        # Validate URLs if provided
        if self.author_url.value and not self.bot.get_cog(
                "EmbedCreator").is_valid_url(self.author_url.value):
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description=
                f"Invalid URL in Author URL: {self.author_url.value}",
                color=discord.Color.red(),
            ),
                                                    ephemeral=True)
            return
        if self.author_icon_url.value and not self.bot.get_cog(
                "EmbedCreator").is_valid_url(self.author_icon_url.value):
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description=
                f"Invalid URL in Author Icon URL: {self.author_icon_url.value}",
                color=discord.Color.red(),
            ),
                                                    ephemeral=True)
            return
        # Set the author details in the embed
        self.embed.set_author(
            name=self.author.value,
            url=self.author_url.value or None,
            icon_url=self.author_icon_url.value or None,
        )
        # Confirm the author configuration to the user
        await interaction.response.edit_message(content="✅ Author configured.",
                                                embed=self.embed,
                                                view=create_embed_view(
                                                    self.embed,
                                                    interaction.client))


class BodyModal(Modal):
    """Modal for configuring the body section (title, description, etc.) of an embed."""

    def __init__(self,
                 embed: discord.Embed,
                 bot: commands.Bot,
                 is_edit: bool = False):
        super().__init__(title="Configure Body")
        self.embed = embed
        self.bot = bot
        self.is_edit = is_edit
        self.titl = TextInput(label="Title",
                              max_length=256,
                              default=self.embed.title if is_edit else None)
        self.description = TextInput(
            label="Description",
            max_length=4000,
            style=discord.TextStyle.paragraph,
            default=self.embed.description if is_edit else None)
        self.url = TextInput(label="URL",
                             required=False,
                             default=self.embed.url if is_edit else None)
        self.color = TextInput(label="Color (hex code, name, or 'random')",
                               required=False,
                               default=self.embed.color.value
                               if is_edit and self.embed.color else None)
        self.add_item(self.titl)
        self.add_item(self.description)
        self.add_item(self.url)
        self.add_item(self.color)

    async def on_submit(self, interaction: discord.Interaction):
        # Validate the URL if provided
        if self.url.value and not self.bot.get_cog(
                "EmbedCreator").is_valid_url(self.url.value):
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description=f"Invalid URL in Body URL: {self.url.value}",
                color=discord.Color.red(),
            ),
                                                    ephemeral=True)
            return
        # Process the color input and set the embed color
        if self.color.value:
            if self.color.value.lower() == "random":
                self.embed.color = discord.Color.random()
            elif self.bot.get_cog("EmbedCreator").is_valid_hex_color(
                    self.color.value):
                self.embed.color = discord.Color(
                    int(self.color.value.strip("#"), 16))
            else:
                color = self.bot.get_cog("EmbedCreator").get_color_from_name(
                    self.color.value)
                if color:
                    self.embed.color = color
                else:
                    await interaction.response.send_message(embed=discord.Embed(
                        title="Error",
                        description=f"Invalid color value: {self.color.value}",
                        color=discord.Color.red(),
                    ),
                                                            ephemeral=True)
                    return
        # Set the title, description, and URL in the embed
        self.embed.title = self.titl.value
        self.embed.description = self.description.value or None
        self.embed.url = self.url.value or None
        # Confirm the body configuration to the user
        await interaction.response.edit_message(content="✅ Body configured.",
                                                embed=self.embed,
                                                view=create_embed_view(
                                                    self.embed,
                                                    interaction.client))


class ImagesModal(Modal):
    """Modal for configuring the image and thumbnail sections of an embed."""

    def __init__(self,
                 embed: discord.Embed,
                 bot: commands.Bot,
                 is_edit: bool = False):
        super().__init__(title="Configure Images")
        self.embed = embed
        self.bot = bot  # Pass bot as an argument here
        self.is_edit = is_edit

        self.image_url = TextInput(label="Image URL",
                                   required=False,
                                   default=self.embed.image.url
                                   if is_edit and self.embed.image else None)
        self.thumbnail_url = TextInput(
            label="Thumbnail URL",
            required=False,
            default=self.embed.thumbnail.url
            if is_edit and self.embed.thumbnail else None)
        self.add_item(self.image_url)
        self.add_item(self.thumbnail_url)

    async def on_submit(self, interaction: discord.Interaction):
        # Validate the image URL
        if self.image_url.value and not self.bot.get_cog(
                "EmbedCreator").is_valid_url(self.image_url.value):
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description=f"Invalid URL in Image URL: {self.image_url.value}",
                color=discord.Color.red(),
            ),
                                                    ephemeral=True)
            return
        # Validate the thumbnail URL
        if self.thumbnail_url.value and not self.bot.get_cog(
                "EmbedCreator").is_valid_url(self.thumbnail_url.value):
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description=
                f"Invalid URL in Thumbnail URL: {self.thumbnail_url.value}",
                color=discord.Color.red(),
            ),
                                                    ephemeral=True)
            return
        # Set the image and thumbnail in the embed
        self.embed.set_image(url=self.image_url.value or None)
        self.embed.set_thumbnail(url=self.thumbnail_url.value or None)
        # Confirm the images configuration to the user
        await interaction.response.edit_message(content="✅ Images configured.",
                                                embed=self.embed,
                                                view=create_embed_view(
                                                    self.embed,
                                                    interaction.client))


class FooterModal(Modal):

    def __init__(self,
                 embed: discord.Embed,
                 bot: commands.Bot,
                 is_edit: bool = False):
        super().__init__(title="Configure Footer")
        self.embed = embed
        self.bot = bot
        self.is_edit = is_edit

        self.footer = TextInput(label="Footer Text",
                                max_length=2048,
                                default=self.embed.footer.text
                                if is_edit and self.embed.footer else None)
        self.timestamp = TextInput(
            label="Timestamp (YYYY-MM-DD hh:mm or 'auto')",
            required=False,
            default=self.embed.timestamp.strftime("%Y-%m-%d %H:%M")
            if is_edit and self.embed.timestamp else None)
        self.footer_icon_url = TextInput(
            label="Footer Icon URL",
            required=False,
            default=self.embed.footer.icon_url
            if is_edit and self.embed.footer else None)
        self.add_item(self.footer)
        self.add_item(self.timestamp)
        self.add_item(self.footer_icon_url)

    async def on_submit(self, interaction: discord.Interaction):
        # Validate the footer icon URL
        if self.footer_icon_url.value and not self.bot.get_cog(
                "EmbedCreator").is_valid_url(self.footer_icon_url.value):
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description=
                f"Invalid URL in Footer Icon URL: {self.footer_icon_url.value}",
                color=discord.Color.red(),
            ),
                                                    ephemeral=True)
            return
        # Set the footer details in the embed
        self.embed.set_footer(text=self.footer.value,
                              icon_url=self.footer_icon_url.value or None)
        # Handle the timestamp
        if self.timestamp.value:
            if self.timestamp.value.lower() == "auto":
                self.embed.timestamp = discord.utils.utcnow()
            else:
                try:
                    self.embed.timestamp = discord.utils.parse_time(
                        self.timestamp.value)
                except ValueError:
                    await interaction.response.send_message(embed=discord.Embed(
                        title="Error",
                        description=
                        f"Invalid timestamp format: {self.timestamp.value}",
                        color=discord.Color.red(),
                    ),
                                                            ephemeral=True)
                    return
        else:
            self.embed.timestamp = None
        # Confirm the footer configuration to the user
        await interaction.response.edit_message(content="✅ Footer configured.",
                                                embed=self.embed,
                                                view=create_embed_view(
                                                    self.embed,
                                                    interaction.client))


class PlusButton(Button):
    """Button to open a modal for adding a new field to the embed."""

    def __init__(self, embed: discord.Embed) -> None:
        """Initialize the plus button with the configured embed."""
        super().__init__(label="",
                         style=discord.ButtonStyle.green,
                         emoji="➕",
                         row=2)
        self.embed = embed

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event to open the add field modal."""
        if self.embed is None:
            self.embed = discord.Embed()

        await interaction.response.send_modal(AddFieldModal(self.embed))
        if self.embed.description is None or not self.embed.description.strip(
        ):
            self.embed.description = "** **"


class AddFieldModal(Modal):

    def __init__(self, embed: discord.Embed) -> None:
        super().__init__(title="Add Field")
        self.embed = embed
        self.field_name = TextInput(label="Field Name")
        self.field_value = TextInput(label="Field Value")
        self.inline = TextInput(label="Inline (True/False)", required=False)
        self.add_item(self.field_name)
        self.add_item(self.field_value)
        self.add_item(self.inline)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        name = self.field_name.value
        value = self.field_value.value
        inline = self.inline.value.lower(
        ) == "true" if self.inline.value else False

        self.embed.add_field(name=name, value=value, inline=inline)

        await interaction.response.edit_message(content="✅ Field added.",
                                                embed=self.embed,
                                                view=create_embed_view(
                                                    self.embed,
                                                    interaction.client))


class MinusButton(Button):

    def __init__(self, embed: discord.Embed):
        super().__init__(label="",
                         style=discord.ButtonStyle.red,
                         emoji="➖",
                         row=2)
        self.embed = embed

    async def callback(self, interaction: discord.Interaction):
        if self.embed is None or not self.embed.fields:
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description="No fields available to remove.",
                color=discord.Color.red(),
            ),
                                                    ephemeral=True)
            return

        options = [
            discord.SelectOption(
                label=f"Field {i+1}: {field.name}",
                value=str(i),
                description=field.
                value[:100],  # Truncate description if too long
            ) for i, field in enumerate(self.embed.fields)
        ]
        view = discord.ui.View(timeout=None)
        select = discord.ui.Select(placeholder="Select a field to remove...",
                                   options=options)
        select.callback = self.remove_field_callback
        view.add_item(select)
        view.add_item(BackButton(self.embed))
        await interaction.response.edit_message(
            content="Select a field to remove:", embed=self.embed, view=view)

    async def remove_field_callback(self,
                                    interaction: discord.Interaction) -> None:
        index = int(interaction.data["values"][0])
        self.embed.remove_field(index)
        if not self.embed.fields:
            await interaction.response.edit_message(
                content=
                "✅ All fields removed. Returning to embed configuration preview.",
                embed=self.embed,
                view=create_embed_view(self.embed, interaction.client))
            return
        options = [
            discord.SelectOption(label=f"Field {i+1}: {field.name}",
                                 value=str(i),
                                 description=field.value[:100])
            for i, field in enumerate(self.embed.fields)
        ]
        view = discord.ui.View(timeout=None)
        select = discord.ui.Select(placeholder="Select a field to remove...",
                                   options=options)
        select.callback = self.remove_field_callback
        view.add_item(select)
        view.add_item(BackButton(self.embed))
        await interaction.response.edit_message(
            content=
            "✅ Field removed. Select another field to remove or use the Back button:",
            embed=self.embed,
            view=view)


class BackButton(Button):
    """Button to go back to the embed configuration preview."""

    def __init__(self, embed: discord.Embed) -> None:
        """Initialize the back button."""
        super().__init__(label="Back", style=discord.ButtonStyle.secondary)
        self.embed = embed

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event to return to the embed preview."""
        await interaction.response.edit_message(
            content="Embed Configuration Preview:",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client))


class SendButton(Button):
    """Button to send the configured embed to the current channel."""

    def __init__(self, embed: discord.Embed) -> None:
        """Initialize the send button with the configured embed."""
        super().__init__(label="Send",
                         style=discord.ButtonStyle.green,
                         emoji="🚀")
        self.embed = embed

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event to send the embed."""
        # Ensure at least one part of the embed is configured
        if not any([
                self.embed.title,
                self.embed.description.strip(), self.embed.fields,
                self.embed.author.name, self.embed.thumbnail.url,
                self.embed.image.url, self.embed.footer.text
        ]):
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description="Nothing has been configured yet.",
                color=discord.Color.red(),
            ),
                                                    ephemeral=True)
            return
        # Ensure the description is not empty
        if not self.embed.description.strip():
            self.embed.description = None
        # Send the configured embed to the channel
        await interaction.channel.send(embed=self.embed)
        # Reset the embed for a new configuration session
        self.embed = discord.Embed(description="Configure another embed. ⤵️")
        await interaction.response.edit_message(content="✅ Embed sent!",
                                                embed=self.embed,
                                                view=create_embed_view(
                                                    self.embed,
                                                    interaction.client))


class ResetButton(Button):
    """Button to reset the entire embed configuration."""

    def __init__(self, embed: discord.Embed) -> None:
        """Initialize the reset button with the configured embed."""
        super().__init__(label="Reset",
                         style=discord.ButtonStyle.red,
                         emoji="🔄")
        self.embed = embed

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event to reset the embed."""
        # Reset all parts of the embed
        self.embed.title = ""
        self.embed.description = "** **"
        self.embed.url = ""
        self.embed.color = discord.Color.default()
        self.embed.set_author(name="", url=None, icon_url=None)
        self.embed.set_image(url=None)
        self.embed.set_thumbnail(url=None)
        self.embed.set_footer(text="", icon_url=None)
        self.embed.timestamp = None
        self.embed.clear_fields()
        # Confirm the reset to the user
        await interaction.response.edit_message(content="✅ Embed reset.",
                                                embed=self.embed,
                                                view=create_embed_view(
                                                    self.embed,
                                                    interaction.client))


class HelpButton(Button):
    """Button to display help information about the embed creator wizard."""

    def __init__(self):
        """Initialize the help button."""
        super().__init__(label="Help",
                         style=discord.ButtonStyle.grey,
                         emoji="🔍",
                         row=3)

    async def callback(self, interaction: discord.Interaction):
        """Handle the button click event to display help information."""
        await interaction.response.send_message(embed=get_help_embed(1),
                                                view=HelpNavigationView(
                                                    interaction.client, 1, 10),
                                                ephemeral=True)


class HelpNavigationView(BaseView):
    """View for navigating between help pages."""

    def __init__(self,
                 bot: commands.Bot,
                 current_page: int = 1,
                 total_pages: int = 16):  # Updated total_pages
        super().__init__(bot=bot,
                         current_page=current_page,
                         total_pages=total_pages)
        self.add_navigation_buttons()


class PreviousButton(Button):
    """Button to navigate to the previous help page."""

    def __init__(self, current_page: int, total_pages: int) -> None:
        """Initialize the previous button with the current and total pages."""
        super().__init__(label="Previous",
                         style=discord.ButtonStyle.blurple,
                         disabled=current_page == 1)
        self.current_page = current_page
        self.total_pages = total_pages

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event to navigate to the previous page."""
        new_page = max(1, self.current_page - 1)
        await interaction.response.edit_message(
            embed=get_help_embed(new_page),
            view=HelpNavigationView(interaction.client, new_page,
                                    self.total_pages))


class NextButton(Button):
    """Button to navigate to the next help page."""

    def __init__(self, current_page: int, total_pages: int) -> None:
        """Initialize the next button with the current and total pages."""
        super().__init__(label="Next",
                         style=discord.ButtonStyle.blurple,
                         disabled=current_page == total_pages)
        self.current_page = current_page
        self.total_pages = total_pages

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event to navigate to the next page."""
        new_page = min(self.total_pages, self.current_page + 1)
        await interaction.response.edit_message(
            embed=get_help_embed(new_page),
            view=HelpNavigationView(interaction.client, new_page,
                                    self.total_pages))


class JumpToPageButton(Button):
    """Button to open a modal for jumping to a specific help page."""

    def __init__(self) -> None:
        """Initialize the jump to page button."""
        super().__init__(label="Jump to Page",
                         style=discord.ButtonStyle.grey,
                         emoji="🔍")

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event to open the jump to page modal."""
        await interaction.response.send_modal(JumpToPageModal())


class JumpToPageModal(Modal):
    """Modal to input the page number for jumping to a specific help page."""

    def __init__(self) -> None:
        """Initialize the modal with input for the page number."""
        super().__init__(title="Jump to Page")
        self.page_number = TextInput(
            label="Page Number",
            placeholder=
            "Enter a page number between 1 and 16",  # Updated placeholder
            required=True)
        self.add_item(self.page_number)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle the submission of the jump to page modal."""
        try:
            page = int(self.page_number.value)
            if 1 <= page <= 16:  # Updated range
                await interaction.response.edit_message(
                    embed=get_help_embed(page),
                    view=HelpNavigationView(interaction.client, page,
                                            16))  # Updated total_pages
            else:
                await interaction.response.send_message(
                    "Please enter a valid page number (1-16).",
                    ephemeral=True)  # Updated error message
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid page number (1-16).",
                ephemeral=True)  # Updated error message


class EditFieldButton(Button):
    """Button to open a dropdown for editing fields of the embed."""

    def __init__(self, embed: discord.Embed, bot: commands.Bot):
        super().__init__(label="Edit Fields",
                         style=discord.ButtonStyle.grey,
                         emoji="📝",
                         row=2)
        self.embed = embed
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        if not self.embed.fields:
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description="No fields have been added to the embed yet.",
                color=discord.Color.red()),
                                                    ephemeral=True)
            return

        options = []
        for i, field in enumerate(self.embed.fields):
            options.append(
                discord.SelectOption(
                    label=f"Field {i+1}: {field.name}",
                    value=f"field_{i}",
                    description=field.
                    value[:100]  # Truncate description if too long
                ))

        view = discord.ui.View(timeout=None)
        select = discord.ui.Select(placeholder="Select a field to edit...",
                                   options=options)
        select.callback = self.edit_field_callback
        view.add_item(select)
        view.add_item(BackButton(self.embed))

        await interaction.response.edit_message(
            content="Select a field to edit:", embed=self.embed, view=view)

    async def edit_field_callback(self, interaction: discord.Interaction):
        value = interaction.data["values"][0]
        field_index = int(value.split("_")[1])
        await interaction.response.send_modal(
            EditFieldModal(self.embed, field_index))


class EditFieldModal(Modal):
    """Modal for editing an existing field in the embed."""

    def __init__(self, embed: discord.Embed, field_index: int):
        super().__init__(title=f"Edit Field {field_index + 1}")
        self.embed = embed
        self.field_index = field_index
        field = self.embed.fields[field_index]

        self.field_name = TextInput(label="Field Name", default=field.name)
        self.field_value = TextInput(label="Field Value", default=field.value)
        self.inline = TextInput(label="Inline (True/False)",
                                default=str(field.inline),
                                required=False)

        self.add_item(self.field_name)
        self.add_item(self.field_value)
        self.add_item(self.inline)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.field_name.value
        value = self.field_value.value
        inline = self.inline.value.lower(
        ) == "true" if self.inline.value else False

        self.embed.set_field_at(self.field_index,
                                name=name,
                                value=value,
                                inline=inline)

        await interaction.response.edit_message(content="✅ Field updated.",
                                                embed=self.embed,
                                                view=create_embed_view(
                                                    self.embed,
                                                    interaction.client))


class SendToButton(Button):
    """Button to open a dropdown for selecting a channel to send the embed to."""

    def __init__(self, embed: discord.Embed) -> None:
        """Initialize the send to button with the configured embed."""
        super().__init__(label="Send To",
                         style=discord.ButtonStyle.green,
                         emoji="📤")
        self.embed = embed

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event to open the channel selection dropdown."""
        # Check if the embed is properly configured
        if not self.is_embed_valid():
            await interaction.response.send_message(embed=discord.Embed(
                title="Embed Not Configured",
                description=
                "Please configure the embed with some content before attempting to send it.",
                color=discord.Color.red()),
                                                    ephemeral=True)
            return

        # Get all text channels the user has permission to send messages in
        channels = [
            channel for channel in interaction.guild.text_channels
            if channel.permissions_for(interaction.user).send_messages
        ]

        if not channels:
            await interaction.response.send_message(
                "You don't have permission to send messages in any channel.",
                ephemeral=True)
            return

        options = [
            discord.SelectOption(label=channel.name, value=str(channel.id))
            for channel in channels
        ]

        view = discord.ui.View(timeout=None)
        select = discord.ui.Select(
            placeholder="Select a channel to send the embed to...",
            options=options)
        select.callback = self.send_to_channel_callback
        view.add_item(select)
        view.add_item(BackButton(self.embed))

        await interaction.response.edit_message(
            content="Select a channel to send the embed to:",
            embed=self.embed,
            view=view)

    def is_embed_valid(self) -> bool:
        """Check if the embed is properly configured and not empty."""
        if self.embed is None:
            return False
        return any([
            self.embed.title, self.embed.description, self.embed.fields,
            self.embed.author, self.embed.footer, self.embed.image,
            self.embed.thumbnail
        ])

    async def send_to_channel_callback(
            self, interaction: discord.Interaction) -> None:
        """Handle the selection of a channel and send the embed to it."""
        channel_id = int(interaction.data["values"][0])
        channel = interaction.guild.get_channel(channel_id)

        if channel is None:
            await interaction.response.send_message(
                "The selected channel no longer exists.", ephemeral=True)
            return

        # Check if the embed is properly configured
        if not self.is_embed_valid():
            await interaction.response.send_message(
                "The embed is not properly configured. Please add some content before sending.",
                ephemeral=True)
            return

        try:
            await channel.send(embed=self.embed)
            await interaction.response.edit_message(
                content=f"✅ Embed sent to #{channel.name}!",
                embed=self.embed,
                view=create_embed_view(self.embed, interaction.client))
        except discord.errors.Forbidden:
            await interaction.response.send_message(
                f"I don't have permission to send messages in #{channel.name}.",
                ephemeral=True)


class FieldsButton(Button):
    """Button to display the 'Fields: ' label."""

    def __init__(self):
        super().__init__(label="Fields: ",
                         style=discord.ButtonStyle.grey,
                         disabled=True,
                         row=2)

    async def callback(self, interaction: discord.Interaction):
        # This button does nothing, so we don't need to implement any callback logic
        pass


class FieldCountButton(Button):
    """Button to display the number of configured fields."""

    def __init__(self, embed: discord.Embed):
        field_count = len(
            embed.fields) if embed and hasattr(embed, 'fields') else 0
        super().__init__(label=f"{field_count}/25 fields",
                         style=discord.ButtonStyle.grey,
                         disabled=True,
                         row=3)
        self.embed = embed

    async def callback(self, interaction: discord.Interaction):

        pass


class ScheduleModal(Modal):

    def __init__(self, embed: discord.Embed, bot: commands.Bot):
        super().__init__(title="Schedule Embed")
        self.embed = embed
        self.bot = bot

        self.schedule_time = TextInput(
            label="Schedule Time",
            placeholder="e.g., 1m, 1h, 1d, 1w, or YYYY-MM-DD HH:MM",
            required=True)
        self.channel = TextInput(
            label="Channel ID",
            placeholder="Enter the channel ID to send the embed",
            required=True)
        self.add_item(self.schedule_time)
        self.add_item(self.channel)

    async def on_submit(self, interaction: discord.Interaction):
        schedule_time = self.schedule_time.value
        channel_id = self.channel.value

        try:
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                raise ValueError("Invalid channel ID")
        except ValueError:
            await interaction.response.send_message(
                "Invalid channel ID. Please try again.", ephemeral=True)
            return

        send_time = self.parse_schedule_time(schedule_time)
        if not send_time:
            await interaction.response.send_message(
                "Invalid schedule time format. Please try again.",
                ephemeral=True)
            return

        await interaction.response.send_message(
            f"Embed scheduled to be sent in {channel.mention} at {send_time.strftime('%Y-%m-%d %H:%M:%S')}",
            ephemeral=True)

        # Schedule the embed to be sent
        await self.schedule_embed(send_time, channel)

    def parse_schedule_time(self, schedule_time: str) -> datetime:
        now = datetime.utcnow()

        # Check for relative time format (e.g., 1m, 1h, 1d, 1w)
        match = re.match(r'^(\d+)([mhdw])$', schedule_time.lower())
        if match:
            amount, unit = match.groups()
            amount = int(amount)
            if unit == 'm':
                return now + timedelta(minutes=amount)
            elif unit == 'h':
                return now + timedelta(hours=amount)
            elif unit == 'd':
                return now + timedelta(days=amount)
            elif unit == 'w':
                return now + timedelta(weeks=amount)

        # Check for absolute time format (YYYY-MM-DD HH:MM)
        try:
            return datetime.strptime(schedule_time, "%Y-%m-%d %H:%M")
        except ValueError:
            return None

    async def schedule_embed(self, send_time: datetime,
                             channel: discord.TextChannel):
        await asyncio.sleep((send_time - datetime.utcnow()).total_seconds())
        await channel.send(embed=self.embed)


def create_embed_view(embed: discord.Embed, bot: commands.Bot) -> View:
    view = BaseView(bot, embed)
    select_options = [
        discord.SelectOption(label="Author", value="author", emoji="📝"),
        discord.SelectOption(label="Body", value="body", emoji="📄"),
        discord.SelectOption(label="Images", value="images", emoji="🖼️"),
        discord.SelectOption(label="Footer", value="footer", emoji="🔻"),
        discord.SelectOption(label="Schedule Embed",
                             value="schedule",
                             emoji="🕒"),  # Added this line
    ]
    select = Select(placeholder="Choose a part of the embed to configure...",
                    options=select_options)
    select.callback = bot.get_cog("EmbedCreator").dropdown_callback
    view.add_item(select)
    view.add_item(FieldCountButton(embed))
    view.add_embed_buttons()
    return view


async def setup(bot: commands.Bot) -> None:
    """Setup the EmbedCreator cog."""
    await bot.add_cog(EmbedCreator(bot))

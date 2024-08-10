import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Modal, TextInput, Button
import aiohttp
from urllib.parse import urlparse
import webcolors
import random
from data.custom_colors import custom_colors  # Import custom colors from custom_colors.py


class EmbedCreator(commands.Cog):
    """A cog for creating and managing custom embeds."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

    async def close(self) -> None:
        """Close the aiohttp session."""
        await self.session.close()

    @commands.Cog.listener()
    async def on_shutdown(self):
        await self.close()

    @commands.Cog.listener()
    async def on_disconnect(self):
        await self.close()

    @app_commands.command(name="embed",
                          description="Create a custom embed message")
    async def embed(self, interaction: discord.Interaction) -> None:
        """Command to start the embed creation process."""
        self.embed_object = discord.Embed(
            description=" ")  # Ensure description is not empty
        options = [
            discord.SelectOption(label="Author", value="author", emoji="📝"),
            discord.SelectOption(label="Body", value="body", emoji="📄"),
            discord.SelectOption(label="Images", value="images", emoji="🖼️"),
            discord.SelectOption(label="Footer", value="footer", emoji="🔻"),
            discord.SelectOption(label="Fields", value="fields", emoji="🔠"),
        ]
        select = Select(
            placeholder="Choose a part of the embed to configure...",
            options=options)
        select.callback = self.dropdown_callback

        view = View()
        view.add_item(select)
        view.add_item(SendButton(self.embed_object))
        view.add_item(AddFieldsButton(self.embed_object))
        view.add_item(ResetButton(self.embed_object))
        view.add_item(SelectiveResetButton(self.embed_object))
        view.add_item(HelpButton())  # Add Help button

        await interaction.response.send_message("Configure your embed:",
                                                view=view,
                                                ephemeral=True)

    async def dropdown_callback(self,
                                interaction: discord.Interaction) -> None:
        """Callback for the dropdown to open the respective modal for configuration."""
        data = interaction.data
        value = data["values"][0] if isinstance(
            data, dict) and "values" in data else None
        if value == "author":
            await interaction.response.send_modal(
                AuthorModal(self.embed_object))
        elif value == "body":
            await interaction.response.send_modal(BodyModal(self.embed_object))
        elif value == "images":
            await interaction.response.send_modal(
                ImagesModal(self.embed_object))
        elif value == "footer":
            await interaction.response.send_modal(
                FooterModal(self.embed_object))
        elif value == "fields":
            await interaction.response.send_modal(
                FieldsModal(self.embed_object))


def is_valid_url(url: str) -> bool:
    """Check if a URL is valid."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def is_valid_hex_color(color: str) -> bool:
    """Check if a string is a valid hex color code."""
    if color.startswith("#"):
        color = color[1:]
    return len(color) == 6 and all(c in "0123456789ABCDEFabcdef"
                                   for c in color)


def get_color_from_name(name: str) -> discord.Color:
    """Return a discord.Color object based on a color name."""
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
    """Modal to configure the author part of the embed."""

    def __init__(self, embed: discord.Embed) -> None:
        super().__init__(title="Configure Author")
        self.embed = embed
        self.author = TextInput(label="Author")
        self.author_url = TextInput(label="Author URL", required=False)
        self.author_icon_url = TextInput(label="Author Icon URL",
                                         required=False)
        self.add_item(self.author)
        self.add_item(self.author_url)
        self.add_item(self.author_icon_url)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle the submission of the modal."""
        if self.author_url.value and not is_valid_url(self.author_url.value):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error",
                    description=
                    f"Invalid URL in Author URL: {self.author_url.value}",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        if self.author_icon_url.value and not is_valid_url(
                self.author_icon_url.value):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error",
                    description=
                    f"Invalid URL in Author Icon URL: {self.author_icon_url.value}",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        self.embed.set_author(
            name=self.author.value,
            url=self.author_url.value or None,
            icon_url=self.author_icon_url.value or None,
        )
        await interaction.response.edit_message(
            content="✅ Author configured.",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client),
        )


class BodyModal(Modal):
    """Modal to configure the body part of the embed."""

    def __init__(self, embed: discord.Embed) -> None:
        super().__init__(title="Configure Body")
        self.embed = embed
        self.titl = TextInput(label="Title", max_length=256)
        self.description = TextInput(label="Description", max_length=4000)
        self.url = TextInput(label="URL", required=False)
        self.colour = TextInput(label="Colour (hex code, name, or 'random')",
                                required=False)
        self.add_item(self.titl)
        self.add_item(self.description)
        self.add_item(self.url)
        self.add_item(self.colour)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle the submission of the modal."""
        if self.url.value and not is_valid_url(self.url.value):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error",
                    description=f"Invalid URL in Body URL: {self.url.value}",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        if self.colour.value:
            if self.colour.value.lower() == "random":
                self.embed.color = discord.Color.random()
            elif is_valid_hex_color(self.colour.value):
                self.embed.color = discord.Color(
                    int(self.colour.value.strip("#"), 16))
            else:
                color = get_color_from_name(self.colour.value)
                if color:
                    self.embed.color = color
                else:
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            title="Error",
                            description=
                            f"Invalid colour value: {self.colour.value}",
                            color=discord.Color.red(),
                        ),
                        ephemeral=True,
                    )
                    return

        self.embed.title = self.titl.value
        self.embed.description = self.description.value or None
        self.embed.url = self.url.value or None

        await interaction.response.edit_message(
            content="✅ Body configured.",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client),
        )


class ImagesModal(Modal):
    """Modal to configure the images part of the embed."""

    def __init__(self, embed: discord.Embed) -> None:
        super().__init__(title="Configure Images")
        self.embed = embed
        self.image_url = TextInput(label="Image URL")
        self.thumbnail_url = TextInput(label="Thumbnail URL")
        self.add_item(self.image_url)
        self.add_item(self.thumbnail_url)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle the submission of the modal."""
        if self.image_url.value and not is_valid_url(self.image_url.value):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error",
                    description=
                    f"Invalid URL in Image URL: {self.image_url.value}",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        if self.thumbnail_url.value and not is_valid_url(
                self.thumbnail_url.value):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error",
                    description=
                    f"Invalid URL in Thumbnail URL: {self.thumbnail_url.value}",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        self.embed.set_image(url=self.image_url.value)
        self.embed.set_thumbnail(url=self.thumbnail_url.value)
        await interaction.response.edit_message(
            content="✅ Images configured.",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client),
        )


class FooterModal(Modal):
    """Modal to configure the footer part of the embed."""

    def __init__(self, embed: discord.Embed) -> None:
        super().__init__(title="Configure Footer")
        self.embed = embed
        self.footer = TextInput(label="Footer", max_length=2048)
        self.timestamp = TextInput(
            label="Timestamp (YYYY-MM-DD hh:mm or 'auto')", required=False)
        self.footer_icon_url = TextInput(label="Footer Icon URL",
                                         required=False)
        self.add_item(self.footer)
        self.add_item(self.timestamp)
        self.add_item(self.footer_icon_url)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle the submission of the modal."""
        if self.footer_icon_url.value and not is_valid_url(
                self.footer_icon_url.value):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error",
                    description=
                    f"Invalid URL in Footer Icon URL: {self.footer_icon_url.value}",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        self.embed.set_footer(
            text=self.footer.value,
            icon_url=self.footer_icon_url.value or None,
        )
        if self.timestamp.value.lower() == "auto":
            self.embed.timestamp = discord.utils.utcnow()
        elif self.timestamp.value:
            self.embed.timestamp = discord.utils.parse_time(
                self.timestamp.value)
        await interaction.response.edit_message(
            content="✅ Footer configured.",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client),
        )


class FieldsModal(Modal):
    """Modal to configure the fields part of the embed."""

    def __init__(self, embed: discord.Embed) -> None:
        super().__init__(title="Configure Fields")
        self.embed = embed
        self.field_1 = TextInput(
            label="<Field Name>, <Field Value>, <true/false>", required=False)
        self.field_2 = TextInput(
            label="<Field Name>, <Field Value>, <true/false>", required=False)
        self.field_3 = TextInput(
            label="<Field Name>, <Field Value>, <true/false>", required=False)
        self.field_4 = TextInput(
            label="<Field Name>, <Field Value>, <true/false>", required=False)
        self.field_5 = TextInput(
            label="<Field Name>, <Field Value>, <true/false>", required=False)
        self.add_item(self.field_1)
        self.add_item(self.field_2)
        self.add_item(self.field_3)
        self.add_item(self.field_4)
        self.add_item(self.field_5)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle the submission of the modal."""
        fields = [
            self.field_1.value,
            self.field_2.value,
            self.field_3.value,
            self.field_4.value,
            self.field_5.value,
        ]
        for field in fields:
            if field:
                parts = field.split(",", 2)
                name = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""
                inline = parts[2].strip().lower() == "true" if len(
                    parts) > 2 else False
                self.embed.add_field(name=name, value=value, inline=inline)
        await interaction.response.edit_message(
            content="✅ Fields configured.",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client),
        )


class AddFieldsModal(Modal):
    """Modal to add more fields to the embed."""

    def __init__(self, embed: discord.Embed) -> None:
        super().__init__(title="Add More Fields")
        self.embed = embed
        self.field_1 = TextInput(
            label="<Field Name>, <Field Value>, <true/false>", required=False)
        self.field_2 = TextInput(
            label="<Field Name>, <Field Value>, <true/false>", required=False)
        self.field_3 = TextInput(
            label="<Field Name>, <Field Value>, <true/false>", required=False)
        self.field_4 = TextInput(
            label="<Field Name>, <Field Value>, <true/false>", required=False)
        self.field_5 = TextInput(
            label="<Field Name>, <Field Value>, <true/false>", required=False)
        self.add_item(self.field_1)
        self.add_item(self.field_2)
        self.add_item(self.field_3)
        self.add_item(self.field_4)
        self.add_item(self.field_5)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle the submission of the modal."""
        fields = [
            self.field_1.value,
            self.field_2.value,
            self.field_3.value,
            self.field_4.value,
            self.field_5.value,
        ]
        for field in fields:
            if field:
                parts = field.split(",", 2)
                name = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""
                inline = parts[2].strip().lower() == "true" if len(
                    parts) > 2 else False
                self.embed.add_field(name=name, value=value, inline=inline)
        await interaction.response.edit_message(
            content="✅ Additional fields configured.",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client),
        )


class SendButton(Button):
    """Button to send the configured embed."""

    def __init__(self, embed: discord.Embed) -> None:
        super().__init__(label="Send",
                         style=discord.ButtonStyle.green,
                         emoji="🚀")
        self.embed = embed

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event."""
        # Check if any component is configured
        if not any([
                self.embed.title,
                self.embed.description.strip(), self.embed.fields,
                self.embed.author.name, self.embed.thumbnail.url,
                self.embed.image.url, self.embed.footer.text
        ]):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error",
                    description="Nothing has been configured yet.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        # Ensure description is not empty
        if not self.embed.description.strip():
            self.embed.description = None

        await interaction.channel.send(embed=self.embed)
        self.embed = discord.Embed(description="Configure another embed. ⤵️"
                                   )  # Reset embed with non-empty description
        await interaction.response.edit_message(
            content="✅ Embed sent!",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client),
        )


class AddFieldsButton(Button):
    """Button to add more fields to the embed."""

    def __init__(self, embed: discord.Embed) -> None:
        super().__init__(label="Add More Fields",
                         style=discord.ButtonStyle.blurple,
                         emoji="➕")
        self.embed = embed

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event."""
        await interaction.response.send_modal(AddFieldsModal(self.embed))


class ResetButton(Button):
    """Button to reset the entire embed."""

    def __init__(self, embed: discord.Embed) -> None:
        super().__init__(label="Reset Embed",
                         style=discord.ButtonStyle.red,
                         emoji="🔄")
        self.embed = embed

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event."""
        self.embed.title = "** **"
        self.embed.description = "** **"  # Ensure description is not empty
        self.embed.url = ""
        self.embed.color = discord.Color.default()
        self.embed.set_author(name="", url=None, icon_url=None)
        self.embed.set_image(url=None)
        self.embed.set_thumbnail(url=None)
        self.embed.set_footer(text="", icon_url=None)
        self.embed.timestamp = None
        self.embed.clear_fields()

        await interaction.response.edit_message(
            content="✅ Embed reset.",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client),
        )


class SelectiveResetModal(Modal):
    """Modal to selectively reset parts of the embed."""

    def __init__(self, embed: discord.Embed) -> None:
        super().__init__(title="Selective Reset")
        self.embed = embed
        self.author = TextInput(label="Author (y/n)",
                                placeholder="y, n, n (name, url, icon)",
                                required=False)
        self.body = TextInput(
            label="Body (y/n)",
            placeholder="y, y, n, n (title, description, url, color)",
            required=False)
        self.images = TextInput(label="Images (y/n)",
                                placeholder="y, y (image, thumbnail)",
                                required=False)
        self.footer = TextInput(label="Footer (y/n)",
                                placeholder="y, y, y (text, timestamp, icon)",
                                required=False)
        self.fields = TextInput(label="Fields (y/n)",
                                placeholder="y (all fields)",
                                required=False)
        self.add_item(self.author)
        self.add_item(self.body)
        self.add_item(self.images)
        self.add_item(self.footer)
        self.add_item(self.fields)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle the submission of the modal."""
        if self.author.value:
            values = [
                val.strip().lower() == "y"
                for val in self.author.value.split(",")
            ]
            if values[0]: self.embed.set_author(name=None)
            if len(values) > 1 and values[1]: self.embed.set_author(url=None)
            if len(values) > 2 and values[2]:
                self.embed.set_author(icon_url=None)
        if self.body.value:
            values = [
                val.strip().lower() == "y"
                for val in self.body.value.split(",")
            ]
            if values[0]: self.embed.title = ""
            if len(values) > 1 and values[1]: self.embed.description = " "
            if len(values) > 2 and values[2]: self.embed.url = ""
            if len(values) > 3 and values[3]:
                self.embed.color = discord.Color.default()
        if self.images.value:
            values = [
                val.strip().lower() == "y"
                for val in self.images.value.split(",")
            ]
            if values[0]: self.embed.set_image(url=None)
            if len(values) > 1 and values[1]:
                self.embed.set_thumbnail(url=None)
        if self.footer.value:
            values = [
                val.strip().lower() == "y"
                for val in self.footer.value.split(",")
            ]
            if values[0]: self.embed.set_footer(text=None)
            if len(values) > 1 and values[1]: self.embed.timestamp = None
            if len(values) > 2 and values[2]:
                self.embed.set_footer(icon_url=None)
        if self.fields.value and self.fields.value.strip().lower() == "y":
            self.embed.clear_fields()
        await interaction.response.edit_message(
            content="✅ Selected components reset.",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client),
        )


class SelectiveResetButton(Button):
    """Button to open the selective reset modal."""

    def __init__(self, embed: discord.Embed) -> None:
        super().__init__(label="Selective Reset",
                         style=discord.ButtonStyle.red,
                         emoji="🔄")
        self.embed = embed

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event."""
        await interaction.response.send_modal(SelectiveResetModal(self.embed))


class HelpButton(Button):
    """Button to show help information about the embed creator wizard."""

    def __init__(self) -> None:
        super().__init__(label="Help",
                         style=discord.ButtonStyle.grey,
                         emoji="🔍")

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event to send help information."""
        await interaction.response.send_message(embed=get_help_embed(1),
                                                view=HelpNavigationView(),
                                                ephemeral=True)


def get_help_embed(page: int) -> discord.Embed:
    """Return the help embed for the specified page."""
    total_pages = 10  # Updated total pages count
    help_pages = [{
        "title":
        "Embed Creator Wizard Help - Overview",
        "description":
        ("This wizard helps you create a custom embed message. Use the dropdown to configure different parts of the embed.\n\n"
         "```yaml\n"
         "Pages:\n"
         "1. Overview (this page)\n"
         "2. Author\n"
         "3. Body\n"
         "4. Images\n"
         "5. Footer\n"
         "6. Fields\n"
         "7. Send Button\n"
         "8. Add More Fields Button\n"
         "9. Reset Embed Button\n"
         "10. Selective Reset Button\n"
         "```")
    }, {
        "title":
        "Embed Creator Wizard Help - Author",
        "description":
        ("Configure the author part of the embed:\n"
         "```yaml\n"
         "- Author Name: The name of the author.\n"
         "- Author URL: A URL to link the author's name.\n"
         "- Author Icon URL: A URL to an image to display as the author's icon.\n"
         "```")
    }, {
        "title":
        "Embed Creator Wizard Help - Body",
        "description":
        ("Configure the body part of the embed:\n"
         "```yaml\n"
         "- Title: The title of the embed.\n"
         "- Description: The main content of the embed.\n"
         "- URL: A URL to link the title.\n"
         "- Color: The color of the embed (hex code, color name, or 'random').\n"
         "```")
    }, {
        "title":
        "Embed Creator Wizard Help - Images",
        "description":
        ("Configure the images part of the embed:\n"
         "```yaml\n"
         "- Image URL: A URL to an image to display in the embed.\n"
         "- Thumbnail URL: A URL to a thumbnail image to display in the embed.\n"
         "```")
    }, {
        "title":
        "Embed Creator Wizard Help - Footer",
        "description":
        ("Configure the footer part of the embed:\n"
         "```yaml\n"
         "- Footer Text: The text to display in the footer.\n"
         "- Footer Icon URL: A URL to an image to display as the footer icon.\n"
         "- Timestamp: The timestamp to display in the footer (YYYY-MM-DD hh:mm or 'auto').\n"
         "```")
    }, {
        "title":
        "Embed Creator Wizard Help - Fields",
        "description":
        ("Configure the fields part of the embed:\n"
         "```yaml\n"
         "- Field Name: The name of the field.\n"
         "- Field Value: The value of the field.\n"
         "- Inline: Whether the field should be displayed inline (true/false).\n"
         "```")
    }, {
        "title":
        "Embed Creator Wizard Help - Send Button",
        "description":
        ("**Send Button**:\n\n"
         "This button allows you to send the configured embed to the current channel. It checks if the embed is properly configured and, if valid, sends it as a message.\n\n"
         "Ensure that you have at least one part of the embed configured before attempting to send it."
         )
    }, {
        "title":
        "Embed Creator Wizard Help - Add More Fields Button",
        "description":
        ("**Add More Fields Button**:\n\n"
         "Use this button to add additional fields to your embed. Each field consists of a name, value, and an inline option.\n\n"
         "This is useful for adding more detailed information to your embed in an organized way."
         )
    }, {
        "title":
        "Embed Creator Wizard Help - Reset Embed Button",
        "description":
        ("**Reset Embed Button**:\n\n"
         "This button resets the entire embed, clearing all the configurations you've made. It essentially gives you a fresh start to create a new embed.\n\n"
         "Be cautious when using this, as all your settings will be lost.")
    }, {
        "title":
        "Embed Creator Wizard Help - Selective Reset Button",
        "description":
        ("**Selective Reset Button**:\n\n"
         "This button allows you to selectively reset parts of the embed (e.g., author, body, images, footer, fields). A modal will appear where you can choose which parts to reset.\n\n"
         "This is useful if you want to clear specific sections without losing all your progress."
         )
    }]

    embed = discord.Embed(title=help_pages[page - 1]["title"],
                          description=help_pages[page - 1]["description"],
                          color=discord.Color.from_rgb(
                              *random.choice(list(custom_colors.values()))))

    embed.set_footer(text=f"Page {page}/{total_pages}")
    return embed


class HelpNavigationView(View):
    """View for navigating the help pages."""

    def __init__(self, current_page: int = 1) -> None:
        super().__init__()
        self.current_page = current_page
        total_pages = 6
        self.add_item(PreviousButton(self.current_page, total_pages))
        self.add_item(NextButton(self.current_page, total_pages))
        self.add_item(JumpToPageButton())


class PreviousButton(Button):
    """Button to navigate to the previous help page."""

    def __init__(self, current_page: int, total_pages: int) -> None:
        super().__init__(label="Previous",
                         style=discord.ButtonStyle.blurple,
                         disabled=current_page == 1)
        self.current_page = current_page
        self.total_pages = total_pages

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event."""
        new_page = max(1, self.current_page - 1)
        await interaction.response.edit_message(
            embed=get_help_embed(new_page), view=HelpNavigationView(new_page))


class NextButton(Button):
    """Button to navigate to the next help page."""

    def __init__(self, current_page: int, total_pages: int) -> None:
        super().__init__(label="Next",
                         style=discord.ButtonStyle.blurple,
                         disabled=current_page == total_pages)
        self.current_page = current_page
        self.total_pages = total_pages

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event."""
        new_page = min(self.total_pages, self.current_page + 1)
        await interaction.response.edit_message(
            embed=get_help_embed(new_page), view=HelpNavigationView(new_page))


class JumpToPageButton(Button):
    """Button to open a modal for jumping to a specific help page."""

    def __init__(self) -> None:
        super().__init__(label="Jump to Page",
                         style=discord.ButtonStyle.grey,
                         emoji="🔍")

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event to open the jump to page modal."""
        await interaction.response.send_modal(JumpToPageModal())


class JumpToPageModal(Modal):
    """Modal to input the page number to jump to."""

    def __init__(self) -> None:
        super().__init__(title="Jump to Page")
        self.page_number = TextInput(
            label="Page Number",
            placeholder="Enter a page number between 1 and 6",
            required=True)
        self.add_item(self.page_number)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle the submission of the modal."""
        try:
            page = int(self.page_number.value)
            if 1 <= page <= 6:
                await interaction.response.edit_message(
                    embed=get_help_embed(page), view=HelpNavigationView(page))
            else:
                await interaction.response.send_message(
                    "Please enter a valid page number (1-6).", ephemeral=True)
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid page number (1-6).", ephemeral=True)


def create_embed_view(embed: discord.Embed, bot: commands.Bot) -> View:
    """Create the view for the embed configuration interface."""
    view = View()
    select_options = [
        discord.SelectOption(label="Author", value="author", emoji="📝"),
        discord.SelectOption(label="Body", value="body", emoji="📄"),
        discord.SelectOption(label="Images", value="images", emoji="🖼️"),
        discord.SelectOption(label="Footer", value="footer", emoji="🔻"),
        discord.SelectOption(label="Fields", value="fields", emoji="🔠"),
    ]
    select = Select(placeholder="Choose a part of the embed to configure...",
                    options=select_options)
    select.callback = bot.get_cog("EmbedCreator").dropdown_callback
    view.add_item(select)
    view.add_item(SendButton(embed))
    view.add_item(AddFieldsButton(embed))
    view.add_item(ResetButton(embed))
    view.add_item(SelectiveResetButton(embed))
    view.add_item(HelpButton())  # Add the Help button here
    return view


async def setup(bot: commands.Bot) -> None:
    """Set up the cog."""
    await bot.add_cog(EmbedCreator(bot))

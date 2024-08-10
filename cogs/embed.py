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
    """A Discord cog for creating and managing custom embeds interactively."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the EmbedCreator cog with the bot and aiohttp session."""
        self.bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

    async def close(self) -> None:
        """Close the aiohttp session when the bot shuts down or disconnects."""
        await self.session.close()

    @commands.Cog.listener()
    async def on_shutdown(self) -> None:
        """Listener to close the aiohttp session during bot shutdown."""
        await self.close()

    @commands.Cog.listener()
    async def on_disconnect(self) -> None:
        """Listener to close the aiohttp session when the bot disconnects."""
        await self.close()

    @app_commands.command(
        name="embed",
        description="Create a custom embed message interactively.")
    async def embed(self, interaction: discord.Interaction) -> None:
        """Slash command to initiate the embed creation process."""
        self.embed_object = discord.Embed(
            description=" ",
            color=discord.Color.from_rgb(*random.choice(
                list(custom_colors.values()))
                                         )  # Apply the randomly selected color
        )  # Initialize an empty embed with a non-empty description

        # Define the dropdown options for different parts of the embed
        options = [
            discord.SelectOption(label="Author", value="author", emoji="📝"),
            discord.SelectOption(label="Body", value="body", emoji="📄"),
            discord.SelectOption(label="Images", value="images", emoji="🖼️"),
            discord.SelectOption(label="Footer", value="footer", emoji="🔻"),
            discord.SelectOption(label="Fields", value="fields", emoji="🔠"),
        ]

        # Create the dropdown select menu and assign the callback method
        select = Select(
            placeholder="Choose a part of the embed to configure...",
            options=options)
        select.callback = self.dropdown_callback

        # Create the view and add all the buttons and select menu
        view = View(timeout=None)
        view.add_item(select)
        view.add_item(SendButton(self.embed_object))
        view.add_item(AddFieldsButton(self.embed_object))
        view.add_item(ResetButton(self.embed_object))
        view.add_item(SelectiveResetButton(self.embed_object))
        view.add_item(HelpButton())  # Add Help button

        # Create the preview embed
        preview_embed = discord.Embed(
            title="🛠️ Embed Configuration Preview.",
            description="```yaml\n"
            "Please select an option from the dropdown below to begin configuring your embed.\n\n"
            "Current Options:\n"
            "- Author: Set the author of the embed.\n"
            "- Body: Edit the main content of the embed.\n"
            "- Images: Add an image or thumbnail.\n"
            "- Footer: Configure the footer of the embed.\n"
            "- Fields: Add custom fields to the embed.\n\n"
            "Once you're satisfied, use the buttons below to send or reset the embed.\n"
            "```",
            color=discord.Color.from_rgb(
                *random.choice(list(custom_colors.values())
                               )),  # Use the same randomly selected color
            timestamp=discord.utils.utcnow()  # Add the current timestamp
        )

        # Add the command user's avatar and name in the footer
        preview_embed.set_footer(
            text=f"Command initiated by {interaction.user.name}",
            icon_url=interaction.user.avatar.url)

        # Send the initial message with the view to start the embed configuration
        await interaction.response.send_message(embed=preview_embed,
                                                view=view,
                                                ephemeral=True)

    async def dropdown_callback(self,
                                interaction: discord.Interaction) -> None:
        """Callback method for handling dropdown selections."""
        data = interaction.data
        value = data["values"][0] if isinstance(
            data, dict) and "values" in data else None

        # Trigger the appropriate modal based on the selected dropdown option
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
    """Validate if a given string is a properly formatted URL."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def is_valid_hex_color(color: str) -> bool:
    """Check if a given string is a valid hex color code."""
    if color.startswith("#"):
        color = color[1:]
    return len(color) == 6 and all(c in "0123456789ABCDEFabcdef"
                                   for c in color)


def get_color_from_name(name: str) -> discord.Color:
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
    """Modal for configuring the author section of an embed."""

    def __init__(self, embed: discord.Embed) -> None:
        """Initialize the modal with input fields for the author section."""
        super().__init__(title="Configure Author")
        self.embed = embed

        # Text inputs for author name, URL, and icon URL
        self.author = TextInput(label="Author Name")
        self.author_url = TextInput(label="Author URL", required=False)
        self.author_icon_url = TextInput(label="Author Icon URL",
                                         required=False)

        self.add_item(self.author)
        self.add_item(self.author_url)
        self.add_item(self.author_icon_url)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle the submission of the author modal."""
        # Validate URLs if provided
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

        # Set the author details in the embed
        self.embed.set_author(
            name=self.author.value,
            url=self.author_url.value or None,
            icon_url=self.author_icon_url.value or None,
        )

        # Confirm the author configuration to the user
        await interaction.response.edit_message(
            content="✅ Author configured.",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client),
        )


class BodyModal(Modal):
    """Modal for configuring the body section (title, description, etc.) of an embed."""

    def __init__(self, embed: discord.Embed) -> None:
        """Initialize the modal with input fields for the body section."""
        super().__init__(title="Configure Body")
        self.embed = embed

        # Text inputs for title, description, URL, and color
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
        """Handle the submission of the body modal."""
        # Validate the URL if provided
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

        # Process the color input and set the embed color
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
                            f"Invalid color value: {self.colour.value}",
                            color=discord.Color.red(),
                        ),
                        ephemeral=True,
                    )
                    return

        # Set the title, description, and URL in the embed
        self.embed.title = self.titl.value
        self.embed.description = self.description.value or None
        self.embed.url = self.url.value or None

        # Confirm the body configuration to the user
        await interaction.response.edit_message(
            content="✅ Body configured.",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client),
        )


class ImagesModal(Modal):
    """Modal for configuring the image and thumbnail sections of an embed."""

    def __init__(self, embed: discord.Embed) -> None:
        """Initialize the modal with input fields for the images section."""
        super().__init__(title="Configure Images")
        self.embed = embed

        # Text inputs for image URL and thumbnail URL
        self.image_url = TextInput(label="Image URL")
        self.thumbnail_url = TextInput(label="Thumbnail URL")

        self.add_item(self.image_url)
        self.add_item(self.thumbnail_url)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle the submission of the images modal."""
        # Validate the image URL
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

        # Validate the thumbnail URL
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

        # Set the image and thumbnail in the embed
        self.embed.set_image(url=self.image_url.value)
        self.embed.set_thumbnail(url=self.thumbnail_url.value)

        # Confirm the images configuration to the user
        await interaction.response.edit_message(
            content="✅ Images configured.",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client),
        )


class FooterModal(Modal):
    """Modal for configuring the footer section of an embed."""

    def __init__(self, embed: discord.Embed) -> None:
        """Initialize the modal with input fields for the footer section."""
        super().__init__(title="Configure Footer")
        self.embed = embed

        # Text inputs for footer text, timestamp, and footer icon URL
        self.footer = TextInput(label="Footer Text", max_length=2048)
        self.timestamp = TextInput(
            label="Timestamp (YYYY-MM-DD hh:mm or 'auto')", required=False)
        self.footer_icon_url = TextInput(label="Footer Icon URL",
                                         required=False)

        self.add_item(self.footer)
        self.add_item(self.timestamp)
        self.add_item(self.footer_icon_url)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle the submission of the footer modal."""
        # Validate the footer icon URL
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

        # Set the footer details in the embed
        self.embed.set_footer(
            text=self.footer.value,
            icon_url=self.footer_icon_url.value or None,
        )

        # Handle the timestamp
        if self.timestamp.value.lower() == "auto":
            self.embed.timestamp = discord.utils.utcnow()
        elif self.timestamp.value:
            self.embed.timestamp = discord.utils.parse_time(
                self.timestamp.value)

        # Confirm the footer configuration to the user
        await interaction.response.edit_message(
            content="✅ Footer configured.",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client),
        )


class FieldsModal(Modal):
    """Modal for configuring the fields section of an embed."""

    def __init__(self, embed: discord.Embed) -> None:
        """Initialize the modal with input fields for adding fields."""
        super().__init__(title="Configure Fields")
        self.embed = embed

        # Text inputs for up to 5 fields
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
        """Handle the submission of the fields modal."""
        fields = [
            self.field_1.value,
            self.field_2.value,
            self.field_3.value,
            self.field_4.value,
            self.field_5.value,
        ]

        # Parse and add each field to the embed
        for field in fields:
            if field:
                parts = field.split(",", 2)
                name = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""
                inline = parts[2].strip().lower() == "true" if len(
                    parts) > 2 else False
                self.embed.add_field(name=name, value=value, inline=inline)

        # Confirm the fields configuration to the user
        await interaction.response.edit_message(
            content="✅ Fields configured.",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client),
        )


class AddFieldsModal(Modal):
    """Modal for adding more fields to an embed."""

    def __init__(self, embed: discord.Embed) -> None:
        """Initialize the modal with input fields for adding more fields."""
        super().__init__(title="Add More Fields")
        self.embed = embed

        # Text inputs for up to 5 additional fields
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
        """Handle the submission of the add more fields modal."""
        fields = [
            self.field_1.value,
            self.field_2.value,
            self.field_3.value,
            self.field_4.value,
            self.field_5.value,
        ]

        # Parse and add each additional field to the embed
        for field in fields:
            if field:
                parts = field.split(",", 2)
                name = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""
                inline = parts[2].strip().lower() == "true" if len(
                    parts) > 2 else False
                self.embed.add_field(name=name, value=value, inline=inline)

        # Confirm the additional fields configuration to the user
        await interaction.response.edit_message(
            content="✅ Additional fields configured.",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client),
        )


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
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error",
                    description="Nothing has been configured yet.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        # Ensure the description is not empty
        if not self.embed.description.strip():
            self.embed.description = None

        # Send the configured embed to the channel
        await interaction.channel.send(embed=self.embed)

        # Reset the embed for a new configuration session
        self.embed = discord.Embed(description="Configure another embed. ⤵️")
        await interaction.response.edit_message(
            content="✅ Embed sent!",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client),
        )


class AddFieldsButton(Button):
    """Button to add more fields to the embed."""

    def __init__(self, embed: discord.Embed) -> None:
        """Initialize the add more fields button with the configured embed."""
        super().__init__(label="Add More Fields",
                         style=discord.ButtonStyle.blurple,
                         emoji="➕")
        self.embed = embed

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event to add more fields."""
        await interaction.response.send_modal(AddFieldsModal(self.embed))


class ResetButton(Button):
    """Button to reset the entire embed configuration."""

    def __init__(self, embed: discord.Embed) -> None:
        """Initialize the reset button with the configured embed."""
        super().__init__(label="Reset Embed",
                         style=discord.ButtonStyle.red,
                         emoji="🔄")
        self.embed = embed

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event to reset the embed."""
        # Reset all parts of the embed
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

        # Confirm the reset to the user
        await interaction.response.edit_message(
            content="✅ Embed reset.",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client),
        )


class SelectiveResetModal(Modal):
    """Modal to selectively reset parts of the embed configuration."""

    def __init__(self, embed: discord.Embed) -> None:
        """Initialize the modal with options for selective reset."""
        super().__init__(title="Selective Reset")
        self.embed = embed

        # Text inputs for selective reset options
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
        """Handle the submission of the selective reset modal."""
        # Process and apply selective resets based on user input
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

        # Confirm the selective reset to the user
        await interaction.response.edit_message(
            content="✅ Selected components reset.",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client),
        )


class SelectiveResetButton(Button):
    """Button to open the selective reset modal."""

    def __init__(self, embed: discord.Embed) -> None:
        """Initialize the selective reset button with the configured embed."""
        super().__init__(label="Selective Reset",
                         style=discord.ButtonStyle.red,
                         emoji="🔄")
        self.embed = embed

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event to open the selective reset modal."""
        await interaction.response.send_modal(SelectiveResetModal(self.embed))


class HelpButton(Button):
    """Button to display help information about the embed creator wizard."""

    def __init__(self) -> None:
        """Initialize the help button."""
        super().__init__(label="Help",
                         style=discord.ButtonStyle.grey,
                         emoji="🔍")

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the button click event to display help information."""
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
    """View for navigating between help pages."""

    def __init__(self, current_page: int = 1) -> None:
        """Initialize the help navigation view with the current page."""
        super().__init__()
        self.current_page = current_page
        total_pages = 10  # Make sure this matches the total number of pages
        self.add_item(PreviousButton(self.current_page, total_pages))
        self.add_item(NextButton(self.current_page, total_pages))
        self.add_item(JumpToPageButton())


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
            embed=get_help_embed(new_page), view=HelpNavigationView(new_page))


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
            embed=get_help_embed(new_page), view=HelpNavigationView(new_page))


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
            placeholder="Enter a page number between 1 and 10",
            required=True)
        self.add_item(self.page_number)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle the submission of the jump to page modal."""
        try:
            page = int(self.page_number.value)
            if 1 <= page <= 10:
                await interaction.response.edit_message(
                    embed=get_help_embed(page), view=HelpNavigationView(page))
            else:
                await interaction.response.send_message(
                    "Please enter a valid page number (1-10).", ephemeral=True)
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid page number (1-10).", ephemeral=True)


def create_embed_view(embed: discord.Embed, bot: commands.Bot) -> View:
    """Create the view for the embed configuration interface."""
    view = View(timeout=None)
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
    """Set up the EmbedCreator cog."""
    await bot.add_cog(EmbedCreator(bot))

import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Modal, TextInput, Button
import aiohttp
from urllib.parse import urlparse
from discord import ButtonStyle


class EmbedCreator(commands.Cog):
    """A cog for creating and managing custom embeds."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        """Close the aiohttp session."""
        await self.session.close()

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

        await interaction.response.send_message("Configure your embed:",
                                                view=view,
                                                ephemeral=True)

    async def dropdown_callback(self,
                                interaction: discord.Interaction) -> None:
        """Callback for the dropdown to open the respective modal for configuration."""
        value = interaction.data["values"][0]
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
        self.colour = TextInput(label="Colour (hex code)", required=False)
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

        self.embed.title = self.titl.value
        self.embed.description = self.description.value or " "
        self.embed.url = self.url.value or None
        if self.colour.value:
            self.embed.color = discord.Color(
                int(self.colour.value.strip("#"), 16))
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

        await interaction.channel.send(embed=self.embed)
        self.embed = discord.Embed(
            description=" ")  # Reset embed with non-empty description
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
        self.embed.title = ""
        self.embed.description = " "  # Ensure description is not empty
        self.embed.url = ""
        self.embed.color = discord.Color.default()
        self.embed.set_author(name=None, url=None, icon_url=None)
        self.embed.set_image(url=None)
        self.embed.set_thumbnail(url=None)
        self.embed.set_footer(text=None, icon_url=None)
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
    return view


async def setup(bot: commands.Bot) -> None:
    """Set up the cog."""
    await bot.add_cog(EmbedCreator(bot))

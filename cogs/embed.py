import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Modal, TextInput, Button
import aiohttp
from urllib.parse import urlparse


class EmbedCreator(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.embed_object = discord.Embed()
        self.session = aiohttp.ClientSession()

    async def close(self):
        await self.session.close()

    @app_commands.command(name="embed",
                          description="Create a custom embed message")
    async def embed(self, interaction: discord.Interaction):
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

        await interaction.response.send_message("Configure your embed:",
                                                view=view,
                                                ephemeral=True)

    async def dropdown_callback(self, interaction: discord.Interaction):
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


def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


class AuthorModal(Modal):

    def __init__(self, embed):
        super().__init__(title="Configure Author")
        self.embed = embed
        self.author = TextInput(label="Author")
        self.author_url = TextInput(label="Author URL", required=False)
        self.author_icon_url = TextInput(label="Author Icon URL",
                                         required=False)
        self.add_item(self.author)
        self.add_item(self.author_url)
        self.add_item(self.author_icon_url)

    async def on_submit(self, interaction: discord.Interaction):
        if self.author_url.value and not is_valid_url(self.author_url.value):
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description=
                f"Invalid URL in Author URL: {self.author_url.value}",
                color=discord.Color.red()),
                                                    ephemeral=True)
            return

        if self.author_icon_url.value and not is_valid_url(
                self.author_icon_url.value):
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description=
                f"Invalid URL in Author Icon URL: {self.author_icon_url.value}",
                color=discord.Color.red()),
                                                    ephemeral=True)
            return

        self.embed.set_author(name=self.author.value,
                              url=self.author_url.value or None,
                              icon_url=self.author_icon_url.value or None)
        await interaction.response.edit_message(content="Author configured.",
                                                embed=self.embed,
                                                view=create_embed_view(
                                                    self.embed,
                                                    interaction.client))


class BodyModal(Modal):

    def __init__(self, embed):
        super().__init__(title="Configure Body")
        self.embed = embed
        self.titl = TextInput(label="Title")
        self.description = TextInput(label="Description")
        self.url = TextInput(label="URL", required=False)
        self.colour = TextInput(label="Colour (hex code)", required=False)
        self.add_item(self.titl)
        self.add_item(self.description)
        self.add_item(self.url)
        self.add_item(self.colour)

    async def on_submit(self, interaction: discord.Interaction):
        if self.url.value and not is_valid_url(self.url.value):
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description=f"Invalid URL in Body URL: {self.url.value}",
                color=discord.Color.red()),
                                                    ephemeral=True)
            return

        self.embed.title = self.titl.value
        self.embed.description = self.description.value
        self.embed.url = self.url.value or None
        if self.colour.value:
            self.embed.color = discord.Color(
                int(self.colour.value.strip("#"), 16))
        await interaction.response.edit_message(content="Body configured.",
                                                embed=self.embed,
                                                view=create_embed_view(
                                                    self.embed,
                                                    interaction.client))


class ImagesModal(Modal):

    def __init__(self, embed):
        super().__init__(title="Configure Images")
        self.embed = embed
        self.image_url = TextInput(label="Image URL")
        self.thumbnail_url = TextInput(label="Thumbnail URL")
        self.add_item(self.image_url)
        self.add_item(self.thumbnail_url)

    async def on_submit(self, interaction: discord.Interaction):
        if self.image_url.value and not is_valid_url(self.image_url.value):
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description=f"Invalid URL in Image URL: {self.image_url.value}",
                color=discord.Color.red()),
                                                    ephemeral=True)
            return

        if self.thumbnail_url.value and not is_valid_url(
                self.thumbnail_url.value):
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description=
                f"Invalid URL in Thumbnail URL: {self.thumbnail_url.value}",
                color=discord.Color.red()),
                                                    ephemeral=True)
            return

        self.embed.set_image(url=self.image_url.value)
        self.embed.set_thumbnail(url=self.thumbnail_url.value)
        await interaction.response.edit_message(content="Images configured.",
                                                embed=self.embed,
                                                view=create_embed_view(
                                                    self.embed,
                                                    interaction.client))


class FooterModal(Modal):

    def __init__(self, embed):
        super().__init__(title="Configure Footer")
        self.embed = embed
        self.footer = TextInput(label="Footer")
        self.timestamp = TextInput(label="Timestamp (YYYY-MM-DD hh:mm)",
                                   required=False)
        self.footer_icon_url = TextInput(label="Footer Icon URL",
                                         required=False)
        self.add_item(self.footer)
        self.add_item(self.timestamp)
        self.add_item(self.footer_icon_url)

    async def on_submit(self, interaction: discord.Interaction):
        if self.footer_icon_url.value and not is_valid_url(
                self.footer_icon_url.value):
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description=
                f"Invalid URL in Footer Icon URL: {self.footer_icon_url.value}",
                color=discord.Color.red()),
                                                    ephemeral=True)
            return

        self.embed.set_footer(text=self.footer.value,
                              icon_url=self.footer_icon_url.value or None)
        if self.timestamp.value:
            self.embed.timestamp = discord.utils.parse_time(
                self.timestamp.value)
        await interaction.response.edit_message(content="Footer configured.",
                                                embed=self.embed,
                                                view=create_embed_view(
                                                    self.embed,
                                                    interaction.client))


class FieldsModal(Modal):

    def __init__(self, embed):
        super().__init__(title="Configure Fields")
        self.embed = embed
        self.field_1 = TextInput(label="<Field Name>, <Field Value>",
                                 required=False)
        self.field_2 = TextInput(label="<Field Name>, <Field Value>",
                                 required=False)
        self.field_3 = TextInput(label="<Field Name>, <Field Value>",
                                 required=False)
        self.field_4 = TextInput(label="<Field Name>, <Field Value>",
                                 required=False)
        self.field_5 = TextInput(label="<Field Name>, <Field Value>",
                                 required=False)
        self.add_item(self.field_1)
        self.add_item(self.field_2)
        self.add_item(self.field_3)
        self.add_item(self.field_4)
        self.add_item(self.field_5)

    async def on_submit(self, interaction: discord.Interaction):
        fields = [
            self.field_1.value, self.field_2.value, self.field_3.value,
            self.field_4.value, self.field_5.value
        ]
        for field in fields:
            if field:
                parts = field.split(",")
                name = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""
                self.embed.add_field(name=name, value=value)
        await interaction.response.edit_message(content="Fields configured.",
                                                embed=self.embed,
                                                view=create_embed_view(
                                                    self.embed,
                                                    interaction.client))


class InlineModal(Modal):

    def __init__(self, embed):
        super().__init__(title="Configure Inline Fields")
        self.embed = embed
        self.field_no = TextInput(label="Field Number to Inline",
                                  placeholder="e.g. 1, 2, 3")
        self.add_item(self.field_no)

    async def on_submit(self, interaction: discord.Interaction):
        field_numbers = self.field_no.value.split(",")
        for field_no in field_numbers:
            field_index = int(field_no.strip()) - 1
            if 0 <= field_index < len(self.embed.fields):
                field = self.embed.fields[field_index]
                self.embed.set_field_at(index=field_index,
                                        name=field.name,
                                        value=field.value,
                                        inline=True)
        await interaction.response.edit_message(
            content="Inline fields configured.",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client))


class AddFieldsModal(Modal):

    def __init__(self, embed):
        super().__init__(title="Add More Fields")
        self.embed = embed
        self.field_1 = TextInput(label="<Field Name>, <Field Value>",
                                 required=False)
        self.field_2 = TextInput(label="<Field Name>, <Field Value>",
                                 required=False)
        self.field_3 = TextInput(label="<Field Name>, <Field Value>",
                                 required=False)
        self.field_4 = TextInput(label="<Field Name>, <Field Value>",
                                 required=False)
        self.field_5 = TextInput(label="<Field Name>, <Field Value>",
                                 required=False)
        self.add_item(self.field_1)
        self.add_item(self.field_2)
        self.add_item(self.field_3)
        self.add_item(self.field_4)
        self.add_item(self.field_5)

    async def on_submit(self, interaction: discord.Interaction):
        fields = [
            self.field_1.value, self.field_2.value, self.field_3.value,
            self.field_4.value, self.field_5.value
        ]
        for field in fields:
            if field:
                parts = field.split(",")
                name = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""
                self.embed.add_field(name=name, value=value)
        await interaction.response.edit_message(
            content="Additional fields configured.",
            embed=self.embed,
            view=create_embed_view(self.embed, interaction.client))


class SendButton(Button):

    def __init__(self, embed):
        super().__init__(label="Send",
                         style=discord.ButtonStyle.green,
                         emoji="🚀")
        self.embed = embed

    async def callback(self, interaction: discord.Interaction):
        if not self.embed.title and not self.embed.description and not self.embed.fields:
            await interaction.response.send_message(embed=discord.Embed(
                title="Error",
                description="Nothing has been configured yet.",
                color=discord.Color.red()),
                                                    ephemeral=True)
            return

        await interaction.channel.send(embed=self.embed)
        await interaction.response.edit_message(content="Embed sent!",
                                                view=None)


class AddFieldsButton(Button):

    def __init__(self, embed):
        super().__init__(label="Add More Fields",
                         style=discord.ButtonStyle.blurple,
                         emoji="➕")
        self.embed = embed

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddFieldsModal(self.embed))


def create_embed_view(embed, bot):
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
    select.callback = bot.get_cog('EmbedCreator').dropdown_callback
    view.add_item(select)
    view.add_item(SendButton(embed))
    view.add_item(AddFieldsButton(embed))
    return view


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EmbedCreator(bot))

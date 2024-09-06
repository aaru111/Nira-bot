import discord
from discord import ui
from urllib.parse import quote
import re


class UrbanDictionaryModal(ui.Modal, title="Go to Page"):
    page_number = ui.TextInput(label="Page Number",
                               placeholder="Enter a page number (1-10)",
                               min_length=1,
                               max_length=2)

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            page = int(self.page_number.value) - 1
            if 0 <= page < len(self.view.pages):
                self.view.current_page = page
                await interaction.response.edit_message(
                    embed=self.view.pages[self.view.current_page])
            else:
                await interaction.response.send_message("Invalid page number.",
                                                        ephemeral=True)
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number.", ephemeral=True)


class UrbanDictionaryView(ui.View):

    def __init__(self, pages):
        super().__init__(timeout=30)
        self.pages = pages
        self.current_page = 0
        self.message = None

    @ui.button(label="Previous",
               style=discord.ButtonStyle.primary,
               custom_id="previous",
               row=0)
    async def previous_button(self, interaction: discord.Interaction,
                              button: ui.Button):
        await self.handle_navigation(interaction, -1)

    @ui.button(label="1/10",
               style=discord.ButtonStyle.secondary,
               custom_id="page_count",
               row=0,
               disabled=True)
    async def page_count_button(self, interaction: discord.Interaction,
                                button: ui.Button):
        await interaction.response.defer()

    @ui.button(label="Next",
               style=discord.ButtonStyle.primary,
               custom_id="next",
               row=0)
    async def next_button(self, interaction: discord.Interaction,
                          button: ui.Button):
        await self.handle_navigation(interaction, 1)

    @ui.button(label="Go to",
               style=discord.ButtonStyle.success,
               custom_id="go_to",
               row=1)
    async def go_to_button(self, interaction: discord.Interaction,
                           button: ui.Button):
        modal = UrbanDictionaryModal(self)
        await interaction.response.send_modal(modal)

    async def handle_navigation(self, interaction: discord.Interaction,
                                direction: int):
        new_page = self.current_page + direction
        if 0 <= new_page < len(self.pages):
            self.current_page = new_page
            self.update_buttons()
            await interaction.response.edit_message(
                embed=self.pages[self.current_page], view=self)

    def update_buttons(self):
        self.previous_button.disabled = self.current_page == 0
        self.page_count_button.label = f"{self.current_page + 1}/{len(self.pages)}"
        self.next_button.disabled = self.current_page == len(self.pages) - 1

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)

    async def start(self, ctx):
        self.message = await ctx.send(embed=self.pages[0], view=self)


def format_definition(text):
    words = re.findall(r'\[([^\]]+)\]', text)
    for word in words:
        encoded_word = quote(word)
        link = f"https://www.urbandictionary.com/define.php?term={encoded_word}"
        text = text.replace(f"[{word}]", f"[{word}]({link})")
    return text


def create_definition_embeds(word, encoded_word, definitions):
    pages = []
    for index, definition in enumerate(definitions, start=1):
        embed = discord.Embed(
            title=f"Urban Dictionary: {word}",
            url=
            f"https://www.urbandictionary.com/define.php?term={encoded_word}",
            color=0x00ff00)
        embed.set_author(name="Urban Dictionary",
                         icon_url="https://i.imgur.com/vdoosDm.png")

        formatted_definition = format_definition(definition["definition"])
        formatted_example = format_definition(definition["example"])

        embed.add_field(name="📚 Definition",
                        value=formatted_definition[:1000],
                        inline=False)
        embed.add_field(name="📝 Example",
                        value=f"*{formatted_example[:1000]}*",
                        inline=False)
        embed.add_field(name="👍 Upvotes",
                        value=definition["thumbs_up"],
                        inline=True)
        embed.add_field(name="👎 Downvotes",
                        value=definition["thumbs_down"],
                        inline=True)
        embed.set_footer(
            text=
            f"Definition {index} of {len(definitions)} | Written by {definition['author']}"
        )

        pages.append(embed)
    return pages

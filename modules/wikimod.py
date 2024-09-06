import aiohttp
from bs4 import BeautifulSoup
import textwrap
from abc import ABC, abstractmethod
import discord
from typing import Any, Tuple
import asyncio

class CustomWikipediaAPI:
    BASE_URL = "https://en.wikipedia.org/w/api.php"

    @staticmethod
    async def search(query: str) -> Tuple[str, str]:
        params = {
            "action": "opensearch",
            "search": query,
            "limit": 1,
            "format": "json"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(CustomWikipediaAPI.BASE_URL, params=params) as response:
                data = await response.json()
                return data[1][0] if data[1] else None, data[3][0] if data[3] else None

    @staticmethod
    async def get_page_info(title: str):
        params = {
            "action": "query",
            "prop": "extracts|info|pageimages",
            "exintro": "true",
            "inprop": "url",
            "pithumbsize": "300",
            "titles": title,
            "format": "json"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(CustomWikipediaAPI.BASE_URL, params=params) as response:
                data = await response.json()
                page = next(iter(data['query']['pages'].values()))

                soup = BeautifulSoup(page.get('extract', ''), 'html.parser')
                summary = soup.get_text()

                return {
                    'title': page['title'],
                    'url': page['fullurl'],
                    'summary': summary,
                    'image_url': page.get('thumbnail', {}).get('source')
                }

class WikiSearcher(ABC):
    @staticmethod
    @abstractmethod
    async def search(query: str) -> Tuple[str, str]:
        pass

    @staticmethod
    @abstractmethod
    async def get_page_info(title: str) -> dict[str, Any]:
        pass

class WikipediaSearcher(WikiSearcher):
    @staticmethod
    async def search(query: str) -> Tuple[str, str]:
        return await CustomWikipediaAPI.search(query)

    @staticmethod
    async def get_page_info(title: str) -> dict[str, Any]:
        return await CustomWikipediaAPI.get_page_info(title)

class WikiEmbedCreator:
    @staticmethod
    def create_base_embed(title: str, url: str, image_url: str):
        embed = discord.Embed(title=title, url=url, color=0x3498db)
        if image_url:
            embed.set_thumbnail(url=image_url)
        embed.set_footer(text="Source: Wikipedia")
        return embed

    @staticmethod
    def split_content(content: str, max_chars: int = 2048):
        return textwrap.wrap(content, max_chars, replace_whitespace=False)

class WikiView(discord.ui.View):
    def __init__(self, base_embed: discord.Embed, content_chunks: list):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.base_embed = base_embed
        self.content_chunks = content_chunks
        self.current_page = 0
        self.update_buttons()
        self.message = None

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray, row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.change_page(interaction, -1)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.green, disabled=True, row=0)
    async def page_counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray, row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.change_page(interaction, 1)

    @discord.ui.button(label="Go to", style=discord.ButtonStyle.blurple, row=1)
    async def goto_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GotoModal(self))

    async def change_page(self, interaction: discord.Interaction, change: int):
        self.current_page = (self.current_page + change) % len(self.content_chunks)
        await self.update_view(interaction)

    async def update_view(self, interaction: discord.Interaction):
        self.update_buttons()
        embed = self.base_embed.copy()
        embed.description = self.content_chunks[self.current_page]
        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.content_chunks)} | Source: Wikipedia")
        await interaction.response.edit_message(embed=embed, view=self)

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.content_chunks) - 1
        self.page_counter.label = f"{self.current_page + 1}/{len(self.content_chunks)}"

    async def on_timeout(self):
        if self.message:
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

class GotoModal(discord.ui.Modal, title="Go to Page"):
    def __init__(self, view: WikiView):
        super().__init__()
        self.view = view
        self.page_number = discord.ui.TextInput(label="Page Number", placeholder="Enter a page number")
        self.add_item(self.page_number)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            page = int(self.page_number.value) - 1
            if 0 <= page < len(self.view.content_chunks):
                self.view.current_page = page
                await self.view.update_view(interaction)
            else:
                await interaction.response.send_message(
                    f"Invalid page number. Please enter a number between 1 and {len(self.view.content_chunks)}.",
                    ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Please enter a valid number.", ephemeral=True)
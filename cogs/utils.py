import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
from typing import Optional, List
from urllib.parse import quote

from modules.wikimod import WikipediaSearcher, WikiEmbedCreator, WikiView
from modules.weathermod import create_weather_embed
from modules.urbanmod import UrbanDictionaryView, create_definition_embed, create_urban_dropdown, search_urban_dictionary
from modules.shortnermod import URLShortenerCore

# Retrieve the Bitly API token from environment variables
BITLY_TOKEN = os.getenv("BITLY_API")
# In-memory storage for user rate limits (user_id -> (last_reset_time, count))
user_rate_limits = {}
RATE_LIMIT = 5  # Max number of URL shortenings per user within the reset interval
RESET_INTERVAL = 60 * 60  # Reset interval in seconds (e.g., 1 hour)


class Utilities(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.searcher = WikipediaSearcher()
        self.embed_creator = WikiEmbedCreator()
        self.url_shortener_core = URLShortenerCore(BITLY_TOKEN or "",
                                                   RATE_LIMIT, RESET_INTERVAL)

    async def cog_load(self):
        """Initialize resources when the cog is loaded."""
        await self.url_shortener_core.initialize_session()

    async def cog_unload(self):
        """Cleanup resources when the cog is unloaded."""
        await self.session.close()
        await self.url_shortener_core.close_session()

    async def wiki_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        suggestions = await self.searcher.autocomplete(current)
        return [app_commands.Choice(name=suggestion, value=suggestion) for suggestion in suggestions[:25]]

    @commands.hybrid_command(name="wiki",
                             description="Search Wikipedia for information")
    @app_commands.describe(query="The search query for Wikipedia")
    @app_commands.autocomplete(query=wiki_autocomplete)
    async def wiki(self, ctx: commands.Context, *, query: str):
        await ctx.defer()
        try:
            page_title, page_url = await self.searcher.search(query)
            if not page_title:
                await ctx.send(
                    "No results found for your query. Please try a different search term.",
                    ephemeral=True)
                return
            page_info = await self.searcher.get_page_info(page_title)
            base_embed = self.embed_creator.create_base_embed(
                page_info['title'], page_url or page_info['url'],
                page_info.get('image_url'))
            content_chunks = self.embed_creator.split_content(
                page_info['summary'])
            initial_embed = base_embed.copy()
            initial_embed.description = content_chunks[
                0] if content_chunks else f"No summary available for '{query}'. This is the closest match found."
            if len(content_chunks) <= 1:
                # If there's only one page or no content, don't use the WikiView
                initial_embed.set_footer(text="Source: Wikipedia")
                await ctx.send(embed=initial_embed)
            else:
                # If there are multiple pages, use the WikiView
                view = WikiView(base_embed, content_chunks)
                initial_embed.set_footer(
                    text=f"Page 1/{len(content_chunks)} | Source: Wikipedia")
                message = await ctx.send(embed=initial_embed, view=view)
                view.message = message
        except Exception as e:
            await ctx.send(
                f"An error occurred while processing your request: {str(e)}",
                ephemeral=True)

    @commands.hybrid_command(
        name="weather", description="Get the weather for a specified location")
    @app_commands.describe(location="The location to get weather for")
    async def weather(self, ctx: commands.Context, *, location: str):
        api_key = os.getenv(
            "WEATHER_API_KEY")  # Retrieve the API key from the environment
        if not api_key:
            await ctx.send("Error: API key not found.")
            return
        base_url = "http://api.openweathermap.org/data/2.5/weather"
        params = {"q": location, "appid": api_key, "units": "metric"}
        async with self.session.get(base_url, params=params) as response:
            data = await response.json()
        if data["cod"] != 200:
            await ctx.send(f"Error: {data['message']}")
            return
        embed = create_weather_embed(data, location)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="urban",
                             description="Search Urban Dictionary for a word")
    @app_commands.describe(word="The word to search for in Urban Dictionary")
    @app_commands.autocomplete(word=search_urban_dictionary)
    async def urban(self, ctx: commands.Context, *, word: str):
        encoded_word = quote(word)
        url = f"https://api.urbandictionary.com/v0/define?term={encoded_word}"
        async with self.session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                definitions = data.get("list", [])
                if not definitions:
                    await ctx.send(f"No definitions found for '{word}'.")
                    return
                main_embed = create_definition_embed(word, encoded_word,
                                                     definitions[0], 1,
                                                     min(8, len(definitions)))
                dropdown = create_urban_dropdown(definitions[:8])
                view = UrbanDictionaryView(definitions[:8], dropdown)
                await view.start(ctx, main_embed)
            else:
                await ctx.send(
                    "An error occurred while fetching the definition.")

    @commands.hybrid_command(
        name="shorten",
        description=
        "Shorten any valid URL using the Bitly API. Optionally generate a QR code and set an expiration time."
    )
    @app_commands.describe(
        url="The URL to shorten",
        generate_qr="Generate a QR code for the shortened URL (true/false)",
        expire_days=
        "Number of days after which the shortened URL will expire (default is no expiry)"
    )
    async def shorten(self,
                      ctx: commands.Context,
                      url: str,
                      generate_qr: bool = False,
                      expire_days: Optional[int] = None) -> None:
        """Handles the /shorten command to shorten a given URL."""
        await ctx.defer()
        user_id = ctx.author.id
        if not self.url_shortener_core.is_within_rate_limit(
                user_id, user_rate_limits):
            await ctx.send(
                "You have reached the rate limit. Please try again later.")
            return
        if self.url_shortener_core.is_already_shortened(url):
            await ctx.send("Cannot shorten an already shortened URL.")
            return
        shortened_url = await self.url_shortener_core.shorten_url(url, expire_days)
        if shortened_url:
            formatted_url = self.url_shortener_core.format_shortened_url(
                shortened_url)
            if generate_qr:
                qr_image = self.url_shortener_core.generate_qr_code(
                    shortened_url)
                file = discord.File(qr_image, filename="qrcode.png")
                await ctx.send(
                    content=f"Here is your shortened URL: {formatted_url}",
                    file=file)
            else:
                await ctx.send(f"Here is your shortened URL: {formatted_url}")
        else:
            await ctx.send(
                "Failed to shorten the URL. Please ensure it's a valid URL and try again."
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utilities(bot))
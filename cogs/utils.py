import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
from urllib.parse import quote

from modules.wikimod import WikipediaSearcher, WikiEmbedCreator, WikiView
from modules.weathermod import create_weather_embed
from modules.urbanmod import UrbanDictionaryView, create_definition_embeds
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
        self.url_shortener_core = URLShortenerCore(BITLY_TOKEN, RATE_LIMIT,
                                                   RESET_INTERVAL)

    async def cog_unload(self):
        """Cleanup resources when the cog is unloaded."""
        await self.session.close()
        await self.url_shortener_core.close_session()

    @app_commands.command(name="wiki",
                          description="Search Wikipedia for information")
    async def wiki(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        try:
            page_title = await self.searcher.search(query)
            if not page_title:
                await interaction.followup.send(
                    "No results found for your query. Please try a different search term.",
                    ephemeral=True)
                return
            page_info = await self.searcher.get_page_info(page_title)
            base_embed = self.embed_creator.create_base_embed(
                page_info['title'], page_info['url'], page_info['image_url'])
            content_chunks = self.embed_creator.split_content(
                page_info['summary'])
            initial_embed = base_embed.copy()
            initial_embed.description = content_chunks[0]
            if len(content_chunks) == 1:
                # If there's only one page, don't use the WikiView
                initial_embed.set_footer(text="Source: Wikipedia")
                await interaction.followup.send(embed=initial_embed)
            else:
                # If there are multiple pages, use the WikiView
                view = WikiView(base_embed, content_chunks)
                initial_embed.set_footer(
                    text=f"Page 1/{len(content_chunks)} | Source: Wikipedia")
                message = await interaction.followup.send(embed=initial_embed,
                                                          view=view)
                view.message = message
                view.reset_timer()
        except Exception as e:
            await interaction.followup.send(
                f"An error occurred while processing your request: {str(e)}",
                ephemeral=True)

    @app_commands.command(
        name="weather", description="Get the weather for a specified location")
    async def weather(self, interaction: discord.Interaction, location: str):
        api_key = os.getenv(
            "WEATHER_API_KEY")  # Retrieve the API key from the environment
        if not api_key:
            await interaction.response.send_message("Error: API key not found."
                                                    )
            return
        base_url = "http://api.openweathermap.org/data/2.5/weather"
        params = {"q": location, "appid": api_key, "units": "metric"}
        async with self.session.get(base_url, params=params) as response:
            data = await response.json()
        if data["cod"] != 200:
            await interaction.response.send_message(f"Error: {data['message']}"
                                                    )
            return
        embed = create_weather_embed(data, location)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="urban")
    async def urban(self, ctx, *, word: str):
        encoded_word = quote(word)
        url = f"https://api.urbandictionary.com/v0/define?term={encoded_word}"
        async with self.session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                definitions = data.get("list", [])
                if not definitions:
                    await ctx.send(f"No definitions found for '{word}'.")
                    return
                pages = create_definition_embeds(word, encoded_word,
                                                 definitions[:10])
                view = UrbanDictionaryView(pages)
                await view.start(ctx)
            else:
                await ctx.send(
                    "An error occurred while fetching the definition.")

    @app_commands.command(
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
                      interaction: discord.Interaction,
                      url: str,
                      generate_qr: bool = False,
                      expire_days: int = None) -> None:
        """Handles the /shorten command to shorten a given URL."""
        user_id = interaction.user.id
        if not self.url_shortener_core.is_within_rate_limit(
                user_id, user_rate_limits):
            await interaction.response.send_message(
                "You have reached the rate limit. Please try again later.")
            return
        if self.url_shortener_core.is_already_shortened(url):
            await interaction.response.send_message(
                "Cannot shorten an already shortened URL.")
            return
        shortened_url = self.url_shortener_core.shorten_url(url, expire_days)
        if shortened_url:
            formatted_url = self.url_shortener_core.format_shortened_url(
                shortened_url)
            if generate_qr:
                qr_image = self.url_shortener_core.generate_qr_code(
                    shortened_url)
                file = discord.File(qr_image, filename="qrcode.png")
                await interaction.response.send_message(
                    content=f"Here is your shortened URL: {formatted_url}",
                    file=file)
            else:
                await interaction.response.send_message(
                    f"Here is your shortened URL: {formatted_url}")
        else:
            await interaction.response.send_message(
                "Failed to shorten the URL. Please ensure it's a valid URL and try again."
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utilities(bot))

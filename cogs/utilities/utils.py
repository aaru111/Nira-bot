import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
import typing
from typing import Optional, List
from urllib.parse import quote
from abc import ABC, abstractmethod

from .modules.wikimod import WikipediaSearcher, WikiEmbedCreator, WikiView
from .modules.weathermod import create_weather_embed
from .modules.urbanmod import UrbanDictionaryView, create_definition_embed, create_urban_dropdown, search_urban_dictionary
from .modules.shortnermod import URLShortenerCore
from .modules.timestampmod import DatetimeTransformer, TimezoneTransformer, TimezoneTransformerError, make_timestamps_embed, TIMESTAMP_STYLE
from .modules.encodemod import encode_text, decode_text
from .modules.translatemod import TranslationCore

from database import db

# Retrieve the Bitly API token from environment variables
BITLY_TOKEN = os.getenv("BITLY_API")
# In-memory storage for user rate limits (user_id -> (last_reset_time, count))
user_rate_limits = {}
RATE_LIMIT = 5  # Max number of URL shortenings per user within the reset interval
RESET_INTERVAL = 60 * 60  # Reset interval in seconds (e.g., 1 hour)


# DatabaseManager interface for abstracting database operations
class DatabaseManager(ABC):

    @abstractmethod
    async def get_prefix(self, guild_id: int) -> str:
        pass

    @abstractmethod
    async def set_prefix(self, guild_id: int, prefix: str) -> None:
        pass


class PostgreSQLManager(DatabaseManager):

    async def initialize(self):
        await db.initialize()

    async def get_prefix(self, guild_id: int) -> str:
        query = 'SELECT prefix FROM guild_prefixes WHERE guild_id = $1'
        result = await db.fetch(query, guild_id)
        return result[0]['prefix'] if result else '.'

    async def set_prefix(self, guild_id: int, prefix: str) -> None:
        query = '''
        INSERT INTO guild_prefixes (guild_id, prefix)
        VALUES ($1, $2)
        ON CONFLICT (guild_id) DO UPDATE SET prefix = $2
        '''
        await db.execute(query, guild_id, prefix)


class Utilities(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.searcher = WikipediaSearcher()
        self.embed_creator = WikiEmbedCreator()
        self.url_shortener_core = URLShortenerCore(BITLY_TOKEN or "",
                                                   RATE_LIMIT, RESET_INTERVAL)
        self.translation_core = TranslationCore()

        self.db_manager = PostgreSQLManager()

    async def cog_load(self):
        """Initialize resources when the cog is loaded."""
        await self.url_shortener_core.initialize_session()

        await self.db_manager.initialize()

    async def cog_unload(self):
        """Cleanup resources when the cog is unloaded."""
        await self.session.close()
        await self.url_shortener_core.close_session()

        await db.close()

    async def wiki_autocomplete(
            self, interaction: discord.Interaction,
            current: str) -> List[app_commands.Choice[str]]:
        suggestions = await self.searcher.autocomplete(current)
        return [
            app_commands.Choice(name=suggestion, value=suggestion)
            for suggestion in suggestions[:25]
        ]

    async def language_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        return self.translation_core.get_language_suggestions(current)

    @commands.hybrid_command(name="wiki",
                             description="Search Wikipedia for information")
    @app_commands.describe(query="The search query for Wikipedia")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True,
                                   dms=True,
                                   private_channels=True)
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
        name="translate",
        description="Translate text to any language (defaults to English)")
    @app_commands.describe(
        text="The text you want to translate",
        language=
        "The target language to translate to (optional, defaults to English)")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True,
                                   dms=True,
                                   private_channels=True)
    @app_commands.autocomplete(language=language_autocomplete)
    async def translate(self,
                        ctx: commands.Context,
                        *,
                        text: str,
                        language: Optional[str] = 'en'):
        """Translate text to any language using fuzzy matching (defaults to English)"""
        await ctx.defer()

        try:
            # Perform translation
            translation = await self.translation_core.translate_text(
                text, language)

            # Create and send embed
            embed = self.translation_core.create_translation_embed(translation)
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Translation failed: {str(e)}", ephemeral=True)

    @app_commands.command(
        name="encode",
        description="Encode text to base64, hex, or binary (up to 5 layers)")
    @app_commands.describe(text="The text to encode",
                           encoding="Choose encoding type",
                           layers="Number of encoding layers (1-5)")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True,
                                   dms=True,
                                   private_channels=True)
    @app_commands.choices(encoding=[
        app_commands.Choice(name="base64", value="base64"),
        app_commands.Choice(name="hex", value="hex"),
        app_commands.Choice(name="binary", value="binary")
    ])
    async def encode(self,
                     interaction: discord.Interaction,
                     text: str,
                     encoding: str,
                     layers: Optional[int] = 1):
        await interaction.response.defer(ephemeral=True)
        await encode_text(interaction, text, encoding, layers)

    @app_commands.command(
        name="decode",
        description="Decode text with automatic format detection")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True,
                                   dms=True,
                                   private_channels=True)
    @app_commands.describe(encoded_text="The encoded text to decode")
    async def decode(self, interaction: discord.Interaction,
                     encoded_text: str):
        await interaction.response.defer(ephemeral=True)
        await decode_text(interaction, encoded_text)

    @encode.error
    @decode.error
    async def error_handler(self, interaction: discord.Interaction,
                            error: app_commands.AppCommandError):
        await interaction.followup.send(
            f"❌ {str(error.original) if isinstance(error, app_commands.CommandInvokeError) else str(error)}",
            ephemeral=True)

    @commands.hybrid_command(
        name="weather", description="Get the weather for a specified location")
    @app_commands.describe(location="The location to get weather for")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True,
                                   dms=True,
                                   private_channels=True)
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
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True,
                                   dms=True,
                                   private_channels=True)
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
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True,
                                   dms=True,
                                   private_channels=True)
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
        shortened_url = await self.url_shortener_core.shorten_url(
            url, expire_days)
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

    @staticmethod
    def is_valid_prefix(prefix: str) -> bool:
        return len(prefix) <= 10 and not any(char.isspace() for char in prefix)

    @app_commands.command(
        name='prefix',
        description='Change or view the bot prefix for this server')
    @app_commands.describe(
        new_prefix='The new prefix to set (leave empty to view current prefix)'
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def change_prefix(self,
                            interaction: discord.Interaction,
                            new_prefix: Optional[str] = None):
        if new_prefix is None:
            current_prefix = await self.db_manager.get_prefix(
                interaction.guild.id)
            await interaction.response.send_message(
                f"The current prefix is: `{current_prefix}`")
            return
        if not self.is_valid_prefix(new_prefix):
            await interaction.response.send_message(
                "Invalid prefix. It must be 10 characters or less and contain no spaces.",
                ephemeral=True)
            return
        await self.db_manager.set_prefix(interaction.guild.id, new_prefix)
        self.bot.command_prefix = commands.when_mentioned_or(new_prefix)
        await interaction.response.send_message(
            f"Prefix updated to: `{new_prefix}`")

    @change_prefix.error
    async def change_prefix_error(self, interaction: discord.Interaction,
                                  error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need 'Manage Server' permissions to change the prefix.",
                ephemeral=True)

    async def get_prefix(self, message: discord.Message) -> str:
        if message.guild:
            return await self.db_manager.get_prefix(message.guild.id)
        return '.'  # Default prefix for DMs

    @app_commands.command()
    @app_commands.describe(style="The style to format the datetime with.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True,
                                   dms=True,
                                   private_channels=True)
    @app_commands.choices(style=TIMESTAMP_STYLE)
    async def now(
        self,
        interaction: discord.Interaction,
        style: typing.Optional[app_commands.Choice[str]] = None,
    ) -> None:
        """Create timestamps of now to send to get rich formatting."""

        _now = discord.utils.utcnow()

        embed = make_timestamps_embed(_now, style=style)
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @app_commands.describe(
        dt="The date and time.",
        tz="The time zone of the time.",
        style="The style to format the datetime with.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True,
                                   dms=True,
                                   private_channels=True)
    @app_commands.rename(dt="datetime", tz="timezone")
    @app_commands.choices(style=TIMESTAMP_STYLE)
    async def timestamp(
        self,
        interaction: discord.Interaction,
        dt: app_commands.Transform[str, DatetimeTransformer],
        tz: app_commands.Transform[str, TimezoneTransformer],
        style: typing.Optional[app_commands.Choice[str]] = None,
    ) -> None:
        """Create timestamps of the given time to send to get rich formatting."""

        dt_tz = dt.replace(tzinfo=tz)  # type: ignore

        embed = make_timestamps_embed(dt_tz, style=style)
        await interaction.response.send_message(embed=embed)

    @timestamp.error
    async def timestamp_error(self, interaction: discord.Interaction,
                              error: app_commands.AppCommandError) -> None:
        """Error handler for the timestamp command."""

        if isinstance(error, TimezoneTransformerError):
            await interaction.response.send_message(
                f"Could not find the appropriate time zone `{error.tz_key}`. "
                "Try again by selecting a proposed value.",
                ephemeral=True,
            )
        else:
            interaction.extras["error_handled"] = False

    @app_commands.command()
    async def say(self, interaction: discord.Interaction, content: str):
        await interaction.response.defer()
        await interaction.followup.send(content)


async def setup(bot: commands.Bot) -> None:
    cog = Utilities(bot)
    await bot.add_cog(cog)
    bot.get_prefix = cog.get_prefix

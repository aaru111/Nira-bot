import discord
from discord.ext import commands
from discord import app_commands
import os
from modules.shortnermod import URLShortenerCore

# Retrieve the Bitly API token from environment variables
BITLY_TOKEN = os.getenv("BITLY_API")

# In-memory storage for user rate limits (user_id -> (last_reset_time, count))
user_rate_limits = {}
RATE_LIMIT = 5  # Max number of URL shortenings per user within the reset interval
RESET_INTERVAL = 60 * 60  # Reset interval in seconds (e.g., 1 hour)


class URLShortener(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.core = URLShortenerCore(BITLY_TOKEN, RATE_LIMIT, RESET_INTERVAL)
        self.session = self.core.session

    async def cog_unload(self) -> None:
        """Clean up resources when the cog is unloaded."""
        await self.core.close_session()

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

        if not self.core.is_within_rate_limit(user_id, user_rate_limits):
            await interaction.response.send_message(
                "You have reached the rate limit. Please try again later.")
            return

        if self.core.is_already_shortened(url):
            await interaction.response.send_message(
                "Cannot shorten an already shortened URL.")
            return

        shortened_url = self.core.shorten_url(url, expire_days)
        if shortened_url:
            formatted_url = self.core.format_shortened_url(shortened_url)
            if generate_qr:
                qr_image = self.core.generate_qr_code(shortened_url)
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
    """Registers the URLShortener cog with the bot."""
    await bot.add_cog(URLShortener(bot))

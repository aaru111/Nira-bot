import discord
from discord.ext import commands
from discord import app_commands
import requests
import os
from dotenv import load_dotenv

load_dotenv()

BITLY_TOKEN = os.getenv("BITLY_API")


class URLShortener(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="shorten",
        description="Shorten any valid URL using the Bitly API.")
    @app_commands.describe(url="The URL to shorten")
    async def shorten(self, interaction: discord.Interaction, url: str):
        shortened_url = self.shorten_url(url)
        if shortened_url:
            await interaction.response.send_message(
                f"Here is your shortened URL: {shortened_url}")
        else:
            await interaction.response.send_message(
                "Failed to shorten the URL. Please ensure it's a valid URL and try again."
            )

    def shorten_url(self, url: str) -> str:
        headers = {
            "Authorization": f"Bearer {BITLY_TOKEN}",
            "Content-Type": "application/json",
        }
        data = {
            "long_url": url,
            "domain":
            "bit.ly"  # Ensures that the shortened URL uses the bit.ly domain
        }

        try:
            response = requests.post("https://api-ssl.bitly.com/v4/shorten",
                                     json=data,
                                     headers=headers)
            response.raise_for_status(
            )  # This will raise an error for HTTP status codes 4xx/5xx
            return response.json().get("link")
        except requests.exceptions.RequestException as e:
            print(f"Error occurred: {e}")  # Logs the error for debugging
            return None


async def setup(bot):
    await bot.add_cog(URLShortener(bot))

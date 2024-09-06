import os
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from modules.weathermod import create_weather_embed


class Weather(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

    async def cog_unload(self):
        """Clean up resources when the cog is unloaded."""
        await self.session.close()

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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Weather(bot))

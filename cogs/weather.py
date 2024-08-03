import discord
from discord.ext import commands
from discord import app_commands
import aiohttp


class Weather(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def close(self):
        await self.session.close()

    @app_commands.command(
        name="weather", description="Get the weather for a specified location")
    async def weather(self, interaction: discord.Interaction, location: str):
        api_key = "d5a9ac7eb6359f1ecedcf2226a023e57"
        base_url = "http://api.openweathermap.org/data/2.5/weather"
        params = {"q": location, "appid": api_key, "units": "metric"}

        async with self.session.get(base_url, params=params) as response:
            data = await response.json()

        if data["cod"] != 200:
            await interaction.response.send_message(f"Error: {data['message']}"
                                                    )
            return

        weather_description = data["weather"][0]["description"].capitalize()
        icon = data["weather"][0]["icon"]
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        wind_speed = data["wind"]["speed"]

        embed_color = self.get_embed_color(weather_description)

        embed = discord.Embed(title=f"Weather in {location.capitalize()}",
                              color=embed_color)
        embed.set_thumbnail(
            url=f"http://openweathermap.org/img/wn/{icon}@2x.png")

        embed.add_field(name="Description",
                        value=weather_description,
                        inline=False)
        embed.add_field(name="Temperature", value=f"{temp}°C", inline=True)
        embed.add_field(name="Feels Like",
                        value=f"{feels_like}°C",
                        inline=True)
        embed.add_field(name="\u200b", value="\u200b",
                        inline=True)  # Empty field for spacing
        embed.add_field(name="Humidity", value=f"{humidity}%", inline=True)
        embed.add_field(name="Wind Speed",
                        value=f"{wind_speed} m/s",
                        inline=True)

        await interaction.response.send_message(embed=embed)

    def get_embed_color(self, weather_description):
        if 'clear' in weather_description.lower():
            return discord.Color.blue()
        elif 'clouds' in weather_description.lower():
            return discord.Color.light_grey()
        elif 'rain' in weather_description.lower(
        ) or 'drizzle' in weather_description.lower():
            return discord.Color.blue()
        elif 'thunderstorm' in weather_description.lower():
            return discord.Color.dark_purple()
        elif 'snow' in weather_description.lower():
            return discord.Color.teal()
        elif 'mist' in weather_description.lower(
        ) or 'fog' in weather_description.lower():
            return discord.Color.light_grey()
        else:
            return discord.Color.default()


async def setup(bot: commands.Bot):
    await bot.add_cog(Weather(bot))

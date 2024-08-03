import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from datetime import datetime
import pytz
import pycountry


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

        # Extract data from API response
        weather_description = data["weather"][0]["description"].capitalize()
        icon = data["weather"][0]["icon"]
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        wind_speed = data["wind"]["speed"]
        country_code = data["sys"]["country"]
        country_name = self.get_country_name(
            country_code)  # Get full country name

        # Adjust the title to use country full name
        title = f"Weather in {location.capitalize()} - {country_name}"

        # Calculate the time of the last update
        last_updated = datetime.utcfromtimestamp(data["dt"])
        local_tz = pytz.timezone(
            'Asia/Kolkata')  # Change this to your preferred timezone
        last_updated_local = last_updated.astimezone(local_tz)
        last_updated_time = last_updated_local.strftime(
            '%I:%M %p')  # 12-hour format with AM/PM
        last_updated_date = last_updated_local.strftime('%Y-%m-%d')

        # Determine the embed color based on the weather description
        embed_color = self.get_embed_color(weather_description)

        # Create the embed
        embed = discord.Embed(title=title, color=embed_color)
        embed.set_thumbnail(
            url=f"http://openweathermap.org/img/wn/{icon}@2x.png")
        embed.add_field(name="Description",
                        value=weather_description,
                        inline=False)
        embed.add_field(name="Temperature", value=f"{temp}°C", inline=True)
        embed.add_field(name="Feels Like",
                        value=f"{feels_like}°C",
                        inline=True)
        embed.add_field(name="Humidity", value=f"{humidity}%", inline=True)
        embed.add_field(name="Wind Speed",
                        value=f"{wind_speed} m/s",
                        inline=True)
        embed.set_footer(
            text=
            f"Forecast by openweathermap.org | Last updated: {last_updated_date} {last_updated_time}"
        )

        await interaction.response.send_message(embed=embed)

    def get_country_name(self, country_code):
        # Use pycountry to get the country name from the country code
        try:
            country = pycountry.countries.get(alpha_2=country_code)
            return country.name if country else 'Unknown Country'
        except LookupError:
            return 'Unknown Country'

    def get_embed_color(self, weather_description):
        color_map = {
            'clear': '#00BFFF',  # Sky Blue
            'clouds': '#D3D3D3',  # Light Grey
            'rain': '#1E90FF',  # Dodger Blue
            'drizzle': '#1E90FF',  # Dodger Blue
            'thunderstorm': '#8A2BE2',  # Blue Violet
            'snow': '#00CED1',  # Dark Turquoise
            'mist': '#B0E0E6',  # Powder Blue
            'fog': '#B0E0E6',  # Powder Blue
            'haze': '#F5F5DC',  # Beige
            'sand': '#F4A460',  # Sandy Brown
            'dust': '#D2B48C',  # Tan
            'tornado': '#FF4500',  # Orange Red
            'hurricane': '#FF6347'  # Tomato
        }
        for key, color in color_map.items():
            if key in weather_description.lower():
                return discord.Color(int(color[1:], 16))  # Convert hex to int
        return discord.Color.default()


async def setup(bot: commands.Bot):
    await bot.add_cog(Weather(bot))

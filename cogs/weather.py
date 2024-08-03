import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import datetime


class Weather(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def close(self):
        await self.session.close()

    async def fetch_weather(self, city, days):
        api_key = 'd5a9ac7eb6359f1ecedcf2226a023e57'  # Replace with your OpenWeatherMap API key
        base_url = 'http://api.openweathermap.org/data/2.5/forecast?'
        complete_url = f"{base_url}q={city}&cnt={days * 8}&appid={api_key}&units=metric"

        async with self.session.get(complete_url) as response:
            data = await response.json()
            if data['cod'] == '404':
                return None
            return data

    @app_commands.command(name="weather",
                          description="Get the weather forecast for a city")
    async def weather(self, interaction: discord.Interaction):
        modal = WeatherModal(self)
        await interaction.response.send_modal(modal)


class WeatherModal(discord.ui.Modal, title="Weather Forecast"):
    city = discord.ui.TextInput(label="City",
                                placeholder="Enter city name",
                                required=True)
    days = discord.ui.TextInput(label="Days",
                                placeholder="Enter number of days (1-5)",
                                required=True,
                                max_length=1)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        city = self.city.value
        days = int(self.days.value)

        data = await self.cog.fetch_weather(city, days)
        if data is None or 'list' not in data:
            await interaction.response.send_message(
                f"City {city} not found or invalid response from API. Please check the city name and try again.",
                ephemeral=True)
        else:
            forecasts = self.parse_forecast(data)
            view = WeatherPaginator(forecasts)
            await interaction.response.send_message(embed=view.embeds[0],
                                                    view=view)

    def parse_forecast(self, data):
        forecasts = []
        for entry in data['list']:
            timestamp = entry['dt']
            date_time = datetime.datetime.fromtimestamp(timestamp).strftime(
                '%Y-%m-%d %H:%M:%S')
            weather_desc = entry['weather'][0]['description']
            temp = entry['main']['temp']
            feels_like = entry['main']['feels_like']
            humidity = entry['main']['humidity']
            wind_speed = entry['wind']['speed']

            embed = discord.Embed(title=f"Weather on {date_time}",
                                  description=f"{weather_desc.capitalize()}",
                                  color=discord.Color.blue())
            embed.add_field(name="Temperature", value=f"{temp}°C", inline=True)
            embed.add_field(name="Feels Like",
                            value=f"{feels_like}°C",
                            inline=True)
            embed.add_field(name="Humidity", value=f"{humidity}%", inline=True)
            embed.add_field(name="Wind Speed",
                            value=f"{wind_speed} m/s",
                            inline=True)

            forecasts.append(embed)

        return forecasts


class WeatherPaginator(discord.ui.View):

    def __init__(self, embeds):
        super().__init__(timeout=None)
        self.embeds = embeds
        self.current_page = 0
        self.total_pages = len(embeds)

        self.first_page.disabled = self.current_page == 0
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page == self.total_pages - 1
        self.last_page.disabled = self.current_page == self.total_pages - 1

    async def update_buttons(self):
        self.first_page.disabled = self.current_page == 0
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page == self.total_pages - 1
        self.last_page.disabled = self.current_page == self.total_pages - 1

    @discord.ui.button(emoji='⏪', style=discord.ButtonStyle.primary)
    async def first_page(self, interaction: discord.Interaction,
                         button: discord.ui.Button):
        self.current_page = 0
        await self.update_buttons()
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(emoji='⬅️', style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction: discord.Interaction,
                        button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_buttons()
            await interaction.response.edit_message(
                embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        await interaction.response.delete_message()

    @discord.ui.button(emoji='➡️', style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction,
                        button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await self.update_buttons()
            await interaction.response.edit_message(
                embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(emoji='⏩', style=discord.ButtonStyle.primary)
    async def last_page(self, interaction: discord.Interaction,
                        button: discord.ui.Button):
        self.current_page = self.total_pages - 1
        await self.update_buttons()
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page], view=self)


async def setup(bot):
    await bot.add_cog(Weather(bot))

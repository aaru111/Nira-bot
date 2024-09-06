import discord
import pycountry
from datetime import datetime
import pytz


def get_country_name(country_code):
    try:
        country = pycountry.countries.get(alpha_2=country_code)
        return country.name if country else 'Unknown Country'
    except LookupError:
        return 'Unknown Country'


def get_embed_color(weather_description):
    color_map = {
        'clear': '#00BFFF',
        'clouds': '#D3D3D3',
        'rain': '#1E90FF',
        'drizzle': '#1E90FF',
        'thunderstorm': '#8A2BE2',
        'snow': '#00CED1',
        'mist': '#B0E0E6',
        'fog': '#B0E0E6',
        'haze': '#F5F5DC',
        'sand': '#F4A460',
        'dust': '#D2B48C',
        'tornado': '#FF4500',
        'hurricane': '#FF6347'
    }
    for key, color in color_map.items():
        if key in weather_description.lower():
            return discord.Color(int(color[1:], 16))
    return discord.Color.default()


def create_weather_embed(data, location):
    weather_description = data["weather"][0]["description"].capitalize()
    icon = data["weather"][0]["icon"]
    temp = data["main"]["temp"]
    feels_like = data["main"]["feels_like"]
    humidity = data["main"]["humidity"]
    wind_speed = data["wind"]["speed"]
    country_code = data["sys"]["country"]
    country_name = get_country_name(country_code)

    title = f"Weather in {location.capitalize()} - {country_name}"

    last_updated = datetime.utcfromtimestamp(data["dt"])
    local_tz = pytz.timezone('Asia/Kolkata')
    last_updated_local = last_updated.astimezone(local_tz)
    last_updated_time = last_updated_local.strftime('%I:%M %p')
    last_updated_date = last_updated_local.strftime('%Y-%m-%d')

    embed_color = get_embed_color(weather_description)

    embed = discord.Embed(title=title, color=embed_color)
    embed.set_thumbnail(url=f"http://openweathermap.org/img/wn/{icon}@2x.png")
    embed.add_field(name="Description",
                    value=weather_description,
                    inline=False)
    embed.add_field(name="Temperature", value=f"{temp}°C", inline=True)
    embed.add_field(name="Feels Like", value=f"{feels_like}°C", inline=True)
    embed.add_field(name="Humidity", value=f"{humidity}%", inline=True)
    embed.add_field(name="Wind Speed", value=f"{wind_speed} m/s", inline=True)
    embed.set_footer(
        text=
        f"Forecast by openweathermap.org | Last updated: {last_updated_date} {last_updated_time}"
    )

    return embed

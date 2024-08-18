import discord
from discord.ext import commands
import aiohttp
import os

class PlantIdentifier(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.environ["PLANTNET_API_KEY"]
        self.api_url = "https://my-api.plantnet.org/v2/identify/all"

    @commands.command(name="plant")
    async def identify_plant(self, ctx, image_url: str):
        try:
            async with ctx.typing():
                plant_data = await self.get_plant_data(image_url)
                if plant_data and plant_data.get("results"):
                    embed = self.create_plant_embed(plant_data["results"][0])
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("Sorry, I couldn't identify the plant in the image.")
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    async def get_plant_data(self, image_url: str) -> dict:
        params = {
            "api-key": self.api_key,
            "images": image_url,
            "include-related-images": "false",
            "no-reject": "false",
            "lang": "en",
            "type": "all"
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.api_url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return None
            except aiohttp.ClientError:
                return None

    def create_plant_embed(self, plant_data: dict) -> discord.Embed:
        embed = discord.Embed(
            title="Plant Identification Result",
            color=discord.Color.green(),
            description="Here's what I found based on the image:"
        )

        species = plant_data["species"]
        scientific_name = species["scientificNameWithoutAuthor"]
        common_names = species.get("commonNames", ["N/A"])
        family = species["family"].get("scientificNameWithoutAuthor", "N/A")
        genus = species["genus"].get("scientificNameWithoutAuthor", "N/A")
        confidence = plant_data["score"]

        embed.add_field(name="Scientific Name", value=f"*{scientific_name}*", inline=False)
        embed.add_field(name="Common Name(s)", value=", ".join(common_names[:3]), inline=False)
        embed.add_field(name="Family", value=family, inline=True)
        embed.add_field(name="Genus", value=genus, inline=True)
        embed.add_field(name="Confidence", value=f"{confidence:.2%}", inline=False)

        if plant_data.get("images"):
            embed.set_thumbnail(url=plant_data["images"][0]["url"]["m"])

        embed.set_footer(text="Data provided by PlantNet")
        return embed

async def setup(bot):
    await bot.add_cog(PlantIdentifier(bot))
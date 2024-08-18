import discord
from discord.ext import commands
import aiohttp
import os
import asyncio


class PlantView(discord.ui.View):

    def __init__(self, pages):
        super().__init__(timeout=60)
        self.pages = pages
        self.current_page = 0
        self.last_interaction = asyncio.get_event_loop().time()

    async def interaction_check(self,
                                interaction: discord.Interaction) -> bool:
        self.last_interaction = asyncio.get_event_loop().time()
        return True

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.blurple)
    async def previous_button(self, interaction: discord.Interaction,
                              button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(
                embed=self.pages[self.current_page], view=self)
        else:
            await interaction.response.send_message(
                "You're already on the first page!", ephemeral=True)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.success)
    async def next_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await interaction.response.edit_message(
                embed=self.pages[self.current_page], view=self)
        else:
            await interaction.response.send_message("No more pages left!",
                                                    ephemeral=True)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)


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
                    pages = self.create_plant_embeds(
                        plant_data["results"][:5])  # Limit to top 5 results
                    view = PlantView(pages)
                    message = await ctx.send(embed=pages[0], view=view)
                    view.message = message
                    self.bot.loop.create_task(self.check_view_timeout(view))
                else:
                    await ctx.send(
                        "Sorry, I couldn't identify the plant in the image.")
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    async def check_view_timeout(self, view):
        while not view.is_finished():
            if asyncio.get_event_loop().time() - view.last_interaction > 60:
                await view.on_timeout()
                break
            await asyncio.sleep(1)

    async def get_plant_data(self, image_url: str) -> dict:
        params = {
            "api-key": self.api_key,
            "images": image_url,
            "include-related-images": "true",
            "no-reject": "false",
            "lang": "en",
            "type": "all"
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.api_url,
                                       params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return None
            except aiohttp.ClientError:
                return None

    def create_plant_embeds(self, plant_results: list) -> list:
        pages = []
        for index, plant_data in enumerate(plant_results, start=1):
            embed = discord.Embed(
                title=f"Plant Identification Result (Guess {index})",
                color=discord.Color.green(),
                description="Here's what I found based on the image:")

            species = plant_data["species"]
            scientific_name = species["scientificNameWithoutAuthor"]
            common_names = species.get("commonNames", ["N/A"])
            family = species["family"].get("scientificNameWithoutAuthor",
                                           "N/A")
            genus = species["genus"].get("scientificNameWithoutAuthor", "N/A")
            confidence = plant_data["score"]

            embed.add_field(name="Scientific Name",
                            value=f"*{scientific_name}*",
                            inline=False)
            embed.add_field(name="Common Name(s)",
                            value=", ".join(common_names[:3]),
                            inline=False)
            embed.add_field(name="Family", value=family, inline=True)
            embed.add_field(name="Genus", value=genus, inline=True)
            embed.add_field(name="Confidence",
                            value=f"{confidence:.2%}",
                            inline=False)

            # Add Wikipedia link
            wiki_link = f"https://en.wikipedia.org/wiki/{scientific_name.replace(' ', '_')}"
            embed.add_field(name="Learn More",
                            value=f"[Wikipedia]({wiki_link})",
                            inline=False)

            if "images" in plant_data and len(plant_data["images"]) > 0:
                image_url = plant_data["images"][0].get("url", {}).get("m")
                if image_url:
                    embed.set_thumbnail(url=image_url)

            embed.set_footer(
                text=
                f"Data provided by PlantNet | Page {index} of {len(plant_results)}"
            )
            pages.append(embed)

        return pages


async def setup(bot):
    await bot.add_cog(PlantIdentifier(bot))

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
import asyncio
from io import BytesIO
from PIL import Image
from discord.app_commands import Choice
from typing import Optional, List, Dict
from collections import defaultdict
import time


# OCR Service for text recognition
class OCRService:

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = "https://api.ocr.space/parse/image"

    async def extract_text(self, image_data: bytes) -> Dict:
        data = aiohttp.FormData()
        data.add_field('apikey', self.api_key)
        data.add_field('language', 'eng')
        data.add_field('file',
                       image_data,
                       filename='image.jpg',
                       content_type='image/jpeg')
        data.add_field('detectOrientation', 'true')
        data.add_field('scale', 'true')
        data.add_field('isTable', 'false')
        data.add_field('OCREngine', '2')

        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, data=data,
                                    ssl=False) as response:
                return await response.json()


# UI Modal for page navigation in the Paginator
class GoToPageModal(discord.ui.Modal, title="Go to Page"):
    page_number = discord.ui.TextInput(label="Page Number",
                                       style=discord.TextStyle.short,
                                       placeholder="Enter the page number",
                                       required=True)

    def __init__(self, paginator: 'Paginator'):
        super().__init__()
        self.paginator = paginator

    async def on_submit(self, interaction: discord.Interaction):
        try:
            page_number = int(self.page_number.value) - 1
            if 0 <= page_number < len(self.paginator.pages):
                self.paginator.current_page = page_number
                await self.paginator.update_embed(interaction)
            else:
                await interaction.response.send_message("Invalid page number.",
                                                        ephemeral=True)
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number.", ephemeral=True)


# Base class for paginated views
class BasePaginator(discord.ui.View):

    def __init__(self, timeout: int = 30):
        super().__init__(timeout=timeout)
        self.current_page = 0
        self.message: Optional[discord.Message] = None

    async def on_timeout(self):
        if self.message:
            await self.message.edit(view=None)

    async def update_embed(self,
                           interaction: discord.Interaction,
                           embed: discord.Embed,
                           initial: bool = False):
        if initial:
            self.message = await interaction.followup.send(embed=embed,
                                                           view=self)
        else:
            await self.message.edit(embed=embed, view=self)


# Paginator for navigating through pages of text results
class Paginator(BasePaginator):

    def __init__(self, interaction: discord.Interaction, pages: List[str],
                 image_url: str):
        super().__init__(timeout=30)
        self.interaction = interaction
        self.pages = pages
        self.image_url = image_url

    async def update_embed(self,
                           interaction: discord.Interaction,
                           initial: bool = False):
        embed = discord.Embed(title="Image Text Recognition",
                              color=discord.Color.blue())
        embed.set_thumbnail(url=self.image_url)
        embed.add_field(
            name=
            f"Detected Text (Page {self.current_page + 1}/{len(self.pages)})",
            value=self.pages[self.current_page],
            inline=False)
        await super().update_embed(interaction, embed, initial)

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.primary)
    async def prev_page(self, button: discord.ui.Button,
                        interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_embed(interaction)
        else:
            await interaction.response.send_message(
                "You're already on the first page.", ephemeral=True)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_page(self, button: discord.ui.Button,
                        interaction: discord.Interaction):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await self.update_embed(interaction)
        else:
            await interaction.response.send_message(
                "You're already on the last page.", ephemeral=True)

    @discord.ui.button(label="Go to", style=discord.ButtonStyle.secondary)
    async def go_to_page(self, button: discord.ui.Button,
                         interaction: discord.Interaction):
        await interaction.response.send_modal(GoToPageModal(self))


# Plant View for plant identification
class PlantView(BasePaginator):

    def __init__(self, pages: List[discord.Embed]):
        super().__init__(timeout=60)
        self.pages = pages

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.blurple)
    async def previous_button(self, button: discord.ui.Button,
                              interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(
                embed=self.pages[self.current_page], view=self)
        else:
            await interaction.response.send_message(
                "You're already on the first page!", ephemeral=True)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.success)
    async def next_button(self, button: discord.ui.Button,
                          interaction: discord.Interaction):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await interaction.response.edit_message(
                embed=self.pages[self.current_page], view=self)
        else:
            await interaction.response.send_message("No more pages left!",
                                                    ephemeral=True)


# Main Imagery Cog
class Imagery(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.ocr_service = OCRService(os.environ["ITT_KEY"])
        self.api_key = os.environ["PLANTNET_API_KEY"]
        self.api_url = "https://my-api.plantnet.org/v2/identify/all"
        self.cooldowns = defaultdict(lambda: 0)
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.session.close()

    async def cooldown_check(self, interaction: discord.Interaction) -> bool:
        current_time = time.time()
        if current_time - self.cooldowns[(interaction.guild_id,
                                          interaction.user.id)] < 5:
            return False
        self.cooldowns[(interaction.guild_id,
                        interaction.user.id)] = current_time
        return True

    @app_commands.command(
        name="identify",
        description="Identify text from an image or image URL")
    @app_commands.describe(
        image="Upload an image or provide an image URL",
        url="URL of the image (optional if image is uploaded)")
    async def identify(self,
                       interaction: discord.Interaction,
                       image: Optional[discord.Attachment] = None,
                       url: Optional[str] = None):
        if not image and not url:
            await interaction.response.send_message(
                "Please provide either an image or an image URL.")
            return
        await interaction.response.defer()
        try:
            image_data = await self.get_image_data(image, url)
            result = await self.ocr_service.extract_text(image_data)
            if result.get('IsErroredOnProcessing'):
                error_message = result.get('ErrorMessage', 'Unknown error')
                await interaction.followup.send(
                    f"There was an error processing the image: {error_message}"
                )
                return
            parsed_results = result.get("ParsedResults", [])
            if not parsed_results:
                await interaction.followup.send(
                    "No text could be extracted from the image. Please ensure the image is clear and contains readable text."
                )
                return
            text_detected = parsed_results[0].get("ParsedText", "").strip()
            if not text_detected:
                await interaction.followup.send(
                    "No text was detected in the image. Please try with a different image or ensure the text is clearly visible."
                )
                return
            pages = self.format_text(text_detected)
            if len(pages) > 1:
                paginator = Paginator(interaction, pages,
                                      image.url if image else url)
                await paginator.update_embed(interaction, initial=True)
            else:
                await interaction.followup.send(embed=discord.Embed(
                    title="Image Text Recognition",
                    description=pages[0],
                    color=discord.Color.blue()).set_thumbnail(
                        url=image.url if image else url))
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}")

    @app_commands.command(name="plant",
                          description="Identify a plant from an image")
    @app_commands.describe(
        image="Upload an image of the plant",
        image_url="Or provide a URL to an image of the plant",
        language="Select the language for plant information (default: English)"
    )
    @app_commands.choices(language=[
        Choice(name="English", value="en"),
        Choice(name="French", value="fr"),
        Choice(name="German", value="de"),
        Choice(name="Spanish", value="es")
    ])
    async def identify_plant(self,
                             interaction: discord.Interaction,
                             image: discord.Attachment = None,
                             image_url: str = None,
                             language: str = "en"):
        if not await self.cooldown_check(interaction):
            await interaction.response.send_message(
                "Please wait 5 seconds before using this command again.",
                ephemeral=True)
            return
        if not image and not image_url:
            await interaction.response.send_message(
                "Please provide either an image attachment or an image URL.",
                ephemeral=True)
            return
        await interaction.response.defer()
        try:
            jpg_image = await self.convert_to_jpg(
                image.url if image else image_url)
            plant_data = await self.get_plant_data(jpg_image, language)
            if plant_data and plant_data.get("results"):
                pages = self.create_plant_embeds(plant_data["results"][:5],
                                                 language)
                view = PlantView(pages)
                message = await interaction.followup.send(embed=pages[0],
                                                          view=view)
                view.message = message
                self.bot.loop.create_task(self.check_view_timeout(view))
            else:
                await interaction.followup.send(
                    "Sorry, I couldn't identify the plant in the image.")
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}")

    async def check_view_timeout(self, view: PlantView):
        while not view.is_finished():
            if asyncio.get_event_loop().time() - view.last_interaction > 60:
                await view.on_timeout()
                break
            await asyncio.sleep(1)

    async def get_image_data(self, attachment: Optional[discord.Attachment],
                             url: Optional[str]) -> bytes:
        if attachment:
            return await self.process_image(await attachment.read())
        elif url:
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise ValueError(
                        f"Failed to fetch image from URL. Status code: {response.status}"
                    )
                return await self.process_image(await response.read())

    async def process_image(self, image_data: bytes) -> bytes:
        with Image.open(BytesIO(image_data)) as img:
            if img.format not in ['JPEG', 'PNG']:
                buffer = BytesIO()
                img = img.convert('RGB')
                img.save(buffer, format="JPEG", quality=95)
                return buffer.getvalue()
            return image_data

    async def convert_to_jpg(self, image_url: str) -> BytesIO:
        async with self.session.get(image_url) as response:
            if response.status == 200:
                image_data = await response.read()
                image = Image.open(BytesIO(image_data))
                jpg_image = BytesIO()
                image.convert('RGB').save(jpg_image, format='JPEG')
                jpg_image.seek(0)
                return jpg_image
            else:
                raise Exception("Failed to fetch the image")

    async def get_plant_data(self, jpg_image: BytesIO, language: str) -> Dict:
        data = aiohttp.FormData()
        data.add_field('images',
                       jpg_image,
                       filename='image.jpg',
                       content_type='image/jpeg')
        params = {
            "api-key": self.api_key,
            "include-related-images": "true",
            "no-reject": "false",
            "lang": language,
            "type": "all"
        }
        async with self.session.post(self.api_url, data=data,
                                     params=params) as response:
            if response.status == 200:
                return await response.json()
            return {}

    def create_plant_embeds(self, plant_results: List[Dict],
                            language: str) -> List[discord.Embed]:
        pages = []
        for index, plant_data in enumerate(plant_results, start=1):
            embed = discord.Embed(
                title=f"Plant Identification Result (Guess {index})",
                color=discord.Color.green(),
                description="Here's what I found based on the image:")
            species = plant_data["species"]
            embed.add_field(
                name="Scientific Name",
                value=f"*{species['scientificNameWithoutAuthor']}*",
                inline=False)
            embed.add_field(name="Common Name(s)",
                            value=", ".join(
                                species.get("commonNames", ["N/A"])[:3]),
                            inline=False)
            embed.add_field(name="Family",
                            value=species["family"].get(
                                "scientificNameWithoutAuthor", "N/A"),
                            inline=True)
            embed.add_field(name="Genus",
                            value=species["genus"].get(
                                "scientificNameWithoutAuthor", "N/A"),
                            inline=True)
            embed.add_field(name="Confidence",
                            value=f"{plant_data['score']:.2%}",
                            inline=False)
            wiki_link = f"https://{language}.wikipedia.org/wiki/{species['scientificNameWithoutAuthor'].replace(' ', '_')}"
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

    @staticmethod
    def format_text(text: str) -> List[str]:
        max_field_length = 1024
        lines = text.splitlines()
        formatted_chunks = []
        current_chunk = ""
        for line in lines:
            stripped_line = line.rstrip()
            if len(current_chunk) + len(stripped_line) + 1 > max_field_length:
                formatted_chunks.append(f"```\n{current_chunk.strip()}```")
                current_chunk = stripped_line + '\n'
            else:
                current_chunk += stripped_line + '\n'
        if current_chunk.strip():
            formatted_chunks.append(f"```\n{current_chunk.strip()}```")
        return formatted_chunks


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Imagery(bot))

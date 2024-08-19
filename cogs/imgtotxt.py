import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
from io import BytesIO
from PIL import Image
from typing import Optional


class OCRService:

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = "https://api.ocr.space/parse/image"

    async def extract_text(self, image_data: bytes) -> dict:
        async with aiohttp.ClientSession() as session:
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
            data.add_field('OCREngine', '2')  # Using more advanced OCR engine

            async with session.post(self.url, data=data) as response:
                return await response.json()


class ImageRecognition(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ocr_service = OCRService(os.environ["ITT_KEY"])

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

            await self.send_embed(interaction, image.url if image else url,
                                  text_detected)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}")
            import traceback
            print(f"Exception occurred: {traceback.format_exc()}")

    async def get_image_data(self, attachment: Optional[discord.Attachment],
                             url: Optional[str]) -> bytes:
        if attachment:
            return await self.process_image(await attachment.read())
        elif url:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
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

    async def send_embed(self, interaction: discord.Interaction,
                         image_url: str, text_detected: str):
        embed = discord.Embed(title="Image Text Recognition",
                              color=discord.Color.blue())
        embed.set_thumbnail(url=image_url)

        formatted_text = self.format_text(text_detected)
        for i, chunk in enumerate(formatted_text, 1):
            embed.add_field(name=f"Detected Text (Part {i})",
                            value=chunk,
                            inline=False)

        await interaction.followup.send(embed=embed)

    @staticmethod
    def format_text(text: str) -> list[str]:
        # Preserve newlines and spaces
        lines = text.split('\n')
        formatted_chunks = []
        current_chunk = ""

        for line in lines:
            if len(current_chunk) + len(line) + 1 > 1000:  # +1 for newline
                formatted_chunks.append(f"```\n{current_chunk}```")
                current_chunk = line + '\n'
            else:
                current_chunk += line + '\n'

        if current_chunk:
            formatted_chunks.append(f"```\n{current_chunk}```")

        return formatted_chunks


async def setup(bot: commands.Bot):
    await bot.add_cog(ImageRecognition(bot))

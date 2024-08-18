import discord
from discord.ext import commands
from discord import app_commands
import requests
import os
from io import BytesIO
from PIL import Image

class OCRService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.url = "https://api.ocr.space/parse/image"

    async def extract_text(self, image_data):
        payload = {
            "apikey": self.api_key,
            "language": "eng",
        }
        files = {"filename": ("image.jpg", image_data)}
        response = requests.post(self.url, data=payload, files=files)
        return response.json()

class ImageRecognition(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ocr_service = OCRService(os.environ["ITT_KEY"])

    @app_commands.command(name="identify", description="Identify text from an image")
    async def identify(self, interaction: discord.Interaction, image: discord.Attachment):
        await interaction.response.defer()

        image_data = await self.process_image(image)
        result = await self.ocr_service.extract_text(image_data)

        if result['IsErroredOnProcessing']:
            await interaction.followup.send("There was an error processing the image.")
            return

        text_detected = result.get("ParsedResults", [{}])[0].get("ParsedText", "")
        await self.send_embed(interaction, image.url, text_detected)

    async def process_image(self, image):
        image_data = await image.read()
        if image.content_type not in ['image/jpeg', 'image/png']:
            img = Image.open(BytesIO(image_data))
            buffer = BytesIO()
            img.save(buffer, format="JPEG")
            image_data = buffer.getvalue()
        return image_data

    async def send_embed(self, interaction, image_url, text_detected):
        embed = discord.Embed(title="Image Text Recognition", color=discord.Color.blue())
        embed.set_thumbnail(url=image_url)
        
        if text_detected:
            formatted_text = self.format_text(text_detected)
            embed.add_field(name="Detected Text", value=formatted_text, inline=False)
        else:
            embed.add_field(name="Result", value="No text detected.", inline=False)

        await interaction.followup.send(embed=embed)

    def format_text(self, text):
        if len(text) > 1024:
            text = text[:1021] + "..."
        return f"```{text}```"

async def setup(bot):
    await bot.add_cog(ImageRecognition(bot))
    
import discord
from discord.ext import commands
from discord import app_commands
import requests
import os

class ImageRecognition(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.environ["ITT_KEY"]
    @app_commands.command(name="identify", description="Identify text from an image")
    async def identify(self, interaction: discord.Interaction, image: discord.Attachment):
        await interaction.response.defer()  # Acknowledge the interaction

        # Download the image
        image_data = await image.read()

        # Prepare the request to OCR.Space
        api_key = self.api_key
        url = "https://api.ocr.space/parse/image"
        payload = {
            "apikey": api_key,
            "language": "eng",  # You can change the language if needed
        }
        files = {"filename": ("image.jpg", image_data)}

        response = requests.post(url, data=payload, files=files)
        result = response.json()

        # Process the OCR result
        if result['IsErroredOnProcessing']:
            await interaction.followup.send("There was an error processing the image.")
            return

        text_detected = result.get("ParsedResults", [{}])[0].get("ParsedText", "")

        # Create and send the embed
        embed = discord.Embed(title="Image Text Recognition", color=discord.Color.blue())
        embed.set_image(url=image.url)
        embed.add_field(name="Detected Text", value=text_detected or "No text detected.", inline=False)
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ImageRecognition(bot))

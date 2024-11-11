import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from .modules.encodemod import encode_text, decode_text


class EncodingCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="encode",
        description="Encode text to base64, hex, or binary (up to 5 layers)")
    @app_commands.describe(text="The text to encode",
                           encoding="Choose encoding type",
                           layers="Number of encoding layers (1-5)")
    @app_commands.choices(encoding=[
        app_commands.Choice(name="base64", value="base64"),
        app_commands.Choice(name="hex", value="hex"),
        app_commands.Choice(name="binary", value="binary")
    ])
    async def encode(self,
                     interaction: discord.Interaction,
                     text: str,
                     encoding: str,
                     layers: Optional[int] = 1):
        await interaction.response.defer(ephemeral=True)
        await encode_text(interaction, text, encoding, layers)

    @app_commands.command(
        name="decode",
        description="Decode text with automatic format detection")
    @app_commands.describe(encoded_text="The encoded text to decode")
    async def decode(self, interaction: discord.Interaction,
                     encoded_text: str):
        await interaction.response.defer(ephemeral=True)
        await decode_text(interaction, encoded_text)

    @encode.error
    @decode.error
    async def error_handler(self, interaction: discord.Interaction,
                            error: app_commands.AppCommandError):
        await interaction.followup.send(
            f"❌ {str(error.original) if isinstance(error, app_commands.CommandInvokeError) else str(error)}",
            ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EncodingCog(bot))

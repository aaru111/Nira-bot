import discord
from discord import app_commands
from discord.ext import commands
import base64
from typing import Optional
import re
import binascii


class EncodingCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.MAX_ENCODE_LAYERS = 25
        self.MAX_INPUT_LENGTH = 10240
        self.MAX_OUTPUT_LENGTH = 10240

    @staticmethod
    def cleanup_text(text: str) -> str:
        return re.sub(r'```\w*\n?|\n?```', '', text).strip()

    @staticmethod
    def truncate_text(text: str, max_length: int = 1000) -> str:
        return text if len(text) <= max_length else text[:max_length] + "..."

    @staticmethod
    def format_output(text: str) -> str:
        return f"```{text}```"

    @staticmethod
    def text_to_hex(text: str) -> str:
        return text.encode('utf-8').hex()

    @staticmethod
    def hex_to_text(hex_str: str) -> str:
        try:
            return bytes.fromhex(hex_str.replace('0x', '').replace(
                ' ', '')).decode('utf-8')
        except (ValueError, binascii.Error) as e:
            raise ValueError(f"Invalid hex string: {str(e)}")

    def try_decode(self, text: str) -> tuple[str, str]:
        """
        Try to decode text using both base64 and hex methods.
        Returns tuple of (decoded_text, encoding_method_used).
        Raises ValueError if neither method works.
        """
        # Try base64 decoding
        try:
            decoded = base64.b64decode(text, validate=True).decode('utf-8')
            return decoded, "base64"
        except (binascii.Error, UnicodeDecodeError):
            pass

        # Try hex decoding
        try:
            return self.hex_to_text(text), "hex"
        except ValueError:
            pass

        raise ValueError("Text is not valid base64 or hex encoded")

    @app_commands.command(
        name="encode",
        description="Encode text to base64 or hex (optionally multiple times)")
    @app_commands.describe(
        text="The text you want to encode",
        encoding="Encoding type (base64 or hex)",
        layers="Number of encoding layers (default: 1, max: 25)")
    @app_commands.choices(encoding=[
        app_commands.Choice(name="base64", value="base64"),
        app_commands.Choice(name="hex", value="hex")
    ])
    async def encode(self,
                     interaction: discord.Interaction,
                     text: str,
                     encoding: str,
                     layers: Optional[int] = 1):
        await interaction.response.defer(ephemeral=True)

        text = self.cleanup_text(text)
        if len(text) > self.MAX_INPUT_LENGTH:
            await interaction.followup.send(
                f"❌ Input text is too long! Maximum length is {self.MAX_INPUT_LENGTH} characters.",
                ephemeral=True)
            return

        layers = max(1, min(layers, self.MAX_ENCODE_LAYERS))
        encode_steps = [f"**Original:** {text}"]
        current_text = text

        for i in range(layers):
            try:
                current_text = (base64.b64encode(
                    current_text.encode('utf-8')).decode('utf-8')
                                if encoding == "base64" else
                                self.text_to_hex(current_text))
                if len(current_text) > self.MAX_OUTPUT_LENGTH:
                    await interaction.followup.send(
                        "❌ Output text would be too long! Try fewer encoding layers.",
                        ephemeral=True)
                    return
                encode_steps.append(
                    f"**Layer {i + 1}:** {self.truncate_text(current_text, 100)}"
                )
            except Exception as e:
                await interaction.followup.send(
                    f"❌ Error during encoding at layer {i + 1}: {str(e)}",
                    ephemeral=True)
                return

        response = "\n".join(
            encode_steps
        ) + f"\n\n**Final encoded result:**\n{self.format_output(current_text)}"
        await interaction.followup.send(
            f"✅ Successfully encoded {layers} layer(s)!\n\n{response}",
            ephemeral=True)

    @app_commands.command(
        name="decode",
        description=
        "Automatically decode base64 or hex text (handles multiple layers)")
    @app_commands.describe(encoded_text="The encoded text you want to decode")
    async def decode(self, interaction: discord.Interaction,
                     encoded_text: str):
        await interaction.response.defer(ephemeral=True)

        encoded_text = self.cleanup_text(encoded_text)
        if len(encoded_text) > self.MAX_INPUT_LENGTH:
            await interaction.followup.send(
                f"❌ Input text is too long! Maximum length is {self.MAX_INPUT_LENGTH} characters.",
                ephemeral=True)
            return

        current_text = encoded_text
        decode_steps = []
        for i in range(self.MAX_ENCODE_LAYERS):
            try:
                current_text, method = self.try_decode(current_text)
                decode_steps.append(
                    f"{i + 1}. ({method}) {self.truncate_text(current_text, 100)}"
                )
                if len(current_text) > self.MAX_OUTPUT_LENGTH:
                    await interaction.followup.send(
                        "❌ Output text would be too long! The input might be encoded too many times.",
                        ephemeral=True)
                    return
            except ValueError:
                break

        if not decode_steps:
            response = "❌ The provided text is not valid base64 or hex encoded."
        else:
            response = f"✅ Successfully decoded {len(decode_steps)} layer(s)!\n\n" + "\n".join(
                decode_steps)
            response += f"\n\n**Final decoded result:**\n{self.format_output(current_text)}"

        await interaction.followup.send(response, ephemeral=True)

    @encode.error
    @decode.error
    async def error_handler(self, interaction: discord.Interaction,
                            error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandInvokeError):
            await interaction.followup.send(
                f"❌ An error occurred: {str(error.original)}", ephemeral=True)
        else:
            await interaction.followup.send(
                f"❌ An error occurred: {str(error)}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EncodingCog(bot))

import discord
from discord import app_commands
from discord.ext import commands
import base64
from typing import Optional, Tuple
import re
import binascii


class EncodingCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.MAX_ENCODE_LAYERS = 5  # Changed from 25 to 5
        self.MAX_INPUT_LENGTH = 10240
        self.MAX_OUTPUT_LENGTH = 10240
        # Compile regex for efficiency
        self.code_block_re = re.compile(r'```\w*\n?|\n?```')

    def cleanup_text(self, text: str) -> str:
        """Remove Discord markdown code block syntax."""
        return self.code_block_re.sub('', text).strip()

    @staticmethod
    def truncate_text(text: str, max_length: int = 1000) -> str:
        """Truncate text if it exceeds max_length."""
        return text if len(text) <= max_length else f"{text[:max_length]}..."

    @staticmethod
    def format_output(text: str) -> str:
        """Format text for Discord code block."""
        return f"```{text}```"

    @staticmethod
    def text_to_hex(text: str) -> str:
        """Encode text to hexadecimal format."""
        return text.encode('utf-8').hex()

    @staticmethod
    def hex_to_text(hex_str: str) -> str:
        """Decode hexadecimal string to text."""
        try:
            return bytes.fromhex(hex_str).decode('utf-8')
        except (ValueError, binascii.Error) as e:
            raise ValueError(f"Invalid hex string: {e}")

    @staticmethod
    def base64_to_text(text: str) -> str:
        """Decode base64 string to text."""
        try:
            return base64.b64decode(text, validate=True).decode('utf-8')
        except (binascii.Error, UnicodeDecodeError):
            raise ValueError("Invalid base64 string")

    def try_decode(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Attempt to decode text using both base64 and hex.
        Returns tuple (decoded_text, method) or (None, None) if decoding fails.
        """
        decode_methods = {
            "base64": self.base64_to_text,
            "hex": self.hex_to_text
        }
        for method, func in decode_methods.items():
            try:
                return func(text), method
            except ValueError:
                continue
        return None, None

    @app_commands.command(
        name="encode",
        description="Encode text to base64 or hex (supports up to 5 layers)"
    )  # Updated description
    @app_commands.describe(
        text="The text to encode",
        encoding="Choose encoding type (base64 or hex)",
        layers="Number of encoding layers (default: 1, max: 5)"
    )  # Updated description
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
            return await interaction.followup.send(
                f"❌ Input text exceeds {self.MAX_INPUT_LENGTH} characters.",
                ephemeral=True)

        if layers > self.MAX_ENCODE_LAYERS:
            return await interaction.followup.send(
                f"❌ Maximum allowed encoding layers is {self.MAX_ENCODE_LAYERS}.",
                ephemeral=True)

        layers = min(max(1, layers), self.MAX_ENCODE_LAYERS)
        current_text = text
        encode_steps = [f"**Original:** {self.truncate_text(text, 100)}"]

        try:
            encode_func = (base64.b64encode
                           if encoding == "base64" else self.text_to_hex)
            for i in range(layers):
                current_text = (encode_func(current_text.encode()).decode()
                                if encoding == "base64" else
                                encode_func(current_text))

                if len(current_text) > self.MAX_OUTPUT_LENGTH:
                    return await interaction.followup.send(
                        "❌ Output text too long after encoding. Reduce layers.",
                        ephemeral=True)

                encode_steps.append(
                    f"**Layer {i + 1}:** {self.truncate_text(current_text, 100)}"
                )

        except Exception as e:
            return await interaction.followup.send(
                f"❌ Error during encoding: {e}", ephemeral=True)

        response = "\n".join(
            encode_steps
        ) + f"\n\n**Final Encoded Result:**\n{self.format_output(current_text)}"
        await interaction.followup.send(
            f"✅ Encoded {layers} layers successfully!\n\n{response}",
            ephemeral=True)

    @app_commands.command(
        name="decode",
        description=
        "Decode text (automatically detects and decodes all layers of base64/hex)"
    )
    @app_commands.describe(encoded_text="The encoded text to decode")
    async def decode(self, interaction: discord.Interaction,
                     encoded_text: str):
        await interaction.response.defer(ephemeral=True)

        encoded_text = self.cleanup_text(encoded_text)
        if len(encoded_text) > self.MAX_INPUT_LENGTH:
            return await interaction.followup.send(
                f"❌ Input text exceeds {self.MAX_INPUT_LENGTH} characters.",
                ephemeral=True)

        current_text = encoded_text
        decode_steps = []

        # No maximum layer limit for decoding
        while True:
            decoded, method = self.try_decode(current_text)
            if decoded is None:
                break

            decode_steps.append(
                f"{len(decode_steps) + 1}. ({method}) {self.truncate_text(decoded, 100)}"
            )
            current_text = decoded

            if len(current_text) > self.MAX_OUTPUT_LENGTH:
                return await interaction.followup.send(
                    "❌ Decoded output too long.", ephemeral=True)

        if not decode_steps:
            response = "❌ Unable to decode the provided text."
        else:
            response = f"✅ Decoded {len(decode_steps)} layers:\n" + "\n".join(
                decode_steps)
            response += f"\n\n**Final Decoded Result:**\n{self.format_output(current_text)}"

        await interaction.followup.send(response, ephemeral=True)

    @encode.error
    @decode.error
    async def error_handler(self, interaction: discord.Interaction,
                            error: app_commands.AppCommandError):
        error_message = f"❌ Error: {str(error.original) if isinstance(error, app_commands.CommandInvokeError) else str(error)}"
        await interaction.followup.send(error_message, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EncodingCog(bot))

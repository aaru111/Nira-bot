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
        self.MAX_ENCODE_LAYERS = 5
        self.MAX_INPUT_LENGTH = 10240
        self.MAX_OUTPUT_LENGTH = 10240
        self.code_block_re = re.compile(r'```\w*\n?|\n?```')

    def cleanup_text(self, text: str) -> str:
        return self.code_block_re.sub('', text).strip()

    @staticmethod
    def truncate_text(text: str, max_length: int = 1000) -> str:
        return text if len(text) <= max_length else f"{text[:max_length]}..."

    @staticmethod
    def format_output(text: str) -> str:
        return f"```{text}```"

    @staticmethod
    def text_to_hex(text: str) -> str:
        return text.encode('utf-8').hex()

    @staticmethod
    def text_to_binary(text: str) -> str:
        return ''.join(format(ord(char), '08b') for char in text)

    @staticmethod
    def binary_to_text(binary_str: str) -> str:
        try:
            binary_str = ''.join(binary_str.split())
            if len(binary_str) % 8 != 0:
                raise ValueError("Binary string length must be multiple of 8")
            return ''.join(
                chr(int(binary_str[i:i + 8], 2))
                for i in range(0, len(binary_str), 8))
        except Exception as e:
            raise ValueError(f"Invalid binary string: {e}")

    @staticmethod
    def hex_to_text(hex_str: str) -> str:
        try:
            return bytes.fromhex(hex_str).decode('utf-8')
        except (ValueError, binascii.Error) as e:
            raise ValueError(f"Invalid hex string: {e}")

    @staticmethod
    def base64_to_text(text: str) -> str:
        try:
            return base64.b64decode(text, validate=True).decode('utf-8')
        except (binascii.Error, UnicodeDecodeError):
            raise ValueError("Invalid base64 string")

    def try_decode(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        decode_methods = {
            "binary": self.binary_to_text,
            "base64": self.base64_to_text,
            "hex": self.hex_to_text
        }

        for method, func in decode_methods.items():
            try:
                decoded = func(text)
                return decoded, method
            except ValueError:
                continue
        return None, None

    async def respond_with_error(self, interaction: discord.Interaction,
                                 message: str):
        await interaction.followup.send(f"❌ {message}", ephemeral=True)

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
        text = self.cleanup_text(text)

        if len(text) > self.MAX_INPUT_LENGTH:
            return await self.respond_with_error(
                interaction,
                f"Input text exceeds {self.MAX_INPUT_LENGTH} characters.")

        layers = min(max(1, layers), self.MAX_ENCODE_LAYERS)
        encode_funcs = {
            "base64": lambda x: base64.b64encode(x.encode()).decode(),
            "hex": self.text_to_hex,
            "binary": self.text_to_binary
        }

        current_text = text
        encode_steps = [f"**Original:** {self.truncate_text(text, 100)}"]

        try:
            encode_func = encode_funcs[encoding]
            for i in range(layers):
                current_text = encode_func(current_text)
                if len(current_text) > self.MAX_OUTPUT_LENGTH:
                    return await self.respond_with_error(
                        interaction,
                        "Output text too long after encoding. Reduce layers.")
                encode_steps.append(
                    f"**Layer {i + 1}:** {self.truncate_text(current_text, 100)}"
                )

        except Exception as e:
            return await self.respond_with_error(
                interaction, f"Error during encoding: {e}")

        response = "\n".join(
            encode_steps
        ) + f"\n\n**Final Encoded Result:**\n{self.format_output(current_text)}"
        await interaction.followup.send(
            f"✅ Encoded {layers} layers successfully!\n\n{response}",
            ephemeral=True)

    @app_commands.command(
        name="decode",
        description="Decode text with automatic format detection")
    @app_commands.describe(encoded_text="The encoded text to decode")
    async def decode(self, interaction: discord.Interaction,
                     encoded_text: str):
        await interaction.response.defer(ephemeral=True)
        encoded_text = self.cleanup_text(encoded_text)

        if len(encoded_text) > self.MAX_INPUT_LENGTH:
            return await self.respond_with_error(
                interaction,
                f"Input text exceeds {self.MAX_INPUT_LENGTH} characters.")

        current_text = encoded_text
        decode_steps = []

        while True:
            decoded, method = self.try_decode(current_text)
            if decoded is None:
                break
            decode_steps.append(
                f"{len(decode_steps) + 1}. ({method}) {self.truncate_text(decoded, 100)}"
            )
            current_text = decoded
            if len(current_text) > self.MAX_OUTPUT_LENGTH:
                return await self.respond_with_error(
                    interaction, "Decoded output too long.")

        response = "❌ Unable to decode the provided text." if not decode_steps else \
            f"✅ Decoded {len(decode_steps)} layers:\n" + "\n".join(decode_steps) + \
            f"\n\n**Final Decoded Result:**\n{self.format_output(current_text)}"
        await interaction.followup.send(response, ephemeral=True)

    @encode.error
    @decode.error
    async def error_handler(self, interaction: discord.Interaction,
                            error: app_commands.AppCommandError):
        await self.respond_with_error(
            interaction,
            str(error.original) if isinstance(
                error, app_commands.CommandInvokeError) else str(error))


async def setup(bot: commands.Bot):
    await bot.add_cog(EncodingCog(bot))

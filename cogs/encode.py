import discord
from discord import app_commands
from discord.ext import commands
import base64
from typing import Optional
import re

class Base64Cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.MAX_ENCODE_LAYERS = 25
        self.MAX_INPUT_LENGTH = 10240
        self.MAX_OUTPUT_LENGTH = 10240

    def cleanup_text(self, text: str) -> str:
        text = re.sub(r'```\w*\n?|\n?```', '', text)
        text = text.strip()
        return text

    def truncate_text(self, text: str, max_length: int = 1000) -> str:
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    def format_output(self, text: str) -> str:
        return f"```{text}```"

    @app_commands.command(
        name="encode",
        description="Encode text to base64 (optionally multiple times)"
    )
    @app_commands.describe(
        text="The text you want to encode",
        layers="Number of encoding layers (default: 1, max: 25)"
    )
    async def encode(
        self, 
        interaction: discord.Interaction, 
        text: str,
        layers: Optional[int] = 1
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            text = self.cleanup_text(text)

            if len(text) > self.MAX_INPUT_LENGTH:
                await interaction.followup.send(
                    f"❌ Input text is too long! Maximum length is {self.MAX_INPUT_LENGTH} characters.",
                    ephemeral=True
                )
                return

            layers = max(1, min(layers, self.MAX_ENCODE_LAYERS))

            current_text = text
            encode_steps = [("Original", text)]

            for i in range(layers):
                try:
                    encoded = base64.b64encode(current_text.encode('utf-8')).decode('utf-8')
                    encode_steps.append((f"Layer {i+1}", encoded))
                    current_text = encoded

                    if len(current_text) > self.MAX_OUTPUT_LENGTH:
                        await interaction.followup.send(
                            "❌ Output text would be too long! Try fewer encoding layers.",
                            ephemeral=True
                        )
                        return

                except Exception as e:
                    await interaction.followup.send(
                        f"❌ Error during encoding at layer {i+1}: {str(e)}",
                        ephemeral=True
                    )
                    return

            response = f"✅ Successfully encoded {layers} layer{'s' if layers > 1 else ''}!\n\n"

            response += "**Encoding steps:**\n"
            for step_name, step_text in encode_steps[:-1]:
                response += f"**{step_name}:** {self.truncate_text(step_text, 100)}\n"
            response += "\n"

            response += f"**Final encoded result:**\n{self.format_output(current_text)}"

            await interaction.followup.send(response, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                f"❌ An unexpected error occurred: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(
        name="decode",
        description="Decode base64 text (automatically handles multiple layers)"
    )
    @app_commands.describe(
        encoded_text="The base64 encoded text you want to decode"
    )
    async def decode(
        self, 
        interaction: discord.Interaction, 
        encoded_text: str
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            encoded_text = self.cleanup_text(encoded_text)

            if len(encoded_text) > self.MAX_INPUT_LENGTH:
                await interaction.followup.send(
                    f"❌ Input text is too long! Maximum length is {self.MAX_INPUT_LENGTH} characters.",
                    ephemeral=True
                )
                return

            current_text = encoded_text
            decode_count = 0
            decode_steps = []

            while decode_count < self.MAX_ENCODE_LAYERS:
                try:
                    if len(current_text) % 4 != 0:
                        break

                    decoded = base64.b64decode(current_text).decode('utf-8')

                    decode_count += 1
                    decode_steps.append(current_text)
                    current_text = decoded

                    if len(current_text) > self.MAX_OUTPUT_LENGTH:
                        await interaction.followup.send(
                            "❌ Output text would be too long! The input might be encoded too many times.",
                            ephemeral=True
                        )
                        return

                except (base64.binascii.Error, UnicodeDecodeError):
                    break
                except Exception as e:
                    await interaction.followup.send(
                        f"❌ Error during decoding: {str(e)}",
                        ephemeral=True
                    )
                    return

            if decode_count == 0:
                response = "❌ The provided text is not base64 encoded."
            else:
                response = f"✅ Successfully decoded {decode_count} layer{'s' if decode_count > 1 else ''}!\n\n"

                response += "**Decoding steps:**\n"
                for i, step in enumerate(decode_steps, 1):
                    response += f"{i}. {self.truncate_text(step, 100)}\n"
                response += "\n"

                response += f"**Final decoded result:**\n{self.format_output(current_text)}"

            await interaction.followup.send(response, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                f"❌ An unexpected error occurred: {str(e)}",
                ephemeral=True
            )

    @encode.error
    @decode.error
    async def error_handler(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandInvokeError):
            await interaction.followup.send(
                f"❌ An error occurred while processing your request: {str(error.original)}",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ An error occurred: {str(error)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Base64Cog(bot))
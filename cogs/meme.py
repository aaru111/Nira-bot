import discord
from discord import app_commands
from discord.ext import commands
from modules.mememod import MemeModule, MemeView


class MemeCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.meme_module = MemeModule()

    async def cog_unload(self) -> None:
        """Clean up resources when the cog is unloaded."""
        await self.meme_module.close()

    @app_commands.command(name="meme", description="Get a random meme")
    @app_commands.choices(topic=[
        app_commands.Choice(name="General", value="general"),
        app_commands.Choice(name="Anime", value="anime"),
        app_commands.Choice(name="Gaming", value="gaming"),
        app_commands.Choice(name="Programming", value="programming"),
        app_commands.Choice(name="Science", value="science"),
        app_commands.Choice(name="History", value="history"),
        app_commands.Choice(name="NSFW", value="nsfw"),
        app_commands.Choice(name="Shitposting", value="shitposting")
    ])
    async def meme(self, interaction: discord.Interaction,
                   topic: app_commands.Choice[str]):
        if topic.value == "nsfw" and not interaction.channel.is_nsfw():
            await interaction.response.send_message(
                "NSFW memes can only be sent in age-restricted channels. Please use this command in an appropriate channel.",
                ephemeral=True)
            return

        meme = await self.meme_module.fetch_single_meme(topic.value)
        if not meme:
            await interaction.response.send_message(
                "Sorry, I couldn't fetch a meme at the moment. Please try again later.",
                ephemeral=True)
            return

        view = MemeView(self.bot, interaction, self, topic.value)
        view.meme_history.append(meme)
        view.current_index = 0
        embed = view.create_meme_embed(meme)
        view.update_button_states()
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MemeCog(bot))

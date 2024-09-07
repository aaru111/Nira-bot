import discord
from discord import app_commands
from discord.ext import commands
from modules.animemod import AniListModule, AniListView, LogoutView, ListTypeSelect

class AniListCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.anilist_module: AniListModule = AniListModule()
        self.bot.loop.create_task(self.anilist_module.load_tokens())

    @app_commands.command(name="anilist", description="Connect to AniList or view your stats")
    async def anilist(self, interaction: discord.Interaction) -> None:
        user_id: int = interaction.user.id
        if user_id in self.anilist_module.user_tokens:
            try:
                stats = await self.anilist_module.fetch_anilist_data(self.anilist_module.user_tokens[user_id])
                embed = self.anilist_module.create_stats_embed(stats)

                view = discord.ui.View()
                view.add_item(ListTypeSelect(self))
                view.add_item(LogoutView(self.anilist_module).children[0])  # Add only the logout button

                await interaction.response.send_message(embed=embed, view=view)
            except Exception as e:
                await interaction.response.send_message(
                    f"An error occurred: {str(e)}. Please try reconnecting.",
                    ephemeral=True
                )
                await self.anilist_module.remove_token(user_id)
                del self.anilist_module.user_tokens[user_id]
        else:
            await interaction.response.send_message(
                "AniList Integration",
                view=AniListView(self.anilist_module),
                ephemeral=True
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AniListCog(bot))

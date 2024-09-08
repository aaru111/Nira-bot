import discord
from discord import app_commands
from discord.ext import commands
from modules.animemod import AniListModule, AniListView, LogoutView, ListTypeSelect, CompareButton


class AniListCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.anilist_module: AniListModule = AniListModule()
        self.bot.loop.create_task(self.anilist_module.load_tokens())

    @app_commands.command(
        name="anilist",
        description=
        "Connect to AniList, view your stats, or look up another user")
    @app_commands.describe(
        user="The Discord user to look up (optional)",
        anilist_username="The AniList username to look up (optional)")
    async def anilist(self,
                      interaction: discord.Interaction,
                      user: discord.User = None,
                      anilist_username: str = None) -> None:
        viewing_user_id: int = interaction.user.id

        if user:
            # Look up AniList for mentioned Discord user
            viewed_user_id: int = user.id
            if viewed_user_id in self.anilist_module.user_tokens:
                try:
                    stats = await self.anilist_module.fetch_anilist_data(
                        self.anilist_module.user_tokens[viewed_user_id])
                    embed = self.anilist_module.create_stats_embed(
                        stats, viewing_user_id)

                    view = discord.ui.View()
                    if viewing_user_id in self.anilist_module.user_tokens and viewing_user_id != viewed_user_id:
                        view.add_item(
                            CompareButton(self.anilist_module, viewing_user_id,
                                          viewed_user_id))

                    await interaction.response.send_message(embed=embed,
                                                            view=view)
                except Exception as e:
                    await interaction.response.send_message(
                        f"An error occurred while fetching data for {user.name}: {str(e)}",
                        ephemeral=True)
            else:
                await interaction.response.send_message(
                    f"{user.name} hasn't linked their AniList account yet.",
                    ephemeral=True)
        elif anilist_username:
            # Look up AniList by username
            try:
                stats = await self.anilist_module.fetch_anilist_data_by_username(
                    anilist_username)
                if stats:
                    embed = self.anilist_module.create_stats_embed(
                        stats, viewing_user_id)

                    view = discord.ui.View()
                    if viewing_user_id in self.anilist_module.user_tokens:
                        view.add_item(
                            CompareButton(self.anilist_module, viewing_user_id,
                                          anilist_username))

                    await interaction.response.send_message(embed=embed,
                                                            view=view)
                else:
                    await interaction.response.send_message(
                        f"No AniList user found with the username {anilist_username}.",
                        ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(
                    f"An error occurred while fetching data for {anilist_username}: {str(e)}",
                    ephemeral=True)
        else:
            # Original functionality for the current user
            if viewing_user_id in self.anilist_module.user_tokens:
                try:
                    stats = await self.anilist_module.fetch_anilist_data(
                        self.anilist_module.user_tokens[viewing_user_id])
                    embed = self.anilist_module.create_stats_embed(
                        stats, viewing_user_id)
                    view = discord.ui.View()
                    view.add_item(ListTypeSelect(self))
                    view.add_item(LogoutView(self.anilist_module).children[0])
                    view.add_item(
                        CompareButton(self.anilist_module, viewing_user_id,
                                      viewing_user_id))
                    await interaction.response.send_message(embed=embed,
                                                            view=view)
                except Exception as e:
                    await interaction.response.send_message(
                        f"An error occurred: {str(e)}. Please try reconnecting.",
                        ephemeral=True)
                    await self.anilist_module.remove_token(viewing_user_id)
                    del self.anilist_module.user_tokens[viewing_user_id]
            else:
                await interaction.response.send_message(
                    "AniList Integration",
                    view=AniListView(self.anilist_module),
                    ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AniListCog(bot))

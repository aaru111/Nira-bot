import discord
from discord import app_commands
from discord.ext import commands
from modules.animemod import AniListModule, AniListView, LogoutView, ListTypeSelect, CompareButton
from typing import List


class AniListCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.anilist_module: AniListModule = AniListModule()
        self.bot.loop.create_task(self.anilist_module.load_tokens())

    async def autocomplete_media(
            self, interaction: discord.Interaction,
            current: str) -> List[app_commands.Choice[str]]:
        media_type = interaction.namespace.media_type
        if not current:
            return []
        results = await self.anilist_module.autocomplete_search(
            media_type, current)
        return [
            app_commands.Choice(name=name, value=id)
            for name, id in results[:25]  # Discord limits to 25 choices
        ]

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
        if user:
            # Look up AniList for mentioned Discord user
            user_id: int = user.id
            if user_id in self.anilist_module.user_tokens:
                try:
                    stats = await self.anilist_module.fetch_anilist_data(
                        self.anilist_module.user_tokens[user_id])
                    embed = self.anilist_module.create_stats_embed(stats)
                    await interaction.response.send_message(embed=embed)
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
                    embed = self.anilist_module.create_stats_embed(stats)
                    await interaction.response.send_message(embed=embed)
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
            user_id: int = interaction.user.id
            if user_id in self.anilist_module.user_tokens:
                try:
                    stats = await self.anilist_module.fetch_anilist_data(
                        self.anilist_module.user_tokens[user_id])
                    embed = self.anilist_module.create_stats_embed(stats)
                    view = discord.ui.View()
                    view.add_item(ListTypeSelect(self))
                    view.add_item(LogoutView(self.anilist_module).children[0])
                    view.add_item(CompareButton(self.anilist_module))
                    await interaction.response.send_message(embed=embed,
                                                            view=view)
                except Exception as e:
                    await interaction.response.send_message(
                        f"An error occurred: {str(e)}. Please try reconnecting.",
                        ephemeral=True)
                    await self.anilist_module.remove_token(user_id)
                    del self.anilist_module.user_tokens[user_id]
            else:
                await interaction.response.send_message(
                    "AniList Integration",
                    view=AniListView(self.anilist_module),
                    ephemeral=True)

    @app_commands.command(
        name="search", description="Search for an anime or manga on AniList")
    @app_commands.describe(
        media_type="Choose whether to search for anime or manga",
        query="The name of the anime or manga to search for")
    @app_commands.choices(media_type=[
        app_commands.Choice(name="Anime", value="ANIME"),
        app_commands.Choice(name="Manga", value="MANGA")
    ])
    @app_commands.autocomplete(query=autocomplete_media)
    async def search(self, interaction: discord.Interaction, media_type: str,
                     query: str):
        await interaction.response.defer()

        try:
            search_result = await self.anilist_module.search_media(media_type, query)
            if not search_result:
                await interaction.followup.send(
                    f"No {media_type.lower()} found for '{query}'.")
                return

            embed = await self.create_search_embed(interaction.user, search_result)
            view = SearchView(self.anilist_module, search_result)
            await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            await interaction.followup.send(
                f"An error occurred while searching: {str(e)}")

    async def create_search_embed(self, user: discord.User, media):
        user_id = user.id
        profile_color = await self.anilist_module.get_user_color(user_id)
        embed_color = int(profile_color.lstrip('#'), 16)
        emoji = self.anilist_module.get_color_emoji(profile_color)

        embed = discord.Embed(title=media['title']['romaji'],
                              url=media['siteUrl'],
                              color=embed_color)
        embed.set_thumbnail(url=media['coverImage']['large'])

        if media['bannerImage']:
            embed.set_image(url=media['bannerImage'])

        embed.add_field(name="Type",
                        value=f"{emoji} {media['type']}",
                        inline=True)
        embed.add_field(name="Format",
                        value=f"{emoji} {media['format']}",
                        inline=True)
        embed.add_field(name="Status",
                        value=f"{emoji} {media['status']}",
                        inline=True)

        if media['type'] == 'ANIME':
            embed.add_field(name="Episodes",
                            value=f"{emoji} {media['episodes'] or 'N/A'}",
                            inline=True)
        else:
            embed.add_field(name="Chapters",
                            value=f"{emoji} {media['chapters'] or 'N/A'}",
                            inline=True)
            embed.add_field(name="Volumes",
                            value=f"{emoji} {media['volumes'] or 'N/A'}",
                            inline=True)

        if media['startDate']['year']:
            start_date = f"{media['startDate']['year']}-{media['startDate']['month']}-{media['startDate']['day']}"
            embed.add_field(name="Start Date",
                            value=f"{emoji} {start_date}",
                            inline=True)

        if media['averageScore']:
            score_bar = '█' * int(media['averageScore'] / 10) + '░' * (
                10 - int(media['averageScore'] / 10))
            embed.add_field(
                name="Score",
                value=
                f"{emoji} **{media['averageScore']}%**\n{emoji} {score_bar}",
                inline=True)

        if media['genres']:
            embed.add_field(name="Genres",
                            value=f"{emoji} {', '.join(media['genres'])}",
                            inline=False)

        if media['description']:
            description = self.anilist_module.clean_anilist_text(
                media['description'])
            embed.add_field(name="Description",
                            value=description[:1024],
                            inline=False)

        return embed


class SearchView(discord.ui.View):

    def __init__(self, module: AniListModule, media):
        super().__init__()
        self.module = module
        self.media = media
        self.update_buttons()

    def update_buttons(self):
        relations = self.media.get('relations', {}).get('edges', [])
        self.prequels = [edge['node'] for edge in relations if edge['relationType'].lower() == 'prequel']
        self.sequels = [edge['node'] for edge in relations if edge['relationType'].lower() == 'sequel']

        self.prequel_button.disabled = len(self.prequels) == 0
        self.sequel_button.disabled = len(self.sequels) == 0

    @discord.ui.button(label="Prequel", style=discord.ButtonStyle.primary)
    async def prequel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.prequels:
            await self.show_related(interaction, self.prequels[0])

    @discord.ui.button(label="Sequel", style=discord.ButtonStyle.primary)
    async def sequel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.sequels:
            await self.show_related(interaction, self.sequels[0])

    async def show_related(self, interaction: discord.Interaction, related_media):
        full_media = await self.module.search_media(related_media['type'], str(related_media['id']))

        embed = await interaction.client.get_cog('AniListCog').create_search_embed(interaction.user, full_media)
        new_view = SearchView(self.module, full_media)

        await interaction.response.edit_message(embed=embed, view=new_view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AniListCog(bot))
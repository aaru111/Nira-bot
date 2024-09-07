import os
import re
from typing import Optional, Dict, Any
import discord
from discord import app_commands
from discord.ext import commands
from aiohttp import ClientSession

from database import db

LOGOUT_BUTTON_TIMEOUT = 30


class AniListCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.anilist_client_id: str = os.environ['ANILIST_CLIENT_ID']
        self.anilist_client_secret: str = os.environ['ANILIST_CLIENT_SECRET']
        self.anilist_redirect_uri: str = 'https://anilist.co/api/v2/oauth/pin'
        self.anilist_auth_url: str = f'https://anilist.co/api/v2/oauth/authorize?client_id={self.anilist_client_id}&response_type=code&redirect_uri={self.anilist_redirect_uri}'
        self.anilist_token_url: str = 'https://anilist.co/api/v2/oauth/token'
        self.anilist_api_url: str = 'https://graphql.anilist.co'
        self.user_tokens: Dict[int, str] = {}
        self.bot.loop.create_task(self.load_tokens())

    async def load_tokens(self) -> None:
        query = "SELECT user_id, access_token FROM anilist_tokens"
        results = await db.fetch(query)
        self.user_tokens = {
            record['user_id']: record['access_token']
            for record in results
        }

    async def save_token(self, user_id: int, access_token: str) -> None:
        query = """
        INSERT INTO anilist_tokens (user_id, access_token) 
        VALUES ($1, $2) 
        ON CONFLICT (user_id) 
        DO UPDATE SET access_token = $2
        """
        await db.execute(query, user_id, access_token)

    async def remove_token(self, user_id: int) -> None:
        query = "DELETE FROM anilist_tokens WHERE user_id = $1"
        await db.execute(query, user_id)

    @app_commands.command(name="anilist",
                          description="Connect to AniList or view your stats")
    async def anilist(self, interaction: discord.Interaction) -> None:
        user_id = interaction.user.id
        if user_id in self.user_tokens:
            try:
                stats = await self.fetch_anilist_data(self.user_tokens[user_id]
                                                      )
                embed = self.create_stats_embed(stats)
                view = LogoutView(self)
                await interaction.response.send_message(embed=embed, view=view)
                view.message = await interaction.original_response()
            except Exception as e:
                await interaction.response.send_message(
                    f"An error occurred: {str(e)}. Please try reconnecting.",
                    ephemeral=True)
                await self.remove_token(user_id)
                del self.user_tokens[user_id]
        else:
            await interaction.response.send_message("AniList Integration",
                                                    view=AniListView(self),
                                                    ephemeral=True)

    async def get_access_token(self, auth_code: str) -> Optional[str]:
        data: Dict[str, str] = {
            'grant_type': 'authorization_code',
            'client_id': self.anilist_client_id,
            'client_secret': self.anilist_client_secret,
            'redirect_uri': self.anilist_redirect_uri,
            'code': auth_code
        }

        async with ClientSession() as session:
            async with session.post(self.anilist_token_url,
                                    data=data) as response:
                if response.status == 200:
                    token_data: Dict[str, Any] = await response.json()
                    return token_data.get('access_token')
        return None

    async def fetch_anilist_data(
            self, access_token: str) -> Optional[Dict[str, Any]]:
        query: str = '''
        query {
            Viewer {
                name
                avatar {
                    medium
                }
                bannerImage
                siteUrl
                about
                options {
                    profileColor
                }
                favourites {
                    anime {
                        nodes {
                            title {
                                romaji
                            }
                        }
                    }
                    manga {
                        nodes {
                            title {
                                romaji
                            }
                        }
                    }
                }
                statistics {
                    anime {
                        count
                        episodesWatched
                        minutesWatched
                        meanScore
                    }
                    manga {
                        count
                        chaptersRead
                        volumesRead
                        meanScore
                    }
                }
            }
        }
        '''

        headers: Dict[str, str] = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        async with ClientSession() as session:
            async with session.post(self.anilist_api_url,
                                    json={'query': query},
                                    headers=headers) as response:
                if response.status == 200:
                    data: Dict[str, Any] = await response.json()
                    if 'errors' in data:
                        error_message = data['errors'][0]['message']
                        raise Exception(f"AniList API Error: {error_message}")
                    return data.get('data', {}).get('Viewer')
                else:
                    raise Exception(
                        f"AniList API returned status code {response.status}")

    def clean_anilist_text(self, text: str) -> str:
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'(img|Img)(\d*%?)?\(+', '', text)
        text = re.sub(r'\)+', '', text)
        text = re.sub(r'\(+', '', text)
        text = re.sub(r'~!.*?!~', '', text)
        text = re.sub(r'__(.*?)__', r'\1', text)
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'_(.*?)_', r'\1', text)
        text = re.sub(r'[~\[\]{}]', '', text)
        text = ' '.join(text.split())
        return text.strip()

    def create_stats_embed(self, stats: Dict[str, Any]) -> discord.Embed:
        profile_color = stats['options']['profileColor']
        color_map = {
            'blue': 0x3DB4F2,
            'purple': 0xC063FF,
            'pink': 0xFC9DD6,
            'orange': 0xFC9344,
            'red': 0xE13333,
            'green': 0x4CCA51,
            'gray': 0x677B94
        }

        if profile_color:
            if profile_color.startswith('#'):
                embed_color = int(profile_color.lstrip('#'), 16)
            else:
                embed_color = color_map.get(profile_color.lower(), 0x02A9FF)
        else:
            embed_color = 0x02A9FF

        embed = discord.Embed(title=f"AniList Profile for {stats['name']}",
                              url=stats['siteUrl'],
                              color=embed_color)

        if stats['avatar']['medium']:
            embed.set_thumbnail(url=stats['avatar']['medium'])

        if stats['bannerImage']:
            embed.set_image(url=stats['bannerImage'])

        if stats['about']:
            about_clean = self.clean_anilist_text(stats['about'])
            if about_clean:
                embed.add_field(name="About",
                                value=about_clean[:1024],
                                inline=False)

        anime_stats: Dict[str, Any] = stats['statistics']['anime']
        manga_stats: Dict[str, Any] = stats['statistics']['manga']

        anime_value = (f"Count: {anime_stats['count']}\n"
                       f"Episodes: {anime_stats['episodesWatched']}\n"
                       f"Time: {anime_stats['minutesWatched'] // 1440} days")

        anime_score = anime_stats['meanScore']
        anime_score_bar = '█' * int(
            anime_score / 10) + '░' * (10 - int(anime_score / 10))
        anime_score_value = f"**{anime_score:.2f} // 100**\n{anime_score_bar}"

        manga_value = (f"Count: {manga_stats['count']}\n"
                       f"Chapters: {manga_stats['chaptersRead']}\n"
                       f"Volumes: {manga_stats['volumesRead']}")

        manga_score = manga_stats['meanScore']
        manga_score_bar = '█' * int(
            manga_score / 10) + '░' * (10 - int(manga_score / 10))
        manga_score_value = f"**{manga_score:.2f} // 100**\n{manga_score_bar}"

        embed.add_field(name="Anime Stats", value=anime_value, inline=True)
        embed.add_field(name="Anime Score",
                        value=anime_score_value,
                        inline=True)
        embed.add_field(name="\u200b", value="\u200b",
                        inline=True)  # Empty field for alignment
        embed.add_field(name="Manga Stats", value=manga_value, inline=True)
        embed.add_field(name="Manga Score",
                        value=manga_score_value,
                        inline=True)
        embed.add_field(name="\u200b", value="\u200b",
                        inline=True)  # Empty field for alignment

        fav_anime = stats['favourites']['anime']['nodes'][:5]
        fav_manga = stats['favourites']['manga']['nodes'][:5]

        if fav_anime:
            fav_anime_list = "\n".join(
                [f"• {anime['title']['romaji']}" for anime in fav_anime])
            embed.add_field(name="Favorite Anime",
                            value=fav_anime_list,
                            inline=True)

        if fav_manga:
            fav_manga_list = "\n".join(
                [f"• {manga['title']['romaji']}" for manga in fav_manga])
            embed.add_field(name="Favorite Manga",
                            value=fav_manga_list,
                            inline=True)

        return embed


class AniListView(discord.ui.View):

    def __init__(self, cog: AniListCog):
        super().__init__()
        self.cog: AniListCog = cog

    @discord.ui.button(label="Get Auth Code",
                       style=discord.ButtonStyle.primary)
    async def get_auth_code(self, interaction: discord.Interaction,
                            button: discord.ui.Button) -> None:
        instructions: str = (
            f"Please follow these steps to get your authorization code:\n\n"
            f"1. Click this link: [**Authenticate here**]({self.cog.anilist_auth_url})\n"
            f"2. If prompted, log in to your AniList account and authorize the application.\n"
            f"3. You will be redirected to a page that says 'Authorization Complete'.\n"
            f"4. On that page, you will see a 'PIN' or 'Authorization Code'. Copy this code.\n"
            f"5. Come back here and click the 'Enter Auth Code' button to enter the code you copied.\n\n"
            f"If you have any issues, please let me know!")
        await interaction.response.send_message(instructions, ephemeral=True)

    @discord.ui.button(label="Enter Auth Code",
                       style=discord.ButtonStyle.green)
    async def enter_auth_code(self, interaction: discord.Interaction,
                              button: discord.ui.Button) -> None:
        await interaction.response.send_modal(AniListAuthModal(self.cog))


class AniListAuthModal(discord.ui.Modal, title='Enter AniList Auth Code'):

    def __init__(self, cog: AniListCog):
        super().__init__()
        self.cog: AniListCog = cog

    auth_code: discord.ui.TextInput = discord.ui.TextInput(
        label='Enter your AniList authorization code',
        placeholder='Paste your auth code here...',
        required=True)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            access_token: Optional[str] = await self.cog.get_access_token(
                self.auth_code.value)
            if not access_token:
                await interaction.followup.send(
                    "Failed to authenticate. Please try again.",
                    ephemeral=True)
                return

            user_id = interaction.user.id
            self.cog.user_tokens[user_id] = access_token
            await self.cog.save_token(user_id, access_token)

            stats: Optional[Dict[
                str, Any]] = await self.cog.fetch_anilist_data(access_token)
            if not stats:
                await interaction.followup.send(
                    "Failed to fetch AniList data. Please try again.",
                    ephemeral=True)
                return

            embed: discord.Embed = self.cog.create_stats_embed(stats)
            view = LogoutView(self.cog)
            message = await interaction.followup.send(embed=embed, view=view)
            view.message = message
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}",
                                            ephemeral=True)


class LogoutView(discord.ui.View):

    def __init__(self, cog: AniListCog):
        super().__init__(timeout=LOGOUT_BUTTON_TIMEOUT)
        self.cog: AniListCog = cog
        self.message: Optional[discord.Message] = None

    @discord.ui.button(label="Logout", style=discord.ButtonStyle.danger)
    async def logout(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id in self.cog.user_tokens:
            del self.cog.user_tokens[user_id]
            await self.cog.remove_token(user_id)
            await interaction.response.send_message(
                "You have been logged out from AniList. You'll need to reauthenticate to access your AniList data again.",
                ephemeral=True)
        else:
            await interaction.response.send_message(
                "You are not currently logged in to AniList.", ephemeral=True)

    async def on_timeout(self):
        if self.message:
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AniListCog(bot))

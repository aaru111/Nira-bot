import os
import re
from typing import Optional, Dict, Any, List, Union
import discord
from discord.ext import commands
from aiohttp import ClientSession
import matplotlib.pyplot as plt
import io
from datetime import datetime
import logging

from database import db

LOGOUT_BUTTON_TIMEOUT = 30
ITEMS_PER_PAGE = 6


class AniListModule:

    def __init__(self) -> None:
        self.anilist_client_id: str = os.environ['ANILIST_CLIENT_ID']
        self.anilist_client_secret: str = os.environ['ANILIST_CLIENT_SECRET']
        self.anilist_redirect_uri: str = 'https://anilist.co/api/v2/oauth/pin'
        self.anilist_auth_url: str = f'https://anilist.co/api/v2/oauth/authorize?client_id={self.anilist_client_id}&response_type=code&redirect_uri={self.anilist_redirect_uri}'
        self.anilist_token_url: str = 'https://anilist.co/api/v2/oauth/token'
        self.anilist_api_url: str = 'https://graphql.anilist.co'
        self.user_tokens: Dict[int, str] = {}

    async def load_tokens(self) -> None:
        await db.initialize()
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

    def blend_colors(self, color1: str, color2: str) -> int:
        # Convert hex to RGB
        def hex_to_rgb(hex_color):
            return tuple(
                int(hex_color.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))

        # Blend two colors
        def blend(c1, c2):
            return int((c1 + c2) / 2)

        # Convert profile colors to RGB
        rgb1 = hex_to_rgb(color1) if color1.startswith('#') else hex_to_rgb(
            self.get_default_color(color1))
        rgb2 = hex_to_rgb(color2) if color2.startswith('#') else hex_to_rgb(
            self.get_default_color(color2))

        # Blend the colors
        blended = tuple(blend(c1, c2) for c1, c2 in zip(rgb1, rgb2))

        # Convert back to hex
        return int(f'0x{blended[0]:02x}{blended[1]:02x}{blended[2]:02x}', 16)

    def get_default_color(self, color_name: str) -> str:
        color_map = {
            'blue': '#3DB4F2',
            'purple': '#C063FF',
            'pink': '#FC9DD6',
            'orange': '#FC9344',
            'red': '#E13333',
            'green': '#4CCA51',
            'gray': '#677B94'
        }
        return color_map.get(color_name.lower(), '#02A9FF')

    async def fetch_recent_activities(
            self, access_token: str) -> List[Dict[str, Any]]:
        # First, fetch the user's ID
        user_query = '''
        query {
            Viewer {
                id
            }
        }
        '''

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        async with ClientSession() as session:
            async with session.post(self.anilist_api_url,
                                    json={'query': user_query},
                                    headers=headers) as response:
                if response.status != 200:
                    raise Exception(
                        f"Failed to fetch user ID. Status: {response.status}")
                user_data = await response.json()
                user_id = user_data['data']['Viewer']['id']

        # Now fetch the activities using the user's ID
        query = '''
        query ($userId: Int, $page: Int, $perPage: Int) {
            Page(page: $page, perPage: $perPage) {
                activities(userId: $userId, sort: ID_DESC, type_in: [ANIME_LIST, MANGA_LIST, TEXT, MESSAGE]) {
                    ... on ListActivity {
                        id
                        type
                        status
                        progress
                        media {
                            id
                            title {
                                romaji
                                english
                            }
                            coverImage {
                                large
                            }
                            type
                        }
                        createdAt
                    }
                    ... on TextActivity {
                        id
                        type
                        text
                        createdAt
                    }
                    ... on MessageActivity {
                        id
                        type
                        message
                        createdAt
                    }
                }
            }
        }
        '''

        variables = {"userId": user_id, "page": 1, "perPage": 50}

        async with ClientSession() as session:
            async with session.post(self.anilist_api_url,
                                    json={
                                        'query': query,
                                        'variables': variables
                                    },
                                    headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    activities = data['data']['Page']['activities']
                    logging.info(
                        f"Fetched {len(activities)} activities for user {user_id}"
                    )
                    return activities
                else:
                    error_message = f"AniList API returned status code {response.status}"
                    logging.error(error_message)
                    raise Exception(error_message)

    def create_recent_activities_embed(self, activities: List[Dict[str, Any]],
                                       page: int) -> discord.Embed:
        embed = discord.Embed(title="Recent Activity", color=0x02A9FF)

        if not activities:
            embed.description = "No recent activities found."
            embed.set_footer(text="Page 1/1")
            return embed

        activity = activities[page - 1]
        activity_type = activity['type']
        time_ago = discord.utils.format_dt(datetime.fromtimestamp(
            activity['createdAt']),
                                           style='R')

        if activity_type in ['ANIME_LIST', 'MANGA_LIST']:
            media = activity['media']
            title = media['title']['english'] or media['title']['romaji']
            status = activity['status']
            progress = activity['progress']
            embed.add_field(
                name=f"{media['type']}: {title}",
                value=
                f"- **Status:** {status}\n- **Progress:** {progress}\n- **Updated:** {time_ago}",
                inline=False)

            if media['coverImage']['large']:
                embed.set_image(url=media['coverImage']['large'])

        elif activity_type == 'TEXT':
            text = activity['text']
            embed.add_field(name="Text Post",
                            value=f"{text}\n- **Posted:** {time_ago}",
                            inline=False)

        elif activity_type == 'MESSAGE':
            message = activity['message']
            embed.add_field(name="Message",
                            value=f"{message}\n- **Sent:** {time_ago}",
                            inline=False)

        else:
            embed.add_field(
                name="Unknown Activity",
                value=f"Type: {activity_type}\n- **Occurred:** {time_ago}",
                inline=False)

        total_pages = len(activities)
        embed.set_footer(text=f"Page {page}/{total_pages}")

        return embed

    async def fetch_anilist_data_by_username(
            self, username: str) -> Optional[Dict[str, Any]]:
        query = '''
        query ($username: String) {
            User(name: $username) {
                name
                avatar {
                    large
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

        variables = {"username": username}

        async with ClientSession() as session:
            async with session.post(self.anilist_api_url,
                                    json={
                                        'query': query,
                                        'variables': variables
                                    }) as response:
                if response.status == 404:
                    return None  # User not found
                elif response.status != 200:
                    raise Exception(
                        f"AniList API returned status code {response.status}")

                data: Dict[str, Any] = await response.json()
                if 'errors' in data:
                    error_message = data['errors'][0]['message']
                    if "User not found" in error_message:
                        return None  # User not found
                    raise Exception(f"AniList API Error: {error_message}")
                return data.get('data', {}).get('User')

    async def fetch_user_list(self, access_token: str, list_type: str,
                              status: str) -> List[Dict[str, Any]]:
        query = '''
        query ($userId: Int, $type: MediaType, $status: MediaListStatus) {
            MediaListCollection(userId: $userId, type: $type, status: $status) {
                lists {
                    entries {
                        media {
                            title {
                                romaji
                                english
                            }
                            episodes
                            chapters
                            status
                        }
                        status
                        progress
                        score(format: POINT_10)
                    }
                }
            }
        }
        '''

        user_query = '''
        query {
            Viewer {
                id
            }
        }
        '''

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        async with ClientSession() as session:
            async with session.post(self.anilist_api_url,
                                    json={'query': user_query},
                                    headers=headers) as response:
                if response.status != 200:
                    raise Exception(
                        f"Failed to fetch user ID. Status: {response.status}")
                user_data = await response.json()
                user_id = user_data['data']['Viewer']['id']

            variables = {
                "userId": user_id,
                "type": list_type.upper(),
                "status": status
            }
            async with session.post(self.anilist_api_url,
                                    json={
                                        'query': query,
                                        'variables': variables
                                    },
                                    headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'errors' in data:
                        raise Exception(
                            f"AniList API Error: {data['errors'][0]['message']}"
                        )
                    lists = data['data']['MediaListCollection']['lists']
                    if not lists:
                        return []
                    return lists[0]['entries']
                else:
                    raise Exception(
                        f"AniList API returned status code {response.status}")

    async def fetch_anilist_data(
            self, access_token: str) -> Optional[Dict[str, Any]]:
        query: str = '''
        query {
            Viewer {
                name
                avatar {
                    large
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

    def create_list_embed(self,
                          list_data: List[Dict[str, Any]],
                          list_type: str,
                          status: str,
                          page: int = 1) -> discord.Embed:
        embed = discord.Embed(
            title=f"{list_type.capitalize()} List - {status.capitalize()}",
            color=0x02A9FF)

        # Pagination logic
        start = (page - 1) * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        paginated_list = list_data[start:end]

        if not paginated_list:
            embed.description = "No entries found for this status."
            return embed

        for entry in paginated_list:
            media = entry['media']
            title = media['title']['english'] or media['title']['romaji']
            progress = entry['progress']
            score = entry['score']
            emoji = self.get_color_emoji(
                entry.get('user', {}).get('options',
                                          {}).get('profileColor', 'blue'))

            if list_type == 'anime':
                total = media['episodes'] or '?'
                value = f"-# Progress: {progress}/{total} episodes\n-# Score: {score}/10"
            else:  # manga
                total = media['chapters'] or '?'
                value = f"-# Progress: {progress}/{total} chapters\n-# Score: {score}/10"

            embed.add_field(name=f"{emoji} **{title}**",
                            value=value,
                            inline=False)

        # Footer for pagination
        total_pages = (len(list_data) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        start_entry = start + 1
        end_entry = min(end, len(list_data))
        embed.set_footer(
            text=
            f"Page {page}/{total_pages} | Showing entries {start_entry}-{end_entry} out of {len(list_data)}"
        )

        return embed

    def clean_anilist_text(self, text: str) -> str:
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # Remove image placeholders
        text = re.sub(r'~~~\s*(Img\s*)+(\[\d+%\s*\])+', '', text)

        # Remove specific AniList syntax
        text = re.sub(r'(img|src=|alt=|width=|height=|a href=)', '', text)

        # Remove ~~ to prevent unintended strikethrough
        text = text.replace('~~', '')

        return text.strip()

    async def compare_stats(
            self, stats1: Dict[str, Any],
            stats2: Dict[str, Any]) -> tuple[discord.Embed, discord.File]:
        # Blend the profile colors
        color1 = stats1['options']['profileColor'] or 'blue'
        color2 = stats2['options']['profileColor'] or 'blue'
        blended_color = self.blend_colors(color1, color2)

        embed = discord.Embed(title="AniList Profile Comparison",
                              color=blended_color)

        # User information
        embed.add_field(name=stats1['name'],
                        value=f"-# ╰> [Profile]({stats1['siteUrl']})",
                        inline=True)
        embed.add_field(name=stats2['name'],
                        value=f"-# ╰> [Profile]({stats2['siteUrl']})",
                        inline=True)
        embed.add_field(name="\u200b", value="\u200b",
                        inline=True)  # Empty field for alignment

        if stats1['avatar']['large']:
            embed.set_thumbnail(url=stats1['avatar']['large'])
        if stats2['avatar']['large']:
            embed.set_image(url=stats2['avatar']['large'])

        # Anime and Manga Statistics
        anime_stats1 = stats1['statistics']['anime']
        anime_stats2 = stats2['statistics']['anime']
        manga_stats1 = stats1['statistics']['manga']
        manga_stats2 = stats2['statistics']['manga']

        self.add_comparison_fields(
            embed,
            "Anime",
            stats1['name'],
            stats2['name'],
            color1,
            color2,
            count=(anime_stats1['count'], anime_stats2['count']),
            episodes=(anime_stats1['episodesWatched'],
                      anime_stats2['episodesWatched']),
            hours=(anime_stats1['minutesWatched'] // 60,
                   anime_stats2['minutesWatched'] // 60),
            score=(anime_stats1['meanScore'], anime_stats2['meanScore']))

        self.add_comparison_fields(
            embed,
            "Manga",
            stats1['name'],
            stats2['name'],
            color1,
            color2,
            count=(manga_stats1['count'], manga_stats2['count']),
            chapters=(manga_stats1['chaptersRead'],
                      manga_stats2['chaptersRead']),
            volumes=(manga_stats1['volumesRead'], manga_stats2['volumesRead']),
            score=(manga_stats1['meanScore'], manga_stats2['meanScore']))

        # Create and add graph
        graph_file = await self.create_comparison_graph(stats1, stats2)
        embed.set_image(url="attachment://comparison_graph.png")

        # Favorites comparison
        fav_anime1 = ", ".join([
            anime['title']['romaji']
            for anime in stats1['favourites']['anime']['nodes'][:3]
        ])
        fav_anime2 = ", ".join([
            anime['title']['romaji']
            for anime in stats2['favourites']['anime']['nodes'][:3]
        ])
        fav_manga1 = ", ".join([
            manga['title']['romaji']
            for manga in stats1['favourites']['manga']['nodes'][:3]
        ])
        fav_manga2 = ", ".join([
            manga['title']['romaji']
            for manga in stats2['favourites']['manga']['nodes'][:3]
        ])

        embed.add_field(
            name="Top 3 Favorite Anime",
            value=
            f"-# ╰> **{stats1['name']}**: {fav_anime1}\n-# ╰> **{stats2['name']}**: {fav_anime2}",
            inline=False)
        embed.add_field(
            name="Top 3 Favorite Manga",
            value=
            f"-# ╰> **{stats1['name']}**: {fav_manga1}\n-# ╰> **{stats2['name']}**: {fav_manga2}",
            inline=False)

        return embed, graph_file

    def add_comparison_fields(self, embed: discord.Embed, category: str,
                              name1: str, name2: str, color1: str, color2: str,
                              **kwargs):
        for key, (value1, value2) in kwargs.items():
            key = key.replace('_', ' ').title()
            embed.add_field(name=f"{category} {key}",
                            value=self.format_comparison(
                                name1, name2, value1, value2, color1, color2),
                            inline=True)

    # Bullet point animated emojis
    def get_color_emoji(self, profile_color: str) -> str:
        color_emoji_map = {
            'blue': "<a:Blue_Dot:1289188840547811328>",
            'purple': "<a:purple_Dot:1289184290298658879>",
            'pink': "<a:dot_pink:1289188856494690334>",
            'orange': "<a:dot_orange:1289188848806658088>",
            'red': "<a:dot_red:1289188864795344959>",
            'green': "<a:green_Dot:1289184290298658879>",
            'gray': "<a:gray_Dot:1289184290298658879>"
        }
        return color_emoji_map.get(profile_color.lower(),
                                   "<a:purple_Dot:1289184290298658879>")

    def format_comparison(self, name1: str, name2: str,
                          value1: Union[int, float], value2: Union[int, float],
                          color1: str, color2: str) -> str:
        emoji1 = self.get_color_emoji(color1)
        emoji2 = self.get_color_emoji(color2)

        if isinstance(value1, float) and isinstance(value2, float):
            return f"-# {emoji1}{name1}: {value1:.2f}\n-# {emoji2}{name2}: {value2:.2f}"
        else:
            return f"-# {emoji1}{name1}: {value1}\n-# {emoji2}{name2}: {value2}"

    async def create_comparison_graph(self, stats1: Dict[str, Any],
                                      stats2: Dict[str, Any]) -> discord.File:
        anime_stats1 = stats1['statistics']['anime']
        anime_stats2 = stats2['statistics']['anime']
        manga_stats1 = stats1['statistics']['manga']
        manga_stats2 = stats2['statistics']['manga']

        categories = [
            'Anime Count', 'Anime Episodes', 'Anime Score', 'Manga Count',
            'Manga Chapters', 'Manga Score'
        ]
        user1_data = [
            anime_stats1['count'], anime_stats1['episodesWatched'],
            anime_stats1['meanScore'], manga_stats1['count'],
            manga_stats1['chaptersRead'], manga_stats1['meanScore']
        ]
        user2_data = [
            anime_stats2['count'], anime_stats2['episodesWatched'],
            anime_stats2['meanScore'], manga_stats2['count'],
            manga_stats2['chaptersRead'], manga_stats2['meanScore']
        ]

        x = range(len(categories))
        width = 0.35

        fig, ax = plt.subplots(figsize=(12, 6))

        # Create two separate axes for counts/episodes and scores
        ax2 = ax.twinx()

        # Get user profile colors
        color1 = self.get_color(stats1['options']['profileColor'])
        color2 = self.get_color(stats2['options']['profileColor'])

        rects1_counts = ax.bar([i - width / 2 for i in [0, 1, 3, 4]],
                               [user1_data[i] for i in [0, 1, 3, 4]],
                               width,
                               label=f"{stats1['name']} (Counts)",
                               color=color1)
        rects2_counts = ax.bar([i + width / 2 for i in [0, 1, 3, 4]],
                               [user2_data[i] for i in [0, 1, 3, 4]],
                               width,
                               label=f"{stats2['name']} (Counts)",
                               color=color2)

        rects1_scores = ax2.bar([i - width / 2 for i in [2, 5]],
                                [user1_data[i] for i in [2, 5]],
                                width,
                                label=f"{stats1['name']} (Scores)",
                                color=color1,
                                alpha=0.5)
        rects2_scores = ax2.bar([i + width / 2 for i in [2, 5]],
                                [user2_data[i] for i in [2, 5]],
                                width,
                                label=f"{stats2['name']} (Scores)",
                                color=color2,
                                alpha=0.5)

        ax.set_ylabel('Counts')
        ax2.set_ylabel('Scores')
        ax.set_title('AniList Stats Comparison')
        ax.set_xticks(x)
        ax.set_xticklabels(categories, rotation=45, ha='right')

        # Combine legends
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

        ax.bar_label(rects1_counts, padding=3, rotation=90)
        ax.bar_label(rects2_counts, padding=3, rotation=90)
        ax2.bar_label(rects1_scores, padding=3, rotation=90, fmt='%.2f')
        ax2.bar_label(rects2_scores, padding=3, rotation=90, fmt='%.2f')

        fig.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)

        return discord.File(buf, filename="comparison_graph.png")

    def get_color(self, profile_color: str) -> str:
        color_map = {
            'blue': '#3DB4F2',
            'purple': '#C063FF',
            'pink': '#FC9DD6',
            'orange': '#FC9344',
            'red': '#E13333',
            'green': '#4CCA51',
            'gray': '#677B94'
        }
        if profile_color:
            if profile_color.startswith('#'):
                return profile_color
            else:
                return color_map.get(profile_color.lower(), '#02A9FF')
        return '#02A9FF'

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

        emoji = self.get_color_emoji(profile_color)

        embed = discord.Embed(title=f"AniList Profile for {stats['name']}",
                              url=stats['siteUrl'],
                              color=embed_color)

        if stats['avatar']['large']:
            embed.set_thumbnail(url=stats['avatar']['large'])

        if stats['bannerImage']:
            embed.set_image(url=stats['bannerImage'])

        if stats['about']:
            about_clean = self.clean_anilist_text(stats['about'])
            if about_clean:
                chunks = [
                    about_clean[i:i + 1024]
                    for i in range(0, len(about_clean), 1024)
                ]
                for i, chunk in enumerate(chunks):
                    field_name = "About" if i == 0 else "About (continued)"
                    embed.add_field(name=field_name, value=chunk, inline=False)

        anime_stats: Dict[str, Any] = stats['statistics']['anime']
        manga_stats: Dict[str, Any] = stats['statistics']['manga']

        anime_value = (
            f"-# {emoji} Count: {anime_stats['count']}\n"
            f"-# {emoji} Episodes: {anime_stats['episodesWatched']}\n"
            f"-# {emoji} Time: {anime_stats['minutesWatched'] // 1440} days")

        anime_score = anime_stats['meanScore']
        anime_score_bar = '█' * int(
            anime_score / 10) + '░' * (10 - int(anime_score / 10))
        anime_score_value = f"-# {emoji} **{anime_score:.2f} // 100**\n-# ╰> {anime_score_bar}"

        manga_value = (f"-# {emoji} Count: {manga_stats['count']}\n"
                       f"-# {emoji} Chapters: {manga_stats['chaptersRead']}\n"
                       f"-# {emoji} Volumes: {manga_stats['volumesRead']}")

        manga_score = manga_stats['meanScore']
        manga_score_bar = '█' * int(
            manga_score / 10) + '░' * (10 - int(manga_score / 10))
        manga_score_value = f"-# {emoji} **{manga_score:.2f} // 100**\n-# ╰> {manga_score_bar}"

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
            fav_anime_list = "\n".join([
                f"-# {emoji} {anime['title']['romaji']}" for anime in fav_anime
            ])
            embed.add_field(name="Favorite Anime",
                            value=fav_anime_list,
                            inline=True)

        if fav_manga:
            fav_manga_list = "\n".join([
                f"-# {emoji} {manga['title']['romaji']}" for manga in fav_manga
            ])
            embed.add_field(name="Favorite Manga",
                            value=fav_manga_list,
                            inline=True)

        return embed


class Paginator(discord.ui.View):

    def __init__(self,
                 cog: commands.Cog,
                 list_data: List[Dict[str, Any]],
                 list_type: str,
                 status: str,
                 page: int = 1):
        super().__init__()
        self.cog = cog
        self.list_data = list_data
        self.list_type = list_type
        self.status = status
        self.page = page

        self.update_buttons()

    def update_buttons(self):
        total_pages = len(self.list_data) if self.list_type == "recent" else (
            len(self.list_data) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

        self.first_page_button.disabled = self.page <= 1
        self.prev_page_button.disabled = self.page <= 1
        self.next_page_button.disabled = self.page >= total_pages
        self.last_page_button.disabled = self.page >= total_pages

    @discord.ui.button(label="<<", style=discord.ButtonStyle.primary, row=0)
    async def first_page_button(self, interaction: discord.Interaction,
                                button: discord.ui.Button):
        self.page = 1
        self.update_buttons()
        await self.update_message(interaction)

    @discord.ui.button(label="<", style=discord.ButtonStyle.danger, row=0)
    async def prev_page_button(self, interaction: discord.Interaction,
                               button: discord.ui.Button):
        self.page = max(self.page - 1, 1)
        self.update_buttons()
        await self.update_message(interaction)

    @discord.ui.button(label=">", style=discord.ButtonStyle.success, row=0)
    async def next_page_button(self, interaction: discord.Interaction,
                               button: discord.ui.Button):
        total_pages = (len(self.list_data) + ITEMS_PER_PAGE -
                       1) // ITEMS_PER_PAGE
        self.page = min(self.page + 1, total_pages)
        self.update_buttons()
        await self.update_message(interaction)

    @discord.ui.button(label=">>", style=discord.ButtonStyle.primary, row=0)
    async def last_page_button(self, interaction: discord.Interaction,
                               button: discord.ui.Button):
        total_pages = (len(self.list_data) + ITEMS_PER_PAGE -
                       1) // ITEMS_PER_PAGE
        self.page = total_pages
        self.update_buttons()
        await self.update_message(interaction)

    @discord.ui.button(emoji="🗑️", style=discord.ButtonStyle.danger, row=2)
    async def delete_button(self, interaction: discord.Interaction,
                            button: discord.ui.Button):
        await interaction.message.delete()

    async def update_message(self, interaction: discord.Interaction):
        if self.list_type == "recent":
            embed = self.cog.anilist_module.create_recent_activities_embed(
                self.list_data, self.page)
        else:
            embed = self.cog.anilist_module.create_list_embed(
                self.list_data, self.list_type, self.status, self.page)
        await interaction.response.edit_message(embed=embed, view=self)


class ListTypeSelect(discord.ui.Select):

    def __init__(self, cog: commands.Cog) -> None:
        options = [
            discord.SelectOption(label="Anime List", value="anime"),
            discord.SelectOption(label="Manga List", value="manga"),
            discord.SelectOption(label="Recent Activities", value="recent")
        ]
        super().__init__(placeholder="Choose a list type", options=options)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        list_type: str = self.values[0]
        user_id: int = interaction.user.id
        access_token = self.cog.anilist_module.user_tokens.get(user_id)
        if access_token:
            try:
                if list_type == "recent":
                    activities = await self.cog.anilist_module.fetch_recent_activities(
                        access_token)
                    embed = self.cog.anilist_module.create_recent_activities_embed(
                        activities, 1)
                    view = Paginator(self.cog, activities, list_type, "recent")
                else:
                    current_list = await self.cog.anilist_module.fetch_user_list(
                        access_token, list_type, "CURRENT")
                    embed = self.cog.anilist_module.create_list_embed(
                        current_list, list_type, "CURRENT")
                    view = Paginator(self.cog, current_list, list_type,
                                     "CURRENT")
                    view.add_item(StatusSelect(self.cog, list_type))

                view.add_item(BackButton(self.cog))

                await interaction.response.edit_message(embed=embed, view=view)
            except Exception as e:
                await interaction.response.send_message(
                    f"An error occurred: {str(e)}", ephemeral=True)
        else:
            await interaction.response.send_message(
                "You are not authenticated. Please use the /anilist command to log in.",
                ephemeral=True)


class StatusSelect(discord.ui.Select):

    def __init__(self, cog: commands.Cog, list_type: str) -> None:
        options = [
            discord.SelectOption(label="Current", value="CURRENT"),
            discord.SelectOption(label="Completed", value="COMPLETED"),
            discord.SelectOption(label="Planning", value="PLANNING"),
            discord.SelectOption(label="Dropped", value="DROPPED"),
            discord.SelectOption(label="Paused", value="PAUSED")
        ]
        super().__init__(placeholder="Choose a status", options=options)
        self.cog = cog
        self.list_type = list_type

    async def callback(self, interaction: discord.Interaction) -> None:
        status: str = self.values[0]
        user_id: int = interaction.user.id
        access_token = self.cog.anilist_module.user_tokens.get(user_id)
        if access_token:
            try:
                list_data = await self.cog.anilist_module.fetch_user_list(
                    access_token, self.list_type, status)
                embed = self.cog.anilist_module.create_list_embed(
                    list_data, self.list_type, status)

                view = Paginator(self.cog, list_data, self.list_type, status)
                view.add_item(StatusSelect(self.cog, self.list_type))
                view.add_item(BackButton(self.cog))

                await interaction.response.edit_message(embed=embed, view=view)
            except Exception as e:
                await interaction.response.send_message(
                    f"An error occurred: {str(e)}", ephemeral=True)
        else:
            await interaction.response.send_message(
                "You are not authenticated. Please use the /anilist command to log in.",
                ephemeral=True)


class BackButton(discord.ui.Button):

    def __init__(self, cog: commands.Cog) -> None:
        super().__init__(label="Back", style=discord.ButtonStyle.secondary)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        user_id: int = interaction.user.id
        access_token = self.cog.anilist_module.user_tokens.get(user_id)
        if access_token:
            try:
                stats = await self.cog.anilist_module.fetch_anilist_data(
                    access_token)
                embed = self.cog.anilist_module.create_stats_embed(stats)

                view = discord.ui.View()
                view.add_item(ListTypeSelect(self.cog))
                view.add_item(CompareButton(self.cog.anilist_module))
                view.add_item(LogoutView(self.cog.anilist_module).children[0])

                await interaction.response.edit_message(embed=embed, view=view)
            except Exception as e:
                await interaction.response.send_message(
                    f"An error occurred: {str(e)}. Please try reconnecting.",
                    ephemeral=True)
                await self.cog.anilist_module.remove_token(user_id)
                del self.cog.anilist_module.user_tokens[user_id]
        else:
            view = AniListView(self.cog.anilist_module)
            await interaction.response.edit_message(
                content="AniList Integration", view=view, embed=None)


class AniListView(discord.ui.View):

    def __init__(self, module: AniListModule) -> None:
        super().__init__()
        self.module: AniListModule = module

    @discord.ui.button(label="Get Auth Code",
                       style=discord.ButtonStyle.primary)
    async def get_auth_code(self, interaction: discord.Interaction,
                            button: discord.ui.Button) -> None:
        instructions: str = (
            f"Please follow these steps to get your authorization code:\n\n"
            f"1. Click this link: [**Authenticate here**]({self.module.anilist_auth_url})\n"
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
        await interaction.response.send_modal(AniListAuthModal(self.module))


class AniListAuthModal(discord.ui.Modal, title='Enter AniList Auth Code'):

    def __init__(self, module: AniListModule) -> None:
        super().__init__()
        self.module: AniListModule = module

    auth_code: discord.ui.TextInput = discord.ui.TextInput(
        label='Enter your AniList authorization code',
        placeholder='Paste your auth code here...',
        required=True)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            access_token: Optional[str] = await self.module.get_access_token(
                self.auth_code.value)
            if not access_token:
                await interaction.followup.send(
                    "Failed to authenticate. Please try again.",
                    ephemeral=True)
                return

            user_id = interaction.user.id
            self.module.user_tokens[user_id] = access_token
            await self.module.save_token(user_id, access_token)

            stats: Optional[Dict[
                str, Any]] = await self.module.fetch_anilist_data(access_token)
            if not stats:
                await interaction.followup.send(
                    "Failed to fetch AniList data. Please try again.",
                    ephemeral=True)
                return

            embed: discord.Embed = self.module.create_stats_embed(stats)
            view = discord.ui.View()
            view.add_item(ListTypeSelect(self.module))  # Change this line
            view.add_item(CompareButton(self.module))
            view.add_item(LogoutView(self.module).children[0])
            message = await interaction.followup.send(embed=embed, view=view)
            view.message = message
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}",
                                            ephemeral=True)


class CompareButton(discord.ui.Button):

    def __init__(self, module: AniListModule):
        super().__init__(label="Compare", style=discord.ButtonStyle.primary)
        self.module = module

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CompareModal(self.module))


class CompareModal(discord.ui.Modal, title='Compare AniList Profiles'):

    def __init__(self, module: AniListModule):
        super().__init__()
        self.module = module

    compare_input = discord.ui.TextInput(
        label='Enter AniList username or Discord user ID',
        placeholder='Username or User ID to compare with',
        required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id
        if user_id not in self.module.user_tokens:
            await interaction.followup.send(
                "You need to connect your AniList account first.",
                ephemeral=True)
            return

        compare_value = self.compare_input.value

        try:
            # Fetch current user's stats
            current_user_stats = await self.module.fetch_anilist_data(
                self.module.user_tokens[user_id])

            # Fetch comparison user's stats
            if compare_value.isdigit():
                # It's a Discord user ID
                compare_user_id = int(compare_value)
                if compare_user_id in self.module.user_tokens:
                    compare_user_stats = await self.module.fetch_anilist_data(
                        self.module.user_tokens[compare_user_id])
                else:
                    await interaction.followup.send(
                        "The specified Discord user hasn't connected their AniList account.",
                        ephemeral=True)
                    return
            else:
                # It's an AniList username
                compare_user_stats = await self.module.fetch_anilist_data_by_username(
                    compare_value)

            if not compare_user_stats:
                await interaction.followup.send(
                    "Couldn't find AniList data for the specified user.",
                    ephemeral=True)
                return

            comparison_embed, graph_file = await self.module.compare_stats(
                current_user_stats, compare_user_stats)
            await interaction.followup.send(embed=comparison_embed,
                                            file=graph_file)

        except Exception as e:
            await interaction.followup.send(
                f"An error occurred during comparison: {str(e)}",
                ephemeral=True)


class LogoutView(discord.ui.View):

    def __init__(self, module: AniListModule) -> None:
        super().__init__(timeout=LOGOUT_BUTTON_TIMEOUT)
        self.module: AniListModule = module
        self.message: Optional[discord.Message] = None

    @discord.ui.button(label="Logout", style=discord.ButtonStyle.danger)
    async def logout(self, interaction: discord.Interaction,
                     button: discord.ui.Button) -> None:
        user_id = interaction.user.id
        if user_id in self.module.user_tokens:
            del self.module.user_tokens[user_id]
            await self.module.remove_token(user_id)
            await interaction.response.send_message(
                "You have been logged out from AniList. You'll need to reauthenticate to access your AniList data again.",
                ephemeral=True)
        else:
            await interaction.response.send_message(
                "You are not currently logged in to AniList.", ephemeral=True)

    async def on_timeout(self) -> None:
        if self.message:
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)

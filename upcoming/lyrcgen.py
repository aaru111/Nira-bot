"""
The MIT License (MIT)

Copyright (c) 2025-present Developer Anonymous

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

from collections.abc import Callable, ItemsView, Iterator, KeysView, ValuesView
import datetime
import io
import os
from typing import Any, Generic, Literal, TypeVar
import logging
import cachetools
import aiohttp
import discord
from discord.ext import commands, tasks
from playwright.async_api import async_playwright, Playwright, Browser

try:
    import orjson as json
except ImportError:
    import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MISSING = discord.utils.MISSING
K = TypeVar('K')
V = TypeVar('V')


class SpotifyHandler:

    def __init__(self, bot) -> None:
        self.client_id: str = os.environ['SPOTIFY_CLIENT_ID']
        self.client_secret: str = os.environ['SPOTIFY_CLIENT_SECRET']
        self.access_token: str = MISSING
        self.token_type: str = 'Bearer'
        self.expires_at: datetime.datetime | None = None
        self.bot = bot
        self._session: aiohttp.ClientSession | None = None
        self._song_cache = cachetools.LRUCache(maxsize=100)
        self._lyrics_cache = cachetools.LRUCache(maxsize=100)

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close_session(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def create_token(self) -> None:
        try:
            async with await self.get_session() as session:
                async with session.post(
                        'https://accounts.spotify.com/api/token',
                        headers={
                            'Content-Type': 'application/x-www-form-urlencoded'
                        },
                        data={
                            'grant_type': 'client_credentials',
                            'client_id': self.client_id,
                            'client_secret': self.client_secret,
                        },
                ) as response:
                    if response.status == 429:
                        raise RuntimeError(
                            "Spotify API rate limit exceeded. Please try again later."
                        )
                    data = await response.json(loads=json.loads)
                    if any(key not in data
                           for key in ('access_token', 'token_type',
                                       'expires_in')):
                        raise RuntimeError(
                            'Could not fetch Spotify access token')
                    self.access_token = data['access_token']
                    self.token_type = data['token_type']
                    self.expires_at = datetime.datetime.now(
                        datetime.timezone.utc) + datetime.timedelta(
                            seconds=int(data['expires_in']) -
                            60  # Buffer for safety
                        )
        except aiohttp.ClientError as e:
            logger.error(f"Failed to create Spotify token: {e}")
            raise RuntimeError(
                "Network error while fetching Spotify token. Please check your connection."
            )

    async def search_songs(self, query: str, /) -> list['Song']:
        cache_key = f"search:{query.lower()}"
        if cache_key in self._song_cache:
            return self._song_cache[cache_key]

        try:
            async with await self.get_session() as session:
                async with session.get(
                        'https://api.spotify.com/v1/search',
                        params={
                            'q': query,
                            'type': 'track',
                            'limit': 6
                        },
                        headers={
                            'Authorization':
                            f'{self.token_type} {self.access_token}'
                        },
                ) as response:
                    if response.status == 429:
                        raise RuntimeError(
                            "Spotify API rate limit exceeded. Please try again later."
                        )
                    data = await response.json(loads=json.loads)
                    if 'tracks' not in data or 'items' not in data['tracks']:
                        raise RuntimeError(
                            f"Could not fetch tracks for query {query!r}")
                    songs = Song._from_items(data['tracks']['items'], session)
                    self._song_cache[cache_key] = songs
                    return songs
        except aiohttp.ClientError as e:
            logger.error(f"Failed to search songs: {e}")
            raise RuntimeError(
                "Network error while searching songs. Please check your connection."
            )

    async def fetch_song_lyrics(self, artist: str, song: str) -> list[str]:
        cache_key = f"lyrics:{artist.lower()}:{song.lower()}"
        if cache_key in self._lyrics_cache:
            return self._lyrics_cache[cache_key]

        try:
            async with await self.get_session() as session:
                async with session.get(
                        'https://lrclib.net/api/get',
                        params={
                            'track_name': song,
                            'artist_name': artist
                        },
                ) as response:
                    if response.status == 429:
                        raise RuntimeError(
                            "Lyrics API rate limit exceeded. Please try again later."
                        )
                    data = await response.json(loads=json.loads)
                    if 'message' in data:
                        raise RuntimeError(data['message'])
                    lyrics = data.get('plainLyrics', '').split('\n')
                    self._lyrics_cache[cache_key] = lyrics
                    return lyrics
        except aiohttp.ClientError as e:
            logger.error(f"Failed to fetch lyrics: {e}")
            raise RuntimeError(
                "Network error while fetching lyrics. Please check your connection."
            )


class Album:

    def __init__(self, data: dict[str, Any],
                 session: aiohttp.ClientSession) -> None:
        self.name: str = data['name']
        self.album_type: str = data['album_type']
        self.artists: list['Artist'] = Artist._from_artists(data['artists'])
        self.external_urls: dict[str, str] = data['external_urls']
        self.href: str = data['href']
        self.id: str = data['id']
        self.images: list['SpotifyAsset'] = SpotifyAsset._from_images(
            data['images'], self.name, session)
        self.playable: bool = data['is_playable']
        self.release_date: str = data['release_date']
        self.track_count: int = data['total_tracks']
        self.type: Literal['album'] = data['type']
        self.uri: str = data['uri']

    @property
    def best_image(self) -> 'SpotifyAsset':
        l = sorted(self.images, key=lambda i: (i.height, i.width))
        return l[0]


class OrderedDict(Generic[K, V]):

    def __init__(self) -> None:
        self._data: dict[K, V] = {}

    def __setitem__(self, key: K, value: V) -> None:
        self._data[key] = value
        self._data = dict(sorted(self._data.items(), key=lambda i: i[0]))

    def __bool__(self) -> bool:
        return bool(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, key: K) -> V:
        return self._data[key]

    def __contains__(self, key: Any) -> bool:
        return key in self._data

    def __iter__(self) -> Iterator[K]:
        return iter(self._data)

    def keys(self) -> KeysView[K]:
        return self._data.keys()

    def values(self) -> ValuesView[V]:
        return self._data.values()

    def items(self) -> ItemsView[K, V]:
        return self._data.items()

    def pop(self, key: K, default: Any = None) -> Any:
        return self._data.pop(key, default)


class SpotifyAsset:

    def __init__(self, data: dict[str, Any], parent_name: str,
                 session: aiohttp.ClientSession) -> None:
        self.height: int = data['height']
        self.width: int = data['width']
        self.url: str = data['url']
        self._parent_name: str = parent_name
        self._session: aiohttp.ClientSession = session

    async def save(self,
                   fp: str | bytes | os.PathLike[Any] | io.BufferedIOBase,
                   *,
                   seek_begin: bool = True) -> int:
        data = await self.read()
        if isinstance(fp, io.BufferedIOBase):
            written = fp.write(data)
            if seek_begin:
                fp.seek(0)
            return written
        else:
            with open(fp, 'wb') as f:
                return f.write(data)

    async def read(self) -> bytes:
        try:
            async with self._session.get(self.url) as resp:
                return await resp.read()
        except aiohttp.ClientError as e:
            logger.error(f"Failed to read Spotify asset: {e}")
            raise RuntimeError("Failed to download image. Please try again.")

    async def to_file(self) -> discord.File:
        return discord.File(await self.read(), filename=self.filename)

    @property
    def filename(self) -> str:
        return f'{self._parent_name}-{self.height}x{self.width}.jpeg'

    @classmethod
    def _from_images(cls, images: list[dict[str, Any]], parent_name: str,
                     session: aiohttp.ClientSession) -> list['SpotifyAsset']:
        return [cls(d, parent_name, session) for d in images]


class Artist:

    def __init__(self, data: dict[str, Any]) -> None:
        self.external_urls: dict[str, str] = data['external_urls']
        self.href: str = data['href']
        self.id: str = data['id']
        self.name: str = data['name']
        self.type: Literal['artist'] = data['type']
        self.uri: str = data['uri']

    @classmethod
    def _from_artists(cls, data: list[dict[str, Any]]) -> list['Artist']:
        return [cls(d) for d in data]


class Song:

    def __init__(self, data: dict[str, Any],
                 session: aiohttp.ClientSession) -> None:
        self.album: Album = Album(data['album'], session)
        self.artists: list[Artist] = Artist._from_artists(data['artists'])
        self.disc_number: int = int(data['disc_number'])
        self.duration: int = int(data['duration_ms'])
        self.explicit: bool = data['explicit']
        self.external_urls: dict[str, str] = data['external_urls']
        self.href: str = data['href']
        self.id: str = data['id']
        self.local: bool = data['is_local']
        self.playable: bool = data['is_playable']
        self.name: str = data['name']
        self.popularity: int = data['popularity']
        self.preview_url: str | None = data['preview_url']
        self.track: int = data['track_number']
        self.type: Literal['track'] = data['type']
        self.uri: str = data['uri']

    @property
    def thumbnail(self) -> SpotifyAsset:
        return self.album.best_image

    @property
    def thumbnail_url(self) -> str:
        return self.thumbnail.url

    @property
    def main_artist(self) -> Artist:
        return self.artists[0]

    @classmethod
    def _from_items(cls, items: list[dict[str, Any]],
                    session: aiohttp.ClientSession) -> list['Song']:
        return [cls(d, session) for d in items]


class SelectSongView(discord.ui.View):

    def __init__(self, options: list[Song], author_id: int) -> None:
        super().__init__(timeout=180.0)
        self.author_id: int = author_id
        self.songs: list[Song] = options
        self.message: discord.Message = MISSING
        self.add_select_menu()

    def get_embed(self) -> discord.Embed:
        embed = discord.Embed(title="Select a Song",
                              colour=discord.Colour.blurple())
        for i, song in enumerate(self.songs, 1):
            embed.add_field(
                name=f"{i}. {song.name} by {song.main_artist.name}",
                value=
                f"**Album:** {song.album.name}\n**Track:** {song.track}\n**Explicit:** {'Yes' if song.explicit else 'No'}\n**Popularity:** {song.popularity}/100",
                inline=False)
        embed.set_footer(text="Use the dropdown to choose a song")
        if self.songs:
            embed.set_thumbnail(url=self.songs[0].thumbnail_url)
        return embed

    def add_select_menu(self) -> None:
        self.clear_items()
        select_options = [
            discord.SelectOption(
                label=f"{song.main_artist.name} - {song.name}", value=song.id)
            for song in self.songs
        ]
        self.add_item(
            ChooseSongSelect(options=select_options, songs=self.songs))

    async def interaction_check(self,
                                interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "You cannot use this select menu!", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        if self.message is not MISSING:
            for item in self.children:
                if hasattr(item, 'disabled'):
                    item.disabled = True
            try:
                await self.message.edit(view=self,
                                        embed=self.get_embed().set_footer(
                                            text="Selection timed out"))
            except discord.DiscordException as e:
                logger.error(f"Failed to edit message on timeout: {e}")


class ChooseSongSelect(discord.ui.Select):

    def __init__(self, options: list[discord.SelectOption],
                 songs: list[Song]) -> None:
        super().__init__(placeholder='Choose a song to get lyrics...',
                         options=options,
                         disabled=False)
        self.songs: dict[str, Song] = {song.id: song for song in songs}

    async def callback(self, interaction: discord.Interaction) -> None:
        song_id = self.values[0]
        song = self.songs.get(song_id)

        if song is None:
            await interaction.response.send_message(
                "Selected song not found. Please try again.", ephemeral=True)
            return

        cog: LyricsGenerator | None = interaction.client.get_cog(
            'LyricsGenerator')
        if not cog:
            await interaction.response.send_message(
                "Lyrics feature is currently unavailable.", ephemeral=True)
            return

        await interaction.response.defer()
        try:
            lyrics = await cog.handler.fetch_song_lyrics(
                song.main_artist.name, song.name)
            if not lyrics:
                await interaction.followup.send(
                    "No lyrics found for this song.", ephemeral=True)
                return
            view = LyricsGeneratorView(lyrics, interaction.client,
                                       interaction.user.id, song)
            await interaction.edit_original_response(embed=view.get_embed(),
                                                     view=view)
        except RuntimeError as error:
            await interaction.followup.send(str(error), ephemeral=True)


class AddLyricsButton(discord.ui.Button):

    def __init__(self, sect_id: int, page: int) -> None:
        super().__init__(label=f"Line {sect_id}",
                         style=discord.ButtonStyle.grey,
                         custom_id=f"add_lyrics_{sect_id}")
        self.sect_id: int = sect_id
        self.page: int = page

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view
        view: LyricsGeneratorView = self.view
        if self.sect_id in view.selected_lyrics:
            center = len(view.lyrics) / 2
            to_remove = [
                i for i in view.selected_lyrics
                if (i <= self.sect_id if self.sect_id < center else i >=
                    self.sect_id)
            ]
            for i in to_remove:
                view.selected_lyrics.pop(i, None)
            view.disable_items()
            await interaction.response.edit_message(embed=view.get_embed(),
                                                    view=view)
            return

        if view.selected_lyrics:
            selected_lines = sorted(view.selected_lyrics.keys())
            max_prev_line = min(selected_lines) - 1
            max_next_line = max(selected_lines) + 1
            if self.sect_id not in (max_prev_line, max_next_line):
                await interaction.response.send_message(
                    "You can only select adjacent lines!", ephemeral=True)
                return

        lyrics = view.lyrics[self.sect_id - 1]
        if not lyrics:
            await interaction.response.send_message(
                "Invalid lyric data. Please try again.", ephemeral=True)
            return

        view.selected_lyrics[self.sect_id] = lyrics
        view.disable_items()
        await interaction.response.edit_message(embed=view.get_embed(),
                                                view=view)
        await interaction.followup.send(
            f"Selected line {self.sect_id}: {lyrics[:50]}...", ephemeral=True)


class LyricsGeneratorView(discord.ui.View):

    def __init__(self, lyrics: list[str], bot, author_id: int,
                 song: Song) -> None:
        super().__init__(timeout=3600)
        self.song: Song = song
        self.lyrics: list[str] = lyrics
        self.paged_lyrics: dict[int, list[str]] = {
            page_id: page
            for page_id, page in enumerate(
                discord.utils.as_chunks([l for l in self.lyrics if l],
                                        max_size=10)) if page
        }
        self.current_page: int = 0
        self.selected_lyrics: OrderedDict[int, str] = OrderedDict()
        self.author_id: int = author_id
        self.add_items_to_container()

    def get_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=
            f"Lyrics for {self.song.name} by {self.song.main_artist.name}",
            colour=discord.Colour.blurple())
        start_idx = sum(
            len(self.paged_lyrics[i]) for i in range(self.current_page))
        for i, lyric in enumerate(self.paged_lyrics.get(self.current_page, []),
                                  start=start_idx + 1):
            status = "✅" if i in self.selected_lyrics else ""
            embed.add_field(name=f"Line {i}",
                            value=f"{status} {lyric[:200]}",
                            inline=False)
        embed.set_thumbnail(url=self.song.thumbnail_url)
        embed.set_footer(
            text=
            f"Page {self.current_page + 1}/{len(self.paged_lyrics)} | Select lines to generate image"
        )
        return embed

    def disable_items(self) -> None:
        if not self.selected_lyrics:
            for item in self.children:
                if isinstance(item, discord.ui.Button
                              ) and item.custom_id.startswith("add_lyrics_"):
                    item.disabled = False
                    item.label = f"Line {item.custom_id.split('_')[-1]}"
            return
        selected_lyrics = self.selected_lyrics.keys()
        selected_ids = list(selected_lyrics)
        prev_line = min(selected_ids) - 1
        next_line = max(selected_ids) + 1
        adjacent_ids = {prev_line, next_line}
        for item in self.children:
            if not isinstance(
                    item, discord.ui.Button) or not item.custom_id.startswith(
                        "add_lyrics_"):
                continue
            section_id = int(item.custom_id.split('_')[-1])
            if section_id in self.selected_lyrics:
                item.disabled = False
                item.label = f"Line {section_id} (Deselect)"
            elif section_id in adjacent_ids:
                item.disabled = False
                item.label = f"Line {section_id}"
            else:
                item.disabled = True
                item.label = f"Line {section_id}"

    def add_items_to_container(self) -> None:
        self.clear_items()
        start_idx = sum(
            len(self.paged_lyrics[i]) for i in range(self.current_page))
        for i, _ in enumerate(self.paged_lyrics.get(self.current_page, []),
                              start=start_idx + 1):
            self.add_item(AddLyricsButton(i, self.current_page))
        self.add_item(
            MovePage(lambda c: c - 1,
                     'Previous Page',
                     disabled=self.current_page == 0))
        self.add_item(
            discord.ui.Button(
                label=f'Page {self.current_page + 1}/{len(self.paged_lyrics)}',
                disabled=True,
                style=discord.ButtonStyle.grey))
        self.add_item(
            MovePage(lambda c: c + 1,
                     'Next Page',
                     disabled=self.current_page + 1 >= len(self.paged_lyrics)))
        self.add_item(GenerateLyrics(view=self, disabled=False))

    async def interaction_check(self,
                                interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "You cannot use these controls!", ephemeral=True)
            return False
        return True


class GenerateLyrics(discord.ui.Button):

    def __init__(self, disabled: bool, view: 'LyricsGeneratorView') -> None:
        super().__init__(style=discord.ButtonStyle.green,
                         label='Generate Image',
                         disabled=disabled)
        self.parent: LyricsGeneratorView = view

    async def callback(self, interaction: discord.Interaction) -> None:
        if not self.parent.selected_lyrics:
            await interaction.response.send_message(
                "Select at least one lyric line to generate an image!",
                ephemeral=True)
            return
        embed = discord.Embed(
            title="Generating Image",
            description="Please wait, this may take a moment...",
            colour=discord.Colour.blurple())
        await interaction.response.edit_message(embed=embed, view=None)
        view = LyricsImageSettingsView(self.parent)
        try:
            buffer = await view.generate_image()
            await interaction.edit_original_response(
                embed=view.get_embed(),
                view=view,
                attachments=[discord.File(buffer, 'image.png')])
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            await interaction.edit_original_response(embed=discord.Embed(
                title="Error",
                description="Failed to generate image. Please try again.",
                colour=discord.Colour.red()),
                                                     view=None,
                                                     attachments=[])


DEFAULT_CSS = """
@import url("https://fonts.googleapis.com/css2?family=Poppins:ital,wght@0,100;0,200;0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,100;1,200;1,300;1,400;1,500;1,600;1,700;1,800;1,900&family=Roboto:wght@400;700&family=Open+Sans:wght@400;700&display=swap");

* {
    box-sizing: border-box;
    font-family: "{font_family}", sans-serif;
    --background-color: rgba(246, 246, 246, 1);
    --background-text-color: rgba(18, 55, 64, 1);
    --surface-light-color: rgba(84, 154, 171, 0.1);
    --surface-color: rgba(84, 154, 171, 0.3);
    --surface-text-color: rgba(18, 55, 64, 0.85);
    --primary-color: rgba(241, 128, 45, 1);
    --primary-text-color: rgba(246, 246, 246, 1);
    --error-color: rgba(240, 40, 30, 0.3);
    --error-text-color: rgba(240, 40, 30, 1);
    --cubic-ease-out: cubic-bezier(0.215, 0.61, 0.355, 1);
}

.dark-mode, .dark-mode * {
    --background-color: rgba(20, 20, 20, 1);
    --background-text-color: rgba(72, 220, 255, 0.8);
    --surface-light-color: rgba(84, 154, 171, 0.1);
    --surface-color: rgba(84, 154, 171, 0.25);
    --surface-text-color: rgba(72, 220, 255, 0.7);
    --primary-color: rgba(241, 128, 45, 0.95);
    --primary-text-color: rgba(246, 246, 246, 1);
    --error-color: rgba(240, 40, 30, 0.2);
    --error-text-color: rgba(240, 40, 30, 1);
}

body {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    padding: 0;
    margin: 0;
}

.song-image {
    display: flex;
    flex-direction: column;
    padding: 1.2rem 1rem 1rem;
    max-width: 20rem;
    width: 95%;
    background-color: rgba({br}, {bg}, {bb}, 1);
    color: rgba(0, 0, 0, 0.95);
    border-radius: {border_radius}rem;
    transition: 200ms var(--cubic-ease-out);
}

.light-text .song-image {
    color: rgba(255, 255, 255, 0.95);
}

.song-image > .header {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding-bottom: 1.5rem;
}

.song-image > .header > img {
    height: 2.4rem;
    aspect-ratio: 1;
    border-radius: 0.5rem;
    object-fit: cover;
}

.song-image > .header .name {
    font-size: 0.95rem;
    font-weight: 700;
    line-height: 1.2rem;
    padding-bottom: 0.1rem;
}

.song-image > .header .authors {
    font-size: 0.75rem;
    line-height: 1rem;
    font-weight: 600;
    color: rgba(0, 0, 0, 0.6);
    transition: 200ms var(--cubic-ease-out);
}

.light-text .song-image > .header .authors {
    color: rgba(255, 255, 255, 0.7);
}

.song-image > .lyrics {
    font-size: 1.2rem;
    font-weight: 700;
    line-height: 1.5rem;
    padding-bottom: 0.2rem;
}

.song-image > .spotify {
    filter: brightness(0) saturate(100%) invert(0%) sepia(5%) saturate(22%) hue-rotate(164deg) brightness(96%) contrast(105%);
    height: 0;
    padding: 0;
    overflow: hidden;
    transition: 200ms var(--cubic-ease-out);
}

.spotify-tag .song-image > .spotify {
    height: 3rem;
    padding: 1.2rem 0 0.3rem;
}

.song-image > .spotify > img {
    height: 100%;
}

.light-text .song-image > .spotify {
    filter: brightness(0) saturate(100%) invert(100%) sepia(0%) saturate(0%) hue-rotate(93deg) brightness(103%) contrast(103%);
}

@media screen and (max-width: 450px) {
    .select-song {
        width: 45%;
    }
}
"""

DEFAULT_HTML = """
<!DOCTYPE html>
<head>
  <style>
  {css}
  </style>
</head>
<body>
  <div class="{light_mode}">
    <div class="song-image">
        <div class="header">
        <img src="{thumbnail}" alt="album-cover">
        <div>
            <div class="name">{songname}</div>
            <div class="authors">{songauthors}</div>
        </div>
        </div>
        <div class="lyrics">
          {lines}
        </div>
      {spotify}
    </div>
  </div>
</body>
"""

SPOTIFY_DIV = """
<div class="spotify">
  <img src="https://upload.wikimedia.org/wikipedia/commons/2/26/Spotify_logo_with_text.svg">
</div>
"""


class LyricsImageSettingsView(discord.ui.View):

    def __init__(self, parent: 'LyricsGeneratorView') -> None:
        super().__init__(timeout=3600)
        self.selected_lyrics = parent.selected_lyrics
        self.parent = parent
        self.raw_colour: str = '#008fd1'
        self.colour: discord.Colour = discord.Colour.from_str(self.raw_colour)
        self.light_text: bool = False
        self.spotify_logo: bool = False
        self.font_family: str = 'Poppins'
        self.border_radius: float = 1.5
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self.update_view()

    def get_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Customize Lyrics Image",
            description=
            "Adjust the settings below to customize your lyrics image.",
            colour=self.colour)
        embed.add_field(
            name="Selected Lyrics",
            value="\n".join(f"- {line}"
                            for line in self.selected_lyrics.values())[:1000]
            or "None",
            inline=False)
        embed.add_field(
            name="Current Settings",
            value=(
                f"**Colour:** {self.raw_colour}\n"
                f"**Font:** {self.font_family}\n"
                f"**Border Radius:** {self.border_radius}rem\n"
                f"**Light Text:** {'Yes' if self.light_text else 'No'}\n"
                f"**Spotify Logo:** {'Yes' if self.spotify_logo else 'No'}"),
            inline=False)
        embed.set_image(url='attachment://image.png')
        embed.set_footer(text="Use the dropdown to adjust settings")
        return embed

    async def _init_playwright(self) -> tuple[Playwright, Browser]:
        if self._playwright is None:
            self._playwright = await async_playwright().start()
        if self._browser is None:
            self._browser = await self._playwright.chromium.launch()
        return self._playwright, self._browser

    async def on_timeout(self) -> None:
        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.error(f"Failed to clean up Playwright resources: {e}")

    def get_replace_dict(self) -> dict[str, Any]:
        return {
            "light_mode":
            "light-text" if self.light_text else "",
            "br":
            self.colour.r,
            "bg":
            self.colour.g,
            "bb":
            self.colour.b,
            "thumbnail":
            self.parent.song.thumbnail_url,
            "songname":
            self.parent.song.name,
            "songauthors":
            ", ".join(a.name for a in self.parent.song.artists),
            "lines":
            '\n<br>'.join(self.selected_lyrics.values()).removesuffix('<br>'),
            "spotify":
            SPOTIFY_DIV if self.spotify_logo else "",
            "css":
            DEFAULT_CSS.format(font_family=self.font_family,
                               br=self.colour.r,
                               bg=self.colour.g,
                               bb=self.colour.b,
                               border_radius=self.border_radius),
        }

    def get_html(self) -> str:
        return DEFAULT_HTML.format_map(self.get_replace_dict())

    async def generate_image(self) -> io.BytesIO:
        try:
            playwright, browser = await self._init_playwright()
            async with browser.new_context() as context:
                page = await context.new_page()
                try:
                    await page.set_content(self.get_html(), wait_until='load')
                    await page.wait_for_selector('.song-image', timeout=5000)
                    elem = page.locator('.song-image')
                    ss = await elem.screenshot(omit_background=True,
                                               scale='css')
                finally:
                    await page.close()
            return io.BytesIO(ss)
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            raise RuntimeError("Failed to generate image. Please try again.")
        finally:
            self.update_view()

    def update_view(self) -> None:
        self.clear_items()
        options = [
            discord.SelectOption(label=f"Colour: {label}",
                                 value=f"colour:{value}")
            for label, value in (('Lochmara', '#008fd1'),
                                 ('Hippie Blue', '#549aab'),
                                 ('Pistachio', '#8fc00c'),
                                 ('Highland', '#729962'),
                                 ('Limed Oak', '#a2904e'),
                                 ('Indochine', '#cd6800'),
                                 ('Red Orange', '#fc302f'))
        ] + [
            discord.SelectOption(label=f"Font: {label}", value=f"font:{label}")
            for label in ('Poppins', 'Roboto', 'Open Sans')
        ] + [
            discord.SelectOption(label=f"Border Radius: {value}rem",
                                 value=f"radius:{value}")
            for value in (0.5, 1.0, 1.5, 2.0)
        ] + [
            discord.SelectOption(label="Toggle Spotify Logo",
                                 value="toggle_spotify"),
            discord.SelectOption(label="Toggle Light Text",
                                 value="toggle_light")
        ]
        self.add_item(
            discord.ui.Select(placeholder="Customize Image...",
                              options=options,
                              custom_id="customize_select"))
        self.add_item(FinishButton(self))
        self.add_item(ReturnToLyricsSelector(self, self.parent))


class FinishButton(discord.ui.Button):

    def __init__(self, parent: 'LyricsImageSettingsView') -> None:
        self.parent = parent
        super().__init__(style=discord.ButtonStyle.green, label='Finish')

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            ret = await self.parent.generate_image()
            file = discord.File(ret, filename='image.png')
            embed = discord.Embed(title="Your Lyrics Image",
                                  colour=self.parent.colour)
            embed.set_image(url='attachment://image.png')
            embed.set_footer(text="Enjoy your custom lyrics image!")
            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(label="Final Image",
                                  style=discord.ButtonStyle.grey,
                                  disabled=True))
            await self.parent.on_timeout()
            self.parent.stop()
            await interaction.response.edit_message(embed=embed,
                                                    attachments=[file],
                                                    view=view)
        except RuntimeError as e:
            await interaction.response.edit_message(
                embed=discord.Embed(title="Error",
                                    description=str(e),
                                    colour=discord.Colour.red()),
                view=None,
                attachments=[])


class ReturnToLyricsSelector(discord.ui.Button):

    def __init__(self, prev: 'LyricsImageSettingsView',
                 parent: 'LyricsGeneratorView') -> None:
        self.parent: LyricsGeneratorView = parent
        self.prev = prev
        super().__init__(style=discord.ButtonStyle.grey, label='Go Back')

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.prev.on_timeout()
        self.prev.stop()
        await interaction.response.edit_message(embed=self.parent.get_embed(),
                                                view=self.parent,
                                                attachments=[])


class CustomizeSelect(discord.ui.Select):

    def __init__(self, parent: 'LyricsImageSettingsView') -> None:
        options = [
            discord.SelectOption(label=f"Colour: {label}",
                                 value=f"colour:{value}")
            for label, value in (('Lochmara', '#008fd1'),
                                 ('Hippie Blue', '#549aab'),
                                 ('Pistachio', '#8fc00c'),
                                 ('Highland', '#729962'),
                                 ('Limed Oak', '#a2904e'),
                                 ('Indochine', '#cd6800'),
                                 ('Red Orange', '#fc302f'))
        ] + [
            discord.SelectOption(label=f"Font: {label}", value=f"font:{label}")
            for label in ('Poppins', 'Roboto', 'Open Sans')
        ] + [
            discord.SelectOption(label=f"Border Radius: {value}rem",
                                 value=f"radius:{value}")
            for value in (0.5, 1.0, 1.5, 2.0)
        ] + [
            discord.SelectOption(label="Toggle Spotify Logo",
                                 value="toggle_spotify"),
            discord.SelectOption(label="Toggle Light Text",
                                 value="toggle_light")
        ]
        super().__init__(placeholder="Customize Image...",
                         options=options,
                         custom_id="customize_select")
        self.parent = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        value = self.values[0]
        if value.startswith("colour:"):
            self.parent.raw_colour = value.split(":")[1]
            self.parent.colour = discord.Colour.from_str(
                self.parent.raw_colour)
        elif value.startswith("font:"):
            self.parent.font_family = value.split(":")[1]
        elif value.startswith("radius:"):
            self.parent.border_radius = float(value.split(":")[1])
        elif value == "toggle_spotify":
            self.parent.spotify_logo = not self.parent.spotify_logo
        elif value == "toggle_light":
            self.parent.light_text = not self.parent.light_text
        file = await self.parent.generate_image()
        await interaction.edit_original_response(
            embed=self.parent.get_embed(),
            view=self.parent,
            attachments=[discord.File(file, 'image.png')])


class MovePage(discord.ui.Button):

    def __init__(self,
                 key: Callable[[int], int],
                 label: str,
                 disabled: bool = False) -> None:
        self.key: Callable[[int], int] = key
        super().__init__(style=discord.ButtonStyle.blurple,
                         label=label,
                         disabled=disabled)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view
        view: LyricsGeneratorView = self.view
        view.current_page = self.key(view.current_page)
        view.add_items_to_container()
        view.disable_items()
        await interaction.response.edit_message(embed=view.get_embed(),
                                                view=view)


class LyricsGenerator(commands.Cog):
    """Generate lyric images for your favourite song!"""
    display_emoji = '\N{MUSICAL NOTE}'

    def __init__(self, bot) -> None:
        self.bot = bot
        self.handler: SpotifyHandler = SpotifyHandler(bot)

    async def cog_load(self) -> None:
        try:
            await self.handler.create_token()
            self.refresh_token.start()
        except Exception as e:
            logger.error(f"Failed to load cog: {e}")
            raise

    async def cog_unload(self) -> None:
        self.refresh_token.stop()
        await self.handler.close_session()

    @tasks.loop(hours=1)
    async def refresh_token(self) -> None:
        if self.handler.expires_at is None or self.handler.expires_at < datetime.datetime.now(
                datetime.timezone.utc):
            try:
                await self.handler.create_token()
            except RuntimeError as e:
                logger.error(f"Failed to refresh Spotify token: {e}")

    @commands.hybrid_command(name='generate-lyrics')
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def generate_lyrics(self, ctx: commands.Context, *,
                              query: str) -> None:
        """Generates a song's lyrics.

        Parameters
        ----------
        query
            The song to find and create the lyrics of.
        """
        try:
            songs = await self.handler.search_songs(query)
            if not songs:
                await ctx.reply(embed=discord.Embed(
                    title="No Results",
                    description=
                    "No songs found for your query. Try a different search term.",
                    colour=discord.Colour.red()))
                return
            view = SelectSongView(songs, ctx.author.id)
            view.message = await ctx.reply(embed=view.get_embed(), view=view)
        except RuntimeError as error:
            await ctx.reply(embed=discord.Embed(title="Error",
                                                description=str(error),
                                                colour=discord.Colour.red()))


async def setup(bot) -> None:
    await bot.add_cog(LyricsGenerator(bot))

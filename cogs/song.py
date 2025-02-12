import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from ShazamAPI import Shazam
import aiofiles
import aiohttp
import os
import yt_dlp
import tempfile

class MusicRecognition(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.temp_dir = tempfile.gettempdir()

    async def download_attachment(self, attachment, filename):
        full_path = os.path.join(self.temp_dir, filename)
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status == 200:
                    async with aiofiles.open(full_path, mode='wb') as f:
                        await f.write(await resp.read())
                        return full_path
        return None

    async def download_from_url(self, url):
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(self.temp_dir, '%(id)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return os.path.join(self.temp_dir, f"{info['id']}.mp3")

    def get_thumbnail_url(self, track):
        if 'images' in track:
            image_keys = ['coverarthq', 'coverart', 'background']
            for key in image_keys:
                if key in track['images'] and track['images'][key]:
                    return track['images'][key]
        return None

    async def process_audio_file(self, filename):
        with open(filename, 'rb') as file:
            shazam = Shazam(file.read())
            recognize_generator = shazam.recognizeSong()

            try:
                for result in recognize_generator:
                    if result and isinstance(result, tuple) and len(result) >= 2 and result[1]:
                        matches = result[1].get('matches', [])
                        if matches:
                            return result[1]
                return None
            except StopIteration:
                return None

    async def recognize_song_logic(self, ctx, url: str = None):
        if not url and not ctx.message.attachments:
            await ctx.send("Please provide a YouTube URL or attach an audio file!")
            return

        if url and not ('youtube.com' in url or 'youtu.be' in url):
            await ctx.send("Only YouTube URLs are supported!")
            return

        processing_msg = await ctx.send("🎵 Analyzing the audio...")
        filename = None

        try:
            if url:
                filename = await self.download_from_url(url)
            else:
                attachment = ctx.message.attachments[0]
                temp_filename = f"attachment_{ctx.message.id}{os.path.splitext(attachment.filename)[1]}"
                filename = await self.download_attachment(attachment, temp_filename)
                if not filename:
                    await processing_msg.edit(content="Failed to download the audio file!")
                    return

            result = await self.process_audio_file(filename)

            if not result:
                await processing_msg.edit(content="❌ Sorry, I couldn't recognize this song!")
                return

            if 'track' in result:
                track = result['track']
            else:
                matches = result.get('matches', [])
                if not matches:
                    await processing_msg.edit(content="❌ No matches found!")
                    return
                track = matches[0]

            title = track.get('title', 'Unknown Title')
            artist = track.get('subtitle', 'Unknown Artist')

            embed = discord.Embed(
                title="🎵 Song Recognized!",
                color=discord.Color.green()
            )
            embed.add_field(name="Title", value=title, inline=False)
            embed.add_field(name="Artist", value=artist, inline=False)

            if 'url' in track:
                embed.add_field(name="Listen On", value=f"[Shazam]({track['url']})", inline=False)

            thumbnail_url = self.get_thumbnail_url(track)
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

            await processing_msg.edit(content=None, embed=embed)

        except Exception as e:
            await processing_msg.edit(content=f"An error occurred: {str(e)}")

        finally:
            if filename and os.path.exists(filename):
                try:
                    os.remove(filename)
                except:
                    pass

    @commands.hybrid_command(
        name="recognize",
        description="Recognize a song from a YouTube URL or audio file"
    )
    @app_commands.describe(url="YouTube URL of the song to recognize")
    async def recognize_song(self, ctx, url: str = None):
        await self.recognize_song_logic(ctx, url)

async def setup(bot):
    await bot.add_cog(MusicRecognition(bot))
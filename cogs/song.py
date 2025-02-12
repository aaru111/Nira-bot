import discord
from discord.ext import commands
from discord import app_commands
from ShazamAPI import Shazam
import aiofiles
import aiohttp
import os
import yt_dlp
import tempfile
from typing import Optional
import audioop
import wave
import logging

logging.getLogger('yt_dlp').setLevel(logging.ERROR)

class MusicRecognition(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.temp_dir = tempfile.gettempdir()
        self.MAX_FILE_SIZE = 25 * 1024 * 1024
        self.MAX_DURATION = 300
        self.RATE_LIMIT = commands.CooldownMapping.from_cooldown(3, 60, commands.BucketType.user)

    async def download_attachment(self, attachment, filename):
        if attachment.size > self.MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds maximum limit of {self.MAX_FILE_SIZE // (1024*1024)}MB")

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
            'no_warnings': True,
            'max_filesize': self.MAX_FILE_SIZE,
            'max_duration': self.MAX_DURATION,
            'logger': None
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info.get('duration', 0) > self.MAX_DURATION:
                    raise ValueError(f"Video duration exceeds maximum limit of {self.MAX_DURATION // 60} minutes")
                return os.path.join(self.temp_dir, f"{info['id']}.mp3")
        except yt_dlp.utils.DownloadError as e:
            raise ValueError(f"Failed to download: {str(e)}")

    def get_thumbnail_url(self, track):
        if 'images' in track:
            image_keys = ['coverarthq', 'coverart', 'background']
            for key in image_keys:
                if key in track['images'] and track['images'][key]:
                    return track['images'][key]
        return None

    async def preprocess_audio(self, filename: str) -> Optional[str]:
        try:
            with wave.open(filename, 'rb') as wav_file:
                frames = wav_file.readframes(wav_file.getnframes())
                if wav_file.getnchannels() == 2:
                    frames = audioop.tomono(frames, wav_file.getsampwidth(), 1, 1)
                frames = audioop.normalize(frames, wav_file.getsampwidth(), 65535)
                processed_filename = os.path.join(self.temp_dir, f"processed_{os.path.basename(filename)}")
                with wave.open(processed_filename, 'wb') as processed_file:
                    processed_file.setnchannels(1)
                    processed_file.setsampwidth(wav_file.getsampwidth())
                    processed_file.setframerate(wav_file.getframerate())
                    processed_file.writeframes(frames)
                return processed_filename
        except:
            return filename

    async def process_audio_file(self, filename):
        processed_file = await self.preprocess_audio(filename)
        with open(processed_file, 'rb') as file:
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
            finally:
                if processed_file != filename and os.path.exists(processed_file):
                    try:
                        os.remove(processed_file)
                    except:
                        pass

    async def recognize_song_logic(self, ctx, url: str = None):
        bucket = self.RATE_LIMIT.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            raise commands.CommandOnCooldown(bucket, retry_after)

        if not url and not ctx.message.attachments:
            await ctx.send("Please provide a YouTube URL or attach an audio file!")
            return

        if url and not ('youtube.com' in url or 'youtu.be' in url):
            await ctx.send("Only YouTube URLs are supported!")
            return

        processing_msg = await ctx.send("🎵 Initializing...")
        filename = None

        try:
            if url:
                await processing_msg.edit(content="🎵 Downloading audio...")
                filename = await self.download_from_url(url)
            else:
                attachment = ctx.message.attachments[0]
                await processing_msg.edit(content="🎵 Processing attachment...")
                temp_filename = f"attachment_{ctx.message.id}{os.path.splitext(attachment.filename)[1]}"
                filename = await self.download_attachment(attachment, temp_filename)
                if not filename:
                    await processing_msg.edit(content="Failed to download the audio file!")
                    return

            await processing_msg.edit(content="🎵 Analyzing audio...")
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

        except ValueError as e:
            await processing_msg.edit(content=f"❌ Error: {str(e)}")
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
    @app_commands.describe(
        url="YouTube URL of the song to recognize (optional)",
        attachment="Audio file to recognize (optional)"
    )
    @commands.cooldown(3, 60, commands.BucketType.user)
    async def recognize_song(self, ctx, url: str = None, attachment: discord.Attachment = None):
        await ctx.defer()
        if attachment:
            ctx.message.attachments = [attachment]
        await self.recognize_song_logic(ctx, url)

    @recognize_song.error
    async def recognize_song_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"Please wait {error.retry_after:.1f} seconds before using this command again.")
        else:
            await ctx.send(f"An error occurred: {str(error)}")

async def setup(bot):
    await bot.add_cog(MusicRecognition(bot))
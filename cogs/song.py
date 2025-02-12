import discord
from discord.ext import commands
from discord import app_commands
from ShazamAPI import Shazam
import aiofiles
import aiohttp
import os
import yt_dlp
import tempfile
from typing import Optional, Dict
import audioop
import wave
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
from dataclasses import dataclass
from contextlib import asynccontextmanager

logging.getLogger('yt_dlp').setLevel(logging.ERROR)

@dataclass
class AudioProcessingResult:
    success: bool
    filename: str
    error: Optional[str] = None

class ResourceManager:
    def __init__(self, max_concurrent_downloads: int = 3):
        self.session: Optional[aiohttp.ClientSession] = None
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_downloads)
        self.temp_files: Dict[str, float] = {}
        self.cleanup_lock = asyncio.Lock()

    async def initialize(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def cleanup(self):
        if self.session:
            await self.session.close()
            self.session = None
        self.executor.shutdown(wait=False)

    async def register_temp_file(self, filepath: str):
        async with self.cleanup_lock:
            self.temp_files[filepath] = time.time()

    async def cleanup_old_files(self, max_age: int = 300):  # 5 minutes
        async with self.cleanup_lock:
            current_time = time.time()
            files_to_remove = []

            for filepath, creation_time in self.temp_files.items():
                if current_time - creation_time > max_age:
                    try:
                        if os.path.exists(filepath):
                            os.remove(filepath)
                        files_to_remove.append(filepath)
                    except Exception as e:
                        logging.error(f"Failed to remove temp file {filepath}: {e}")

            for filepath in files_to_remove:
                self.temp_files.pop(filepath, None)

    @asynccontextmanager
    async def get_session(self):
        await self.initialize()
        try:
            yield self.session
        except Exception as e:
            logging.error(f"Session error: {e}")
            raise

class MusicRecognition(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.temp_dir = tempfile.gettempdir()
        self.MAX_FILE_SIZE = 25 * 1024 * 1024
        self.MAX_DURATION = 300
        self.RATE_LIMIT = commands.CooldownMapping.from_cooldown(3, 60, commands.BucketType.user)
        self.resource_manager = ResourceManager()
        self.cleanup_task = None

    async def cog_load(self):
        await self.resource_manager.initialize()
        self.cleanup_task = self.bot.loop.create_task(self._periodic_cleanup())

    async def cog_unload(self):
        if self.cleanup_task:
            self.cleanup_task.cancel()
        await self.resource_manager.cleanup()

    async def _periodic_cleanup(self):
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                await self.resource_manager.cleanup_old_files()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Cleanup task error: {e}")

    async def download_attachment(self, attachment, filename) -> AudioProcessingResult:
        if attachment.size > self.MAX_FILE_SIZE:
            return AudioProcessingResult(
                success=False,
                filename="",
                error=f"File size exceeds maximum limit of {self.MAX_FILE_SIZE // (1024*1024)}MB"
            )

        full_path = os.path.join(self.temp_dir, filename)
        try:
            async with self.resource_manager.get_session() as session:
                async with session.get(attachment.url) as resp:
                    if resp.status == 200:
                        async with aiofiles.open(full_path, mode='wb') as f:
                            await f.write(await resp.read())
                            await self.resource_manager.register_temp_file(full_path)
                            return AudioProcessingResult(success=True, filename=full_path)
            return AudioProcessingResult(success=False, filename="", error="Failed to download attachment")
        except Exception as e:
            return AudioProcessingResult(success=False, filename="", error=str(e))

    async def download_from_url(self, url) -> AudioProcessingResult:
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
            def _download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if info.get('duration', 0) > self.MAX_DURATION:
                        raise ValueError(f"Video duration exceeds maximum limit of {self.MAX_DURATION // 60} minutes")
                    return os.path.join(self.temp_dir, f"{info['id']}.mp3")

            filename = await self.bot.loop.run_in_executor(
                self.resource_manager.executor,
                _download
            )
            await self.resource_manager.register_temp_file(filename)
            return AudioProcessingResult(success=True, filename=filename)
        except Exception as e:
            return AudioProcessingResult(success=False, filename="", error=str(e))

    def get_thumbnail_url(self, track):
        if 'images' in track:
            image_keys = ['coverarthq', 'coverart', 'background']
            for key in image_keys:
                if key in track['images'] and track['images'][key]:
                    return track['images'][key]
        return None

    async def preprocess_audio(self, filename: str) -> AudioProcessingResult:
        try:
            def _process():
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

            processed_filename = await self.bot.loop.run_in_executor(
                self.resource_manager.executor,
                _process
            )
            await self.resource_manager.register_temp_file(processed_filename)
            return AudioProcessingResult(success=True, filename=processed_filename)
        except Exception as e:
            return AudioProcessingResult(success=False, filename=filename, error=str(e))

    async def process_audio_file(self, filename):
        processed_result = await self.preprocess_audio(filename)
        processed_file = processed_result.filename

        def _recognize():
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

        try:
            result = await self.bot.loop.run_in_executor(
                self.resource_manager.executor,
                _recognize
            )
            return result
        finally:
            if processed_file != filename and os.path.exists(processed_file):
                try:
                    os.remove(processed_file)
                except Exception as e:
                    logging.error(f"Error removing processed file: {e}")

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
                download_result = await self.download_from_url(url)
                if not download_result.success:
                    await processing_msg.edit(content=f"❌ Error: {download_result.error}")
                    return
                filename = download_result.filename
            else:
                attachment = ctx.message.attachments[0]
                await processing_msg.edit(content="🎵 Processing attachment...")
                temp_filename = f"attachment_{ctx.message.id}{os.path.splitext(attachment.filename)[1]}"
                download_result = await self.download_attachment(attachment, temp_filename)
                if not download_result.success:
                    await processing_msg.edit(content=f"❌ Error: {download_result.error}")
                    return
                filename = download_result.filename

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

        except Exception as e:
            await processing_msg.edit(content=f"An error occurred: {str(e)}")

        finally:
            if filename and os.path.exists(filename):
                try:
                    os.remove(filename)
                except Exception as e:
                    logging.error(f"Error removing file {filename}: {e}")

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
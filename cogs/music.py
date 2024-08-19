import discord
from discord.ext import commands
import yt_dlp
import asyncio


class Music(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def join(self, ctx):
        if ctx.author.voice is None:
            await ctx.send("You are not in a voice channel")
            return
        voice_channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await voice_channel.connect()
        else:
            await ctx.voice_client.move_to(voice_channel)

    @commands.command()
    async def disconnect(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        else:
            await ctx.send("I'm not connected to a voice channel")

    @commands.command()
    async def play(self, ctx, *, query):
        if ctx.voice_client is None:
            await ctx.send(
                "I'm not connected to a voice channel. Use the join command first."
            )
            return

        await ctx.send(f"Searching for: {query}")

        ydl_opts = {
            'format':
            'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'no_warnings':
            True,
            'default_search':
            'ytsearch',
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)

                if 'entries' in info:
                    # It's a playlist or search query, get the first video
                    video = info['entries'][0]
                else:
                    # It's a single video
                    video = info

                url = video['url']
                title = video.get('title', 'Unknown Title')

            FFMPEG_OPTIONS = {
                'before_options':
                '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                'options': '-vn'
            }

            source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
            ctx.voice_client.play(source,
                                  after=lambda e: print(f'Player error: {e}')
                                  if e else None)

            await ctx.send(f"Now playing: {title}")

        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    @commands.command()
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("Paused")
        else:
            await ctx.send("Nothing is playing")

    @commands.command()
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("Resumed")
        else:
            await ctx.send("Nothing is paused")

    @commands.command()
    async def stop(self, ctx):
        if ctx.voice_client and (ctx.voice_client.is_playing()
                                 or ctx.voice_client.is_paused()):
            ctx.voice_client.stop()
            await ctx.send("Stopped")
        else:
            await ctx.send("Nothing is playing")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))

import discord
from discord.ext import commands
import asyncio
from shazamio import Shazam
import aiohttp
import os

class MusicRecognition(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.shazam = Shazam()

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Music Recognition cog loaded.")

    @commands.command(name='recognize', help='Recognize the song from an attached file')
    async def recognize_song(self, ctx):
        if len(ctx.message.attachments) == 0:
            await ctx.send("Please attach an audio or video file to recognize the song.")
            return

        attachment = ctx.message.attachments[0]
        # Check for valid file extensions
        if attachment.filename.lower().endswith(('.mp3', '.ogg', '.wav', '.flac', '.m4a', '.mp4')):
            try:
                # Download the file
                filename = f"temp_{attachment.filename}"
                await attachment.save(filename)

                # Recognize the song
                result = await self.recognize(filename)

                if result:
                    await ctx.send(f"**Song recognized:** {result['title']} by {result['subtitle']}")
                else:
                    await ctx.send("Sorry, I couldn't recognize this song.")

            except Exception as e:
                await ctx.send(f"An error occurred: {str(e)}")
            finally:
                if os.path.exists(filename):
                    os.remove(filename)
        else:
            await ctx.send("Please attach a valid audio or video file.")

    async def recognize(self, filename):
        async with aiohttp.ClientSession() as session:
            try:
                result = await self.shazam.recognize_song(session, filename)
                if result.get('matches'):
                    return result['track']
            except Exception as e:
                print(f"Shazam API error: {e}")
        return None

async def setup(bot):
    await bot.add_cog(MusicRecognition(bot))
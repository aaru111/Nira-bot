import discord
from discord.ext import commands
import random
from discord import Member, File
from io import BytesIO
from PIL import Image
from main import Bot
from typing import Union
from scripts.emojify import emojify_image
from jokeapi import Jokes
import aiohttp
import requests
from scripts.asciify import asciify
import os
from scripts.collatz import is_collatz_conjecture
import aiofiles
import asyncio


class Fun(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

    async def close(self):
        await self.session.close()

    @commands.Cog.listener()
    async def on_shutdown(self):
        await self.close()

    @commands.Cog.listener()
    async def on_disconnect(self):
        await self.close()

    class Fun(commands.Cog):

        def __init__(self, bot):
            self.bot = bot

    @commands.command()
    async def wanted(self, ctx: commands.Context, *, member: discord.Member):
        await ctx.defer()

        # Define the paths for the images
        wanted_image_path = "images/wanted.jpg"
        profile_image_path = "images/profile.jpg"  # Updated path

        # Check if the wanted image file exists
        if not os.path.exists(wanted_image_path):
            await ctx.send(
                f"File {wanted_image_path} not found. Please check the file path."
            )
            return

        try:
            # Open the wanted poster image asynchronously
            async with aiofiles.open(wanted_image_path, mode='rb') as f:
                wanted_bytes = await f.read()
                wanted = Image.open(BytesIO(wanted_bytes))
        except IOError:
            await ctx.send(
                f"Failed to open {wanted_image_path}. Please check the file.")
            return

        try:
            # Read the member's avatar
            avatar_bytes = BytesIO(await member.display_avatar.read())
            pfp = Image.open(avatar_bytes)
            pfp = pfp.resize((2691, 2510))
            wanted.paste(pfp, (750, 1867))
        except IOError:
            await ctx.send(
                "Failed to process the avatar image. Please try again.")
            return

        try:
            # Save the combined image asynchronously
            async with aiofiles.open(profile_image_path, mode='wb') as f:
                output_bytes = BytesIO()
                wanted.save(output_bytes, format='JPEG')
                await f.write(output_bytes.getvalue())
        except IOError:
            await ctx.send(
                f"Failed to save the profile image to {profile_image_path}.")
            return

        try:
            await ctx.send(file=discord.File(profile_image_path))
        except discord.DiscordException:
            await ctx.send("Failed to send the image. Please try again.")

    @commands.command()
    async def collatz(self, ctx, number: int):
        await ctx.defer()
        original_number = int(number)
        if is_collatz_conjecture(original_number):
            steps = []
            while original_number > 1:
                steps.append(original_number)
                if original_number % 2 == 0:
                    original_number //= 2
                else:
                    original_number = 3 * original_number + 1
            steps.append(1)

            steps_message = (
                f"The number {number} holds true for **Collatz conjecture**.\n"
                f"**Steps:**\n```py\n{steps}```\nReached 1 successfully!!")

            if len(steps_message) > 2000:
                with open("collatztxt.py", "w") as file:
                    file.write("steps = [\n")
                    for i in range(0, len(steps), 7):
                        file.write(", ".join(map(str, steps[i:i + 7])) + ",\n")
                    file.write("]\n")
                await ctx.send(
                    "The steps are too long to display here, so I've uploaded them as a file:",
                    file=discord.File("collatztxt.py"))
                os.remove("collatztxt.py")
            else:
                await ctx.send(steps_message)
        else:
            await ctx.send(f"The number {number} is not a Collatz conjecture.")

    @commands.command(aliases=['peepee', 'pipi', 'pepe'])
    async def pp(self, ctx):
        await ctx.defer()
        user = ctx.author.name
        footer_pfp = ctx.author.display_avatar
        pp_list = [
            '8>\nYou Have The Smallest PP In The World!🤣', '8=>', '8==>',
            '8===>', '8====>', '8=====>', '8======>', '8=======>',
            '8========>', '8==========>', '8===========>',
            '8============D\nYou Have The Largest PP In The World!🙀'
        ]
        embed = discord.Embed(title='PP Size Machine~', color=0x2f3135)
        embed.add_field(name='Your PP size is:',
                        value=f'```py\n{random.choice(pp_list)}```')
        embed.set_footer(text=f"Requested By: {user}", icon_url=footer_pfp)
        await ctx.send(embed=embed)

    @commands.command()
    async def emojify(self, ctx, url: Union[discord.Member, str], size: int):
        await ctx.defer()
        if isinstance(url, discord.Member):
            url = url.display_avatar.url

        def get_emojified_image():
            r = requests.get(url, stream=True)
            image = Image.open(r.raw).convert("RGB")
            res = emojify_image(image, size)
            if size > size:
                res = f"```{res}```"
            return res

        result = await self.bot.loop.run_in_executor(None, get_emojified_image)
        await ctx.send(f"```py\n{result}```")

    @commands.command()
    async def asciify(self,
                      ctx: commands.Context,
                      link: Union[Member, str],
                      new_width: int = 100):
        await ctx.defer()
        await asciify(ctx, link, new_width)

    @commands.command()
    async def rng(self, ctx):
        await ctx.defer()
        rand_int = random.randint(0, 1000)
        embed = discord.Embed(
            title="RNG Machine~",
            description="Generates A Random Number Between 1 And 1000",
            color=0x2f3131)
        embed.add_field(name="Number:", value=f"```py\n{rand_int}```")
        await ctx.send(embed=embed)

    @commands.command()
    async def joke(self, ctx: commands.Context):
        await ctx.defer()
        try:
            j = await Jokes()
            joke = await j.get_joke()

            # Ensure joke is treated as a dictionary
            joke = dict(joke)

            if joke["type"] == "single":
                msg = joke["joke"]
            else:
                msg = joke["setup"]
                if 'delivery' in joke:
                    msg += f"||{joke['delivery']}||"

            await ctx.send(msg)
        except Exception as e:
            await ctx.send(f"Error: {str(e)}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun(bot))

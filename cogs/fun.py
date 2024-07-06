import discord
from discord.ext import commands
import random
from discord import Member
from asciify import asciify
from io import BytesIO
from PIL import Image
from main import Bot
import requests
from typing import Union
from emojify import emojify_image
from jokeapi import Jokes
import aiohttp

class Fun(commands.Cog):

    def __init__(self, bot: Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def close(self):
        await self.session.close()

    @commands.hybrid_command()
    async def wanted(self, ctx: commands.Context, *, member: discord.Member):
        await ctx.defer()
        wanted = Image.open("wanted.jpg")
        data = BytesIO(await member.display_avatar.read())
        pfp = Image.open(data)
        pfp = pfp.resize((2691, 2510))
        wanted.paste(pfp, (750, 1867))
        wanted.save("profile.jpg")
        await ctx.send(file=discord.File("profile.jpg"))

    def is_collatz_conjecture(self, number):
        steps = []
        while number > 1:
            steps.append(number)
            if number % 2 == 0:
                number //= 2
            else:
                number = 3 * number + 1
        return number == 1

    @commands.hybrid_command()
    async def collatz(self, ctx, number: int):
        await ctx.defer()
        original_number = int(number)
        if self.is_collatz_conjecture(original_number):
            steps = []
            while original_number > 1:
                steps.append(original_number)
                if original_number % 2 == 0:
                    original_number //= 2
                else:
                    original_number = 3 * original_number + 1
            steps.append(1)
            await ctx.send(
                f"The number {number} holds true for **Collatz conjecture**.\n**Steps:**\n```py\n{steps}```\nReached 1 successfully!!"
            )
        else:
            await ctx.send(f"The number {number} is not a Collatz conjecture.")

    @commands.hybrid_command(aliases=['peepee', 'pipi', 'pepe'])
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

    @commands.hybrid_command()
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

    @commands.hybrid_command()
    async def asciify(self, ctx: commands.Context, link: Union[Member, str], new_width: int = 100):
        await ctx.defer()
        await asciify(ctx, link, new_width)

    @commands.hybrid_command()
    async def rng(self, ctx):
        await ctx.defer()
        rand_int = random.randint(0, 1000)
        embed = discord.Embed(
            title="RNG Machine~",
            description="Generates A Random Number Between 1 And 1000",
            color=0x2f3131)
        embed.add_field(name="Number:", value=f"```py\n{rand_int}```")
        await ctx.send(embed=embed)

    @commands.hybrid_command()
    async def joke(self, ctx: commands.Context):
        await ctx.defer()
        j = await Jokes()
        blacklist = ["racist"]
        if not ctx.message.channel.is_nsfw():
            blacklist.append("nsfw")
        joke = await j.get_joke(blacklist=blacklist)
        msg = ""
        if joke["type"] == "single":
            msg = joke["joke"]
        else:
            msg = joke["setup"]
            msg += f"||{joke['delivery']}||"
        await ctx.send(msg)

async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))

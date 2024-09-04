import discord
from discord.ext import commands
from discord.ext.commands import Context, Bot
import asyncpraw
import os
import random
from typing import List, Optional
from hentai import Hentai, Format, Utils
import DiscordUtils
from rule34 import Rule34
rule34 = Rule34()


# Load secrets from Replit environment variables
REDDIT_CLIENT_ID = os.environ['redditid']
REDDIT_CLIENT_SECRET = os.environ['redditsecret']
REDDIT_PASSWORD = os.environ['redditpassword']

reddit = asyncpraw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    username="aaru101",
    password=REDDIT_PASSWORD,
    user_agent="nira"  
)


class NSFW(commands.Cog):

    def __init__(self, client: Bot) -> None:
        self.client = client

    async def fetch_reddit_post(self, subreddit_name: str, ctx: Context) -> None:
        """Fetches a random top post from a subreddit and sends it as an embed."""
        msg = await ctx.send("Getting your content...")
        subreddit = await reddit.subreddit(subreddit_name)
        top = subreddit.top(limit=50)
        all_subs: List[asyncpraw.models.Submission] = [submission async for submission in top]

        ransub: asyncpraw.models.Submission = random.choice(all_subs)

        embed = discord.Embed(title=ransub.title, color=ctx.author.color, url=ransub.url)
        embed.set_image(url=ransub.url)
        embed.set_footer(text=f"Posted by {ransub.author} on Reddit. | ❤ {ransub.ups} | 💬 {ransub.num_comments}")

        await msg.delete()
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Get a hentai image from r/hentai.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def hentai(self, ctx: Context) -> None:
        await self.fetch_reddit_post('hentai', ctx)

    @commands.hybrid_command(description="Use a sauce code to find a hentai comic from nhentai.net.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def sauce(self, ctx: Context, id: Optional[str] = None) -> None:
        await ctx.send("Getting your content...")
        doujin = Utils.get_random_hentai() if id is None else Hentai(id)
        if not Hentai.exists(doujin.id):
            await ctx.send("Nothing found.")
        else:
            try:
                artist = doujin.artist[0].name if doujin.artist else "No artist"
            except IndexError:
                artist = "No artist"
                
            embeds = []
            for num, url in enumerate(doujin.image_urls, start=1):
                embed = discord.Embed(title=doujin.title(Format.Pretty), color=ctx.author.color, url=doujin.url)
                embed.set_image(url=url)
                embed.set_footer(text=f"Author: {artist} | Upload date: {doujin.upload_date} | Page {num} of {len(doujin.image_urls)}")
                embeds.append(embed)

            paginator = DiscordUtils.Pagination.CustomEmbedPaginator(ctx, remove_reactions=True)
            paginator.add_reaction('⏪', "back")
            paginator.add_reaction('⏩', "next")

            await paginator.run(embeds)

    @commands.hybrid_command(description="Get a porn image from r/porn.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def porn(self, ctx: Context) -> None:
        await self.fetch_reddit_post('porn', ctx)

    @commands.hybrid_command(aliases=["tits", "boob", "tit"], description="Get a picture of boobs via r/boobs.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def boobs(self, ctx: Context) -> None:
        await self.fetch_reddit_post('boobs', ctx)
    
    @commands.hybrid_command(aliases=["tittydrop", "titdrop"], description="Get a boobdrop from r/tittydrop. [MOST GIFS MAY NOT SHOW]")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def boobdrop(self, ctx: Context) -> None:
        await self.fetch_reddit_post('tittydrop', ctx)

    @commands.hybrid_command(description="What the fuck?")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def feet(self, ctx: Context) -> None:
        await ctx.send("What the fuck is wrong with you? Fucking toe gobbling fuck.")
        log_channel_id = 793927796354449459  # Replace with your actual channel ID
        await self.client.get_channel(log_channel_id).send("Some degenerate just tried to use the feet command.")

    @commands.hybrid_command(description="Get gay porn from r/gayporn.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def gay(self, ctx: Context) -> None:
        await self.fetch_reddit_post('gayporn', ctx)

    @commands.hybrid_command(aliases=["lesbo"], description="Get a lesbian porn image from r/lesbians.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def lesbian(self, ctx: Context) -> None:
        await self.fetch_reddit_post('lesbians', ctx)

    @commands.hybrid_command(description="Get Overwatch porn from r/overwatch_porn.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def overwatch(self, ctx: Context) -> None:
        await self.fetch_reddit_post('overwatch_porn', ctx)

    @commands.hybrid_command(description="Get an SFM piece of porn from r/sfmcompileclub.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def sfm(self, ctx: Context) -> None:
        await self.fetch_reddit_post('sfmcompileclub', ctx)

    @commands.hybrid_command(aliases=["vagina"], description="Get pussy pics from r/pussy.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def pussy(self, ctx: Context) -> None:
        await self.fetch_reddit_post('pussy', ctx)

    @commands.hybrid_command(description="Get a waifu from r/waifusgonewild.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def waifu(self, ctx: Context) -> None:
        await self.fetch_reddit_post('waifusgonewild', ctx)

    @commands.hybrid_command(aliases=["r34"], description="Get Rule34 images! [query] value is optional - defaults to r/rule34 when none.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def rule34(self, ctx: Context, *, query: Optional[str] = None) -> None:
        if query is None:
            await self.fetch_reddit_post('rule34', ctx)
        else:
            query = query.replace(" ", "_")
            msg = await ctx.send("Grabbing your content...")
            images = await rule34.getImages(tags=query)
            total = list(images)

            if not total:
                await ctx.send(f"No images were found on Rule34 with the tag `{query}`")
                return

            finalimg = random.choice(total)

            embed = discord.Embed(
                title=f'ID: {finalimg.id}',
                color=ctx.author.color,
                url=finalimg.file_url,
            )
            embed.set_image(url=finalimg.file_url)
            embed.set_footer(text=f"Posted by {finalimg.creator_ID} on Rule 34. | Score: {finalimg.score}")

            await msg.edit(embed=embed)

    @commands.hybrid_command(aliases=["futa"], description="Is futanari considered gay? Get a Futa image from r/futanari.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def futanari(self, ctx: Context) -> None:
        await self.fetch_reddit_post('futanari', ctx)

    @commands.hybrid_command(description="See images of naked people in pain. Images from r/bdsm.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def bdsm(self, ctx: Context) -> None:
        await self.fetch_reddit_post('bdsm', ctx)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NSFW(bot))
    
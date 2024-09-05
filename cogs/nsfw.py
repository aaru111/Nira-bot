import discord
from discord.ext import commands
from discord.ext.commands import Bot
import asyncpraw
import os
import random
from typing import List, Optional, TypeVar
from hentai import Hentai, Format, Utils
import DiscordUtils
from rule34 import Rule34
import asyncio
import time
from discord.errors import NotFound, HTTPException

rule34 = Rule34()

# Load secrets from environment variables
REDDIT_CLIENT_ID = os.environ['redditid']
REDDIT_CLIENT_SECRET = os.environ['redditsecret']
REDDIT_PASSWORD = os.environ['redditpassword']

reddit = asyncpraw.Reddit(client_id=REDDIT_CLIENT_ID,
                          client_secret=REDDIT_CLIENT_SECRET,
                          username="aaru101",
                          password=REDDIT_PASSWORD,
                          user_agent="nira")

T = TypeVar('T')


class NSFW(commands.Cog):

    def __init__(self, client: Bot) -> None:
        self.client = client

    async def handle_rate_limit(self, response):
        """Handles the rate-limit response from Discord."""
        if response.status == 429:
            retry_after = int(response.headers.get('Retry-After', 0))
            print(f"Rate limited. Retrying after {retry_after} seconds.")
            await asyncio.sleep(retry_after)

    async def fetch_reddit_post(self, subreddit_name: str,
                                ctx: commands.Context) -> None:
        """Fetches a random top post from a subreddit and sends it as an embed."""
        msg = await ctx.send("Getting your content...", delete_after=3)
        try:
            subreddit = await reddit.subreddit(subreddit_name)
            top = subreddit.top(limit=50)
            all_subs = [submission async for submission in top]

            if not all_subs:
                await ctx.send(f"No posts found in r/{subreddit_name}.",
                               delete_after=3)
                return

            ransub = random.choice(all_subs)

            if not ransub.url:
                await ctx.send(
                    "The fetched post does not contain a valid URL.",
                    delete_after=3)
                return

            embed = discord.Embed(title=ransub.title,
                                  color=ctx.author.color,
                                  url=ransub.url)
            embed.set_image(url=ransub.url)
            embed.set_footer(
                text=
                f"Posted by {ransub.author} on Reddit. | ❤ {ransub.ups} | 💬 {ransub.num_comments}"
            )

            # Safely delete the message and handle 404 error
            try:
                pass
            except NotFound:
                print("Message was already deleted.")

            await ctx.send(embed=embed)
        except HTTPException as e:
            if e.status == 429:
                retry_after = e.response.headers.get('Retry-After')
                print(f"Rate limited. Retrying after {retry_after} seconds.")
                await asyncio.sleep(int(retry_after))
            else:
                await ctx.send(f"An error occurred: {e}", delete_after=3)
        except Exception as e:
            await ctx.send(f"An error occurred: {e}", delete_after=3)
            try:
                pass
            except NotFound:
                pass

    async def check_nsfw_channel(self, ctx: commands.Context) -> bool:
        """Checks if the command is invoked in an NSFW channel."""
        if not ctx.channel.is_nsfw():
            await ctx.send("This command can only be used in NSFW channels.",
                           delete_after=3)
            return False
        return True

    @commands.hybrid_command(description="Get a hentai image from r/hentai.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.is_nsfw()
    async def hentai(self, ctx: commands.Context) -> None:
        if not await self.check_nsfw_channel(ctx):
            return
        await self.fetch_reddit_post('hentai', ctx)

    @commands.hybrid_command(
        description="Use a sauce code to find a hentai comic from nhentai.net."
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.is_nsfw()
    async def sauce(self,
                    ctx: commands.Context,
                    id: Optional[str] = None) -> None:
        if not await self.check_nsfw_channel(ctx):
            return
        await ctx.send("Getting your content...", delete_after=3)
        try:
            doujin = Utils.get_random_hentai() if id is None else Hentai(id)

            if not Hentai.exists(doujin.id):
                await ctx.send("Nothing found.", delete_after=3)
                return

            artist = doujin.artist[0].name if doujin.artist else "No artist"
            embeds = []
            for num, url in enumerate(doujin.image_urls, start=1):
                # Update the title to show the sauce code next to the title
                embed = discord.Embed(
                    title=f'{doujin.title(Format.Pretty)} (Sauce: {doujin.id})',
                    color=ctx.author.color,
                    url=doujin.url)
                embed.set_image(url=url)
                embed.set_footer(
                    text=
                    f"Artist: {artist} | Upload date: {doujin.upload_date} | Page {num} of {len(doujin.image_urls)}"
                )
                embeds.append(embed)

            paginator = DiscordUtils.Pagination.CustomEmbedPaginator(
                ctx, remove_reactions=True)
            paginator.add_reaction('⏪', "back")
            paginator.add_reaction('⏩', "next")

            await paginator.run(embeds)
        except Exception as e:
            await ctx.send(f"An error occurred: {e}", delete_after=3)

    @commands.hybrid_command(description="Get a porn image from r/porn.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.is_nsfw()
    async def porn(self, ctx: commands.Context) -> None:
        if not await self.check_nsfw_channel(ctx):
            return
        await self.fetch_reddit_post('porn', ctx)

    @commands.hybrid_command(aliases=["tits", "boob", "tit"],
                             description="Get a picture of boobs via r/boobs.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.is_nsfw()
    async def boobs(self, ctx: commands.Context) -> None:
        if not await self.check_nsfw_channel(ctx):
            return
        await self.fetch_reddit_post('boobs', ctx)

    @commands.hybrid_command(
        aliases=["tittydrop", "titdrop"],
        description="Get a boobdrop from r/tittydrop. [MOST GIFS MAY NOT SHOW]"
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.is_nsfw()
    async def boobdrop(self, ctx: commands.Context) -> None:
        if not await self.check_nsfw_channel(ctx):
            return
        await self.fetch_reddit_post('tittydrop', ctx)

    @commands.hybrid_command(description="What the fuck?")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.is_nsfw()
    async def feet(self, ctx: commands.Context) -> None:
        if not await self.check_nsfw_channel(ctx):
            return
        await ctx.send(
            "What the fuck is wrong with you? Fucking toe gobbling fuck.",
            delete_after=3)
        log_channel_id = 793927796354449459  # Replace with your actual channel ID
        await self.client.get_channel(log_channel_id).send(
            "Some degenerate just tried to use the feet command.")

    @commands.hybrid_command(description="Get gay porn from r/gayporn.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.is_nsfw()
    async def gay(self, ctx: commands.Context) -> None:
        if not await self.check_nsfw_channel(ctx):
            return
        await self.fetch_reddit_post('gayporn', ctx)

    @commands.hybrid_command(
        aliases=["lesbo"],
        description="Get a lesbian porn image from r/lesbians.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.is_nsfw()
    async def lesbian(self, ctx: commands.Context) -> None:
        if not await self.check_nsfw_channel(ctx):
            return
        await self.fetch_reddit_post('lesbians', ctx)

    @commands.hybrid_command(
        description="Get Overwatch porn from r/overwatch_porn.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.is_nsfw()
    async def overwatch(self, ctx: commands.Context) -> None:
        if not await self.check_nsfw_channel(ctx):
            return
        await self.fetch_reddit_post('overwatch_porn', ctx)

    @commands.hybrid_command(
        description="Get an SFM piece of porn from r/sfmcompileclub.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.is_nsfw()
    async def sfm(self, ctx: commands.Context) -> None:
        if not await self.check_nsfw_channel(ctx):
            return
        await self.fetch_reddit_post('sfmcompileclub', ctx)

    @commands.hybrid_command(aliases=["vagina"],
                             description="Get pussy pics from r/pussy.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.is_nsfw()
    async def pussy(self, ctx: commands.Context) -> None:
        if not await self.check_nsfw_channel(ctx):
            return
        await self.fetch_reddit_post('pussy', ctx)

    @commands.hybrid_command(description="Get a waifu from r/waifusgonewild.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.is_nsfw()
    async def waifu(self, ctx: commands.Context) -> None:
        if not await self.check_nsfw_channel(ctx):
            return
        await self.fetch_reddit_post('waifusgonewild', ctx)

    @commands.hybrid_command(
        aliases=["r34"],
        description=
        "Get Rule34 images! [query] value is optional - defaults to r/rule34 when none."
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.is_nsfw()
    async def rule34(self,
                     ctx: commands.Context,
                     *,
                     query: Optional[str] = None) -> None:
        if not await self.check_nsfw_channel(ctx):
            return
        if query is None:
            await self.fetch_reddit_post('rule34', ctx)
        else:
            query = query.replace(" ", "_")
            msg = await ctx.send("Grabbing your content...", delete_after=3)
            try:
                images = await rule34.getImages(tags=query)
                if images is None or not images:
                    await ctx.send(
                        f"No images were found on Rule34 with the tag `{query}`",
                        delete_after=3)
                    try:
                        pass
                    except NotFound:
                        pass
                    return

                total = list(images)
                finalimg = random.choice(total)

                embed = discord.Embed(
                    title=f'ID: {finalimg.id}',
                    color=ctx.author.color,
                    url=finalimg.file_url,
                )
                embed.set_image(url=finalimg.file_url)
                embed.set_footer(
                    text=
                    f"Posted by {finalimg.creator_ID} on Rule 34. | Score: {finalimg.score}"
                )

                try:
                    pass
                except NotFound:
                    pass

                await ctx.send(embed=embed)
            except HTTPException as e:
                if e.status == 429:
                    retry_after = e.response.headers.get('Retry-After')
                    print(
                        f"Rate limited. Retrying after {retry_after} seconds.")
                    await asyncio.sleep(int(retry_after))
                else:
                    await ctx.send(f"An error occurred: {e}", delete_after=3)
            except Exception as e:
                await ctx.send(f"An error occurred: {e}", delete_after=3)
                try:
                    pass
                except NotFound:
                    pass

    @commands.hybrid_command(
        aliases=["futa"],
        description=
        "Is futanari considered gay? Get a Futa image from r/futanari.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.is_nsfw()
    async def futanari(self, ctx: commands.Context) -> None:
        if not await self.check_nsfw_channel(ctx):
            return
        await self.fetch_reddit_post('futanari', ctx)

    @commands.hybrid_command(
        description="See images of naked people in pain. Images from r/bdsm.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.is_nsfw()
    async def bdsm(self, ctx: commands.Context) -> None:
        if not await self.check_nsfw_channel(ctx):
            return
        await self.fetch_reddit_post('bdsm', ctx)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NSFW(bot))

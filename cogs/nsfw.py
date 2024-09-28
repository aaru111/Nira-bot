import discord
from discord.ext import commands
from discord.ext.commands import Bot, Context
import random
from typing import List, Optional, TypeVar, Union
from hentai import Hentai, Format, Utils
import DiscordUtils
from rule34 import Rule34
import asyncio
from discord.errors import NotFound, HTTPException
import aiohttp

rule34 = Rule34()

T = TypeVar('T')


class NSFW(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot

    async def handle_rate_limit(self, response: discord.Message) -> None:
        if isinstance(response,
                      discord.Message) and response.content.startswith(
                          'You are being rate limited'):
            retry_after = int(
                response.content.split('Try again in ')[1].split(' seconds')
                [0])
            print(f"Rate limited. Retrying after {retry_after } seconds.")
            await asyncio.sleep(retry_after)

    async def fetch_realbooru_post(self,
                                   tags: str,
                                   ctx: Context,
                                   gif_only: bool = False) -> None:
        msg: discord.Message = await ctx.send(
            "Getting your content from Realbooru...", delete_after=3)
        try:
            if gif_only:
                tags += " gif"
            else:
                file_type = random.choice(['gif', 'jpg', 'png', 'jpeg'])
                tags += f" {file_type}"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f'https://realbooru.com/index.php?page=dapi&s=post&q=index&json=1&limit=100&tags={tags}'
                ) as resp:
                    if resp.status != 200:
                        await ctx.send(
                            f"An error occurred while fetching from Realbooru: {resp.status}",
                            delete_after=3)
                        return
                    data = await resp.json()

            if not data:
                await ctx.send(
                    f"No posts found on Realbooru with the tags: {tags}.",
                    delete_after=3)
                return

            post = random.choice(data)
            image_url = f"https://realbooru.com/images/{post['directory']}/{post['image']}"

            embed: discord.Embed = discord.Embed(
                title=f"Realbooru - {tags}",
                color=ctx.author.color,
                url=
                f"https://realbooru.com/index.php?page=post&s=view&id={post['id']}"
            )
            embed.set_image(url=image_url)
            embed.set_footer(
                text=
                f"ID: {post['id']} | Score: {post['score']} | Tags: {post['tags'][:100]}..."
            )

            try:
                await msg.delete()
            except NotFound:
                print("Message was already deleted.")

            await ctx.send(embed=embed)
        except HTTPException as e:
            if e.status == 429:
                retry_after: Union[str, None] = e.response.headers.get(
                    'Retry-After')
                print(f"Rate limited. Retrying after {retry_after} seconds.")
                await asyncio.sleep(int(retry_after) if retry_after else 0)
            else:
                await ctx.send(f"An error occurred: {e}", delete_after=3)
        except Exception as e:
            await ctx.send(f"An error occurred: {e}", delete_after=3)

    async def check_nsfw_channel(self, ctx: Context) -> bool:
        if not ctx.channel.is_nsfw():
            await ctx.send("This command can only be used in NSFW channels.",
                           delete_after=3)
            return False
        return True

    @commands.command(
        aliases=["nhentai", "doujin"],
        description="Use a sauce code to find a hentai comic from nhentai.net."
    )
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.is_nsfw()
    async def sauce(self, ctx: Context, id: Optional[str] = None) -> None:
        await ctx.defer()
        if not await self.check_nsfw_channel(ctx):
            return
        await ctx.send("Getting your content...", delete_after=3)
        try:
            doujin: Hentai = Utils.get_random_hentai(
            ) if id is None else Hentai(id)

            if not Hentai.exists(doujin.id):
                await ctx.send("Nothing found.", delete_after=3)
                return

            artist: str = doujin.artist[
                0].name if doujin.artist else "No artist"
            embeds: List[discord.Embed] = []
            for num, url in enumerate(doujin.image_urls, start=1):
                embed: discord.Embed = discord.Embed(
                    title=f'{doujin.title(Format.Pretty)} (Sauce: {doujin.id})',
                    color=ctx.author.color,
                    url=doujin.url)
                embed.set_image(url=url)
                embed.set_footer(
                    text=
                    f"Artist: {artist} | Upload date: {doujin.upload_date} | Page {num} of {len(doujin.image_urls)}"
                )
                embeds.append(embed)

            paginator: DiscordUtils.Pagination.CustomEmbedPaginator = DiscordUtils.Pagination.CustomEmbedPaginator(
                ctx, remove_reactions=True)
            paginator.add_reaction('⏪', "back")
            paginator.add_reaction('⏩', "next")

            await paginator.run(embeds)
        except Exception as e:
            await ctx.send(f"An error occurred: {e}", delete_after=3)

    @commands.command(
        aliases=["rule34"],
        description="Get Rule34 images! [query] value is optional.")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.is_nsfw()
    async def r34(self, ctx: Context, *, query: Optional[str] = None) -> None:
        await ctx.defer()
        if not await self.check_nsfw_channel(ctx):
            return

        msg: discord.Message = await ctx.send("Grabbing your content...",
                                              delete_after=3)

        async def fetch_rule34():
            try:
                images: Union[List[Rule34.Image],
                              None] = await rule34.getImages(
                                  tags=query if query else "")
                if images:
                    finalimg: Rule34.Image = random.choice(images)
                    await ctx.send(
                        f"Rule34 image (ID: {finalimg.id}, Score: {finalimg.score}):\n{finalimg.file_url}"
                    )
                    return True
                return False
            except Exception as e:
                print(f"Error fetching from Rule34: {e}")
                return False

        try:
            if not await fetch_rule34():
                await self.fetch_realbooru_post(query if query else "", ctx)
        except HTTPException as e:
            if e.status == 429:
                retry_after: Union[str, None] = e.response.headers.get(
                    'Retry-After')
                print(f"Rate limited. Retrying after {retry_after} seconds.")
                await asyncio.sleep(int(retry_after) if retry_after else 0)
            else:
                await ctx.send(f"An error occurred: {e}", delete_after=3)
        except Exception as e:
            await ctx.send(f"An error occurred: {e}", delete_after=3)

    @commands.command(aliases=["lesbian", "lesbians"],
                      description="Get real life lesbian images or GIFs")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.is_nsfw()
    async def rllesbian(self, ctx: Context, gif: Optional[str] = None):
        await self.fetch_realbooru_post("real_life lesbian",
                                        ctx,
                                        gif_only=(gif == "gif"))

    @commands.command(aliases=["mom", "mother"],
                      description="Get MILF images or GIFs")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.is_nsfw()
    async def milf(self, ctx: Context, gif: Optional[str] = None):
        await self.fetch_realbooru_post("milf", ctx, gif_only=(gif == "gif"))

    @commands.command(aliases=["tits", "breasts"],
                      description="Get boobs images or GIFs")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.is_nsfw()
    async def boobs(self, ctx: Context, gif: Optional[str] = None):
        await self.fetch_realbooru_post("breasts",
                                        ctx,
                                        gif_only=(gif == "gif"))

    @commands.command(aliases=["butt", "booty"],
                      description="Get ass images or GIFs")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.is_nsfw()
    async def ass(self, ctx: Context, gif: Optional[str] = None):
        await self.fetch_realbooru_post("ass", ctx, gif_only=(gif == "gif"))

    @commands.command(aliases=["vagina", "cunt"],
                      description="Get pussy images or GIFs")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.is_nsfw()
    async def pussy(self, ctx: Context, gif: Optional[str] = None):
        await self.fetch_realbooru_post("pussy", ctx, gif_only=(gif == "gif"))

    @commands.command(aliases=["bj", "oral"],
                      description="Get blowjob images or GIFs")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.is_nsfw()
    async def blowjob(self, ctx: Context, gif: Optional[str] = None):
        await self.fetch_realbooru_post("blowjob",
                                        ctx,
                                        gif_only=(gif == "gif"))

    @commands.command(aliases=["3some", "orgy"],
                      description="Get threesome images or GIFs")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.is_nsfw()
    async def threesome(self, ctx: Context, gif: Optional[str] = None):
        await self.fetch_realbooru_post("threesome",
                                        ctx,
                                        gif_only=(gif == "gif"))

    @commands.command(aliases=["butt_stuff", "backdoor"],
                      description="Get anal images or GIFs")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.is_nsfw()
    async def anal(self, ctx: Context, gif: Optional[str] = None):
        await self.fetch_realbooru_post("anal", ctx, gif_only=(gif == "gif"))

    @commands.command(aliases=["facial", "cum"],
                      description="Get cumshot images or GIFs")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.is_nsfw()
    async def cumshot(self, ctx: Context, gif: Optional[str] = None):
        await self.fetch_realbooru_post("cumshot",
                                        ctx,
                                        gif_only=(gif == "gif"))

    @commands.command(aliases=["bdsm", "tied"],
                      description="Get bondage images or GIFs")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.is_nsfw()
    async def bondage(self, ctx: Context, gif: Optional[str] = None):
        await self.fetch_realbooru_post("bondage",
                                        ctx,
                                        gif_only=(gif == "gif"))


async def setup(bot: Bot) -> None:
    await bot.add_cog(NSFW(bot))
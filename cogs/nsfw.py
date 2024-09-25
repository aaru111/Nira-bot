import discord
from discord.ext import commands
from discord.ext.commands import Bot, Context
import os
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

    def __init__(self, client: Bot) -> None:
        self.client: Bot = client

    async def handle_rate_limit(self, response: discord.Message) -> None:
        """Handles the rate-limit response from Discord."""
        if isinstance(response,
                      discord.Message) and response.content.startswith(
                          'You are being rate limited'):
            retry_after = int(
                response.content.split('Try again in ')[1].split(' seconds')
                [0])
            print(f"Rate limited. Retrying after {retry_after} seconds.")
            await asyncio.sleep(retry_after)

    async def fetch_realbooru_post(self, tags: str, ctx: Context) -> None:
        """Fetches a random post from Realbooru and sends it as an embed."""
        msg: discord.Message = await ctx.send(
            "Getting your content from Realbooru...", delete_after=3)
        try:
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

            # Construct the full image URL
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
        """Checks if the command is invoked in an NSFW channel."""
        if not ctx.channel.is_nsfw():
            await ctx.send("This command can only be used in NSFW channels.",
                           delete_after=3)
            return False
        return True

    @commands.command(
        description="Use a sauce code to find a hentai comic from nhentai.net."
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
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
        aliases=["r34"],
        description="Get Rule34 images! [query] value is optional.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.is_nsfw()
    async def rule34(self,
                     ctx: Context,
                     *,
                     query: Optional[str] = None) -> None:
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


async def setup(bot: Bot) -> None:
    await bot.add_cog(NSFW(bot))

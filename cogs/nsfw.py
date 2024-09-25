import discord
from discord.ext import commands
from discord.ext.commands import Bot, Context
import asyncpraw
import os
import random
from typing import List, Optional, TypeVar, Union
from hentai import Hentai, Format, Utils
import DiscordUtils
from rule34 import Rule34
import asyncio
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

    async def fetch_reddit_post(self, subreddit_name: str,
                                ctx: Context) -> None:
        """Fetches a random top post from a subreddit and sends it as an embed."""
        msg: discord.Message = await ctx.send("Getting your content...",
                                              delete_after=3)
        try:
            subreddit: asyncpraw.models.Subreddit = await reddit.subreddit(
                subreddit_name)
            top: asyncpraw.models.listing.generator.ListingGenerator = subreddit.top(
                limit=50)
            all_subs: List[asyncpraw.models.Submission] = [
                submission async for submission in top
            ]

            if not all_subs:
                await ctx.send(f"No posts found in r/{subreddit_name}.",
                               delete_after=3)
                return

            ransub: asyncpraw.models.Submission = random.choice(all_subs)

            if not ransub.url:
                await ctx.send(
                    "The fetched post does not contain a valid URL.",
                    delete_after=3)
                return

            embed: discord.Embed = discord.Embed(title=ransub.title,
                                                 color=ctx.author.color,
                                                 url=ransub.url)
            embed.set_image(url=ransub.url)
            embed.set_footer(
                text=
                f"Posted by {ransub.author} on Reddit. | ❤ {ransub.ups} | 💬 {ransub.num_comments}"
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
        description=
        "Get Rule34 images! [query] value is optional - defaults to r/rule34 when none."
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.is_nsfw()
    async def rule34(self,
                     ctx: Context,
                     *,
                     query: Optional[str] = None) -> None:
        await ctx.defer()
        if not await self.check_nsfw_channel(ctx):
            return
        if query is None:
            await self.fetch_reddit_post('rule34', ctx)
        else:
            query = query.replace(" ", "_")
            msg: discord.Message = await ctx.send("Grabbing your content...",
                                                  delete_after=3)
            try:
                images: Union[List[Rule34.Image],
                              None] = await rule34.getImages(tags=query)
                if images is None or not images:
                    await ctx.send(
                        f"No images were found on Rule34 with the tag `{query}`",
                        delete_after=3)
                    return

                total: List[Rule34.Image] = list(images)
                finalimg: Rule34.Image = random.choice(total)

                embed: discord.Embed = discord.Embed(
                    title=f'ID: {finalimg.id}',
                    color=ctx.author.color,
                    url=finalimg.file_url,
                )
                embed.set_image(url=finalimg.file_url)
                embed.set_footer(
                    text=
                    f"Posted by {finalimg.creator_ID} on Rule 34. | Score: {finalimg.score}"
                )

                await ctx.send(embed=embed)
            except HTTPException as e:
                if e.status == 429:
                    retry_after: Union[str, None] = e.response.headers.get(
                        'Retry-After')
                    print(
                        f"Rate limited. Retrying after {retry_after} seconds.")
                    await asyncio.sleep(int(retry_after) if retry_after else 0)
                else:
                    await ctx.send(f"An error occurred: {e}", delete_after=3)
            except Exception as e:
                await ctx.send(f"An error occurred: {e}", delete_after=3)


async def setup(bot: Bot) -> None:
    await bot.add_cog(NSFW(bot))

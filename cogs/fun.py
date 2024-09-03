import discord
from discord.ext import commands
from discord import app_commands
import random
from io import BytesIO
from PIL import Image
from jokeapi import Jokes
import aiohttp
import os
from scripts.collatz import is_collatz_conjecture
import aiofiles
from typing import Optional, List

# Global variables for reuse
DEFAULT_EMBED_COLOR: int = 0x2f3135
WANTED_IMAGE_PATH: str = "images/wanted.jpg"
PROFILE_IMAGE_PATH: str = "images/profile.jpg"
QUOTE_API_URL: str = "https://zenquotes.io/api/random"  # Tokenless API URL for random quotes
SLAP_GIF_API_URL: str = "https://g.tenor.com/v1/random?q=anime+slap&key=LIVDSRZULELA"  # Tenor API for random slap GIFs


class Fun(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        """Clean up resources when the cog is unloaded."""
        await self.session.close()

    async def fetch_quote(self) -> str:
        """Fetches a random quote from a tokenless API."""
        try:
            async with self.session.get(QUOTE_API_URL) as response:
                if response.status == 200:
                    data: List[dict[str, str]] = await response.json()
                    return data[0]['q'] + " — " + data[0][
                        'a']  # Quote with author
                else:
                    return "Could not retrieve a quote at this time."
        except Exception as e:
            return f"Error fetching quote: {str(e)}"

    async def fetch_slap_gif(self) -> str:
        """Fetches a random slap GIF URL from Tenor API."""
        try:
            async with self.session.get(SLAP_GIF_API_URL) as response:
                if response.status == 200:
                    data: dict = await response.json()
                    gif_url: str = data['results'][0]['media'][0]['gif']['url']
                    return gif_url
                else:
                    return "https://media.tenor.com/slap.gif"  # Fallback GIF
        except Exception as e:
            return "https://media.tenor.com/slap.gif"  # Fallback GIF

    @commands.hybrid_command(name="quote")
    @app_commands.describe(choice="Choose a quote type or write your own")
    @app_commands.choices(choice=[
        app_commands.Choice(name="Quote of the Day", value="qotd"),
        app_commands.Choice(name="Quote of the Month", value="qotm"),
        app_commands.Choice(name="Quote of the Year", value="qoty"),
        app_commands.Choice(name="Random Quote", value="random")
    ])
    async def quote(self,
                    ctx: commands.Context,
                    choice: Optional[str] = None) -> None:
        """
        Command to fetch a quote of the day, month, year, or a random quote.
        Users can also provide their custom quote.
        """
        await ctx.defer()

        # Using match-case for handling quote types
        match choice:
            case "qotd":
                quote: str = "This is the Quote of the Day!"
            case "qotm":
                quote = "This is the Quote of the Month!"
            case "qoty":
                quote = "This is the Quote of the Year!"
            case "random":
                quote = await self.fetch_quote()
            case _:
                quote = choice if choice else "No quote provided."

        embed: discord.Embed = discord.Embed(title="Quote",
                                             description=quote,
                                             color=DEFAULT_EMBED_COLOR)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="wanted")
    @app_commands.describe(member="The member to generate a wanted poster for")
    async def wanted(self,
                     ctx: commands.Context,
                     *,
                     member: Optional[discord.Member] = None) -> None:
        await ctx.defer()

        # If no member is mentioned, use the command issuer's profile picture
        if member is None:
            member = ctx.author

        # Check if the wanted image file exists
        if not os.path.exists(WANTED_IMAGE_PATH):
            await ctx.send(
                f"File {WANTED_IMAGE_PATH} not found. Please check the file path."
            )
            return

        try:
            # Open the wanted poster image asynchronously
            async with aiofiles.open(WANTED_IMAGE_PATH, mode='rb') as f:
                wanted_bytes: bytes = await f.read()
                wanted: Image.Image = Image.open(BytesIO(wanted_bytes))
        except IOError:
            await ctx.send(
                f"Failed to open {WANTED_IMAGE_PATH}. Please check the file.")
            return

        try:
            # Read the member's avatar
            avatar_bytes: BytesIO = BytesIO(await member.display_avatar.read())
            pfp: Image.Image = Image.open(avatar_bytes)
            pfp = pfp.resize((2691, 2510))
            wanted.paste(pfp, (750, 1867))
        except IOError:
            await ctx.send(
                "Failed to process the avatar image. Please try again.")
            return

        try:
            # Save the combined image asynchronously
            async with aiofiles.open(PROFILE_IMAGE_PATH, mode='wb') as f:
                output_bytes: BytesIO = BytesIO()
                wanted.save(output_bytes, format='JPEG')
                await f.write(output_bytes.getvalue())
        except IOError:
            await ctx.send(
                f"Failed to save the profile image to {PROFILE_IMAGE_PATH}.")
            return

        try:
            await ctx.send(file=discord.File(PROFILE_IMAGE_PATH))
        except discord.DiscordException:
            await ctx.send("Failed to send the image. Please try again.")

    @commands.hybrid_command(name="collatz")
    @app_commands.describe(
        number="Number to check against the Collatz conjecture")
    async def collatz(self, ctx: commands.Context, number: int) -> None:
        await ctx.defer()
        original_number: int = int(number)
        if is_collatz_conjecture(original_number):
            steps: List[int] = []
            while original_number > 1:
                steps.append(original_number)
                if original_number % 2 == 0:
                    original_number //= 2
                else:
                    original_number = 3 * original_number + 1
            steps.append(1)

            steps_message: str = (
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

    @commands.hybrid_command(name="pp")
    async def pp(self, ctx: commands.Context) -> None:
        """Generates a random 'pp' size."""
        await ctx.defer()
        user: str = ctx.author.name
        footer_pfp: discord.Asset = ctx.author.display_avatar
        pp_list: List[str] = [
            '8>\nYou Have The Smallest PP In The World!🤣', '8=>', '8==>',
            '8===>', '8====>', '8=====>', '8======>', '8=======>',
            '8========>', '8==========>', '8===========>',
            '8============D\nYou Have The Largest PP In The World!🙀'
        ]
        embed: discord.Embed = discord.Embed(title='PP Size Machine~',
                                             color=DEFAULT_EMBED_COLOR)
        embed.add_field(name='Your PP size is:',
                        value=f'```py\n{random.choice(pp_list)}```')
        embed.set_footer(text=f"Requested By: {user}", icon_url=footer_pfp)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="rng")
    async def rng(self, ctx: commands.Context) -> None:
        """Generates a random number between 1 and 1000."""
        await ctx.defer()
        rand_int: int = random.randint(0, 1000)
        embed: discord.Embed = discord.Embed(
            title="RNG Machine~",
            description="Generates A Random Number Between 1 And 1000",
            color=DEFAULT_EMBED_COLOR)
        embed.add_field(name="Number:", value=f"```py\n{rand_int}```")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="joke")
    async def joke(self, ctx: commands.Context) -> None:
        """Fetches a random joke from an API."""
        await ctx.defer()
        try:
            j: Jokes = await Jokes()
            joke: dict = await j.get_joke()

            # Ensure joke is treated as a dictionary
            joke = dict(joke)

            if joke["type"] == "single":
                msg: str = joke["joke"]
            else:
                msg = joke["setup"]
                if 'delivery' in joke:
                    msg += f"||{joke['delivery']}||"

            await ctx.send(msg)
        except Exception as e:
            await ctx.send(f"Error: {str(e)}")

    @commands.hybrid_command(name="slap")
    @app_commands.describe(who="The member to slap",
                           reason="Reason for slapping")
    async def slap(self,
                   ctx: commands.Context,
                   who: discord.Member,
                   reason: Optional[str] = None) -> None:
        """Command to slap a user with a reason."""
        await ctx.defer()
        gif_url: str = await self.fetch_slap_gif()

        default_reason_list: List[str] = [
            "an eyesore", "a fool", "stupid", "a dumbass", "a moron",
            "a loser", "a noob", "a bot", "a fool"
        ]

        if not reason:
            reason = random.choice(default_reason_list)

        embed: discord.Embed = discord.Embed(
            colour=discord.Color.random(),
            description=
            f"# {ctx.author.mention} slaps {who.mention} for being {' '.join(reason)}"
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        embed.set_image(url=gif_url)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun(bot))

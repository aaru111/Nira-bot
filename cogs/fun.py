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
from typing import Optional, List, Dict

# Global variables for reuse
DEFAULT_EMBED_COLOR: int = 0x2f3135
WANTED_IMAGE_PATH: str = "images/wanted.jpg"
PROFILE_IMAGE_PATH: str = "images/profile.jpg"
QUOTE_API_URL: str = "https://zenquotes.io/api/quotes/random"  # URL for random quotes
TENOR_API_KEY: str = "LIVDSRZULELA"  # Tenor API key


class Fun(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        """Clean up resources when the cog is unloaded."""
        await self.session.close()

    async def fetch_quote(self) -> str:
        """Fetches a random quote from the API."""
        try:
            async with self.session.get(QUOTE_API_URL) as response:
                if response.status == 200:
                    data: List[Dict[str, str]] = await response.json()
                    return data[0]['q'] + " — " + data[0][
                        'a']  # Quote with author
                else:
                    return "Could not retrieve a random quote at this time."
        except Exception as e:
            return f"Error fetching quote: {str(e)}"

    async def fetch_slap_gif(self, style: str) -> str:
        """Fetches a random slap GIF URL from Tenor API based on the selected style."""
        slap_styles: Dict[str, str] = {
            "anime": "anime slap",
            "classic": "classic slap",
            "meme": "meme slap"
        }
        query: str = slap_styles.get(style, "slap")
        slap_gif_api_url: str = f"https://g.tenor.com/v1/random?q={query}&key={TENOR_API_KEY}"

        try:
            async with self.session.get(slap_gif_api_url) as response:
                if response.status == 200:
                    data: Dict = await response.json()
                    gif_url: str = data['results'][0]['media'][0]['gif']['url']
                    return gif_url
                else:
                    return "https://media.tenor.com/slap.gif"  # Fallback GIF
        except Exception as e:
            return "https://media.tenor.com/slap.gif"  # Fallback GIF

    @commands.hybrid_command(name="quote")
    @app_commands.describe(
        quote="Enter your own quote or leave it empty for a random quote")
    async def quote(self,
                    ctx: commands.Context,
                    *,
                    quote: Optional[str] = None) -> None:
        """
        Command to fetch a random quote or display a user-provided quote.
        """
        await ctx.defer()

        if quote:
            display_quote = f"{quote} - {ctx.author.display_name}"
        else:
            display_quote = await self.fetch_quote()

        embed: discord.Embed = discord.Embed(title="Quote",
                                             description=display_quote,
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
        member = member or ctx.author

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

            joke = dict(joke)  # Ensure joke is treated as a dictionary

            match joke["type"]:
                case "single":
                    msg: str = joke["joke"]
                case "twopart":
                    msg = joke["setup"]
                    if 'delivery' in joke:
                        msg += f" ||{joke['delivery']}||"
                case _:
                    msg = "No joke found."

            await ctx.send(msg)
        except Exception as e:
            await ctx.send(f"Error: {str(e)}")

    @commands.hybrid_command(name="slap")
    @app_commands.describe(who="The member to slap",
                           reason="Reason for slapping",
                           style="Style of slap GIF")
    @app_commands.choices(style=[
        app_commands.Choice(name="Anime", value="anime"),
        app_commands.Choice(name="Classic", value="classic"),
        app_commands.Choice(name="Meme", value="meme")
    ])
    async def slap(self,
                   ctx: commands.Context,
                   who: discord.Member,
                   style: Optional[str] = "anime",
                   reason: Optional[str] = None) -> None:
        """Command to slap a user with a reason and choose a style of slap GIF."""
        await ctx.defer()
        gif_url: str = await self.fetch_slap_gif(style)

        default_reason_list: List[str] = [
            "an eyesore", "a fool", "stupid", "a dumbass", "a moron",
            "a loser", "a noob", "a bot", "a fool"
        ]

        reason = reason or random.choice(default_reason_list)

        embed: discord.Embed = discord.Embed(
            colour=discord.Color.random(),
            description=
            f"# {ctx.author.mention} slaps {who.mention} for being {reason}")
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        embed.set_image(url=gif_url)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun(bot))

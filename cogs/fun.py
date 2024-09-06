import discord
from discord.ext import commands
from discord import app_commands
import random
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import os
from scripts.collatz import is_collatz_conjecture
import aiofiles
from typing import Optional, List, Dict, Tuple, Any, Union
from modules.mememod import MemeView, MemeModule

# Global variables for reuse
DEFAULT_EMBED_COLOR: int = 0x2f3136
WANTED_IMAGE_PATH: str = "images/wanted.jpg"
PROFILE_IMAGE_PATH: str = "images/profile.jpg"
QUOTE_API_URL: str = "https://zenquotes.io/api/quotes/random"
TENOR_API_KEY: str = "LIVDSRZULELA"
QUOTE_IMAGE_SIZE: Tuple[int, int] = (1250, 500)
FONT_PATH: str = "fonts/ndot47.ttf"


class Fun(commands.Cog):
    bot: commands.Bot
    session: aiohttp.ClientSession
    meme_module: MemeModule

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.meme_module = MemeModule()

    async def cog_unload(self) -> None:
        await self.session.close()
        await self.meme_module.close()

    @app_commands.command(name="meme", description="Get a random meme")
    @app_commands.choices(topic=[
        app_commands.Choice(name="General", value="general"),
        app_commands.Choice(name="Anime", value="anime"),
        app_commands.Choice(name="Gaming", value="gaming"),
        app_commands.Choice(name="Programming", value="programming"),
        app_commands.Choice(name="Science", value="science"),
        app_commands.Choice(name="History", value="history"),
        app_commands.Choice(name="NSFW", value="nsfw"),
        app_commands.Choice(name="Shitposting", value="shitposting")
    ])
    async def meme(self, interaction: discord.Interaction,
                   topic: app_commands.Choice[str]):
        """Fetch a random meme from the specified topic."""
        if topic.value == "nsfw" and not interaction.channel.is_nsfw():
            await interaction.response.send_message(
                "NSFW memes can only be sent in age-restricted channels. Please use this command in an appropriate channel.",
                ephemeral=True)
            return
        meme = await self.meme_module.fetch_single_meme(topic.value)
        if not meme:
            await interaction.response.send_message(
                "Sorry, I couldn't fetch a meme at the moment. Please try again later.",
                ephemeral=True)
            return
        view = MemeView(self.bot, interaction, self, topic.value)
        view.meme_history.append(meme)
        view.current_index = 0
        embed = view.create_meme_embed(meme)
        view.update_button_states()
        await interaction.response.send_message(embed=embed, view=view)

    async def fetch_quote(self) -> Tuple[str, str]:
        try:
            async with self.session.get(QUOTE_API_URL) as response:
                if response.status == 200:
                    data: List[Dict[str, str]] = await response.json()
                    return data[0]['q'], data[0]['a']
                else:
                    return "Could not retrieve a random quote at this time.", "Unknown"
        except Exception as e:
            return f"Error fetching quote: {str(e)}", "Error"

    async def generate_quote_image(self, user: discord.Member, quote: str,
                                   author: str, sepia: bool) -> discord.File:
        # Create a new image with a black background
        image = Image.new('RGB', QUOTE_IMAGE_SIZE, color=(0, 0, 0))

        # Get user avatar
        avatar_width = QUOTE_IMAGE_SIZE[0] // 2
        avatar_height = QUOTE_IMAGE_SIZE[1]
        avatar_bytes = await user.display_avatar.read()
        avatar = Image.open(BytesIO(avatar_bytes)).convert('RGBA')
        avatar = avatar.resize((avatar_width, avatar_height), Image.LANCZOS)

        # Create a gradient mask for smooth transition
        gradient = Image.new('L', (avatar_width, avatar_height), color=0)
        gradient_draw = ImageDraw.Draw(gradient)
        for x in range(avatar_width):
            gradient_draw.line([(x, 0), (x, avatar_height)],
                               fill=int(255 * (1 - x / avatar_width)))

        # Apply gradient mask to avatar
        avatar.putalpha(gradient)

        # Paste avatar onto main image
        image.paste(avatar, (0, 0), avatar)

        # Apply sepia effect if requested
        if sepia:
            sepia_image = Image.new('RGB', QUOTE_IMAGE_SIZE)
            sepia_data = []
            for pixel in image.getdata():
                r, g, b = pixel[:3]
                tr = int(0.393 * r + 0.769 * g + 0.189 * b)
                tg = int(0.349 * r + 0.686 * g + 0.168 * b)
                tb = int(0.272 * r + 0.534 * g + 0.131 * b)
                sepia_data.append((min(tr, 255), min(tg, 255), min(tb, 255)))
            sepia_image.putdata(sepia_data)
            image = sepia_image

        draw = ImageDraw.Draw(image)

        # Load fonts (now using a bold font file)
        try:
            quote_font = ImageFont.truetype(
                FONT_PATH, 40)  # Initial size, will be adjusted
            author_font = ImageFont.truetype(FONT_PATH, 24)
        except IOError:
            quote_font = ImageFont.load_default()
            author_font = ImageFont.load_default()

        # Calculate and adjust font size based on quote length
        max_width = QUOTE_IMAGE_SIZE[0] // 2 - 50  # Space for quote
        max_height = QUOTE_IMAGE_SIZE[1] - 100  # Space for quote
        font_size = 40
        while font_size > 12:
            quote_font = ImageFont.truetype(FONT_PATH, font_size)
            lines = []
            words = quote.split()
            current_line = []
            for word in words:
                test_line = ' '.join(current_line + [word])
                bbox = draw.textbbox((0, 0), test_line, font=quote_font)
                if bbox[2] - bbox[0] <= max_width:
                    current_line.append(word)
                else:
                    lines.append(' '.join(current_line))
                    current_line = [word]
            lines.append(' '.join(current_line))

            total_height = len(lines) * (font_size + 10
                                         )  # 10 pixels between lines
            if total_height <= max_height:
                break
            font_size -= 2

        # Add quote text
        y_text = (QUOTE_IMAGE_SIZE[1] - total_height) // 2  # Center vertically
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=quote_font)
            x_text = QUOTE_IMAGE_SIZE[0] // 2 + (
                max_width -
                (bbox[2] - bbox[0])) // 2  # Center horizontally in right half
            draw.text((x_text, y_text),
                      line,
                      font=quote_font,
                      fill=(255, 255, 255))
            y_text += font_size + 10

        # Add author
        author_bbox = draw.textbbox((0, 0), f"- {author}", font=author_font)
        x_author = QUOTE_IMAGE_SIZE[0] // 2 + (
            max_width - (author_bbox[2] - author_bbox[0])
        ) // 2  # Center horizontally in right half
        draw.text((x_author, y_text + 20),
                  f"- {author}",
                  font=author_font,
                  fill=(200, 200, 200))

        # Save image to buffer
        buffer = BytesIO()
        image.save(buffer, 'PNG')
        buffer.seek(0)

        return discord.File(buffer, filename='quote.png')

    @commands.hybrid_command(name="quote")
    @app_commands.describe(
        quote="Enter your own quote or leave it empty for a random quote",
        member="The member to use the profile picture of (defaults to you)",
        sepia="Apply a sepia effect to the image (True/False)")
    async def quote(self,
                    ctx: commands.Context,
                    *,
                    quote: Optional[str] = None,
                    member: Optional[discord.Member] = None,
                    sepia: bool = False) -> None:
        await ctx.defer()

        member = member or ctx.author

        if quote:
            display_quote, author = quote, member.display_name
        else:
            display_quote, author = await self.fetch_quote()

        quote_image = await self.generate_quote_image(member, display_quote,
                                                      author, sepia)
        await ctx.send(file=quote_image)

    @commands.hybrid_command(name="wanted")
    @app_commands.describe(member="The member to generate a wanted poster for")
    async def wanted(self,
                     ctx: commands.Context,
                     *,
                     member: Optional[discord.Member] = None) -> None:
        await ctx.defer()

        member = member or ctx.author

        if not os.path.exists(WANTED_IMAGE_PATH):
            await ctx.send(
                f"File {WANTED_IMAGE_PATH} not found. Please check the file path."
            )
            return

        try:
            async with aiofiles.open(WANTED_IMAGE_PATH, mode='rb') as f:
                wanted_bytes: bytes = await f.read()
                wanted: Image.Image = Image.open(BytesIO(wanted_bytes))
        except IOError:
            await ctx.send(
                f"Failed to open {WANTED_IMAGE_PATH}. Please check the file.")
            return

        try:
            avatar_bytes: BytesIO = BytesIO(await member.display_avatar.read())
            pfp: Image.Image = Image.open(avatar_bytes)
            pfp = pfp.resize((2691, 2510))
            wanted.paste(pfp, (750, 1867))
        except IOError:
            await ctx.send(
                "Failed to process the avatar image. Please try again.")
            return

        try:
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
            steps: List[int] = self.generate_collatz_steps(original_number)
            steps_message: str = self.format_collatz_steps(number, steps)

            if len(steps_message) > 2000:
                self.save_collatz_steps_to_file(steps)
                await ctx.send(
                    "The steps are too long to display here, so I've uploaded them as a file:",
                    file=discord.File("collatztxt.py"))
                os.remove("collatztxt.py")
            else:
                await ctx.send(steps_message)
        else:
            await ctx.send(f"The number {number} is not a Collatz conjecture.")

    def generate_collatz_steps(self, number: int) -> List[int]:
        steps: List[int] = [number]
        while number > 1:
            number = number // 2 if number % 2 == 0 else 3 * number + 1
            steps.append(number)
        return steps

    def format_collatz_steps(self, original_number: int,
                             steps: List[int]) -> str:
        return (
            f"The number {original_number} holds true for **Collatz conjecture**.\n"
            f"**Steps:**\n```py\n{steps}```\nReached 1 successfully!!")

    def save_collatz_steps_to_file(self, steps: List[int]) -> None:
        with open("collatztxt.py", "w") as file:
            file.write("steps = [\n")
            for i in range(0, len(steps), 7):
                file.write(", ".join(map(str, steps[i:i + 7])) + ",\n")
            file.write("]\n")

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

    @app_commands.command(name="joke")
    @app_commands.describe(category="Choose a joke category")
    @app_commands.choices(category=[
        app_commands.Choice(name="Any", value="Any"),
        app_commands.Choice(name="Programming", value="Programming"),
        app_commands.Choice(name="Misc", value="Misc"),
        app_commands.Choice(name="Dark", value="Dark"),
        app_commands.Choice(name="Pun", value="Pun"),
        app_commands.Choice(name="Spooky", value="Spooky"),
        app_commands.Choice(name="Christmas", value="Christmas"),
        app_commands.Choice(name="NSFW", value="NSFW")
    ])
    async def joke(self,
                   interaction: discord.Interaction,
                   category: str = "Any") -> None:
        """Fetches a random joke from the selected category."""
        await interaction.response.defer()

        is_nsfw_channel = isinstance(
            interaction.channel,
            discord.TextChannel) and interaction.channel.is_nsfw()

        if (category in ["NSFW"] and not is_nsfw_channel):
            await interaction.followup.send(
                "This joke category can only be used in NSFW channels.")
            return

        try:
            joke = await self.get_joke(category, is_nsfw_channel)
            msg = self.format_joke(joke)
            await interaction.followup.send(msg)
        except Exception as e:
            await interaction.followup.send(f"Error: {str(e)}")

    async def get_joke(
            self, category: str,
            allow_nsfw: bool) -> Dict[str, Union[str, Dict[str, str]]]:
        params = {}
        if not allow_nsfw:
            params[
                "blacklistFlags"] = "nsfw,religious,political,racist,sexist,explicit"

        if category == "NSFW":
            url = "https://v2.jokeapi.dev/joke/Any"
            params["blacklistFlags"] = "religious,political,racist,sexist"
        else:
            url = f"https://v2.jokeapi.dev/joke/{category}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(
                        f"Failed to fetch joke: HTTP {response.status}")

    def format_joke(self, joke: Dict[str, Union[str, Dict[str, str]]]) -> str:
        if joke["type"] == "single":
            return joke["joke"]
        elif joke["type"] == "twopart":
            return f"{joke['setup']} ||{joke['delivery']}||"
        else:
            return "No joke found."

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
                    data: Dict[str, Any] = await response.json()
                    return data['results'][0]['media'][0]['gif']['url']
                else:
                    return "https://media.tenor.com/slap.gif"  # Fallback GIF
        except Exception:
            return "https://media.tenor.com/slap.gif"  # Fallback GIF

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

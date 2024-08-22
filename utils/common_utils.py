import discord
from discord.ext import commands
import asyncio
import aiohttp
import datetime

# Common settings
DEFAULT_TIMEOUT = 60  # Default timeout in seconds
MAX_RETRIES = 3  # Maximum number of retries for API calls


# Common classes
class TimeoutError(Exception):
    """Custom exception for timeout errors"""
    pass


class APIError(Exception):
    """Custom exception for API errors"""
    pass


# Utility functions
async def fetch_with_retry(session, url, max_retries=MAX_RETRIES):
    """Fetch data from URL with retry logic"""
    for attempt in range(max_retries):
        try:
            async with session.get(url, timeout=DEFAULT_TIMEOUT) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    # Rate limited, wait and retry
                    await asyncio.sleep(2**attempt)
                else:
                    raise APIError(
                        f"API returned status code {response.status}")
        except asyncio.TimeoutError:
            if attempt == max_retries - 1:
                raise TimeoutError("Request timed out after multiple attempts")
            await asyncio.sleep(2**attempt)
    raise APIError("Max retries reached")


# Common cog setup
class BaseCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        asyncio.create_task(self.session.close())

    @staticmethod
    def format_timestamp(timestamp):
        """Format a timestamp for Discord embed footer"""
        return f"Requested at {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"


# Embed utilities
def create_embed(title, description, color=discord.Color.blue()):
    """Create a basic embed with title, description, and timestamp"""
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text=BaseCog.format_timestamp(datetime.datetime.utcnow()))
    return embed


# Pagination
class PaginationView(discord.ui.View):

    def __init__(self, pages):
        super().__init__(timeout=300)
        self.pages = pages
        self.current_page = 0

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray)
    async def previous_button(self, interaction: discord.Interaction,
                              button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(
                embed=self.pages[self.current_page])

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await interaction.response.edit_message(
                embed=self.pages[self.current_page])


async def paginate(ctx, pages):
    """Send paginated embeds"""
    view = PaginationView(pages)
    await ctx.send(embed=pages[0], view=view)

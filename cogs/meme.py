import discord
from discord.ext import commands
import aiohttp
import random
import asyncio


class MemeView(discord.ui.View):

    def __init__(self, memes, ctx):
        super().__init__(timeout=60)
        self.memes = memes
        self.current_page = 0
        self.ctx = ctx

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray)
    async def previous_button(self, interaction: discord.Interaction,
                              button: discord.ui.Button):
        self.current_page = (self.current_page - 1) % len(self.memes)
        await self.update_message(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        self.current_page = (self.current_page + 1) % len(self.memes)
        await self.update_message(interaction)

    @discord.ui.button(emoji="🗑️", style=discord.ButtonStyle.red)
    async def delete_button(self, interaction: discord.Interaction,
                            button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        self.stop()

    async def update_message(self, interaction: discord.Interaction):
        embed = self.create_meme_embed(self.memes[self.current_page])
        await interaction.response.edit_message(embed=embed, view=self)

    @staticmethod
    def create_meme_embed(meme):
        embed = discord.Embed(title=meme['title'],
                              color=discord.Color.random())
        embed.set_image(url=meme['url'])
        embed.set_footer(
            text=f"Subreddit: r/{meme['subreddit']} | 👍 {meme['ups']}")
        return embed

    async def on_timeout(self):
        # Remove buttons after timeout
        try:
            await self.ctx.message.edit(view=None)
        except discord.errors.NotFound:
            # Message might have been deleted
            pass
        self.stop()


class MemeCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.meme_topics = {
            "anime": ["animemes", "AnimeFunny", "animenocontext"],
            "gaming": ["gamingmemes", "gaming"],
            "programming": ["ProgrammerHumor", "programmerreactions"],
            "dank": ["dankmemes", "memes"],
            "wholesome": ["wholesomememes", "MadeMeSmile"]
        }

    async def fetch_memes(self, subreddit=None, count=10):
        url = f'https://meme-api.com/gimme{"/" + subreddit if subreddit else ""}/{count}'
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        memes = data.get('memes', [])
                        return [
                            meme for meme in memes
                            if meme['url'].endswith(('.jpg', '.jpeg', '.png',
                                                     '.gif'))
                        ]
                    else:
                        print(f"Error fetching memes: HTTP {response.status}")
                        return []
            except aiohttp.ClientError as e:
                print(f"Error fetching memes: {str(e)}")
                return []

    @commands.command(name="meme")
    async def meme(self, ctx, topic: str = None):
        subreddit = None
        if topic:
            topic = topic.lower()
            if topic in self.meme_topics:
                subreddit = random.choice(self.meme_topics[topic])
            else:
                await ctx.send(
                    f"I don't have a specific category for '{topic}'. Using general memes instead."
                )

        memes = await self.fetch_memes(subreddit)

        if not memes:
            await ctx.send(
                "Sorry, I couldn't fetch any memes at the moment. Please try again later."
            )
            return

        view = MemeView(memes, ctx)
        embed = view.create_meme_embed(memes[0])
        view.message = await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(MemeCog(bot))

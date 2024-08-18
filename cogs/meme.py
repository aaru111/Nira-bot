import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import random
import asyncio


class MemeTopicModal(discord.ui.Modal, title="Change Meme Topic"):

    def __init__(self, meme_cog, view):
        super().__init__()
        self.meme_cog = meme_cog
        self.view = view

        self.topic = discord.ui.TextInput(
            label="Enter a new topic",
            placeholder="e.g., general, anime, gaming",
            max_length=20)
        self.add_item(self.topic)

    async def on_submit(self, interaction: discord.Interaction):
        new_topic = self.topic.value.strip().lower()
        if new_topic not in self.meme_cog.meme_topics:
            await interaction.response.send_message(
                f"Topic '{new_topic}' is not recognized. Please choose a valid topic.",
                ephemeral=True)
            return

        self.view.topic = new_topic
        self.view.meme_history = []
        self.view.current_index = -1
        await self.view.change_meme(interaction, direction=1)
        await interaction.followup.send(
            f"Topic changed to '{new_topic}'. Here's a meme from this topic:",
            ephemeral=True)


class MemeView(discord.ui.View):

    def __init__(self, bot, interaction, meme_cog, topic):
        super().__init__(timeout=60)
        self.bot = bot
        self.interaction = interaction
        self.meme_cog = meme_cog
        self.topic = topic
        self.meme_history = []
        self.current_index = -1

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray)
    async def previous_button(self, interaction: discord.Interaction,
                              button: discord.ui.Button):
        await self.change_meme(interaction, -1)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        await self.change_meme(interaction, 1)

    @discord.ui.button(emoji="🗑️", style=discord.ButtonStyle.red)
    async def delete_button(self, interaction: discord.Interaction,
                            button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        self.stop()

    @discord.ui.button(label="Change Topic",
                       style=discord.ButtonStyle.blurple,
                       row=2)
    async def change_topic_button(self, interaction: discord.Interaction,
                                  button: discord.ui.Button):
        modal = MemeTopicModal(self.meme_cog, self)
        await interaction.response.send_modal(modal)

    async def change_meme(self, interaction: discord.Interaction,
                          direction: int):
        if interaction.response.is_done():
            await interaction.followup.send(
                "This interaction has already been processed.", ephemeral=True)
            return

        try:
            if direction == 1:  # Next button
                meme = await self.meme_cog.fetch_single_meme(self.topic)
                if meme:
                    self.meme_history = self.meme_history[:self.current_index +
                                                          1]
                    self.meme_history.append(meme)
                    self.current_index += 1
            elif direction == -1:  # Previous button
                if self.current_index > 0:
                    self.current_index -= 1
                    meme = self.meme_history[self.current_index]
                else:
                    await interaction.response.send_message(
                        "No previous memes available.", ephemeral=True)
                    return

            if meme:
                embed = self.create_meme_embed(meme)
                self.update_button_states()
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.response.send_message(
                    "Failed to fetch a new meme. Please try again.",
                    ephemeral=True)

        except discord.errors.NotFound:
            try:
                await interaction.followup.send(
                    "This interaction is no longer valid. Please try again.",
                    ephemeral=True)
            except discord.errors.NotFound:
                pass

    def update_button_states(self):
        self.previous_button.disabled = self.current_index == 0
        self.next_button.disabled = False

    @staticmethod
    def create_meme_embed(meme):
        embed = discord.Embed(
            title=
            f"[{meme['title']}]({meme['postLink']}) (r/{meme['subreddit']})",
            color=discord.Color.random())
        embed.set_image(url=meme['url'])
        embed.set_footer(
            text=f"Posted by u/{meme['author']} | 👍 {meme['ups']}")
        return embed

    async def on_timeout(self):
        try:
            await self.interaction.edit_original_response(view=None)
        except discord.errors.NotFound:
            pass
        self.stop()


class MemeCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.meme_topics = {
            "general": [
                "memes", "dankmemes", "funny", "me_irl", "wholesomememes",
                "AdviceAnimals"
            ],
            "anime":
            ["Animemes", "anime_irl", "animenocontext", "wholesomeanimemes"],
            "gaming": ["gaming", "gamingmemes", "pcmasterrace", "gamephysics"],
            "programming":
            ["ProgrammerHumor", "programmerreactions", "softwaregore"],
            "science": ["sciencememes", "chemistrymemes", "physicsmemes"],
            "history": ["historymemes", "trippinthroughtime"],
            "nsfw": ["NSFWMemes", "pornmemes", "rule34memes"]
        }

    async def fetch_single_meme(self, topic):
        subreddit = random.choice(
            self.meme_topics.get(topic, self.meme_topics["general"]))
        url = f'https://meme-api.com/gimme/{subreddit}'
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data['url'].endswith(
                            ('.jpg', '.jpeg', '.png', '.gif')):
                            return data
                    return None
            except aiohttp.ClientError:
                return None

    @app_commands.command(name="meme", description="Get a random meme")
    @app_commands.choices(topic=[
        app_commands.Choice(name="General", value="general"),
        app_commands.Choice(name="Anime", value="anime"),
        app_commands.Choice(name="Gaming", value="gaming"),
        app_commands.Choice(name="Programming", value="programming"),
        app_commands.Choice(name="Science", value="science"),
        app_commands.Choice(name="History", value="history"),
        app_commands.Choice(name="NSFW", value="nsfw")
    ])
    async def meme(self, interaction: discord.Interaction,
                   topic: app_commands.Choice[str]):
        if topic.value == "nsfw" and not interaction.channel.is_nsfw():
            await interaction.response.send_message(
                "NSFW memes can only be sent in age-restricted channels. Please use this command in an appropriate channel.",
                ephemeral=True)
            return

        meme = await self.fetch_single_meme(topic.value)
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MemeCog(bot))

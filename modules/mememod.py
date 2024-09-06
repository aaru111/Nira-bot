import discord
from discord.ext import commands
from typing import Dict, List, Optional
import random
import aiohttp
import asyncio


class MemeModule:

    def __init__(self) -> None:
        self.meme_topics: Dict[str, List[str]] = {
            "general": [
                "memes", "dankmemes", "funny", "me_irl", "wholesomememes",
                "AdviceAnimals", "MemeEconomy", "ComedyCemetery",
                "terriblefacebookmemes"
            ],
            "anime":
            ["Animemes", "anime_irl", "animenocontext", "wholesomeanimemes"],
            "gaming": [
                "gaming", "pcmasterrace", "gamephysics", "gamingmemes",
                "truegaming", "leagueofmemes"
            ],
            "programming": ["ProgrammerHumor", "softwaregore", "linuxmemes"],
            "science": [
                "sciencememes", "chemistrymemes", "physicsmemes",
                "BiologyMemes", "mathmemes"
            ],
            "history": ["historymemes", "trippinthroughtime"],
            "nsfw": ["NSFWMemes", "BrainrotSluts"],
            "shitposting": [
                "shitposting", "okbuddyretard", "surrealmemes",
                "DeepFriedMemes", "bonehurtingjuice", "comedyheaven"
            ]
        }
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.last_request_time: float = 0
        self.request_cooldown: int = 1

    async def close(self) -> None:
        """Close the aiohttp session."""
        await self.session.close()

    async def fetch_single_meme(self, topic: str) -> Optional[Dict]:
        """Fetch a single meme from a randomly selected subreddit within the given topic."""
        current_time = asyncio.get_event_loop().time()
        if current_time - self.last_request_time < self.request_cooldown:
            await asyncio.sleep(self.request_cooldown -
                                (current_time - self.last_request_time))

        subreddit = random.choice(
            self.meme_topics.get(topic, self.meme_topics["general"]))
        url = f'https://meme-api.com/gimme/{subreddit}'
        async with self.session.get(url) as response:
            self.last_request_time = asyncio.get_event_loop().time()
            if response.status == 200:
                data = await response.json()
                if data['url'].endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    return data
            elif response.status == 429:
                retry_after = int(response.headers.get('Retry-After', 5))
                await asyncio.sleep(retry_after)
                return await self.fetch_single_meme(topic)
            return None


class TopicSelect(discord.ui.Select):

    def __init__(self, meme_view):
        self.meme_view = meme_view
        options = [
            discord.SelectOption(label="General", value="general"),
            discord.SelectOption(label="Anime", value="anime"),
            discord.SelectOption(label="Gaming", value="gaming"),
            discord.SelectOption(label="Programming", value="programming"),
            discord.SelectOption(label="Science", value="science"),
            discord.SelectOption(label="History", value="history"),
            discord.SelectOption(label="NSFW", value="nsfw"),
            discord.SelectOption(label="Shitposting", value="shitposting")
        ]
        super().__init__(placeholder="Select a topic", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.meme_view.interaction.user:
            await interaction.response.send_message(
                "You cannot interact with this command.", ephemeral=True)
            return

        new_topic = self.values[0]
        if new_topic == "nsfw" and not interaction.channel.is_nsfw():
            await interaction.response.send_message(
                "NSFW memes can only be sent in age-restricted channels.",
                ephemeral=True)
            return

        self.meme_view.topic = new_topic
        self.meme_view.meme_history = []
        self.meme_view.current_index = -1

        # Fetch a new meme for the changed topic
        await self.meme_view.change_meme(interaction, direction=1)


class MemeView(discord.ui.View):

    def __init__(self, bot: commands.Bot, interaction: discord.Interaction,
                 meme_cog, topic: str):
        super().__init__(timeout=60)
        self.bot = bot
        self.interaction = interaction
        self.meme_cog = meme_cog
        self.topic = topic
        self.meme_history: list = []
        self.current_index: int = -1

        # Add the TopicSelect first
        self.add_item(TopicSelect(self))

        # Then add the buttons
        self.previous_button = discord.ui.Button(
            label="Previous", style=discord.ButtonStyle.gray)
        self.previous_button.callback = self.previous_button_callback
        self.add_item(self.previous_button)

        self.next_button = discord.ui.Button(label="Next",
                                             style=discord.ButtonStyle.gray)
        self.next_button.callback = self.next_button_callback
        self.add_item(self.next_button)

        self.delete_button = discord.ui.Button(emoji="🗑️",
                                               style=discord.ButtonStyle.red)
        self.delete_button.callback = self.delete_button_callback
        self.add_item(self.delete_button)

        self.save_to_dm_button = discord.ui.Button(
            emoji="💾", style=discord.ButtonStyle.gray)
        self.save_to_dm_button.callback = self.save_to_dm_button_callback
        self.add_item(self.save_to_dm_button)

    async def previous_button_callback(self, interaction: discord.Interaction):
        await self.change_meme(interaction, -1)

    async def next_button_callback(self, interaction: discord.Interaction):
        await self.change_meme(interaction, 1)

    async def delete_button_callback(self, interaction: discord.Interaction):
        if interaction.user != self.interaction.user:
            await interaction.response.send_message(
                "You cannot interact with this command.", ephemeral=True)
            return
        await interaction.message.delete()
        self.stop()

    async def save_to_dm_button_callback(self,
                                         interaction: discord.Interaction):
        if interaction.user != self.interaction.user:
            await interaction.response.send_message(
                "You cannot interact with this command.", ephemeral=True)
            return

        if self.current_index >= 0:
            meme = self.meme_history[self.current_index]
            try:
                await interaction.user.send(
                    f"Here's the meme you requested:\n{meme['url']}")
                await interaction.response.send_message("Meme Saved!",
                                                        ephemeral=True)
            except discord.errors.Forbidden:
                await interaction.response.send_message(
                    "I don't have permission to send messages to your DMs.",
                    ephemeral=True)
        else:
            await interaction.response.send_message("No meme to save.",
                                                    ephemeral=True)

    async def change_meme(self, interaction: discord.Interaction,
                          direction: int):
        if interaction.user != self.interaction.user:
            await interaction.response.send_message(
                "You cannot interact with this command.", ephemeral=True)
            return

        try:
            meme = None
            if direction == 1:  # Next button
                meme = await self.meme_cog.meme_module.fetch_single_meme(
                    self.topic)
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

        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            await interaction.response.send_message(
                "An unexpected error occurred. Please try again later.",
                ephemeral=True)

    def update_button_states(self):
        self.previous_button.disabled = self.current_index == 0
        self.next_button.disabled = False
        self.save_to_dm_button.disabled = self.current_index < 0

    def create_meme_embed(self, meme: dict) -> discord.Embed:
        embed = discord.Embed(
            title=meme['title'],
            description=f"[View on r/{meme['subreddit']}]({meme['postLink']})",
            color=discord.Color.random())
        embed.set_image(url=meme['url'])
        embed.set_footer(
            text=
            f"Posted by u/{meme['author']} | 👍 {meme['ups']} | Topic: {self.topic}"
        )
        return embed

    async def on_timeout(self):
        try:
            await self.interaction.edit_original_response(view=None)
        except discord.errors.NotFound:
            pass
        self.stop()

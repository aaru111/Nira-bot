# modules/mememod.py

import discord
from discord import Interaction
from discord.ui import Modal, View, TextInput, Button
from discord.ext import commands
from discord.errors import HTTPException, NotFound, InteractionResponded
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
            "anime": [
                "Animemes", "anime_irl", "animenocontext", "wholesomeanimemes",
                "GoodAnimeMemes", "MemeAnime", "animeshitposting"
            ],
            "gaming": [
                "gaming", "gamingmemes", "pcmasterrace", "gamephysics",
                "gamememes", "truegaming", "leagueofmemes"
            ],
            "programming": [
                "ProgrammerHumor", "programmerreactions", "softwaregore",
                "codinghumor", "linuxmemes", "techhumor"
            ],
            "science": [
                "sciencememes", "chemistrymemes", "physicsmemes",
                "BiologyMemes", "mathmemes", "SpaceMemes"
            ],
            "history": [
                "historymemes", "trippinthroughtime", "HistoryAnimemes",
                "badlinguistics"
            ],
            "nsfw": ["NSFWMemes", "porn", "NSFW_IndianMemes", "BrainrotSluts"],
            "shitposting": [
                "shitposting", "okbuddyretard", "surrealmemes",
                "DeepFriedMemes", "nukedmemes", "bonehurtingjuice",
                "comedyheaven"
            ]
        }
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.last_request_time: float = 0
        self.request_cooldown: int = 2  # 2 seconds between requests

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


class MemeTopicModal(Modal, title="Change Meme Topic"):

    def __init__(self, meme_cog, view):
        super().__init__()
        self.meme_cog = meme_cog
        self.view = view
        self.topic = TextInput(
            label="Enter a new topic",
            placeholder="e.g., general, anime, gaming, shitposting",
            max_length=20)
        self.add_item(self.topic)

    async def on_submit(self, interaction: Interaction):
        if interaction.user != self.view.interaction.user:
            await interaction.response.send_message(
                "You cannot interact with this command.", ephemeral=True)
            return

        new_topic = self.topic.value.strip().lower()
        if new_topic not in self.meme_cog.meme_module.meme_topics:
            await interaction.response.send_message(
                f"Topic '{new_topic}' is not recognized. Please choose a valid topic.",
                ephemeral=True)
            return

        self.view.topic = new_topic
        self.view.meme_history = []
        self.view.current_index = -1

        # Fetch a new meme for the changed topic
        await self.view.change_meme(interaction, direction=1)
        try:
            await interaction.followup.send(
                f"Topic changed to '{new_topic}'. Here's a meme from this topic:",
                ephemeral=True)
        except NotFound:
            pass  # Ignore if the interaction is no longer valid


class MemeView(View):

    def __init__(self, bot: commands.Bot, interaction: Interaction, meme_cog,
                 topic: str):
        super().__init__(timeout=60)
        self.bot = bot
        self.interaction = interaction
        self.meme_cog = meme_cog
        self.topic = topic
        self.meme_history: list = []
        self.current_index: int = -1

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray)
    async def previous_button(self, interaction: Interaction, button: Button):
        if interaction.user != self.interaction.user:
            await interaction.response.send_message(
                "You cannot interact with this command.", ephemeral=True)
            return
        await self.change_meme(interaction, -1)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: Interaction, button: Button):
        if interaction.user != self.interaction.user:
            await interaction.response.send_message(
                "You cannot interact with this command.", ephemeral=True)
            return
        await self.change_meme(interaction, 1)

    @discord.ui.button(emoji="🗑️", style=discord.ButtonStyle.red)
    async def delete_button(self, interaction: Interaction, button: Button):
        if interaction.user != self.interaction.user:
            await interaction.response.send_message(
                "You cannot interact with this command.", ephemeral=True)
            return
        await interaction.response.edit_message(view=None)
        self.stop()

    @discord.ui.button(label="Change Topic",
                       style=discord.ButtonStyle.blurple,
                       row=2)
    async def change_topic_button(self, interaction: Interaction,
                                  button: Button):
        if interaction.user != self.interaction.user:
            await interaction.response.send_message(
                "You cannot interact with this command.", ephemeral=True)
            return
        modal = MemeTopicModal(self.meme_cog, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(emoji="💾", style=discord.ButtonStyle.gray, row=2)
    async def save_to_dm_button(self, interaction: Interaction,
                                button: Button):
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

    async def change_meme(self, interaction: Interaction, direction: int):
        if interaction.user != self.interaction.user:
            await interaction.response.send_message(
                "You cannot interact with this command.", ephemeral=True)
            return

        try:
            meme: Optional[Dict] = None
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
                try:
                    await interaction.response.edit_message(embed=embed,
                                                            view=self)
                except InteractionResponded:
                    await interaction.followup.edit_message(
                        embed=embed,
                        view=self,
                        message_id=interaction.message.id)
            else:
                await interaction.response.send_message(
                    "Failed to fetch a new meme. Please try again.",
                    ephemeral=True)

        except HTTPException as e:
            if e.status == 429:  # Too Many Requests
                retry_after = e.retry_after if hasattr(e, 'retry_after') else 5
                await asyncio.sleep(retry_after)
                await self.change_meme(interaction, direction)
            else:
                await self.handle_error(
                    interaction, "An error occurred. Please try again later.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            await self.handle_error(
                interaction,
                "An unexpected error occurred. Please try again later.")

    async def handle_error(self, interaction: Interaction, message: str):
        try:
            await interaction.response.send_message(message, ephemeral=True)
        except InteractionResponded:
            await interaction.followup.send(message, ephemeral=True)
        except NotFound:
            pass  # Ignore if the interaction is no longer valid

    def update_button_states(self):
        self.previous_button.disabled = self.current_index == 0
        self.next_button.disabled = False
        self.save_to_dm_button.disabled = self.current_index < 0

    def create_meme_embed(self, meme: Dict) -> discord.Embed:
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

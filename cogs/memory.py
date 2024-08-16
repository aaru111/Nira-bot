import discord
import random
from discord.ext import commands
from discord.ui import View, Button
from datetime import timedelta


class MemoryGameButton(Button):

    def __init__(self, x, y, emoji, cog):
        super().__init__(style=discord.ButtonStyle.secondary,
                         label="\u200b",
                         row=y)  # Using zero-width space as label
        self.x = x
        self.y = y
        self.hidden_emoji = emoji
        self.cog = cog
        self.revealed = False

    async def callback(self, interaction: discord.Interaction):
        if not self.revealed:
            self.revealed = True
            self.style = discord.ButtonStyle.success  # Green background
            self.emoji = self.hidden_emoji  # Reveal the hidden emoji
            self.label = "\u200b"  # Clear the label (question mark)
            await interaction.response.edit_message(view=self.cog.view)

            # Process the revealed button
            await self.cog.process_revealed_button(self, interaction)


class MemoryGameCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.view = None
        self.emojis = None
        self.board = None
        self.selected_buttons = []
        self.message = None

    @commands.command(name="memorygame")
    async def memorygame(self, ctx: commands.Context):
        """Starts a 5x5 memory game with custom server emojis."""
        # Gather custom emojis from the server
        guild_emojis = ctx.guild.emojis
        if len(guild_emojis) < 12:
            await ctx.send(
                "Not enough custom emojis in the server! You need at least 12."
            )
            return

        self.emojis = random.sample(guild_emojis, 12) * 2  # We need 12 pairs
        random.shuffle(self.emojis)

        self.view = View(
            timeout=20
        )  # Set the game to timeout after 20 seconds of inactivity
        self.board = [[None for _ in range(5)] for _ in range(5)]

        # Initialize the buttons
        for y in range(5):
            for x in range(5):
                if x == 2 and y == 2:
                    # Disable the middle button
                    button = Button(style=discord.ButtonStyle.secondary,
                                    label="X",
                                    disabled=True,
                                    row=y)
                else:
                    emoji = self.emojis.pop()
                    button = MemoryGameButton(x, y, emoji, self)

                self.board[y][x] = button
                self.view.add_item(button)

        # Show the game board with the emojis for 7 seconds
        self.message = await ctx.send(
            "Memory Game: Match the pairs! (Showing the emojis for 7 seconds...)",
            view=self.view)
        await self.reveal_all_emojis()
        await discord.utils.sleep_until(discord.utils.utcnow() +
                                        timedelta(seconds=7))
        await self.hide_all_emojis()
        await self.message.edit(content="Memory Game: Match the pairs!",
                                view=self.view)

    async def reveal_all_emojis(self):
        for y in range(5):
            for x in range(5):
                button = self.board[y][x]
                if not button.disabled:
                    button.emoji = button.hidden_emoji
                    button.label = "\u200b"  # Clear the label
                    button.style = discord.ButtonStyle.secondary
        await self.message.edit(view=self.view)

    async def hide_all_emojis(self):
        for y in range(5):
            for x in range(5):
                button = self.board[y][x]
                if not button.disabled:
                    button.label = "?"
                    button.emoji = None  # Hide the emoji
                    button.style = discord.ButtonStyle.secondary
                    button.revealed = False
        await self.message.edit(view=self.view)

    async def process_revealed_button(self, button: MemoryGameButton,
                                      interaction: discord.Interaction):
        self.selected_buttons.append(button)

        if len(self.selected_buttons) == 2:
            btn1, btn2 = self.selected_buttons

            if btn1.hidden_emoji == btn2.hidden_emoji:
                # If the two buttons match, disable them
                btn1.disabled = True
                btn2.disabled = True
            else:
                # If they don't match, turn them red and then hide again after a short delay
                btn1.style = discord.ButtonStyle.danger  # Red background
                btn2.style = discord.ButtonStyle.danger  # Red background
                await interaction.message.edit(view=self.view)

                await discord.utils.sleep_until(discord.utils.utcnow() +
                                                timedelta(seconds=1))
                btn1.label = "?"
                btn2.label = "?"
                btn1.emoji = None
                btn2.emoji = None
                btn1.style = discord.ButtonStyle.secondary
                btn2.style = discord.ButtonStyle.secondary
                btn1.revealed = False
                btn2.revealed = False

            # Reset the selected buttons
            self.selected_buttons.clear()

            await interaction.message.edit(view=self.view)

        # Reset the timeout after each interaction
        self.view.timeout = 20
        self.view.last_interaction = discord.utils.utcnow()

    @commands.Cog.listener()
    async def on_timeout(self):
        """Disable all buttons if the game times out due to inactivity."""
        for button in self.view.children:
            button.disabled = True
        await self.message.edit(content="Game ended due to inactivity.",
                                view=self.view)


async def setup(bot):
    await bot.add_cog(MemoryGameCog(bot))

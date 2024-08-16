import discord
import random
from discord.ext import commands
from discord.ui import View, Button
from datetime import timedelta, datetime


class MemoryGameButton(Button):

    def __init__(self, x, y, emoji, cog):
        super().__init__(style=discord.ButtonStyle.secondary, emoji="❓", row=y)
        self.x = x
        self.y = y
        self.hidden_emoji = emoji
        self.cog = cog
        self.revealed = False

    async def callback(self, interaction: discord.Interaction):
        if not self.revealed:
            self.revealed = True
            self.style = discord.ButtonStyle.success
            self.emoji = self.hidden_emoji
            await interaction.response.edit_message(view=self.cog.view)
            await self.cog.process_revealed_button(self, interaction)


class MemoryGameCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.view = None
        self.emojis = None
        self.board = None
        self.selected_buttons = []
        self.message = None
        self.start_time = None
        self.moves = 0
        self.pairs_found = 0

    @commands.command(name="memorygame")
    async def memorygame(self, ctx: commands.Context):
        """Starts a 5x5 memory game with custom server emojis."""
        self.start_time = datetime.now()
        self.moves = 0
        self.pairs_found = 0

        guild_emojis = ctx.guild.emojis
        pairs_needed = 12  # (5 * 5 - 1) // 2
        if len(guild_emojis) < pairs_needed:
            await ctx.send(
                f"Not enough custom emojis in the server! You need at least {pairs_needed}."
            )
            return

        self.emojis = random.sample(guild_emojis, pairs_needed) * 2
        random.shuffle(self.emojis)

        self.view = View(timeout=20)
        self.board = [[None for _ in range(5)] for _ in range(5)]

        middle = 2
        for y in range(5):
            for x in range(5):
                if x == middle and y == middle:
                    button = Button(style=discord.ButtonStyle.secondary,
                                    emoji="🔒",
                                    disabled=True)
                    self.board[y][x] = button
                    self.view.add_item(button)
                elif self.emojis:
                    emoji = self.emojis.pop()
                    button = MemoryGameButton(x, y, emoji, self)
                    self.board[y][x] = button
                    self.view.add_item(button)

        for item in self.view.children:
            item.disabled = True

        self.message = await ctx.send(
            "Memory Game (5x5): Match the pairs! (Showing the emojis for 7 seconds...)",
            view=self.view)
        await self.reveal_all_emojis()
        await discord.utils.sleep_until(discord.utils.utcnow() +
                                        timedelta(seconds=7))
        await self.hide_all_emojis()

        for item in self.view.children:
            if isinstance(item, MemoryGameButton):
                item.disabled = False

        await self.message.edit(content="Memory Game (5x5): Match the pairs!",
                                view=self.view)

    async def reveal_all_emojis(self):
        for row in self.board:
            for button in row:
                if isinstance(button, MemoryGameButton):
                    button.emoji = button.hidden_emoji
                    button.style = discord.ButtonStyle.secondary
        await self.message.edit(view=self.view)

    async def hide_all_emojis(self):
        for row in self.board:
            for button in row:
                if isinstance(button, MemoryGameButton):
                    button.emoji = "❓"
                    button.style = discord.ButtonStyle.secondary
                    button.revealed = False
        await self.message.edit(view=self.view)

    async def process_revealed_button(self, button: MemoryGameButton,
                                      interaction: discord.Interaction):
        self.selected_buttons.append(button)
        self.moves += 1

        if len(self.selected_buttons) == 2:
            btn1, btn2 = self.selected_buttons

            if btn1.hidden_emoji == btn2.hidden_emoji:
                btn1.disabled = True
                btn2.disabled = True
                self.pairs_found += 1

                if self.pairs_found == 12:
                    await self.end_game(interaction)
                    return
            else:
                btn1.style = discord.ButtonStyle.danger
                btn2.style = discord.ButtonStyle.danger
                await interaction.message.edit(view=self.view)

                await discord.utils.sleep_until(discord.utils.utcnow() +
                                                timedelta(seconds=1))
                btn1.emoji = "❓"
                btn2.emoji = "❓"
                btn1.style = discord.ButtonStyle.secondary
                btn2.style = discord.ButtonStyle.secondary
                btn1.revealed = False
                btn2.revealed = False

            self.selected_buttons.clear()
            await interaction.message.edit(view=self.view)

        self.view.timeout = 20
        self.view.last_interaction = discord.utils.utcnow()

    async def end_game(self, interaction: discord.Interaction):
        end_time = datetime.now()
        time_taken = end_time - self.start_time
        minutes, seconds = divmod(time_taken.seconds, 60)

        embed = discord.Embed(title="🎉 Memory Game Completed! 🎉",
                              color=0x00ff00)
        embed.add_field(name="🕒 Time Taken",
                        value=f"{minutes} minutes and {seconds} seconds",
                        inline=False)
        embed.add_field(name="🔢 Total Moves",
                        value=str(self.moves),
                        inline=False)
        embed.add_field(name="🧠 Board Size", value="5x5", inline=False)
        embed.set_footer(text="Thanks for playing!")

        await interaction.message.edit(content=None, embed=embed, view=None)

    @commands.Cog.listener()
    async def on_timeout(self):
        if self.message:
            await self.message.edit(content="Game ended due to inactivity.",
                                    view=None)


async def setup(bot):
    await bot.add_cog(MemoryGameCog(bot))

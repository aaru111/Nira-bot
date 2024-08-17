import discord
from discord.ext import commands
from discord import ui
import random
from datetime import timedelta, datetime


class MemoryGameButton(discord.ui.Button):

    def __init__(self, x: int, y: int, emoji: str):
        super().__init__(style=discord.ButtonStyle.secondary, emoji="❓", row=y)
        self.x = x
        self.y = y
        self.hidden_emoji = emoji
        self.revealed = False

    async def callback(self, interaction: discord.Interaction):
        await self.view.process_button(self, interaction)


class MemoryGameView(discord.ui.View):

    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=20)
        self.ctx = ctx
        self.board = []
        self.selected_buttons = []
        self.moves = 0
        self.pairs_found = 0
        self.start_time = None
        self.message = None
        self.setup_board()

    def setup_board(self):
        guild_emojis = self.ctx.guild.emojis
        pairs_needed = 12
        if len(guild_emojis) < pairs_needed:
            raise ValueError(
                f"Not enough custom emojis in the server! You need at least {pairs_needed}."
            )

        emojis = random.sample(guild_emojis, pairs_needed) * 2
        random.shuffle(emojis)

        for y in range(5):
            for x in range(5):
                if x == 2 and y == 2:
                    self.add_item(
                        ui.Button(style=discord.ButtonStyle.secondary,
                                  emoji="🔒",
                                  disabled=True,
                                  row=y))
                else:
                    button = MemoryGameButton(x, y, emojis.pop())
                    self.add_item(button)
                    self.board.append(button)

    async def start_game(self, existing_message=None):
        self.start_time = datetime.now()
        for child in self.children:
            child.disabled = True

        if existing_message:
            self.message = existing_message
            await self.message.edit(
                content=
                "Memory Game (5x5): Match the pairs! (Showing the emojis for 7 seconds...)",
                view=self,
                embed=None)
        else:
            self.message = await self.ctx.send(
                "Memory Game (5x5): Match the pairs! (Showing the emojis for 7 seconds...)",
                view=self)

        await self.reveal_all_emojis()
        await discord.utils.sleep_until(discord.utils.utcnow() +
                                        timedelta(seconds=7))
        await self.hide_all_emojis()
        for child in self.children:
            if isinstance(child, MemoryGameButton):
                child.disabled = False
        await self.message.edit(content="Memory Game (5x5): Match the pairs!",
                                view=self)

    async def reveal_all_emojis(self):
        for button in self.board:
            button.emoji = button.hidden_emoji
            button.style = discord.ButtonStyle.secondary
        await self.message.edit(view=self)

    async def hide_all_emojis(self):
        for button in self.board:
            button.emoji = "❓"
            button.style = discord.ButtonStyle.secondary
            button.revealed = False
        await self.message.edit(view=self)

    async def process_button(self, button: MemoryGameButton,
                             interaction: discord.Interaction):
        if not button.revealed:
            button.revealed = True
            button.style = discord.ButtonStyle.success
            button.emoji = button.hidden_emoji
            self.selected_buttons.append(button)
            self.moves += 1

            if len(self.selected_buttons) == 2:
                for child in self.children:
                    if isinstance(child, MemoryGameButton):
                        child.disabled = True
                await interaction.response.edit_message(view=self)

                btn1, btn2 = self.selected_buttons
                if btn1.hidden_emoji == btn2.hidden_emoji:
                    btn1.disabled = True
                    btn2.disabled = True
                    self.pairs_found += 1

                    if self.pairs_found == 12:
                        await self.end_game(interaction)
                        return
                else:
                    btn1.style = btn2.style = discord.ButtonStyle.danger
                    await interaction.message.edit(view=self)
                    await discord.utils.sleep_until(discord.utils.utcnow() +
                                                    timedelta(seconds=1))
                    btn1.emoji = btn2.emoji = "❓"
                    btn1.style = btn2.style = discord.ButtonStyle.secondary
                    btn1.revealed = btn2.revealed = False

                self.selected_buttons.clear()

                for child in self.children:
                    if isinstance(child,
                                  MemoryGameButton) and not child.revealed:
                        child.disabled = False

                await interaction.message.edit(view=self)
            else:
                await interaction.response.edit_message(view=self)

        self.timeout = 20

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
        embed.set_footer(text="Thanks for playing!")

        rematch_view = RematchView(self.ctx, self.message)
        await interaction.message.edit(content=None,
                                       embed=embed,
                                       view=rematch_view)


class RematchView(discord.ui.View):

    def __init__(self, ctx: commands.Context, message: discord.Message):
        super().__init__()
        self.ctx = ctx
        self.message = message

    @discord.ui.button(label="Rematch", style=discord.ButtonStyle.primary)
    async def rematch(self, interaction: discord.Interaction,
                      button: ui.Button):
        if interaction.user == self.ctx.author:
            await interaction.response.defer()
            new_game = MemoryGameView(self.ctx)
            await new_game.start_game(self.message)
        else:
            await interaction.response.send_message(
                "Only the original player can start a rematch.",
                ephemeral=True)


class MemoryGameCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="memorygame")
    async def memorygame(self, ctx: commands.Context):
        """Starts a 5x5 memory game with custom server emojis."""
        try:
            game = MemoryGameView(ctx)
            await game.start_game()
        except ValueError as e:
            await ctx.send(str(e))


async def setup(bot):
    await bot.add_cog(MemoryGameCog(bot))

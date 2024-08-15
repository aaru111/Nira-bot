import discord
from discord.ext import commands
from discord.ui import View, Button
import asyncio
import random

DEFAULT_PLAYER_X = "❌"
DEFAULT_PLAYER_O = "⭕"
EMPTY = "‎‎‎‎‎‎‎‎‎‎‎‎‎‎‎‎‎‎"  # A zero-width space to make buttons appear empty


class TicTacToeButton(Button):

    def __init__(self, x: int, y: int, game):
        super().__init__(style=discord.ButtonStyle.secondary,
                         label=EMPTY,
                         row=y)
        self.x = x
        self.y = y
        self.game = game
        self.emoji = None

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.game.current_player:
            await interaction.response.send_message("It's not your turn!",
                                                    ephemeral=True)
            return

        if self.emoji is not None or self.label != EMPTY:
            await interaction.response.send_message(
                "This spot is already taken!", ephemeral=True)
            return

        self.emoji = self.game.current_symbol
        self.label = None  # Remove the label when setting an emoji
        self.style = (discord.ButtonStyle.success if self.game.current_player
                      == self.game.player1 else discord.ButtonStyle.danger)
        self.disabled = True
        await interaction.response.edit_message(view=self.game.board_view)

        self.game.reset_timeout_task()

        if self.game.check_winner():
            await self.game.show_winner(interaction)
        elif self.game.check_draw():
            await self.game.show_draw(interaction)
        else:
            self.game.switch_turn()
            if self.game.current_player.bot:
                await self.game.bot_move(interaction)
            else:
                await interaction.edit_original_response(
                    content=
                    f"It's {self.game.current_player.mention}'s turn ({self.game.current_symbol})",
                    view=self.game.board_view,
                )


class TicTacToeGame:

    def __init__(self, player1: discord.Member, player2: discord.Member,
                 ctx: commands.Context, player_x: str, player_o: str):
        self.player1 = player1
        self.player2 = player2
        self.current_player = player1
        self.current_symbol = self._format_emoji(player_x or DEFAULT_PLAYER_X)
        self.player_x = self._format_emoji(player_x or DEFAULT_PLAYER_X)
        self.player_o = self._format_emoji(player_o or DEFAULT_PLAYER_O)
        self.board_view = self.create_board_view()
        self.ctx = ctx
        self.timeout_task = None
        self.message = None
        self.reset_timeout_task()

    def _format_emoji(self, emoji: str) -> discord.PartialEmoji:
        """Converts emoji string to discord.PartialEmoji object."""
        if emoji.startswith("<") and emoji.endswith(">"):
            # It's a custom emoji
            emoji_id = int(emoji.split(":")[-1][:-1])
            emoji_name = emoji.split(":")[1]
            return discord.PartialEmoji(name=emoji_name, id=emoji_id)
        else:
            # It's a Unicode emoji or default
            return discord.PartialEmoji(name=emoji)

    def reset_timeout_task(self):
        if self.timeout_task:
            self.timeout_task.cancel()
        self.timeout_task = asyncio.create_task(self.handle_timeout())

    async def handle_timeout(self):
        await asyncio.sleep(60)
        if self.message:
            await self.clear_board("Game timed out due to inactivity.")

    def create_board_view(self) -> View:
        view = View(timeout=None)
        for y in range(3):
            for x in range(3):
                view.add_item(TicTacToeButton(x, y, self))
        return view

    def switch_turn(self):
        self.current_player = self.player2 if self.current_player == self.player1 else self.player1
        self.current_symbol = self.player_o if self.current_symbol == self.player_x else self.player_x

    def check_winner(self) -> bool:
        board = [[self.get_button(x, y).emoji for x in range(3)]
                 for y in range(3)]

        for i in range(3):
            if board[i][0] == board[i][1] == board[i][
                    2] is not None:  # Check rows
                return True
            if board[0][i] == board[1][i] == board[2][
                    i] is not None:  # Check columns
                return True

        if board[0][0] == board[1][1] == board[2][
                2] is not None:  # Check main diagonal
            return True
        if board[0][2] == board[1][1] == board[2][
                0] is not None:  # Check anti-diagonal
            return True

        return False

    def get_button(self, x: int, y: int) -> TicTacToeButton:
        for button in self.board_view.children:
            if button.x == x and button.y == y:
                return button

    def check_draw(self) -> bool:
        return all(button.emoji is not None
                   for button in self.board_view.children)

    def end_game(self, result: str):
        if self.timeout_task:
            self.timeout_task.cancel()

        # Clear the board
        for button in self.board_view.children:
            self.board_view.remove_item(button)

        # Add a single button showing the game result
        color, label = ((discord.ButtonStyle.green,
                         "You won!") if result == "win" else
                        (discord.ButtonStyle.red,
                         "You lost!") if result == "loss" else
                        (discord.ButtonStyle.blurple, "It's a draw!"))

        result_button = Button(style=color, label=label, disabled=True)
        self.board_view.add_item(result_button)

    async def show_winner(self, interaction: discord.Interaction):
        result = "win" if interaction.user == self.current_player else "loss"
        self.end_game(result)
        await interaction.edit_original_response(view=self.board_view)

    async def show_draw(self, interaction: discord.Interaction):
        self.end_game("draw")
        await interaction.edit_original_response(view=self.board_view)

    async def bot_move(self, interaction: discord.Interaction):
        best_score = -float('inf')
        best_move = None

        for button in self.board_view.children:
            if button.emoji is None:
                button.emoji = self.current_symbol
                score = self.minimax(0, False)
                button.emoji = None
                if score > best_score:
                    best_score = score
                    best_move = button

        if best_move:
            best_move.emoji = self.current_symbol
            best_move.label = None  # Remove the label when setting an emoji
            best_move.style = discord.ButtonStyle.danger
            best_move.disabled = True
            await interaction.edit_original_response(view=self.board_view)

            if self.check_winner():
                await self.show_winner(interaction)
            elif self.check_draw():
                await self.show_draw(interaction)
            else:
                self.switch_turn()

    async def hard_bot_move(self, interaction: discord.Interaction):
        best_score = -float('inf')
        best_move = None

        for button in self.board_view.children:
            if button.label == EMPTY:
                button.label = self.current_symbol
                score = self.minimax(0, False)
                button.label = EMPTY
                if score > best_score:
                    best_score = score
                    best_move = button

        if best_move:
            best_move.label = self.current_symbol
            best_move.style = discord.ButtonStyle.danger
            best_move.disabled = True
            await interaction.edit_original_response(view=self.board_view)

            if self.check_winner():
                await self.show_winner(interaction)
            elif self.check_draw():
                await self.show_draw(interaction)
            else:
                self.switch_turn()

    def minimax(self, depth: int, is_maximizing: bool) -> int:
        if self.check_winner():
            return 1 if not is_maximizing else -1
        elif self.check_draw():
            return 0

        if is_maximizing:
            best_score = -float('inf')
            for button in self.board_view.children:
                if button.emoji is None:
                    button.emoji = self.current_symbol
                    score = self.minimax(depth + 1, False)
                    button.emoji = None
                    best_score = max(score, best_score)
            return best_score
        else:
            best_score = float('inf')
            for button in self.board_view.children:
                if button.emoji is None:
                    button.emoji = self.player_x if self.current_symbol == self.player_o else self.player_o
                    score = self.minimax(depth + 1, True)
                    button.emoji = None
                    best_score = min(score, best_score)
            return best_score

    async def clear_board(self, content: str):
        # Clear the board
        for button in self.board_view.children:
            self.board_view.remove_item(button)

        # Edit the original message
        if self.message:
            await self.message.edit(content=content, view=self.board_view)


class AcceptDeclineButtons(View):

    def __init__(self, game, author, opponent):
        super().__init__(timeout=None)
        self.game = game
        self.author = author
        self.opponent = opponent

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        if interaction.user != self.opponent:
            await interaction.response.send_message("This isn't for you!",
                                                    ephemeral=True)
            return

        await interaction.message.delete()
        await interaction.message.edit(
            content=
            f"{self.author.mention} vs {self.opponent.mention} - Let's play Tic Tac Toe!",
            view=self.game.board_view,
        )
        self.game.message = interaction.message
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        if interaction.user != self.opponent:
            await interaction.response.send_message("This isn't for you!",
                                                    ephemeral=True)
            return

        await interaction.message.delete()
        self.stop()


class TicTacToe(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="ttt",
        description="Play Tic Tac Toe against another user or the bot itself.")
    async def tic_tac_toe(self,
                          ctx: commands.Context,
                          opponent: discord.Member = None,
                          player_x: str = None,
                          player_o: str = None):
        # Check if opponent is mentioned
        if opponent is None:
            return

        game = TicTacToeGame(ctx.author, opponent, ctx, player_x, player_o)

        # Send the initial message with the game board
        if opponent == ctx.guild.me:
            message = await ctx.send(
                f"{ctx.author.mention} vs the bot - Let's play Tic Tac Toe!",
                view=game.board_view)
        elif opponent == ctx.author:
            await ctx.send("You cannot play against yourself!")
            return
        else:
            message = await ctx.send(
                f"{ctx.author.mention} vs {opponent.mention} - Let's play Tic Tac Toe!",
                view=game.board_view)

        game.message = message


async def setup(bot):
    await bot.add_cog(TicTacToe(bot))

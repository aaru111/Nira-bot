import discord
from discord.ext import commands
from discord import app_commands
from discord.interactions import Interaction
from discord.embeds import Embed
from discord.message import Message
from discord.ext.commands import Context
from discord.reaction import Reaction
from discord.member import Member
from discord.abc import Messageable
import aiohttp
import asyncio
import time

from typing import Optional, Dict

# Importing modules used in the games
from modules.tetrismod import TetrisGame
from modules.tttmod import TicTacToeGame, AcceptDeclineButtons
from modules.triviamod import TriviaView
from modules.memorymod import MemoryGameView


class Games(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.tetris_games: Dict[int, TetrisGame] = {}
        self.ttt_games: Dict[frozenset[int], TicTacToeGame] = {}
        self.memory_games: Dict[int, MemoryGameView] = {}
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        """Clean up resources when the cog is unloaded."""
        await self.session.close()

    # Tetris Game Command and Methods
    @commands.command(name="tetris")
    async def tetris(self, ctx: commands.Context) -> None:
        if ctx.author.id in self.tetris_games:
            await ctx.send(
                "You're already in a game! Use the 🛑 reaction to end it.")
            return

        game: TetrisGame = TetrisGame()
        self.tetris_games[ctx.author.id] = game

        embed: Embed = discord.Embed(title="Tetris Game", color=0x00ff00)
        embed.add_field(name="\u200b",
                        value="Press ▶️ to start!",
                        inline=False)
        embed.add_field(name="Score", value="0", inline=True)
        embed.add_field(name="Level", value="1", inline=True)
        embed.add_field(name="Lines", value="0", inline=True)
        embed.add_field(name="Next Piece", value="?", inline=True)
        embed.set_footer(
            text=
            "▶️: Start | ⬅️: Left | ➡️: Right | 🔽: Soft Drop | ⏬: Hard Drop\n🔄: Rotate | ⏸️: Pause | 🛑: End | ❓: Help"
        )

        message: Message = await ctx.send(embed=embed)
        # Add reactions for controls
        reactions = ["▶️", "⬅️", "➡️", "🔽", "⏬", "🔄", "⏸️", "🛑", "❓"]
        for reaction in reactions:
            await message.add_reaction(reaction)

    async def game_loop(self, user_id: int, message: Message) -> None:
        game: TetrisGame = self.tetris_games[user_id]
        game.new_piece()
        await self.update_game(user_id, message)
        while not game.game_over and user_id in self.tetris_games:
            if not game.paused:
                await asyncio.sleep(game.get_fall_speed())
                if not game.move(0, 1):
                    game.merge_piece()
                    lines_cleared: int = game.clear_lines()
                    if lines_cleared > 0:
                        game.score += lines_cleared * 100
                        game.level_up(lines_cleared)
                        await self.update_game(user_id, message)
                    if game.game_over:
                        await self.end_tetris_game(user_id, message,
                                                   "Game Over!")
                        return
                    game.new_piece()
                await self.update_game(user_id, message)
            else:
                await asyncio.sleep(0.1)

    async def update_game(self, user_id: int, message: Message) -> None:
        if user_id not in self.tetris_games:
            return
        game: TetrisGame = self.tetris_games[user_id]
        embed: Embed = message.embeds[0]
        embed.color = 0x0000ff if game.paused else 0x00ff00  # Blue when paused, green otherwise
        embed.set_field_at(0, name="\u200b", value=game.render(), inline=False)
        embed.set_field_at(1, name="Score", value=str(game.score), inline=True)
        embed.set_field_at(2, name="Level", value=str(game.level), inline=True)
        embed.set_field_at(3,
                           name="Lines",
                           value=str(game.lines_cleared),
                           inline=True)
        next_piece_preview: str = "\n".join("".join(
            game.cell_to_emoji(cell) for cell in row)
                                            for row in game.next_piece.shape)
        embed.set_field_at(4,
                           name="Next Piece",
                           value=next_piece_preview,
                           inline=True)
        await message.edit(embed=embed)

    async def end_tetris_game(self, user_id: int, message: Message,
                              end_message: str) -> None:
        if user_id not in self.tetris_games:
            return
        game: TetrisGame = self.tetris_games[user_id]
        embed: Embed = message.embeds[0]
        embed.title = end_message
        embed.color = 0xff0000
        embed.set_field_at(0, name="\u200b", value=game.render(), inline=False)
        embed.set_field_at(1,
                           name="Final Score",
                           value=str(game.score),
                           inline=True)
        embed.set_field_at(2,
                           name="Level Reached",
                           value=str(game.level),
                           inline=True)
        embed.set_field_at(3,
                           name="Lines Cleared",
                           value=str(game.lines_cleared),
                           inline=True)
        await message.edit(embed=embed)
        del self.tetris_games[user_id]

    # TicTacToe Game Command and Methods
    @app_commands.command(name="ttt",
                          description="Start a new Tic Tac Toe game")
    @app_commands.describe(
        opponent=
        "The user you want to play against (leave empty to play against the bot)",
        player_x="Custom emoji for player X (optional)",
        player_o="Custom emoji for player O (optional)")
    async def tic_tac_toe(self,
                          interaction: Interaction,
                          opponent: Optional[Member] = None,
                          player_x: Optional[str] = None,
                          player_o: Optional[str] = None) -> None:
        if opponent is None:
            opponent = interaction.guild.me if interaction.guild else None

        if player_x and not self.is_valid_emoji(player_x):
            await interaction.response.send_message(
                "Invalid emoji for player X. Please use a valid emoji.",
                ephemeral=True)
            return

        if player_o and not self.is_valid_emoji(player_o):
            await interaction.response.send_message(
                "Invalid emoji for player O. Please use a valid emoji.",
                ephemeral=True)
            return

        player_key: frozenset[int] = frozenset(
            [interaction.user.id, opponent.id])
        if player_key in self.ttt_games:
            old_game: TicTacToeGame = self.ttt_games[player_key]
            for item in old_game.board_view.children:
                if isinstance(item, RematchButton):
                    item.disabled = True
            await old_game.message.edit(view=old_game.board_view)

        game: TicTacToeGame = TicTacToeGame(interaction.user, opponent,
                                            interaction, player_x, player_o)
        self.ttt_games[player_key] = game

        if opponent == interaction.guild.me:
            await interaction.response.send_message(
                f"**{interaction.user.mention}** vs {opponent.mention} - Let's play Tic Tac Toe!",
                view=game.board_view)
            game.message = await interaction.original_response()
            game.reset_timeout_task()
            game.last_move_time = int(time.time())  # Set initial move time
        elif opponent == interaction.user:
            await interaction.response.send_message(
                "You cannot play against yourself!", ephemeral=True)
            return
        else:
            await interaction.response.send_message(
                f"{interaction.user.mention} has invited {opponent.mention} to play Tic Tac Toe. Would you like to accept?",
                view=AcceptDeclineButtons(game, interaction.user, opponent))

    def is_valid_emoji(self, emoji: str) -> bool:
        """Check if the provided string is a valid emoji."""
        try:
            discord.PartialEmoji.from_str(emoji)
            return True
        except discord.errors.NotFound:
            return False

    # Trivia Game Command and Methods
    @commands.command(name="trivia")
    async def trivia(self, ctx: commands.Context) -> None:
        await self._send_trivia(ctx, ctx.author.id, 0)

    async def _send_trivia(self, ctx: Context, user_id: int,
                           score: int) -> None:
        question_data: Dict[str,
                            str] = await TriviaView.fetch_trivia_question()

        category: str = question_data['category']
        difficulty: str = question_data['difficulty']
        question: str = question_data['question']
        correct_answer: str = question_data['correct_answer']
        all_answers: list[str] = question_data['all_answers']

        embed: Embed = discord.Embed(
            title=
            f"**Category:** {category} | **Difficulty:** {difficulty.capitalize()}",
            description=f"**Question:**\n*{question}*\n\n" + "\n".join([
                f"**{chr(65+i)}:** {answer}"
                for i, answer in enumerate(all_answers)
            ]),
            color=discord.Color.blue())
        embed.set_footer(
            text=f"You have 30 seconds to answer! | Current score: {score}")

        view: TriviaView = TriviaView(correct_answer, self, user_id, score)

        if isinstance(ctx, Interaction):
            if ctx.response.is_done():
                message: Message = await ctx.edit_original_response(
                    embed=embed, view=view)
            else:
                message = await ctx.response.send_message(embed=embed,
                                                          view=view)
                message = await ctx.original_response()
        else:
            message = await ctx.send(embed=embed, view=view)

        view.message = message
        await view.start_timer(
            ctx.channel if isinstance(ctx, Context) else ctx.channel)

    # Memory Game Command and Methods
    @commands.command(name="memorygame")
    async def memorygame(self,
                         ctx: commands.Context,
                         time_limit: int = 5) -> None:
        """Starts a 5x5 memory game with custom server emojis. Optionally set a time limit (1-6 minutes)."""
        if ctx.author.id in self.memory_games:
            await ctx.send(
                "You already have an ongoing game. Please finish it before starting a new one."
            )
            return

        if not 1 <= time_limit <= 6:
            await ctx.send("Time limit must be between 1 and 6 minutes.")
            return

        try:
            game: MemoryGameView = MemoryGameView(ctx, time_limit, self)
            self.memory_games[ctx.author.id] = game
            await game.start_game()
        except ValueError as e:
            await ctx.send(str(e))

    # Shared event listener for reactions (handling Tetris and Memory game)
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, user: Member) -> None:
        if user.bot:
            return

        # Handling Tetris reactions
        if user.id in self.tetris_games:
            game: TetrisGame = self.tetris_games[user.id]
            moved: bool = False

            if reaction.emoji == "▶️" and not game.started:
                game.started = True
                await self.game_loop(user.id, reaction.message)
                return
            elif not game.started:
                await reaction.remove(user)
                return
            elif reaction.emoji == "⬅️":
                moved = game.move(-1, 0)
            elif reaction.emoji == "➡️":
                moved = game.move(1, 0)
            elif reaction.emoji == "🔽":
                moved = game.move(0, 1)
            elif reaction.emoji == "⏬":
                drop_distance: int = game.hard_drop()
                game.score += drop_distance * 2
                game.merge_piece()
                lines_cleared: int = game.clear_lines()
                if lines_cleared > 0:
                    game.score += lines_cleared * 100
                    game.level_up(lines_cleared)
                    await self.update_game(user.id, reaction.message)
                if game.game_over:
                    await self.end_tetris_game(user.id, reaction.message,
                                               "Game Over!")
                    return
                game.new_piece()
                moved = True
            elif reaction.emoji == "🔄":
                moved = game.rotate()
            elif reaction.emoji == "⏸️":
                game.paused = not game.paused
                moved = True  # Force update to change color
            elif reaction.emoji == "🛑":
                await self.end_tetris_game(user.id, reaction.message,
                                           "Game Ended")
                return
            elif reaction.emoji == "❓":
                await self.show_help(reaction.message.channel)
                return

            if moved:
                await self.update_game(user.id, reaction.message)

            await reaction.remove(user)

        # Handling Memory Game reactions
        elif reaction.emoji == "💡":
            game: Optional[MemoryGameView] = self.memory_games.get(user.id)
            if game:
                if user.id != game.ctx.author.id:
                    await reaction.message.channel.send(
                        f"{user.mention}, only the player who started the game can use hints.",
                        delete_after=5)
                else:
                    await reaction.remove(user)
                    await game.show_hint()

    async def show_help(self, channel: Messageable) -> None:
        help_embed: Embed = discord.Embed(title="Tetris Help", color=0x0000ff)
        help_embed.add_field(
            name="How to Play",
            value=("• ▶️: Start the game\n"
                   "• ⬅️: Move left\n"
                   "• ➡️: Move right\n"
                   "• 🔽: Soft drop (move down faster)\n"
                   "• ⏬: Hard drop (instantly drop to bottom)\n"
                   "• 🔄: Rotate piece\n"
                   "• ⏸️: Pause/Resume game\n"
                   "• 🛑: End game\n"
                   "• Clear lines to score points and level up!\n"
                   "• Game speeds up as you level up.\n"
                   "• Game ends if pieces stack up to the top."),
            inline=False)
        await channel.send(embed=help_embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Games(bot))

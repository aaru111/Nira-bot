import discord
from discord.ext import commands
from discord import app_commands
from discord.interactions import Interaction
from discord.embeds import Embed
from discord.message import Message
from discord.ext.commands import Context
from discord.reaction import Reaction
from discord.member import Member

from discord_games import button_games

import aiohttp
import time
import io

from typing import Optional, Dict

# Importing modules used in the games
from .modules.tetrismod import Tetris
from .modules.tttmod import TicTacToeGame, AcceptDeclineButtons
from .modules.triviamod import TriviaView
from .modules.memorymod import MemoryGameView
from .modules.chessmod import ChessGame, ChessView, PlayerStats
from database import db


class Games(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.ttt_games: Dict[frozenset[int], TicTacToeGame] = {}
        self.memory_games: Dict[int, MemoryGameView] = {}
        self.active_chess_games: Dict[int, ChessGame] = {}
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.twenty_48_emojis = {
            "0": "<:0_:1301058145988378635>",
            "2": "<:2_:1301058155048075336>",
            "4": "<:4_:1301058163373772820>",
            "8": "<:8_:1301058170076139550>",
            "16": "<:16:1301058177781076040>",
            "32": "<:32:1301058184676638730>",
            "64": "<:64:1301058191920205895>",
            "128": "<:128:1301058203873710101>",
            "256": "<:256:1301058211708932106>",
            "512": "<:512:1301058220378423296>",
            "1024": "<:1024:1301058230243557396>",
            "2048": "<:2048:1301058238757994506>",
            "4096": "<:4096:1301058250657108008>",
            "8192": "<:8192:1301058262543630389>",
        }

    async def cog_unload(self) -> None:
        """Clean up resources when the cog is unloaded."""
        await self.session.close()

    # Tetris Game Command
    @commands.hybrid_command(name="tetris", brief="Play a game of Tetris")
    async def tetris(self, ctx: commands.Context[commands.Bot]):
        game = Tetris()
        await game.start(ctx)

    # TicTacToe Game Command and Methods
    @app_commands.command(name="ttt", description="Start a new Tic Tac Toe game")
    @app_commands.describe(
        opponent="The user you want to play against (leave empty to play against the bot)",
        player_x="Custom emoji for player X (optional)",
        player_o="Custom emoji for player O (optional)")
    async def tic_tac_toe(self, interaction: Interaction, opponent: Optional[Member] = None,
                          player_x: Optional[str] = None, player_o: Optional[str] = None) -> None:
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
                if isinstance(item, discord.ui.Button) and item.custom_id == "rematch":
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
    @commands.hybrid_command(name="memory")
    @app_commands.describe(time_limit="Time limit for the game (1-6 minutes)")
    async def memory(self, ctx: commands.Context, time_limit: int = 5) -> None:
        """Start a 5x5 memory game with custom server emojis."""
        if ctx.author.id in self.memory_games:
            game = self.memory_games[ctx.author.id]
            if game.game_started and not game.message.channel.permissions_for(
                    ctx.me).read_message_history:
                # If we can't see the message history, assume the game is no longer active
                del self.memory_games[ctx.author.id]
            else:
                try:
                    # Try to fetch the game message
                    await game.message.fetch()
                    await ctx.send(
                        "You already have an ongoing game. Please finish it before starting a new one."
                    )
                    return
                except discord.NotFound:
                    # If the message is not found, remove the game from memory_games
                    del self.memory_games[ctx.author.id]

        if not 1 <= time_limit <= 6:
            await ctx.send("Time limit must be between 1 and 6 minutes.")
            return

        try:
            game = MemoryGameView(ctx, time_limit, self)
            self.memory_games[ctx.author.id] = game
            await game.start_game()
        except ValueError as e:
            await ctx.send(str(e))

    @memory.error
    async def memory_error(self, ctx: commands.Context,
                           error: Exception) -> None:
        if isinstance(error, commands.BadArgument):
            await ctx.send(
                "Invalid time limit. Please provide a number between 1 and 6.")

    # Shared event listener for reactions (handling Memory game)
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, user: Member) -> None:
        if user.bot:
            return

        # Handling Memory Game reactions
        if reaction.emoji == "💡":
            game: Optional[MemoryGameView] = self.memory_games.get(user.id)
            if game:
                if user.id != game.ctx.author.id:
                    await reaction.message.channel.send(
                        f"{user.mention}, only the player who started the game can use hints.",
                        delete_after=5)
                else:
                    # Check if the reaction is from the bot running the game
                    if reaction.me and reaction.count == 2:
                        await reaction.remove(user)
                        await game.show_hint()

    @commands.hybrid_command()
    @app_commands.allowed_installs(guilds=True, users=False)
    async def chess(self, ctx: commands.Context,
                    opponent: discord.Member) -> None:
        """Start a chess game against another player."""
        if ctx.author == opponent:
            return await ctx.send("You can't play against yourself!")

        game = ChessGame(player1=ctx.author, player2=opponent)
        view = ChessView(game)

        # Update player stats in the database
        await self.update_chess_player_stats(ctx.author)
        await self.update_chess_player_stats(opponent)

        svg_board = game.get_svg_board()
        png_image = view.convert_svg_to_png(svg_board)
        file = discord.File(io.BytesIO(png_image), filename="chessboard.png")

        embed = discord.Embed(
            title=f"Chess Game: {ctx.author.name} vs {opponent.name}",
            color=discord.Color.from_rgb(239, 158, 240))
        embed.set_image(url="attachment://chessboard.png")
        embed.add_field(name="Current Turn", value=ctx.author.name)

        await ctx.send(embed=embed, file=file, view=view)

    @commands.hybrid_command()
    @app_commands.allowed_installs(guilds=True, users=False)
    async def chesslb(self,
                      ctx: commands.Context,
                      player: Optional[discord.Member] = None) -> None:
        """Show the stats for a specific player using a Discord Member object."""
        if player is None:
            player = ctx.author

        player_stats = await self.get_chess_player_stats(player)
        if player_stats.games_played > 0:
            stats_embed = player_stats.get_stats()
            await ctx.send(embed=stats_embed)
        else:
            await ctx.send(f"No stats found for {player.mention}.")

    async def update_chess_player_stats(self, player: discord.Member) -> None:
        query = """
        INSERT INTO player_stats (player_id, player_name, games_played, wins, draws, losses)
        VALUES ($1, $2, 0, 0, 0, 0)
        ON CONFLICT (player_id) DO NOTHING
        """
        await db.execute(query, player.id, player.name)

    async def get_chess_player_stats(self,
                                     player: discord.Member) -> PlayerStats:
        query = """
        SELECT * FROM player_stats WHERE player_id = $1
        """
        row = await db.fetch(query, player.id)
        if row:
            player_stats = PlayerStats(player)
            player_stats.games_played = row[0]['games_played']
            player_stats.wins = row[0]['wins']
            player_stats.draws = row[0]['draws']
            player_stats.losses = row[0]['losses']
            return player_stats
        else:
            return PlayerStats(player)

    @commands.hybrid_command(
        name="wordle",
        brief="Play a Wordle game.",
        description=
        "Guess the 5-letter word in 6 tries. Green=correct spot, yellow=right letter wrong spot."
    )
    @app_commands.allowed_installs(guilds=True, users=False)
    async def wordle(self, ctx: commands.Context[commands.Bot]):
        game = button_games.BetaWordle()
        await game.start(ctx)

    @commands.hybrid_command(
        name="twenty48",
        brief="Play a 2048 game.",
        aliases=['2048', 't48'],
        description=
        "Slide and combine matching numbers to reach 2048. Use arrow buttons to move tiles on the board."
    )
    async def twenty48(self, ctx: commands.Context[commands.Bot]):
        game = button_games.BetaTwenty48(self.twenty_48_emojis,
                                         render_image=True)
        await game.start(ctx)

    @commands.hybrid_command(name="hangman")
    async def hangman(self, ctx: commands.Context[commands.Bot]):
        game = button_games.BetaHangman()
        await game.start(ctx)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Games(bot))
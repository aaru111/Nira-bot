import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import time

from modules.tttmod import TicTacToeGame, AcceptDeclineButtons


class TicTacToe(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.active_games = {}  # Store active games

    async def cog_unload(self):
        """Clean up resources when the cog is unloaded."""
        await self.session.close()

    @app_commands.command(name="ttt",
                          description="Start a new Tic Tac Toe game")
    @app_commands.describe(
        opponent=
        "The user you want to play against (leave empty to play against the bot)",
        player_x="Custom emoji for player X (optional)",
        player_o="Custom emoji for player O (optional)")
    async def tic_tac_toe(self,
                          interaction: discord.Interaction,
                          opponent: discord.Member = None,
                          player_x: str = None,
                          player_o: str = None):
        if opponent is None:
            opponent = interaction.guild.me

        # Check for invalid emojis
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

        # Disable rematch button for any existing game involving the same players
        player_key = frozenset([interaction.user.id, opponent.id])
        if player_key in self.active_games:
            old_game = self.active_games[player_key]
            for item in old_game.board_view.children:
                if isinstance(item, RematchButton):
                    item.disabled = True
            await old_game.message.edit(view=old_game.board_view)

        game = TicTacToeGame(interaction.user, opponent, interaction, player_x,
                             player_o)
        self.active_games[player_key] = game

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
            # Try to create a PartialEmoji object
            discord.PartialEmoji.from_str(emoji)
            return True
        except discord.errors.NotFound:
            # Return False if the emoji is not found
            return False


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicTacToe(bot))

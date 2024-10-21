import discord
from discord.ext import commands
from modules.chessmod import ChessGame, ChessView, PlayerStats
from database import db
import io

class Chess(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}

    @commands.hybrid_command()
    async def chess(self, ctx, opponent: discord.Member):
        """Start a chess game against another player."""
        if ctx.author == opponent:
            return await ctx.send("You can't play against yourself!")

        game = ChessGame(player1=ctx.author, player2=opponent)
        view = ChessView(game)

        # Update player stats in the database
        await self.update_player_stats(ctx.author)
        await self.update_player_stats(opponent)

        svg_board = game.get_svg_board()
        png_image = view.convert_svg_to_png(svg_board)
        file = discord.File(io.BytesIO(png_image), filename="chessboard.png")
        embed = discord.Embed(
            title=f"Chess Game: {ctx.author.name} vs {opponent.name}",
            color=discord.Color.from_rgb(239, 158, 240)
        )
        embed.set_image(url="attachment://chessboard.png")
        embed.add_field(name="Current Turn", value=ctx.author.name)
        await ctx.send(embed=embed, file=file, view=view)

    @commands.hybrid_command()
    async def chesslb(self, ctx, player: discord.Member = None):
        """Show the stats for a specific player using a Discord Member object."""
        if player is None:
            player = ctx.author

        player_stats = await self.get_player_stats(player)
        if player_stats.games_played > 0:
            stats_embed = player_stats.get_stats()
            await ctx.send(embed=stats_embed)
        else:
            await ctx.send(f"No stats found for {player.mention}.")

    async def update_player_stats(self, player: discord.Member):
        query = """
        INSERT INTO player_stats (player_id, player_name, games_played, wins, draws, losses)
        VALUES ($1, $2, 0, 0, 0, 0)
        ON CONFLICT (player_id) DO NOTHING
        """
        await db.execute(query, player.id, player.name)

    async def get_player_stats(self, player: discord.Member):
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

async def setup(bot):
    await bot.add_cog(Chess(bot))
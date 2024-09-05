from discord.ext import commands
import aiohttp
from modules.memorymod import MemoryGameView


class MemoryGame(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.ongoing_games = {}
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

    async def cog_unload(self):
        """Clean up resources when the cog is unloaded."""
        await self.session.close()

    def start_game(self, user_id: int, game: MemoryGameView):
        self.ongoing_games[user_id] = game

    def end_game(self, user_id: int):
        if user_id in self.ongoing_games:
            del self.ongoing_games[user_id]

    @commands.command(name="memorygame")
    async def memorygame(self, ctx: commands.Context, time_limit: int = 5):
        """Starts a 5x5 memory game with custom server emojis. Optionally set a time limit (1-6 minutes)."""
        if ctx.author.id in self.ongoing_games:
            await ctx.send(
                "You already have an ongoing game. Please finish it before starting a new one."
            )
            return

        if time_limit < 1 or time_limit > 6:
            await ctx.send("Time limit must be between 1 and 6 minutes.")
            return

        try:
            game = MemoryGameView(ctx, time_limit, self)
            self.start_game(ctx.author.id, game)
            await game.start_game()
        except ValueError as e:
            await ctx.send(str(e))

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return

        if reaction.emoji == "💡":
            game = self.ongoing_games.get(user.id)
            if game:
                if user.id != game.ctx.author.id:
                    await reaction.message.channel.send(
                        f"{user.mention}, only the player who started the game can use hints.",
                        delete_after=5)
                else:
                    await reaction.remove(user)
                    await game.show_hint()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MemoryGame(bot))

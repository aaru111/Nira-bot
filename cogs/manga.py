from discord.ext import commands
from modules.mangamod import MangaMod


class MangaReader(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.manga_mod = MangaMod()

    async def cog_unload(self) -> None:
        await self.manga_mod.close_session()

    @commands.hybrid_command(name='manga')
    async def manga(self, ctx: commands.Context, *, query: str) -> None:
        """
        Command to search and read a manga using the MangaDex API.
        Syntax: /manga <manga_id_or_name> [volume_number]
        """
        await self.manga_mod.handle_manga_command(ctx, query)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MangaReader(bot))

import discord
from discord.ext import commands
import aiohttp
from urllib.parse import quote
from modules.urbanmod import UrbanDictionaryView, create_definition_embeds


class UrbanDictionary(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

    async def cog_unload(self):
        """Clean up resources when the cog is unloaded."""
        await self.session.close()

    @commands.command(name="urban")
    async def urban(self, ctx, *, word: str):
        encoded_word = quote(word)
        url = f"https://api.urbandictionary.com/v0/define?term={encoded_word}"

        async with self.session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                definitions = data.get("list", [])

                if not definitions:
                    await ctx.send(f"No definitions found for '{word}'.")
                    return

                pages = create_definition_embeds(word, encoded_word,
                                                 definitions[:10])
                view = UrbanDictionaryView(pages)
                await view.start(ctx)
            else:
                await ctx.send(
                    "An error occurred while fetching the definition.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UrbanDictionary(bot))

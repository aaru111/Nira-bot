import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from modules.wikimod import WikipediaSearcher, WikiEmbedCreator, WikiView


class Wiki(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.searcher = WikipediaSearcher()
        self.embed_creator = WikiEmbedCreator()
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

    async def cog_unload(self):
        """Clean up resources when the cog is unloaded."""
        await self.session.close()

    @app_commands.command(name="wiki",
                          description="Search Wikipedia for information")
    async def wiki(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        try:
            page_title = await self.searcher.search(query)
            if not page_title:
                await interaction.followup.send(
                    "No results found for your query. Please try a different search term.",
                    ephemeral=True)
                return

            page_info = await self.searcher.get_page_info(page_title)
            base_embed = self.embed_creator.create_base_embed(
                page_info['title'], page_info['url'], page_info['image_url'])
            content_chunks = self.embed_creator.split_content(
                page_info['summary'])

            initial_embed = base_embed.copy()
            initial_embed.description = content_chunks[0]

            if len(content_chunks) == 1:
                # If there's only one page, don't use the WikiView
                initial_embed.set_footer(text="Source: Wikipedia")
                await interaction.followup.send(embed=initial_embed)
            else:
                # If there are multiple pages, use the WikiView
                view = WikiView(base_embed, content_chunks)
                initial_embed.set_footer(
                    text=f"Page 1/{len(content_chunks)} | Source: Wikipedia")
                message = await interaction.followup.send(embed=initial_embed,
                                                          view=view)
                view.message = message
                view.reset_timer()
        except Exception as e:
            await interaction.followup.send(
                f"An error occurred while processing your request: {str(e)}",
                ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Wiki(bot))

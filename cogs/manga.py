import discord
from discord.ext import commands
from discord.ui import Button, View
import aiohttp


class MangaReaderCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='manga')
    async def manga(self, ctx, *, manga_name: str):
        """
        Command to search and read a manga using the MangaDex API.
        """
        async with aiohttp.ClientSession() as session:
            # Step 1: Search for the manga by name
            async with session.get(f'https://api.mangadex.org/manga',
                                   params={
                                       'title': manga_name,
                                       'limit': 1
                                   }) as response:
                if response.status != 200:
                    await ctx.send(
                        'Failed to fetch manga data. Please try again later.')
                    return

                manga_data = await response.json()
                manga_results = manga_data.get('data', [])

            if not manga_results:
                await ctx.send(f'No results found for "{manga_name}".')
                return

            manga_id = manga_results[0]['id']

            # Step 2: Fetch all chapters for the manga, grouped by volume
            async with session.get(
                f'https://api.mangadex.org/manga/{manga_id}/feed',
                params={
                    'translatedLanguage[]': 'en',
                    'limit': 500,
                    'order[volume]': 'asc',
                    'order[chapter]': 'asc'
                }) as chapter_response:
                if chapter_response.status != 200:
                    await ctx.send(
                        'Failed to fetch chapters. Please try again later.')
                    return

                chapter_data = await chapter_response.json()
                chapters = chapter_data.get('data', [])

            if not chapters:
                await ctx.send('No readable chapters found for this manga.')
                return

            # Group chapters by volume
            volumes = {}
            for chapter in chapters:
                volume_number = chapter['attributes'].get('volume', 'Unknown')
                if volume_number not in volumes:
                    volumes[volume_number] = []
                volumes[volume_number].append(chapter)

            sorted_volumes = sorted(volumes.items(), key=lambda x: x[0] if x[0] != 'Unknown' else float('inf'))

            # Start with the first volume
            await self.display_volume(ctx, manga_results, sorted_volumes, 0)

    async def display_volume(self, ctx, manga_results, volumes, volume_index):
        """
        Fetch and display pages of the specified volume.
        """
        current_volume = volumes[volume_index][1]
        first_chapter = current_volume[0]
        chapter_id = first_chapter['id']

        async with aiohttp.ClientSession() as session:
            # Fetch pages for the first chapter of the volume
            async with session.get(
                f'https://api.mangadex.org/at-home/server/{chapter_id}'
            ) as pages_response:
                if pages_response.status != 200:
                    await ctx.send(
                        'Failed to fetch pages. Please try again later.')
                    return

                pages_data = await pages_response.json()
                base_url = pages_data['baseUrl']
                chapter_hash = pages_data['chapter']['hash']
                page_files = pages_data['chapter']['data']

        pages = [
            f"{base_url}/data/{chapter_hash}/{page}" for page in page_files
        ]

        if not pages:
            await ctx.send('No pages available to display.')
            return

        current_page = 0

        async def update_message(page_number):
            embed = discord.Embed(
                title=f"{manga_results[0]['attributes']['title']['en']} - Volume {volumes[volume_index][0]} - Page {page_number + 1}",
                color=discord.Color.blue())
            embed.set_image(url=pages[page_number])
            embed.set_footer(
                text=f'Page {page_number + 1} of {len(pages)}')
            return embed

        # Send the initial embed message
        message = await ctx.send(embed=await update_message(current_page))

        # Adding navigation buttons
        view = View()

        async def go_to_next_page(interaction):
            nonlocal current_page
            if current_page < len(pages) - 1:
                current_page += 1
                await message.edit(embed=await update_message(current_page))

        async def go_to_previous_page(interaction):
            nonlocal current_page
            if current_page > 0:
                current_page -= 1
                await message.edit(embed=await update_message(current_page))

        async def go_to_next_volume(interaction):
            if volume_index < len(volumes) - 1:
                await self.display_volume(ctx, manga_results, volumes, volume_index + 1)

        async def go_to_previous_volume(interaction):
            if volume_index > 0:
                await self.display_volume(ctx, manga_results, volumes, volume_index - 1)

        prev_button = Button(label='Previous Page', style=discord.ButtonStyle.red)
        prev_button.callback = go_to_previous_page

        next_button = Button(label='Next Page', style=discord.ButtonStyle.green)
        next_button.callback = go_to_next_page

        prev_volume_button = Button(label='Previous Volume', style=discord.ButtonStyle.blurple)
        prev_volume_button.callback = go_to_previous_volume

        next_volume_button = Button(label='Next Volume', style=discord.ButtonStyle.blurple)
        next_volume_button.callback = go_to_next_volume

        # Add buttons to the view in the desired order
        view.add_item(prev_button)
        view.add_item(prev_volume_button)
        view.add_item(next_volume_button)
        view.add_item(next_button)

        await message.edit(view=view)


async def setup(bot):
    await bot.add_cog(MangaReaderCog(bot))
    
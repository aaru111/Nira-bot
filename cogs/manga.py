import discord
from discord.ext import commands
from discord.ui import Button, View, Select, Modal, TextInput
import aiohttp
import re


class MangaReaderCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='manga')
    async def manga(self, ctx, *, query: str):
        """
        Command to search and read a manga using the MangaDex API.
        Syntax: /manga <manga_id_or_name> [volume_number]
        """
        query_parts = query.split()
        specified_volume = None

        if query_parts[-1].isdigit():
            specified_volume = int(query_parts[-1])
            query = " ".join(query_parts[:-1])

        if re.match(
                r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$',
                query):
            manga_id = query
            await self.display_manga(ctx, manga_id, specified_volume)
        else:
            await self.search_manga(ctx, query, specified_volume)

    async def search_manga(self, ctx, manga_name, specified_volume):
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.mangadex.org/manga',
                                   params={
                                       'title': manga_name,
                                       'limit': 5,
                                       'order[relevance]': 'desc',
                                       'includes[]': ['author', 'artist']
                                   }) as response:
                if response.status != 200:
                    await ctx.send(
                        f'Failed to search for manga. Please try again later.\nYou can try searching manually at: [ManaDex](https://mangadex.org/search?q={manga_name})',
                        ephemeral=True)
                    return None

                manga_data = await response.json()
                manga_results = manga_data.get('data', [])

        if not manga_results:
            await ctx.send(
                f'No results found for "{manga_name}".\nYou can try searching manually at: [Mangadex](https://mangadex.org/search?q={manga_name})',
                ephemeral=True)
            return None

        if len(manga_results) == 1:
            await self.display_manga(ctx, manga_results[0]['id'],
                                     specified_volume)
            return

        options = []
        for manga in manga_results:
            title = manga['attributes']['title'].get('en') or next(
                iter(manga['attributes']['title'].values()))
            author = next(
                (rel['attributes']['name']
                 for rel in manga['relationships'] if rel['type'] == 'author'),
                'Unknown')
            year = manga['attributes'].get('year') or 'Unknown'
            option_description = f"Author: {author} | Year: {year}"
            options.append(
                discord.SelectOption(label=title[:100],
                                     description=option_description[:100],
                                     value=manga['id']))

        select = Select(placeholder="Choose a manga", options=options)

        async def select_callback(interaction):
            await interaction.response.defer()
            success = await self.display_manga(ctx, select.values[0],
                                               specified_volume)
            if success:
                await interaction.message.delete()

        select.callback = select_callback
        view = View()
        view.add_item(select)
        await ctx.send("Multiple manga found. Please select one:",
                       view=view,
                       ephemeral=True)

    async def display_manga(self, ctx, manga_id, specified_volume=None):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    f'https://api.mangadex.org/manga/{manga_id}') as response:
                if response.status != 200:
                    await ctx.send(
                        f'Failed to fetch manga data. Please try again later.\nYou can try accessing the manga directly at: [MangaDex](https://mangadex.org/title/{manga_id})\nManga ID: {manga_id}',
                        ephemeral=True)
                    return False

                manga_data = await response.json()
                manga_result = manga_data.get('data')

            if not manga_result:
                await ctx.send(
                    f'No manga found with the provided ID.\nYou can try accessing the manga directly at: [MangaDex](https://mangadex.org/title/{manga_id})\nManga ID: {manga_id}',
                    ephemeral=True)
                return False

            async with session.get(
                    f'https://api.mangadex.org/manga/{manga_id}/feed',
                    params={
                        'translatedLanguage[]': ['en'],
                        'limit': 500,
                        'order[volume]': 'asc',
                        'order[chapter]': 'asc'
                    }) as chapter_response:
                if chapter_response.status != 200:
                    await ctx.send(
                        f'Failed to fetch chapters. Please try again later.\nYou can try accessing the manga directly at: https://mangadex.org/title/{manga_id}\nManga ID: {manga_id}',
                        ephemeral=True)
                    return False

                chapter_data = await chapter_response.json()
                chapters = chapter_data.get('data', [])

        if not chapters:
            await ctx.send(
                f'No readable chapters found for this manga.\nYou can check the manga page at: [MangaDex](https://mangadex.org/title/{manga_id})\nManga ID: {manga_id}',
                ephemeral=True)
            return False

        volumes = {}
        for chapter in chapters:
            volume_number = chapter['attributes'].get('volume') or 'Unknown'
            if volume_number not in volumes:
                volumes[volume_number] = []
            volumes[volume_number].append(chapter)

        sorted_volumes = sorted(
            [(vol_num, vol_chapters)
             for vol_num, vol_chapters in volumes.items()
             if vol_num != 'Unknown'],
            key=lambda x: float(x[0])
            if x[0].replace('.', '', 1).isdigit() else float('inf'))

        if 'Unknown' in volumes:
            sorted_volumes.append(('Unknown', volumes['Unknown']))

        if not sorted_volumes:
            await ctx.send(
                f'No readable volumes found for this manga.\nYou can check the manga page at: [MangaDex](https://mangadex.org/title/{manga_id})\nManga ID: {manga_id}',
                ephemeral=True)
            return False

        total_volumes = len(sorted_volumes)

        if specified_volume is not None:
            specified_volume_index = next(
                (i for i, v in enumerate(sorted_volumes)
                 if v[0] != 'Unknown' and float(v[0]) == specified_volume),
                None)
            if specified_volume_index is None:
                await ctx.send(
                    f'Volume {specified_volume} not found. This manga has {total_volumes} volumes.\nYou can check the manga page at: [MangaDex](https://mangadex.org/title/{manga_id})\nManga ID: {manga_id}',
                    ephemeral=True)
                return False
            await self.display_volume(ctx, manga_result, sorted_volumes,
                                      specified_volume_index, total_volumes)
        else:
            await self.display_volume(ctx, manga_result, sorted_volumes, 0,
                                      total_volumes)
        return True

    async def display_volume(self,
                             ctx,
                             manga_result,
                             volumes,
                             volume_index,
                             total_volumes,
                             message=None,
                             chapter_index=0):
        current_volume = volumes[volume_index][1]
        current_chapter = current_volume[chapter_index]
        chapter_id = current_chapter['id']
        external_url = current_chapter['attributes'].get('externalUrl')
        manga_name = current_chapter['attributes'].get('title')
        if external_url:
            await ctx.send(
                f"This chapter is hosted externally and cannot be displayed here. "
                f"You can read it at: [{manga_name}]({external_url})",
                ephemeral=True)
            return False

        async with aiohttp.ClientSession() as session:
            async with session.get(
                    f'https://api.mangadex.org/at-home/server/{chapter_id}'
            ) as pages_response:
                if pages_response.status != 200:
                    await ctx.send(
                        'Failed to fetch pages. Please try again later.',
                        ephemeral=True)
                    return

                pages_data = await pages_response.json()
                base_url = pages_data.get('baseUrl')
                chapter_info = pages_data.get('chapter')
                if chapter_info is None:
                    await ctx.send(
                        'Chapter information is missing. Please try again later.',
                        ephemeral=True)
                    return
                chapter_hash = chapter_info.get('hash')
                page_files = chapter_info.get('data')

        if not page_files or not base_url or not chapter_hash:
            await ctx.send('No pages available to display.', ephemeral=True)
            return

        pages = [
            f"{base_url}/data/{chapter_hash}/{page}" for page in page_files
        ]
        current_page = 0

        embed = await self.create_embed(manga_result, volumes, volume_index,
                                        total_volumes, current_chapter, pages,
                                        current_page)

        if message is None:
            message = await ctx.send(embed=embed, ephemeral=True)
        else:
            await message.edit(embed=embed)

        view = await self.create_view(ctx, manga_result, volumes, volume_index,
                                      total_volumes, message, current_volume,
                                      chapter_index, pages, current_page)
        await message.edit(view=view)

    async def create_embed(self, manga_result, volumes, volume_index,
                           total_volumes, current_chapter, pages, page_number):
        manga_title = manga_result['attributes']['title'].get('en') or next(
            iter(manga_result['attributes']['title'].values()))
        current_volume_number = volumes[volume_index][0]
        manga_id = manga_result['id']
        manga_url = f"https://mangadex.org/title/{manga_id}"

        embed = discord.Embed(
            title=f"[{manga_title}]({manga_url})",
            url=manga_url,
            description=
            f"Volume {current_volume_number} - Chapter {current_chapter['attributes']['chapter']}",
            color=discord.Color.blue())
        embed.set_image(url=pages[page_number])
        embed.set_footer(
            text=
            f'Volume {current_volume_number}/{total_volumes} | Page {page_number + 1} of {len(pages)}'
        )
        return embed

    async def create_view(self, ctx, manga_result, volumes, volume_index,
                          total_volumes, message, current_volume,
                          chapter_index, pages, current_page):
        view = View(timeout=300)  # 5 minutes timeout

        options = []
        for idx, chapter in enumerate(current_volume):
            chapter_title = chapter['attributes'].get(
                'title') or f"Chapter {chapter['attributes']['chapter']}"
            options.append(
                discord.SelectOption(
                    label=f"Chapter {chapter['attributes']['chapter']}",
                    description=
                    f"{chapter_title[:80]}... ({total_volumes} vols)",
                    value=str(idx)))

        options = options[:25]  # Discord limit

        async def select_chapter(interaction):
            await interaction.response.defer()
            selected_idx = int(interaction.data['values'][0])
            await self.display_volume(ctx, manga_result, volumes, volume_index,
                                      total_volumes, message, selected_idx)

        chapter_select = Select(placeholder="Select a Chapter",
                                options=options)
        chapter_select.callback = select_chapter

        async def update_page(new_page):
            nonlocal current_page
            current_page = new_page
            embed = await self.create_embed(manga_result, volumes,
                                            volume_index, total_volumes,
                                            current_volume[chapter_index],
                                            pages, current_page)
            await message.edit(embed=embed)

        async def go_to_next_page(interaction):
            await interaction.response.defer()
            if current_page < len(pages) - 1:
                await update_page(current_page + 1)
            else:
                await interaction.followup.send(
                    'This is the last page of the chapter.', ephemeral=True)

        async def go_to_previous_page(interaction):
            await interaction.response.defer()
            if current_page > 0:
                await update_page(current_page - 1)
            else:
                await interaction.followup.send(
                    'This is the first page of the chapter.', ephemeral=True)

        async def go_to_next_volume(interaction):
            await interaction.response.defer()
            if volume_index < len(volumes) - 1:
                await self.display_volume(ctx, manga_result, volumes,
                                          volume_index + 1, total_volumes,
                                          message)
            else:
                await interaction.followup.send('This is the last volume.',
                                                ephemeral=True)

        async def go_to_previous_volume(interaction):
            await interaction.response.defer()
            if volume_index > 0:
                await self.display_volume(ctx, manga_result, volumes,
                                          volume_index - 1, total_volumes,
                                          message)
            else:
                await interaction.followup.send('This is the first volume.',
                                                ephemeral=True)

        async def go_to_page(interaction):
            modal = Modal(title="Go to Page")
            page_input = TextInput(
                label="Page Number",
                placeholder=f"Enter a number between 1 and {len(pages)}",
                required=True)
            modal.add_item(page_input)

            async def on_submit(modal_interaction):
                await modal_interaction.response.defer()
                try:
                    page_number = int(page_input.value) - 1
                    if 0 <= page_number < len(pages):
                        await update_page(page_number)
                    else:
                        await modal_interaction.followup.send(
                            f"Invalid page number. Please enter a number between 1 and {len(pages)}.",
                            ephemeral=True)
                except ValueError:
                    await modal_interaction.followup.send(
                        "Please enter a valid number.", ephemeral=True)

            modal.on_submit = on_submit
            await interaction.response.send_modal(modal)

        # First row of buttons
        view.add_item(
            Button(label='⏮️',
                   style=discord.ButtonStyle.blurple,
                   custom_id='prev_volume'))
        view.add_item(
            Button(label='⬅️',
                   style=discord.ButtonStyle.red,
                   custom_id='prev_page'))
        view.add_item(
            Button(label='➡️',
                   style=discord.ButtonStyle.green,
                   custom_id='next_page'))
        view.add_item(
            Button(label='⏭️',
                   style=discord.ButtonStyle.blurple,
                   custom_id='next_volume'))

        view.add_item(
            Button(label='🔢',
                   style=discord.ButtonStyle.grey,
                   custom_id='go_to_page'))
        view.add_item(chapter_select)

        view.on_timeout = lambda: message.edit(view=None)

        for item in view.children:
            if isinstance(item, Button):
                if item.custom_id == 'prev_page':
                    item.callback = go_to_previous_page
                elif item.custom_id == 'next_page':
                    item.callback = go_to_next_page
                elif item.custom_id == 'prev_volume':
                    item.callback = go_to_previous_volume
                elif item.custom_id == 'next_volume':
                    item.callback = go_to_next_volume
                elif item.custom_id == 'go_to_page':
                    item.callback = go_to_page

        return view


async def setup(bot):
    await bot.add_cog(MangaReaderCog(bot))

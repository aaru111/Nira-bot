import discord
from discord.ext import commands
from discord.ui import Button, View, Select, Modal, TextInput
import aiohttp

class MangaReaderCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='manga')
    async def manga(self, ctx, *, args: str):
        """
        Command to search and read a manga using the MangaDex API.
        Syntax: /manga <manga_name> [volume_number]
        """
        args_list = args.split()
        manga_name = " ".join(args_list[:-1])
        specified_volume = None

        # Check if the last argument is a volume number
        if args_list[-1].isdigit():
            specified_volume = int(args_list[-1])
            manga_name = " ".join(args_list[:-1])
        else:
            manga_name = args

        async with aiohttp.ClientSession() as session:
            # Step 1: Search for the manga by name
            async with session.get('https://api.mangadex.org/manga',
                                   params={
                                       'title': manga_name,
                                       'limit': 1
                                   }) as response:
                if response.status != 200:
                    await ctx.send(
                        'Failed to fetch manga data. Please try again later.',
                        ephemeral=True)
                    return

                manga_data = await response.json()
                manga_results = manga_data.get('data', [])

            if not manga_results:
                await ctx.send(f'No results found for "{manga_name}".',
                               ephemeral=True)
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
                        'Failed to fetch chapters. Please try again later.',
                        ephemeral=True)
                    return

                chapter_data = await chapter_response.json()
                chapters = chapter_data.get('data', [])

            if not chapters:
                await ctx.send('No readable chapters found for this manga.',
                               ephemeral=True)
                return

            # Group chapters by volume and ensure volumes are in correct order
            volumes = {}
            for chapter in chapters:
                volume_number = chapter['attributes'].get('volume', 'Unknown')
                if volume_number is None:
                    continue  # Skip chapters with no volume number
                if volume_number not in volumes:
                    volumes[volume_number] = []
                volumes[volume_number].append(chapter)

            # Filter out 'Unknown' volumes and sort by volume number correctly
            sorted_volumes = sorted(
                [(vol_num, vol_chapters)
                 for vol_num, vol_chapters in volumes.items()
                 if vol_num != 'Unknown'],
                key=lambda x: int(x[0]) if x[0].isdigit() else float('inf'))

            # Ensure there are volumes to display
            if not sorted_volumes:
                await ctx.send('No readable volumes found for this manga.',
                               ephemeral=True)
                return

            # Determine total number of volumes
            total_volumes = len(sorted_volumes)

            # Determine starting volume index based on specified volume
            if specified_volume is not None:
                specified_volume_index = next(
                    (i for i, v in enumerate(sorted_volumes)
                     if int(v[0]) == specified_volume), None)
                if specified_volume_index is None:
                    await ctx.send(
                        f'Volume {specified_volume} not found. This manga has {total_volumes} volumes.',
                        ephemeral=True)
                    return
                await self.display_volume(ctx, manga_results, sorted_volumes,
                                          specified_volume_index,
                                          total_volumes)
            else:
                # Start with the first volume
                await self.display_volume(ctx, manga_results, sorted_volumes,
                                          0, total_volumes)

    async def display_volume(self,
                             ctx,
                             manga_results,
                             volumes,
                             volume_index,
                             total_volumes,
                             message=None,
                             chapter_index=0):
        """
        Fetch and display pages of the specified volume and chapter.
        """
        current_volume = volumes[volume_index][1]
        current_chapter = current_volume[chapter_index]
        chapter_id = current_chapter['id']

        async with aiohttp.ClientSession() as session:
            # Fetch pages for the current chapter of the volume
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

        async def update_message(page_number):
            embed = discord.Embed(
                title=
                f"{manga_results[0]['attributes']['title']['en']} - Volume {volumes[volume_index][0]} - Chapter {current_chapter['attributes']['chapter']} - Page {page_number + 1}",
                color=discord.Color.blue())
            embed.set_image(url=pages[page_number])
            embed.set_footer(text=f'Page {page_number + 1} of {len(pages)}')
            return embed

        # Check if we need to send a new message or edit the existing one
        if message is None:
            message = await ctx.send(embed=await update_message(current_page),
                                     ephemeral=True)
        else:
            await message.edit(embed=await update_message(current_page))

        async def create_view():
            view = View(timeout=30)

            # Dropdown for chapter selection
            options = []
            for idx, chapter in enumerate(current_volume):
                if idx == chapter_index:
                    continue
                chapter_title = chapter['attributes']['title']
                if isinstance(chapter_title, dict):
                    chapter_title = chapter_title.get('en', '')
                options.append(
                    discord.SelectOption(
                        label=f"Chapter {chapter['attributes']['chapter']}",
                        description=chapter_title,
                        value=str(idx)))

            options = options[:25]  # Show up to 25 chapters, excluding the current one

            async def select_chapter(interaction):
                selected_idx = int(interaction.data['values'][0])
                await self.display_volume(ctx, manga_results, volumes,
                                          volume_index, total_volumes, message,
                                          selected_idx)
                await interaction.response.defer()

            chapter_select = Select(placeholder="Select a Chapter",
                                    options=options)
            chapter_select.callback = select_chapter

            async def go_to_next_page(interaction):
                nonlocal current_page
                if current_page < len(pages) - 1:
                    current_page += 1
                    await message.edit(embed=await update_message(current_page))
                else:
                    await interaction.response.send_message(
                        'This is the last page of the chapter.',
                        ephemeral=True)
                await interaction.response.defer()
                await message.edit(view=await create_view())  # Reset timeout

            async def go_to_previous_page(interaction):
                nonlocal current_page
                if current_page > 0:
                    current_page -= 1
                    await message.edit(embed=await update_message(current_page))
                else:
                    await interaction.response.send_message(
                        'This is the first page of the chapter.',
                        ephemeral=True)
                await interaction.response.defer()
                await message.edit(view=await create_view())  # Reset timeout

            async def go_to_next_volume(interaction):
                if volume_index < len(volumes) - 1:
                    await self.display_volume(ctx, manga_results, volumes,
                                              volume_index + 1, total_volumes,
                                              message)
                else:
                    await interaction.response.send_message(
                        'This is the last volume.', ephemeral=True)
                await interaction.response.defer()

            async def go_to_previous_volume(interaction):
                if volume_index > 0:
                    await self.display_volume(ctx, manga_results, volumes,
                                              volume_index - 1, total_volumes,
                                              message)
                else:
                    await interaction.response.send_message(
                        'This is the first volume.', ephemeral=True)
                await interaction.response.defer()

            async def go_to_page(interaction):
                modal = Modal(title="Go to Page")
                page_input = TextInput(
                    label="Page Number",
                    placeholder=f"Enter a number between 1 and {len(pages)}",
                    required=True
                )
                modal.add_item(page_input)

                async def on_submit(modal_interaction):
                    nonlocal current_page
                    try:
                        page_number = int(page_input.value) - 1
                        if 0 <= page_number < len(pages):
                            current_page = page_number
                            await message.edit(embed=await update_message(current_page))
                        else:
                            await modal_interaction.response.send_message(
                                f"Invalid page number. Please enter a number between 1 and {len(pages)}.",
                                ephemeral=True
                            )
                    except ValueError:
                        await modal_interaction.response.send_message(
                            "Please enter a valid number.",
                            ephemeral=True
                        )
                    await modal_interaction.response.defer()
                    await message.edit(view=await create_view())  # Reset timeout

                modal.on_submit = on_submit
                await interaction.response.send_modal(modal)

            prev_button = Button(label='Previous Page',
                                 style=discord.ButtonStyle.red)
            prev_button.callback = go_to_previous_page

            next_button = Button(label='Next Page',
                                 style=discord.ButtonStyle.green)
            next_button.callback = go_to_next_page

            prev_volume_button = Button(label='Previous Volume',
                                        style=discord.ButtonStyle.blurple)
            prev_volume_button.callback = go_to_previous_volume

            next_volume_button = Button(label='Next Volume',
                                        style=discord.ButtonStyle.blurple)
            next_volume_button.callback = go_to_next_volume

            go_to_button = Button(label='Go to Page',
                                  style=discord.ButtonStyle.grey)
            go_to_button.callback = go_to_page

            # Add items to the view in the desired order
            view.add_item(prev_button)
            view.add_item(prev_volume_button)
            view.add_item(next_volume_button)
            view.add_item(next_button)
            view.add_item(go_to_button)
            view.add_item(chapter_select)

            return view

        # Update the message with the initial view
        await message.edit(view=await create_view())

        # Wait for the view's timeout, then remove the buttons
        view = await create_view()

        # When the view times out, disable all buttons
        async def on_timeout():
            for item in view.children:
                item.disabled = True
            await message.edit(view=view)

        view.on_timeout = on_timeout

        # Start the view with timeout management
        await message.edit(view=view)


async def setup(bot):
    await bot.add_cog(MangaReaderCog(bot))

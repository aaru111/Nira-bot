import discord
from discord.ext import commands
import aiohttp
import math

class EmojiSteal(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_paginated_message(self, ctx, message, max_length=1900):
        """Send a long message in chunks to avoid Discord's character limit"""
        lines = message.split('\n')
        current_chunk = ""

        for line in lines:
            if len(current_chunk) + len(line) + 1 > max_length:
                await ctx.send(current_chunk)
                current_chunk = line + '\n'
            else:
                current_chunk += line + '\n'

        if current_chunk:
            await ctx.send(current_chunk)

    @commands.command(name='emojisteal')
    async def emoji_steal(self, ctx):
        """Steal emojis from one server to another"""
        # Get list of guilds the bot is in
        guilds = self.bot.guilds
        guild_count = len(guilds)

        # Display guild list
        guild_message = "**Guild List:**\n"
        for i, guild in enumerate(guilds):
            guild_message += f"`{i}` - {guild.name}\n"

        await self.send_paginated_message(ctx, guild_message)

        # Prompt for source guild
        def check_source(m):
            try:
                source = int(m.content)
                return m.author == ctx.author and 0 <= source < guild_count
            except ValueError:
                return False

        await ctx.send(f'Enter the SRL_ID of the source guild (0-{guild_count - 1}):')
        source_msg = await self.bot.wait_for('message', check=check_source)
        source = int(source_msg.content)
        source_guild = guilds[source]

        # Prompt for destination guild
        def check_dest(m):
            try:
                sink = int(m.content)
                return m.author == ctx.author and 0 <= sink < guild_count
            except ValueError:
                return False

        await ctx.send(f'Enter the SRL_ID of the destination guild (0-{guild_count - 1}):')
        dest_msg = await self.bot.wait_for('message', check=check_dest)
        sink = int(dest_msg.content)
        sink_guild = guilds[sink]

        # Check permissions
        if not sink_guild.me.guild_permissions.manage_emojis:
            return await ctx.send(f'Error: No permissions to manage emojis in {sink_guild.name}')

        # Display emoji list
        emoji_message = "**Emoji List:**\n"
        for i, emoji in enumerate(source_guild.emojis):
            emoji_message += f"`{i}` - {emoji.name} (Animated: {'Yes' if emoji.animated else 'No'})\n"

        await self.send_paginated_message(ctx, emoji_message)

        # Check emoji slots
        free_slots = sink_guild.emoji_limit - len(sink_guild.emojis)
        if free_slots == 0:
            return await ctx.send(f'Error: {sink_guild.name} has no free emoji slots!')

        await ctx.send(f'{sink_guild.name} has {free_slots} free emoji slots. Enter comma-separated SRL_IDs to steal (or "all"):')
        emoji_selection = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author)

        # Select emojis to steal
        if emoji_selection.content.lower() == 'all':
            emojis_to_steal = source_guild.emojis
        else:
            try:
                emoji_indices = [int(idx.strip()) for idx in emoji_selection.content.split(',')]
                emojis_to_steal = [source_guild.emojis[idx] for idx in emoji_indices]
            except (ValueError, IndexError):
                return await ctx.send('Invalid emoji selection!')

        # Check if enough slots
        if len(emojis_to_steal) > free_slots:
            return await ctx.send(f'Error: Not enough free slots in {sink_guild.name}')

        # Steal emojis
        stolen_emojis = []
        progress_message = await ctx.send(f'Stealing emojis (0/{len(emojis_to_steal)})...')

        async with aiohttp.ClientSession() as session:
            for i, emoji in enumerate(emojis_to_steal, 1):
                try:
                    # Download the emoji image
                    async with session.get(emoji.url) as resp:
                        emoji_image = await resp.read()

                    # Create the emoji
                    stolen_emoji = await sink_guild.create_custom_emoji(name=emoji.name, image=emoji_image, reason='Stolen via EmojiSteal')
                    stolen_emojis.append(stolen_emoji)
                    await progress_message.edit(content=f'Stealing emojis ({i}/{len(emojis_to_steal)})...')
                except discord.HTTPException as e:
                    await ctx.send(f'Failed to steal {emoji.name}: {e}')

        await ctx.send(f'Stolen {len(stolen_emojis)} emojis from {source_guild.name} to {sink_guild.name}')

async def setup(bot):
    await bot.add_cog(EmojiSteal(bot))
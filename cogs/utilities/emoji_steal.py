import discord
from discord import app_commands
from discord.ext import commands
import aiohttp


class EmojiSteal(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def send_long_list(self, interaction: discord.Interaction, title,
                             list_items, color):
        """Send a long list by splitting it into multiple messages if needed"""
        MAX_DESC_LENGTH = 4000  # Maximum length for a single embed description

        full_list_text = "\n".join(list_items)

        # If the full list is short enough, send in a single embed
        if len(full_list_text) <= MAX_DESC_LENGTH:
            embed = discord.Embed(title=title,
                                  description=full_list_text,
                                  color=color)
            return await interaction.response.send_message(embed=embed,
                                                           ephemeral=True)

        # If the list is too long, split it
        current_list = []
        current_length = 0
        message_count = 0

        for item in list_items:
            if current_length + len(item) + 1 > MAX_DESC_LENGTH:
                message_count += 1
                embed = discord.Embed(title=f"{title} (Part {message_count})",
                                      description="\n".join(current_list),
                                      color=color)
                await interaction.followup.send(embed=embed, ephemeral=True)
                current_list = []
                current_length = 0

            current_list.append(item)
            current_length += len(item) + 1

        # Send the last batch of items if any remain
        if current_list:
            message_count += 1
            embed = discord.Embed(title=f"{title} (Part {message_count})",
                                  description="\n".join(current_list),
                                  color=color)
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name='emojisteal',
        description="Steal emojis from one server to another")
    @app_commands.checks.has_permissions(administrator=True)
    async def emoji_steal(self, interaction: discord.Interaction):
        """Slash command for stealing emojis"""
        guilds = self.bot.guilds
        guild_count = len(guilds)

        # Prepare guild list
        guild_list_text = [
            f"`{i}` - {guild.name}" for i, guild in enumerate(guilds)
        ]
        await self.send_long_list(interaction, "**Guild List**",
                                  guild_list_text, discord.Color.blue())

        # Prompt for source guild
        await interaction.followup.send(
            f'Enter the SRL_ID of the source guild (0-{guild_count - 1}):',
            ephemeral=True)

        def check_source(message):
            try:
                source = int(message.content)
                return message.author == interaction.user and 0 <= source < guild_count
            except ValueError:
                return False

        source_msg = await self.bot.wait_for('message', check=check_source)
        source = int(source_msg.content)
        source_guild = guilds[source]

        # Prompt for destination guild
        await interaction.followup.send(
            f'Enter the SRL_ID of the destination guild (0-{guild_count - 1}):',
            ephemeral=True)

        def check_dest(message):
            try:
                sink = int(message.content)
                return message.author == interaction.user and 0 <= sink < guild_count
            except ValueError:
                return False

        dest_msg = await self.bot.wait_for('message', check=check_dest)
        sink = int(dest_msg.content)
        sink_guild = guilds[sink]

        # Check permissions
        if not sink_guild.me.guild_permissions.manage_emojis:
            return await interaction.followup.send(
                f'Error: No permissions to manage emojis in {sink_guild.name}',
                ephemeral=True)

        # Prepare emoji list
        emoji_list_text = [
            f"`{i}` - {emoji} {emoji.name} (Animated: {'Yes' if emoji.animated else 'No'})"
            for i, emoji in enumerate(source_guild.emojis)
        ]

        await self.send_long_list(interaction,
                                  f"**Emoji List from {source_guild.name}**",
                                  emoji_list_text, discord.Color.green())

        # Check emoji slots
        free_slots = sink_guild.emoji_limit - len(sink_guild.emojis)
        if free_slots == 0:
            return await interaction.followup.send(
                f'Error: {sink_guild.name} has no free emoji slots!',
                ephemeral=True)

        await interaction.followup.send(
            f'{sink_guild.name} has {free_slots} free emoji slots. Enter emojis to steal (comma-separated indices, range like "5-10", or "all"):',
            ephemeral=True)
        emoji_selection = await self.bot.wait_for(
            'message', check=lambda m: m.author == interaction.user)

        # Select emojis to steal
        if emoji_selection.content.lower() == 'all':
            emojis_to_steal = source_guild.emojis
        else:
            try:
                if '-' in emoji_selection.content:
                    start, end = map(int, emoji_selection.content.split('-'))
                    emojis_to_steal = source_guild.emojis[start:end + 1]
                else:
                    emoji_indices = [
                        int(idx.strip())
                        for idx in emoji_selection.content.split(',')
                    ]
                    emojis_to_steal = [
                        source_guild.emojis[idx] for idx in emoji_indices
                    ]
            except (ValueError, IndexError):
                return await interaction.followup.send(
                    'Invalid emoji selection!', ephemeral=True)

        if len(emojis_to_steal) > free_slots:
            return await interaction.followup.send(
                f'Error: Not enough free slots in {sink_guild.name}',
                ephemeral=True)

        stolen_emojis = []
        progress_message = await interaction.followup.send(
            f'Stealing emojis (0/{len(emojis_to_steal)})...', ephemeral=True)

        async with aiohttp.ClientSession() as session:
            for i, emoji in enumerate(emojis_to_steal, 1):
                try:
                    async with session.get(emoji.url) as resp:
                        emoji_image = await resp.read()

                    stolen_emoji = await sink_guild.create_custom_emoji(
                        name=emoji.name,
                        image=emoji_image,
                        reason='Stolen via EmojiSteal')
                    stolen_emojis.append(stolen_emoji)
                    await progress_message.edit(
                        content=
                        f'Stealing emojis ({i}/{len(emojis_to_steal)})...')
                except discord.HTTPException as e:
                    await interaction.followup.send(
                        f'Failed to steal {emoji.name}: {e}', ephemeral=True)

        stolen_embed = discord.Embed(
            title="Emoji Steal Complete",
            description=
            f"Stolen {len(stolen_emojis)} emojis from {source_guild.name} to {sink_guild.name}",
            color=discord.Color.gold())

        stolen_list = " ".join(str(emoji) for emoji in stolen_emojis)
        if stolen_list:
            stolen_embed.add_field(name="Stolen Emojis",
                                   value=stolen_list,
                                   inline=False)

        await progress_message.delete()
        await interaction.followup.send(embed=stolen_embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(EmojiSteal(bot))

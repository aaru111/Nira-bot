import discord
import aiohttp
import re


async def steal_emoji(interaction: discord.Interaction,
                      emoji: str,
                      new_name: str = None):

    match = re.search(r"<(a?):(\w+):(\d+)>", emoji)
    if not match:
        return await interaction.response.send_message(
            "Invalid emoji format. Please use a valid custom emoji.",
            ephemeral=True)

    is_animated = bool(match.group(1))
    original_name = match.group(2)
    emoji_id = match.group(3)

    emoji_name = new_name or original_name

    file_extension = "gif" if is_animated else "png"
    emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{file_extension}"

    if interaction.guild.emoji_limit <= len(interaction.guild.emojis):
        return await interaction.response.send_message(
            f"Error: {interaction.guild.name} has no free emoji slots!",
            ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    async with aiohttp.ClientSession() as session:
        async with session.get(emoji_url) as resp:
            if resp.status != 200:
                return await interaction.followup.send(
                    "Failed to fetch the emoji. Make sure it's still available.",
                    ephemeral=True)
            emoji_bytes = await resp.read()

    try:

        new_emoji = await interaction.guild.create_custom_emoji(
            name=emoji_name,
            image=emoji_bytes,
            reason=f"Emoji stolen by {interaction.user}")

        embed = discord.Embed(title="Emoji Stolen Successfully",
                              description=f"Added new emoji: {new_emoji}",
                              color=discord.Color.green())
        embed.add_field(name="Name", value=new_emoji.name, inline=True)
        embed.add_field(name="ID", value=new_emoji.id, inline=True)
        embed.add_field(name="Animated",
                        value="Yes" if new_emoji.animated else "No",
                        inline=True)

        await interaction.followup.send(embed=embed, ephemeral=True)

    except discord.HTTPException as e:
        await interaction.followup.send(f"Failed to add emoji: {str(e)}",
                                        ephemeral=True)

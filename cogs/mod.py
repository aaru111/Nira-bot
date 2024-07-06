import discord
from discord.ext import commands
from main import Bot
from datetime import timedelta

class Moderation(commands.Cog):

    def __init__(self, bot: Bot):
        self.bot = bot

    # --------------------------------------------------------------------------------------------------------------------------

    @commands.command(aliases=['av', 'pfp'])
    async def avatar(self, ctx, user: discord.User = None):
        user = user or ctx.author
        em = discord.Embed(title=f"{user}'s Profile Picture: ", color=0x2f3131)
        em.set_image(url=user.display_avatar)
        em.set_footer(text=f"Requested by -> {ctx.author.name}", icon_url=ctx.author.avatar)
        await ctx.send(embed=em)

    # --------------------------------------------------------------------------------------------------------------------------

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, Reason: str = None):
        await member.kick(reason=Reason)
        await ctx.send(f"{member} You have been Kicked by **{ctx.author}**.\nReason: {Reason}")

    # --------------------------------------------------------------------------------------------------------------------------

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *, Reason: str = None):
        await member.ban(reason=Reason)
        await ctx.send(f"<@{member.id}> **Has Been** *Successfully* **Banned From The Guild**", delete_after=4)

    # --------------------------------------------------------------------------------------------------------------------------

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *, Reason: str = None):
        await ctx.send(f"{member} You have been Warned by **{ctx.author}**.\nReason: {Reason}")

    # --------------------------------------------------------------------------------------------------------------------------

    @commands.command(aliases=['clear', 'clr'])
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: int = 2):
        user = ctx.author.name
        embed = discord.Embed(
            title="**Messages Has Been Deleted** *Successfully*!!",
            description=f"```py\nAmount Deleted: {amount}```")
        embed.set_footer(
            text=f"This Message Will Be Deleted Shortly After 4 Seconds..  •  Moderator: {user}"
        )
        await ctx.channel.purge(limit=amount)
        await ctx.send(embed=embed, delete_after=4)

    # --------------------------------------------------------------------------------------------------------------------------

    @commands.command()
    @commands.has_guild_permissions(ban_members=True)
    async def unban(self, ctx, user: int):
        guild = ctx.guild
        user = discord.Object(user)
        try:
            await guild.unban(user)
            await ctx.channel.send(f"<@{user.id}> **Has Been** *Successfully* **UnBanned!**", delete_after=4)
        except discord.NotFound:
            await ctx.send("This user is not banned", delete_after=4)

    # ---------------------------------------------------------------------------------------------------------------------------

    @commands.command(pass_context=True, aliases=['ch_id', 'channelid'])
    async def channel_id(self, ctx, channel_name: str):
        channel = discord.utils.get(ctx.guild.channels, name=channel_name)
        if channel is None:
            await ctx.channel.send("Channel Not Found")
        else:
            await ctx.channel.send(f"The Channel <#{channel.id}>'s **ID** Is: ```py\n{channel.id}```")

    # -------------------------------------------------------------------------------------------------------------------------

    @commands.command()
    async def slowmode(self, ctx, channel: discord.TextChannel, delay: int):
        """Changes the slowmode of the mentioned channel.

        Args:
            channel: The channel to slowmode.
            delay: The new slowmode delay in seconds.
        """
        await channel.edit(slowmode_delay=delay)
        await ctx.send(f"Slowmode for {channel.name} has been changed to {delay} seconds.")

    # ---------------------------------------------------------------------------------------------------------------------------

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx: commands.Context, member: discord.Member, duration: int, *, reason: str = None):
        """Temporarily prevents a member from interacting for a specified duration in seconds."""
        await member.timeout(timedelta(seconds=duration), reason=reason)
        await ctx.send(f"{member.mention} has been timed out for {duration} seconds.\nReason: {reason}")

# ---------------------------------------------------------------------------------------------------------------------------

async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))

import discord
from discord.ext import commands
from typing import Optional
from discord.ui import Button, View
import aiohttp
import time
import random  # Import random module


class AvatarView(View):

    def __init__(self, user_avatar_url: str):
        super().__init__()

        # List of Button styles to choose from
        button_styles = [
            discord.ButtonStyle.primary, discord.ButtonStyle.secondary,
            discord.ButtonStyle.success, discord.ButtonStyle.danger
        ]

        # Randomly select a button style
        random_style = random.choice(button_styles)

        download_button = Button(
            label="Download",
            emoji="⬇️",
            style=random_style,  # Set the random style
            url=user_avatar_url)
        self.add_item(download_button)


class Moderation(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def close(self):
        await self.session.close()

    @commands.Cog.listener()
    async def on_shutdown(self):
        await self.close()

    @commands.Cog.listener()
    async def on_disconnect(self):
        await self.close()

    @commands.command(aliases=['av', 'pfp'])
    async def avatar(self, ctx, user: Optional[discord.User] = None):
        user = user or ctx.author
        embed = discord.Embed(title=f"{user}'s Profile Picture:",
                              color=discord.Color.random())
        embed.set_image(url=user.display_avatar.url)
        embed.set_footer(text=f"Requested by -> {ctx.author.name}",
                         icon_url=ctx.author.avatar.url)

        view = AvatarView(user.display_avatar.url)
        await ctx.send(embed=embed, view=view)

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self,
                   ctx: commands.Context,
                   member: discord.Member,
                   *,
                   Reason: Optional[str] = None):
        reason_text = Reason if Reason else "No reason provided"
        await member.kick(reason=reason_text)
        await ctx.send(
            f"{member.mention}, you have been kicked by **{ctx.author}**.\nReason: {reason_text}"
        )

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self,
                  ctx: commands.Context,
                  member: discord.Member,
                  *,
                  Reason: str = "No reason provided"):
        await member.ban(reason=Reason)
        await ctx.send(
            f"<@{member.id}> **Has Been** *Successfully* **Banned From The Guild**",
            delete_after=4)

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def warn(self,
                   ctx: commands.Context,
                   member: discord.Member,
                   *,
                   Reason: Optional[str] = None):
        reason_text = Reason if Reason else "No reason provided"
        await ctx.send(
            f"{member.mention}, you have been warned by **{ctx.author}**.\nReason: {reason_text}"
        )

    @commands.command(aliases=['clear', 'clr'])
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: int = 2):
        if isinstance(ctx.channel, discord.TextChannel):
            await ctx.channel.purge(limit=amount)
            embed = discord.Embed(
                title="**Messages Has Been Deleted** *Successfully*!!",
                description=f"```py\nAmount Deleted: {amount}```")
            embed.set_footer(
                text=
                f"This Message Will Be Deleted Shortly After 4 Seconds..  •  Moderator: {ctx.author.name}"
            )
            await ctx.send(embed=embed, delete_after=4)

    @commands.command()
    @commands.has_guild_permissions(ban_members=True)
    async def unban(self, ctx, user: int):
        guild = ctx.guild
        user_obj = discord.Object(user)
        try:
            await guild.unban(user_obj)
            await ctx.channel.send(
                f"<@{user}> **Has Been** *Successfully* **UnBanned!**",
                delete_after=4)
        except discord.NotFound:
            await ctx.send("This user is not banned", delete_after=4)

    @commands.command(pass_context=True, aliases=['ch_id', 'channelid'])
    async def channel_id(self, ctx, channel_name: str):
        channel = discord.utils.get(ctx.guild.channels, name=channel_name)
        if channel:
            await ctx.channel.send(
                f"The Channel <#{channel.id}>'s **ID** Is: ```py\n{channel.id}```"
            )
        else:
            await ctx.channel.send("Channel Not Found")

    @commands.command()
    async def slowmode(self, ctx, channel: discord.TextChannel, delay: int):
        if delay < 0:
            await ctx.send(
                "The slowmode delay must be greater than or equal to 0 seconds."
            )
            return
        await channel.edit(slowmode_delay=delay)
        await ctx.send(
            f"Slowmode for {channel.name} has been changed to {delay} seconds."
        )

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def nuke(self, ctx, channel: Optional[discord.TextChannel] = None):
        channel = channel or ctx.channel  # Use the current channel if none is provided

        if not isinstance(channel, discord.TextChannel):
            await ctx.send("This command can only be used in a text channel.")
            return

        name = channel.name
        category = channel.category
        position = channel.position
        overwrites = {
            target: overwrite
            for target, overwrite in channel.overwrites.items()
            if isinstance(target, (discord.Role, discord.Member))
        }
        topic = channel.topic or ""
        nsfw = channel.is_nsfw()
        slowmode_delay = channel.slowmode_delay
        reason = f"Channel nuked by {ctx.author}"
        permissions_synced = channel.permissions_synced
        announcement_channel = channel.is_news()
        guild = channel.guild

        webhooks = await channel.webhooks()
        invites = await channel.invites()
        pinned_messages = await channel.pins()

        await channel.delete()

        if category:
            new_channel = await category.create_text_channel(
                name, overwrites=overwrites, reason=reason)
        else:
            new_channel = await guild.create_text_channel(
                name, overwrites=overwrites, reason=reason)

        await new_channel.edit(position=position,
                               topic=topic,
                               nsfw=nsfw,
                               slowmode_delay=slowmode_delay,
                               sync_permissions=permissions_synced)
        if announcement_channel:
            await new_channel.edit(type=discord.ChannelType.news)

        for webhook in webhooks:
            name = webhook.name or "Default Webhook Name"
            await new_channel.create_webhook(
                name=name,
                avatar=await webhook.avatar.read() if webhook.avatar else None,
                reason=reason)

        for invite in invites:
            await new_channel.create_invite(max_age=invite.max_age or 0,
                                            max_uses=invite.max_uses or 0,
                                            temporary=invite.temporary
                                            or False,
                                            unique=getattr(
                                                invite, 'unique', False),
                                            reason=reason)

        for message in pinned_messages:
            new_msg = await new_channel.send(message.content)
            await new_msg.pin()

        await new_channel.send(
            f"Channel has been nuked by {ctx.author.mention}")

    @commands.command(name='ping')
    async def ping(self, ctx):
        websocket_latency = round(self.bot.latency * 1000, 2)
        start_time = time.time()
        message = await ctx.send("Pinging...")
        response_time = round((time.time() - start_time) * 1000, 2)
        embed = discord.Embed(title="🏓 Pong!", color=0x2f3131)
        embed.add_field(name="WebSocket Latency",
                        value=f"`{websocket_latency} ms`")
        embed.add_field(name="Response Time", value=f"`{response_time} ms`")
        embed.set_footer(text="Bot Latency Information")
        await message.edit(content=None, embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))

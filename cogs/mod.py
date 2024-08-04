import discord
from discord.ext import commands
from main import Bot
from datetime import timedelta
import aiohttp
from typing import Optional


class Moderation(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def close(self):
        await self.session.close()

    # --------------------------------------------------------------------------------------------------------------------------

    @commands.command(aliases=['av', 'pfp'])
    async def avatar(self, ctx, user: Optional[discord.User] = None):
        user = user or ctx.author
        em = discord.Embed(title=f"{user}'s Profile Picture: ", color=0x2f3131)
        em.set_image(url=user.display_avatar.url)  # Access URL property
        em.set_footer(text=f"Requested by -> {ctx.author.name}",
                      icon_url=ctx.author.avatar.url)  # Access URL property
        await ctx.send(embed=em)

    # --------------------------------------------------------------------------------------------------------------------------

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

    # --------------------------------------------------------------------------------------------------------------------------

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

        # --------------------------------------------------------------------------------------------------------------------------

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

    # --------------------------------------------------------------------------------------------------------------------------

    @commands.command(aliases=['clear', 'clr'])
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: int = 2):
        if isinstance(ctx.channel, discord.TextChannel):
            user = ctx.author.name
            embed = discord.Embed(
                title="**Messages Has Been Deleted** *Successfully*!!",
                description=f"```py\nAmount Deleted: {amount}```")
            embed.set_footer(
                text=
                f"This Message Will Be Deleted Shortly After 4 Seconds..  •  Moderator: {user}"
            )
            await ctx.channel.purge(limit=amount)
            await ctx.send(embed=embed, delete_after=4)
        else:
            await ctx.send("This command can only be used in text channels.",
                           delete_after=4)

    # --------------------------------------------------------------------------------------------------------------------------

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

    # ---------------------------------------------------------------------------------------------------------------------------

    @commands.command(pass_context=True, aliases=['ch_id', 'channelid'])
    async def channel_id(self, ctx, channel_name: str):
        channel = discord.utils.get(ctx.guild.channels, name=channel_name)
        if channel is None:
            await ctx.channel.send("Channel Not Found")
        else:
            await ctx.channel.send(
                f"The Channel <#{channel.id}>'s **ID** Is: ```py\n{channel.id}```"
            )

    # -------------------------------------------------------------------------------------------------------------------------

    @commands.command()
    async def slowmode(self, ctx, channel: discord.TextChannel, delay: int):
        """Changes the slowmode of the mentioned channel.

        Args:
            channel: The channel to slowmode.
            delay: The new slowmode delay in seconds.
        """
        await channel.edit(slowmode_delay=delay)
        await ctx.send(
            f"Slowmode for {channel.name} has been changed to {delay} seconds."
        )

    # ---------------------------------------------------------------------------------------------------------------------------

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def nuke(self, ctx, channel: discord.TextChannel = None):
        """Deletes and recreates a channel with the same properties"""
        if channel is None:
            channel = ctx.channel

        # Save the channel properties
        name = channel.name
        category = channel.category
        position = channel.position
        overwrites = {
            target: overwrite
            for target, overwrite in channel.overwrites.items()
            if isinstance(target, (discord.Role, discord.Member))
        }
        topic = channel.topic or ""  # Ensure topic is a string
        nsfw = channel.is_nsfw()
        slowmode_delay = channel.slowmode_delay
        reason = f"Channel nuked by {ctx.author}"
        permissions_synced = channel.permissions_synced
        announcement_channel = channel.is_news()
        guild = channel.guild

        # Fetch the webhooks
        webhooks = await channel.webhooks()

        # Fetch the invites
        invites = await channel.invites()

        # Fetch pinned messages
        pinned_messages = await channel.pins()

        # Delete the channel
        await channel.delete()

        # Create a new channel with the same properties
        if category:
            new_channel = await category.create_text_channel(
                name, overwrites=overwrites, reason=reason)
        else:
            new_channel = await guild.create_text_channel(
                name, overwrites=overwrites, reason=reason)

        # Edit the new channel with the saved properties
        await new_channel.edit(position=position,
                               topic=topic,
                               nsfw=nsfw,
                               slowmode_delay=slowmode_delay,
                               sync_permissions=permissions_synced)

        # Set the new channel as an announcement channel if it was one before
        if announcement_channel:
            await new_channel.edit(type=discord.ChannelType.news)

        # Recreate the webhooks in the new channel and store their URLs
        webhook_urls = []
        for i, webhook in enumerate(webhooks, start=1):
            webhook_name = webhook.name or "Default Webhook Name"
            new_webhook = await new_channel.create_webhook(
                name=webhook_name,
                avatar=await webhook.avatar.read() if webhook.avatar else None,
                reason=reason)
            webhook_urls.append(f"{i}. [{webhook_name}]({new_webhook.url})")

        # Recreate the invites in the new channel
        for invite in invites:
            await new_channel.create_invite(max_age=invite.max_age or 0,
                                            max_uses=invite.max_uses or 0,
                                            temporary=invite.temporary
                                            or False,
                                            unique=getattr(
                                                invite, 'unique', False),
                                            reason=reason)

        # Repost and pin the pinned messages in the new channel
        for message in pinned_messages:
            new_msg = await new_channel.send(message.content)
            await new_msg.pin()

        # Send a message with the webhook URLs if there are any webhooks
        webhook_message = f"Channel has been nuked by {ctx.author.mention}\n\n"
        if webhook_urls:
            webhook_message += "Webhooks:\n" + "\n".join(webhook_urls)
        await new_channel.send(webhook_message)


# ---------------------------------------------------------------------------------------------------------------------------


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))

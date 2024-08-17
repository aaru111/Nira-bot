import discord
from discord.ext import commands
from typing import Optional, List
import aiohttp
import asyncio
import time
from functools import wraps
import io


def ensure_permissions(permission: str):
    """Decorator to check user permissions."""

    def decorator(func):

        @wraps(func)
        async def wrapper(self, ctx: commands.Context, *args, **kwargs):
            if not getattr(ctx.author.guild_permissions, permission):
                await ctx.send(
                    f"You don't have the {permission} permission to use this command.",
                    ephemeral=True)
                return
            return await func(self, ctx, *args, **kwargs)

        return wrapper

    return decorator


class CustomButton(discord.ui.Button):
    """Custom button for Discord UI."""

    def __init__(self, label: str, emoji: str, url: str):
        super().__init__(label=label,
                         emoji=emoji,
                         style=discord.ButtonStyle.link,
                         url=url)


class AvatarView(discord.ui.View):
    """View containing a button to download a user's avatar."""

    def __init__(self, user_avatar_url: str):
        super().__init__()
        self.add_item(CustomButton("Download", "⬇️", user_avatar_url))


class ConfirmationView(discord.ui.View):

    def __init__(self, ctx: commands.Context, channel: discord.TextChannel):
        super().__init__(timeout=30)  # 30 seconds to respond
        self.ctx = ctx
        self.channel = channel
        self.value = None

    async def interaction_check(self,
                                interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "Only the user who initiated the command can interact.",
                ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Yes",
                       style=discord.ButtonStyle.danger,
                       emoji="✅")
    async def confirm(self, interaction: discord.Interaction,
                      button: discord.ui.Button):
        await interaction.response.defer()
        self.value = True
        self.stop()

    @discord.ui.button(label="No",
                       style=discord.ButtonStyle.secondary,
                       emoji="❌")
    async def cancel(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        await interaction.response.defer()
        self.value = False
        self.stop()


class Moderation(commands.Cog):
    """Cog for moderation commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.nuke_cooldowns = commands.CooldownMapping.from_cooldown(
            1, 300, commands.BucketType.member)

    async def cog_unload(self):
        """Clean up resources when the cog is unloaded."""
        await self.session.close()

    @commands.hybrid_command()
    async def avatar(self,
                     ctx: commands.Context,
                     user: Optional[discord.User] = None):
        """Show a user's avatar."""
        user = user or ctx.author
        embed = discord.Embed(title=f"{user}'s Profile Picture",
                              color=discord.Color.random())
        embed.set_image(url=user.display_avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author.name}",
                         icon_url=ctx.author.avatar.url)
        await ctx.send(embed=embed, view=AvatarView(user.display_avatar.url))

    @commands.hybrid_command()
    @ensure_permissions("kick_members")
    async def kick(self,
                   ctx: commands.Context,
                   member: discord.Member,
                   *,
                   reason: Optional[str] = None):
        """Kick a member."""
        reason = reason or "No reason provided"
        await member.kick(reason=reason)
        await ctx.send(
            f"{member.mention} has been kicked by **{ctx.author}**.\nReason: {reason}",
            ephemeral=True)

    @commands.hybrid_command()
    @ensure_permissions("ban_members")
    async def ban(self,
                  ctx: commands.Context,
                  member: discord.Member,
                  *,
                  reason: Optional[str] = None):
        """Ban a member."""
        reason = reason or "No reason provided"
        await member.ban(reason=reason)
        await ctx.send(f"{member.mention} has been banned from the guild.",
                       ephemeral=True)

    @commands.hybrid_command()
    @ensure_permissions("kick_members")
    async def warn(self,
                   ctx: commands.Context,
                   member: discord.Member,
                   *,
                   reason: Optional[str] = None):
        """Warn a member."""
        reason = reason or "No reason provided"
        await ctx.send(
            f"{member.mention}, you have been warned by **{ctx.author}**.\nReason: {reason}"
        )

    @commands.hybrid_command(name="purge")
    @ensure_permissions("manage_messages")
    async def purge(self, ctx: commands.Context, amount: int = 2):
        """Delete messages."""
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("This command can only be used in a text channel.",
                           ephemeral=True)
            return

        deleted = await ctx.channel.purge(limit=amount)
        await ctx.send(f"Deleted {len(deleted)} messages.",
                       ephemeral=True,
                       delete_after=5)

    @commands.hybrid_command()
    @ensure_permissions("ban_members")
    async def unban(self, ctx: commands.Context, user_id: str):
        """Unban a user."""
        try:
            user = await self.bot.fetch_user(int(user_id))
            await ctx.guild.unban(user)
            await ctx.send(f"{user.mention} has been unbanned.",
                           ephemeral=True)
        except (ValueError, discord.NotFound):
            await ctx.send("User not found or not banned.", ephemeral=True)

    @commands.hybrid_command()
    async def channel_id(self, ctx: commands.Context, channel_name: str):
        """Get a channel's ID by name."""
        channel = discord.utils.get(ctx.guild.channels, name=channel_name)
        if channel:
            await ctx.send(
                f"The Channel {channel.mention}'s ID is: `{channel.id}`")
        else:
            await ctx.send("Channel not found.", ephemeral=True)

    @commands.hybrid_command()
    @ensure_permissions("manage_channels")
    async def slowmode(self, ctx: commands.Context,
                       channel: discord.TextChannel, delay: int):
        """Set a channel's slowmode delay."""
        if delay < 0:
            await ctx.send(
                "The slowmode delay must be greater than or equal to 0 seconds.",
                ephemeral=True)
            return
        await channel.edit(slowmode_delay=delay)
        await ctx.send(
            f"Slowmode for {channel.mention} has been changed to {delay} seconds."
        )

    @commands.hybrid_command()
    @commands.has_permissions(manage_channels=True)
    async def nuke(self,
                   ctx: commands.Context,
                   channel: Optional[discord.TextChannel] = None):
        """Delete and recreate a channel, with confirmation."""
        # Check cooldown
        retry_after = self.nuke_cooldowns.update_rate_limit(ctx.message)
        if retry_after:
            await ctx.send(
                f"You need to wait {retry_after:.1f} seconds before using the nuke command again.",
                ephemeral=True)
            return

        channel = channel or ctx.channel
        if not isinstance(channel, discord.TextChannel):
            await ctx.send("This command can only be used in a text channel.",
                           ephemeral=True)
            return

        confirmation_view = ConfirmationView(ctx, channel)
        confirmation_message = await ctx.send(
            f"Are you sure you want to nuke {channel.mention}? This action cannot be undone.",
            view=confirmation_view)

        timeout = await confirmation_view.wait()

        for child in confirmation_view.children:
            child.disabled = True
        await confirmation_message.edit(view=confirmation_view)

        if confirmation_view.value is None:
            await ctx.send("Nuke command timed out. No action was taken.",
                           ephemeral=True)
            return
        elif confirmation_view.value is False:
            await ctx.send("Nuke command cancelled.", ephemeral=True)
            return

        if ctx.interaction:
            await ctx.interaction.response.defer(ephemeral=True)
        else:
            await ctx.typing()

        properties = await self._get_channel_properties(channel)
        webhooks, invites, pinned_messages = await self._fetch_channel_data(
            channel)

        await channel.delete(reason=f"Channel nuked by {ctx.author}")

        new_channel = await self._create_new_channel(ctx.guild, properties)
        await self._recreate_channel_data(new_channel, webhooks, invites,
                                          pinned_messages)

        message_content = (
            f"Channel has been nuked by {ctx.author.mention}\n"
            f"Channel {new_channel.mention} has been nuked and recreated.")

        try:
            await new_channel.send(message_content)
        except discord.Forbidden:
            await ctx.author.send(
                f"Nuke operation completed, but the bot couldn't send a message to {new_channel.mention} due to missing permissions."
            )

        try:
            if ctx.interaction:
                await ctx.interaction.followup.send(
                    f"Nuked and recreated {new_channel.mention}.",
                    ephemeral=True)
            else:
                await ctx.send(f"Nuked and recreated {new_channel.mention}.")
        except discord.HTTPException:
            pass

    async def _get_channel_properties(self,
                                      channel: discord.TextChannel) -> dict:
        return {
            'name': channel.name,
            'category': channel.category,
            'position': channel.position,
            'overwrites': channel.overwrites,
            'topic': channel.topic or "",
            'nsfw': channel.is_nsfw(),
            'slowmode_delay': channel.slowmode_delay,
            'permissions_synced': channel.permissions_synced,
            'is_news': channel.is_news()
        }

    async def _fetch_channel_data(self, channel: discord.TextChannel) -> tuple:
        webhooks = await channel.webhooks()
        invites = await channel.invites()
        pinned_messages = await channel.pins()
        pinned_messages.sort(key=lambda m: m.created_at)
        return webhooks, invites, pinned_messages

    async def _create_new_channel(self, guild: discord.Guild,
                                  properties: dict) -> discord.TextChannel:
        new_channel = await guild.create_text_channel(
            name=properties['name'],
            category=properties['category'],
            overwrites=properties['overwrites'],
            position=properties['position'],
            topic=properties['topic'],
            nsfw=properties['nsfw'],
            slowmode_delay=properties['slowmode_delay'])
        if properties['is_news']:
            await new_channel.edit(type=discord.ChannelType.news)
        return new_channel

    async def _recreate_channel_data(self, new_channel: discord.TextChannel,
                                     webhooks: List[discord.Webhook],
                                     invites: List[discord.Invite],
                                     pinned_messages: List[discord.Message]):
        for webhook in webhooks:
            avatar = None
            if webhook.avatar:
                avatar = await webhook.avatar.read()
            await new_channel.create_webhook(name=webhook.name, avatar=avatar)

        for invite in invites:
            await new_channel.create_invite(
                max_age=invite.max_age if invite.max_age != 0 else None,
                max_uses=invite.max_uses if invite.max_uses != 0 else None,
                temporary=invite.temporary,
                unique=invite.unique)

        pinned_messages.sort(key=lambda m: m.created_at)

        for message in pinned_messages:
            content = message.content
            embeds = [
                embed for embed in message.embeds if embed.type == 'rich'
            ]
            files = []

            for attachment in message.attachments:
                try:
                    file_data = await attachment.read()
                    file = discord.File(io.BytesIO(file_data),
                                        filename=attachment.filename)
                    files.append(file)
                except discord.HTTPException:
                    continue

            try:
                if content or embeds or files:
                    new_message = await new_channel.send(content=content
                                                         or None,
                                                         embeds=embeds,
                                                         files=files)
                    await new_message.pin()

                    await asyncio.sleep(0.5)
                    if files:
                        await asyncio.sleep(1)
                else:
                    print("Skipping empty message")
            except discord.HTTPException as e:
                if e.code == 429:  # Rate limit error
                    retry_after = e.retry_after
                    await asyncio.sleep(retry_after)
                    try:
                        if content or embeds or files:
                            new_message = await new_channel.send(
                                content=content or None,
                                embeds=embeds,
                                files=files)
                            await new_message.pin()
                    except discord.HTTPException as e2:
                        print(f"Failed to send message after rate limit: {e2}")
                else:
                    print(f"Error recreating message: {e}")

            for file in files:
                file.close()
            files.clear()

    @commands.hybrid_command()
    async def ping(self, ctx: commands.Context):
        """Check bot latency."""
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
    """Set up the Moderation cog."""
    await bot.add_cog(Moderation(bot))

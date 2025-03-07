from typing import Optional, List, Tuple
from discord.ext.commands import Context
from datetime import timedelta, datetime
from discord import app_commands
from discord.ext import commands
import platform
import datetime
import aiohttp
import asyncio
import discord
import psutil
import time
import io


async def _get_channel_properties(channel: discord.TextChannel) -> dict:
    """Retrieve a channel's properties."""
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


async def _fetch_channel_data(
    channel: discord.TextChannel
) -> Tuple[List[discord.Webhook], List[discord.Invite], List[discord.Message]]:
    """Fetch webhooks, invites, and pinned messages from a channel."""
    webhooks = await channel.webhooks()
    invites = await channel.invites()
    pinned_messages = await channel.pins()
    pinned_messages.sort(key=lambda m: m.created_at)
    return webhooks, invites, pinned_messages


async def _create_new_channel(guild: discord.Guild,
                              properties: dict) -> discord.TextChannel:
    """Create a new channel with the same properties."""
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


async def _recreate_channel_data(
    new_channel: discord.TextChannel, webhooks: List[discord.Webhook],
    invites: List[discord.Invite], pinned_messages: List[discord.Message]
) -> Tuple[List[discord.Invite], List[discord.Webhook]]:
    """Recreate webhooks, invites, and pinned messages in the new channel."""
    new_invites = []
    new_webhooks = []

    # Recreate webhooks
    for webhook in webhooks:
        try:
            avatar = await webhook.avatar.read() if webhook.avatar else None
            new_webhook = await new_channel.create_webhook(name=webhook.name,
                                                           avatar=avatar)
            new_webhooks.append(new_webhook)
        except Exception as e:
            print(f"Error recreating webhook: {e}")

    # Recreate invites
    for i, invite in enumerate(invites, 1):
        try:
            new_invite = await new_channel.create_invite(
                max_age=invite.max_age if invite.max_age != 0 else None,
                max_uses=invite.max_uses if invite.max_uses != 0 else None,
                temporary=invite.temporary)
            new_invites.append(new_invite)
        except Exception as e:
            print(f"Error recreating invite: {e}")

    # Recreate pinned messages
    if pinned_messages:
        for message in sorted(pinned_messages, key=lambda m: m.created_at):
            try:
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
                    except Exception:
                        print(
                            f"Error reading attachment: {attachment.filename}")

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
                    print(f"Rate limited. Waiting {e.retry_after} seconds.")
                    await asyncio.sleep(e.retry_after)
                else:
                    print(f"Error recreating message: {e}")
            except Exception as e:
                print(f"Unexpected error recreating message: {e}")

            finally:
                for file in files:
                    file.close()
                files.clear()

    return new_invites, new_webhooks


class RoleInfoView(discord.ui.View):

    def __init__(self, role: discord.Role):
        super().__init__()
        self.role = role

    @discord.ui.button(label="Show Members", style=discord.ButtonStyle.primary)
    async def show_members(self, interaction: discord.Interaction,
                           button: discord.ui.Button):
        members = self.role.members
        if not members:
            await interaction.response.send_message(
                "No members have this role.", ephemeral=True)
            return

        embed = discord.Embed(title=f"Members with {self.role.name} role",
                              color=self.role.color)
        member_list = [member.mention for member in members]
        chunks = [
            member_list[i:i + 20] for i in range(0, len(member_list), 20)
        ]
        for i, chunk in enumerate(chunks, 1):
            embed.add_field(name=f"Members {i}",
                            value="\n".join(chunk),
                            inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Show Permissions",
                       style=discord.ButtonStyle.primary)
    async def show_permissions(self, interaction: discord.Interaction,
                               button: discord.ui.Button):
        permissions = self.role.permissions
        enabled_perms = [
            perm[0].replace('_', ' ').title() for perm in permissions
            if perm[1]
        ]

        if not enabled_perms:
            await interaction.response.send_message(
                "This role has no enabled permissions.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Enabled Permissions for {self.role.name}",
            color=self.role.color)

        # Split permissions into chunks of 20
        chunks = [
            enabled_perms[i:i + 20] for i in range(0, len(enabled_perms), 20)
        ]

        # Add fields for each chunk, making them inline
        for i, chunk in enumerate(chunks, 1):
            embed.add_field(name=f"Permissions {i}",
                            value=" ".join(chunk),
                            inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)


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


class ChannelSelect(discord.ui.Select):
    """Select menu for choosing a channel to get its ID."""

    def __init__(self, options: List[discord.SelectOption], cog):
        super().__init__(placeholder="Select a channel to get its ID...",
                         min_values=1,
                         max_values=1,
                         options=options)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        selected_channel = discord.utils.get(interaction.guild.channels,
                                             id=int(self.values[0]))
        if selected_channel:
            await interaction.response.send_message(
                f"The Channel {selected_channel.mention}'s ID is: ||`{selected_channel.id}`||",
                ephemeral=True)


class PrevButton(discord.ui.Button):
    """Button to go to the previous page of the channel dropdown."""

    def __init__(self):
        super().__init__(label="Prev", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        view: ChannelDropdownView = self.view
        view.page -= 1
        view.update_dropdown_options()
        await interaction.response.edit_message(view=view)


class NextButton(discord.ui.Button):
    """Button to go to the next page of the channel dropdown."""

    def __init__(self):
        super().__init__(label="Next", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        view: ChannelDropdownView = self.view
        view.page += 1
        view.update_dropdown_options()
        await interaction.response.edit_message(view=view)


class ChannelDropdownView(discord.ui.View):
    """View containing the channel select dropdown and pagination buttons."""

    def __init__(self,
                 ctx: commands.Context,
                 channels: List[discord.TextChannel],
                 cog,
                 page: int = 0):
        super().__init__(timeout=20)  # Set timeout to 20 seconds
        self.ctx = ctx
        self.channels = channels
        self.page = page
        self.cog = cog
        self.message = None  # Store the message object to delete it later
        self.update_dropdown_options()

    def update_dropdown_options(self):
        start_index = self.page * 25
        end_index = start_index + 25
        channel_options = [
            discord.SelectOption(label=channel.name, value=str(channel.id))
            for channel in self.channels[start_index:end_index]
        ]
        self.clear_items()
        self.add_item(ChannelSelect(channel_options, cog=self.cog))
        if len(self.channels) > 25:
            if self.page > 0:
                self.add_item(PrevButton())
            if end_index < len(self.channels):
                self.add_item(NextButton())

    async def on_timeout(self):
        """Handles the timeout for the view after 20 seconds of inactivity."""
        for child in self.children:
            child.disabled = True  # Disable all buttons in the view
        if self.message:  # Check if the message has been stored
            await self.message.edit(content="This interaction has timed out.",
                                    view=self)
            await asyncio.sleep(
                5)  # Wait for 5 seconds before deleting the message
            await self.message.delete()

    async def start(self):
        """Start the view by sending a message and storing its reference."""
        self.message = await self.ctx.send("Select a channel to get its ID:",
                                           view=self)


class Moderation(commands.Cog):
    """Cog for moderation commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.headers = {
            'User-Agent': 'Nira-Bot',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.nuke_cooldowns = commands.CooldownMapping.from_cooldown(
            1, 300, commands.BucketType.member)

        self.start_time = time.time()

    async def cog_unload(self):

        await self.session.close()

    def format_commit(self, commit_data: dict) -> str:
        try:
            sha = commit_data['sha'][:7]
            message = commit_data['commit']['message'].split('\n')[0]
            commit_url = commit_data['html_url']
            commit_time = datetime.datetime.strptime(
                commit_data['commit']['author']['date'], "%Y-%m-%dT%H:%M:%SZ")
            timestamp = discord.utils.format_dt(commit_time, "R")
            return f"[`{sha}`]({commit_url}) {timestamp} | {message}"
        except Exception as e:
            return f"Error formatting commit: {str(e)}"

    async def get_latest_commits(self, limit: int = 5) -> List[str]:
        """Fetch latest commits from GitHub repository."""
        url = "https://api.github.com/repos/aaru111/Nira-bot/commits"
        headers = {
            'User-Agent': 'Nira-Bot',
            'Accept': 'application/vnd.github.v3+json'
        }

        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    commits = await response.json()
                    return [
                        self.format_commit(commit)
                        for commit in commits[:limit]
                    ]
                else:
                    error_message = await response.text()
                    print(
                        f"GitHub API Error: Status {response.status} - {error_message}"
                    )
                    return [
                        f"Unable to fetch commit history (Status: {response.status})"
                    ]
        except aiohttp.ClientError as e:
            print(f"Network Error: {str(e)}")
            return ["Error: Could not connect to GitHub"]
        except Exception as e:
            print(f"Unexpected Error: {str(e)}")
            return [f"Error fetching commits: {str(e)}"]

    def get_system_info(self) -> dict:
        return {
            'python_version':
            platform.python_version(),
            'discord_version':
            discord.__version__,
            'os':
            f"{platform.system()} {platform.release()}",
            'cpu_usage':
            f"{psutil.cpu_percent()}%",
            'memory_usage':
            f"{psutil.Process().memory_percent():.2f}%",
            'uptime':
            str(datetime.timedelta(seconds=int(time.time() - self.start_time)))
        }

    def get_bot_stats(self) -> dict:
        total_members = sum(guild.member_count or 0
                            for guild in self.bot.guilds)
        total_channels = sum(len(guild.channels) for guild in self.bot.guilds)

        return {
            'servers': len(self.bot.guilds),
            'users': total_members,
            'channels': total_channels,
            'commands': len(self.bot.commands),
            'latency': f"{round(self.bot.latency * 1000)}ms"
        }

    @commands.hybrid_command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True,
                                   dms=True,
                                   private_channels=True)
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
    @commands.has_permissions(kick_members=True)
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
    @commands.has_permissions(ban_members=True)
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
    @commands.has_permissions(kick_members=True)
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
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: int = 2):
        """Delete messages."""
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("This command can only be used in a text channel.",
                           ephemeral=True)
            return

        is_slash = ctx.interaction is not None

        if is_slash:
            await ctx.defer(ephemeral=True)

        max_messages = 100  # Discord API limit
        remaining = amount
        total_deleted = 0

        while remaining > 0:
            try:
                batch_size = min(remaining, max_messages)
                deleted = await ctx.channel.purge(limit=batch_size)
                total_deleted += len(deleted)
                remaining -= len(deleted)

                if len(deleted) < batch_size:
                    # No more messages to delete
                    break

                # Add a small delay to avoid rate limiting
                await asyncio.sleep(1)

            except discord.errors.HTTPException as e:
                if e.status == 429:  # Rate limit error
                    retry_after = e.retry_after
                    await asyncio.sleep(retry_after)
                else:
                    error_message = f"An error occurred while trying to delete messages: {str(e)}"
                    await ctx.send(error_message, ephemeral=True)
                    return

        completion_message = f"Deleted {total_deleted} messages."

        if is_slash:
            await ctx.interaction.followup.send(completion_message,
                                                ephemeral=True)
        else:
            await ctx.send(completion_message, delete_after=5)

    @commands.hybrid_command()
    @commands.has_permissions(ban_members=True)
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
    async def channel_id(self, ctx: commands.Context):
        """Get a channel's ID by selecting from a dropdown menu."""
        accessible_channels = [
            channel for channel in ctx.guild.text_channels
            if channel.permissions_for(ctx.author).view_channel
        ]
        if not accessible_channels:
            await ctx.send("No accessible channels found.", ephemeral=True)
            return
        view = ChannelDropdownView(ctx, accessible_channels, self)
        await view.start()

    @commands.hybrid_command()
    @commands.has_permissions(manage_channels=True)
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

    async def safe_send(self, ctx, content, **kwargs):
        try:
            if ctx.interaction and not ctx.interaction.response.is_done():
                await ctx.interaction.response.send_message(content, **kwargs)
            else:
                await ctx.send(content, **kwargs)
        except discord.HTTPException as e:
            if e.code == 10062:  # Unknown interaction
                await ctx.send(content, **kwargs)
            else:
                raise

    @commands.hybrid_command()
    @commands.has_permissions(manage_channels=True)
    async def nuke(self,
                   ctx: commands.Context,
                   channel: Optional[discord.TextChannel] = None):
        """Delete and recreate a channel, with confirmation."""
        # Check for cooldown
        bucket = self.nuke_cooldowns.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            return await ctx.send(
                f"You're on cooldown. Try again in {retry_after:.2f} seconds.",
                ephemeral=True)

        channel = channel or ctx.channel
        if not isinstance(channel, discord.TextChannel):
            await ctx.send("This command can only be used in a text channel.",
                           ephemeral=True)
            return

        # Defer the response for slash commands
        if ctx.interaction:
            await ctx.defer(ephemeral=True)

        confirmation_view = ConfirmationView(ctx, channel)
        try:
            confirmation_message = await ctx.send(
                f"Are you sure you want to nuke {channel.mention}? This action cannot be undone.",
                view=confirmation_view)
        except discord.NotFound:
            await self.safe_send(
                ctx,
                "The channel was deleted before the confirmation could be sent.",
                ephemeral=True)
            return

        await confirmation_view.wait()

        try:
            if confirmation_view.value is None:
                for item in confirmation_view.children:
                    item.disabled = True
                await confirmation_message.edit(
                    content="Nuke command timed out. No action was taken.",
                    view=confirmation_view)
                return
            elif confirmation_view.value is False:
                for item in confirmation_view.children:
                    item.disabled = True
                await confirmation_message.edit(
                    content="Nuke command cancelled.", view=confirmation_view)
                return

            # Edit the original message to show that nuking is in progress
            for item in confirmation_view.children:
                item.disabled = True
            await confirmation_message.edit(content="Nuking channel...",
                                            view=confirmation_view)

            properties = await _get_channel_properties(channel)

            try:
                webhooks = await channel.webhooks()
            except discord.NotFound:
                webhooks = []

            try:
                invites = await channel.invites()
            except discord.NotFound:
                invites = []

            try:
                pinned_messages = await channel.pins()
            except discord.NotFound:
                pinned_messages = []

            try:
                await channel.delete(reason=f"Channel nuked by {ctx.author}")
            except discord.NotFound:
                await self.safe_send(ctx,
                                     "The channel was already deleted.",
                                     ephemeral=True)
                return

            new_channel = await _create_new_channel(ctx.guild, properties)
            new_invites, new_webhooks = await _recreate_channel_data(
                new_channel, webhooks, invites, pinned_messages)

            message_content = f"Channel has been nuked by {ctx.author.mention}\n"
            message_content += f"New channel: {new_channel.mention}\n\n"

            if new_invites:
                message_content += "**Invite Links:**\n"
                for i, invite in enumerate(new_invites, 1):
                    expiry_date = datetime.utcnow() + timedelta(
                        seconds=invite.max_age) if invite.max_age else "Never"
                    invite_name = f"Invite {i} - (Expires: {expiry_date})"
                    message_content += f"[{invite_name}]({invite.url})\n"

            if new_webhooks:
                message_content += "\n**Webhook URLs:**\n"
                for webhook in new_webhooks:
                    message_content += f"[{webhook.name}]({webhook.url})\n"

            try:
                await new_channel.send(message_content)
            except discord.Forbidden:
                await ctx.author.send(
                    f"Nuke operation completed, but the bot couldn't send a message to {new_channel.mention} due to missing permissions."
                )

            completion_message = f"Nuked and recreated {new_channel.mention}."
            await self.safe_send(ctx, completion_message, ephemeral=True)

        except discord.NotFound:
            await self.safe_send(
                ctx,
                "The channel was deleted during the nuke process.",
                ephemeral=True)
        except discord.Forbidden:
            await self.safe_send(
                ctx,
                "The bot doesn't have permission to delete or recreate the channel.",
                ephemeral=True)
        except discord.HTTPException as e:
            await self.safe_send(
                ctx,
                f"An error occurred while nuking the channel: {str(e)}",
                ephemeral=True)
        except Exception as e:
            await self.safe_send(ctx,
                                 f"An unexpected error occurred: {str(e)}",
                                 ephemeral=True)

    @commands.hybrid_command(
        name="nick", description="Change the nickname of a user on a server.")
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    @app_commands.describe(user="The user that should have a new nickname.",
                           nickname="The new nickname that should be set.")
    async def nick(self,
                   context: Context,
                   user: discord.User,
                   *,
                   nickname: Optional[str] = None) -> None:
        """Change the nickname of a user on a server.
        :param context: The hybrid command context.
        :param user: The user that should have its nickname changed.
        :param nickname: The new nickname of the user. Default is None, which will reset the nickname.
        """
        member = context.guild.get_member(
            user.id) or await context.guild.fetch_member(user.id)
        try:
            await member.edit(nick=nickname)
            embed = discord.Embed(
                description=f"**{member}'s** new nickname is **{nickname}**!",
                color=0xBEBEFE)
            await context.send(embed=embed)
        except:
            embed = discord.Embed(
                description=
                "An error occurred while trying to change the nickname of the user. Make sure my role is above the role of the user you want to change the nickname.",
                color=0xE02B2B)
            await context.send(embed=embed)

    @commands.hybrid_command()
    async def ping(self, ctx: commands.Context):
        """Check bot latency."""
        websocket_latency = round(self.bot.latency * 1000, 2)
        start_time = time.time()
        message = await ctx.send("Pinging...")
        response_time = round((time.time() - start_time) * 1000, 2)
        embed = discord.Embed(title="🏓 Pong!", color=0x2f3131)
        embed.add_field(name="WebSocket Latency",
                        value=f"`{websocket_latency}ms`")
        embed.add_field(name="Response Time", value=f"`{response_time}ms`")
        embed.set_footer(text="Bot Latency Information")
        await message.edit(content=None, embed=embed)

    @commands.hybrid_command(name="role-add")
    @commands.has_permissions(manage_roles=True)
    async def role_add(self,
                       ctx: commands.Context,
                       member: discord.Member,
                       role: discord.Role,
                       time: Optional[int] = None):
        """Add a role to a user optionally for a limited duration."""
        await member.add_roles(role)
        await ctx.send(f"Added role {role.mention} to {member.mention}.",
                       ephemeral=True)
        if time:
            await asyncio.sleep(time)
            await member.remove_roles(role)
            await ctx.send(
                f"Removed role {role.mention} from {member.mention} after {time} seconds.",
                ephemeral=True)

    @commands.hybrid_command(name="role-remove")
    @commands.has_permissions(manage_roles=True)
    async def role_remove(self, ctx: commands.Context, member: discord.Member,
                          role: discord.Role):
        """Remove a role from a user."""
        await member.remove_roles(role)
        await ctx.send(f"Removed role {role.mention} from {member.mention}.",
                       ephemeral=True)

    @commands.hybrid_command(name="role-list")
    async def role_list(self, ctx: commands.Context, member: discord.Member):
        """List all roles of a user."""
        roles = [
            role.mention for role in member.roles
            if role != ctx.guild.default_role
        ]
        if roles:
            roles_str = "\n".join(f"- {role}" for role in roles)
            embed = discord.Embed(title=f"{member.display_name}'s Roles",
                                  description=roles_str,
                                  color=discord.Color.random())
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"{member.mention} has no roles.")

    @commands.hybrid_command(name="role-info")
    async def role_info(self, ctx: commands.Context, role: discord.Role):
        """Get information about a role."""
        embed = discord.Embed(title=f"Role Info: {role.name}",
                              color=role.color)
        embed.add_field(name="ID", value=role.id)
        embed.add_field(name="Mentionable", value=role.mentionable)
        embed.add_field(name="Hoist", value=role.hoist)
        embed.add_field(name="Position", value=role.position)
        embed.add_field(name="Created At",
                        value=role.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        embed.add_field(name="Member Count", value=len(role.members))
        view = RoleInfoView(role)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(
        name="userinfo",
        description="Show some information about the selected user")
    @app_commands.describe(member="Select the wished member!")
    async def userinfo(self, ctx, member: discord.Member):
        await ctx.defer(ephemeral=False)
        user = await self.bot.fetch_user(member.id)
        banner_url = user.banner.url if user.banner else None
        profile_image = user.avatar.url if user.avatar else user.default_avatar.url
        if bool(member.premium_since) == "True":
            boosts_server = "Yes"
        else:
            boosts_server = "No"

        top_role = member.top_role.mention
        highest_role_color = member.top_role.color if member.top_role.color != discord.Color.default(
        ) else None
        highest_role_color_hex = highest_role_color if highest_role_color else "Default `(#000000)`"

        embed = discord.Embed(color=discord.Color(int('fce38f', 16)))
        embed.set_author(name=member.display_name, icon_url=profile_image)
        embed.set_thumbnail(url=profile_image)
        embed.set_image(url=banner_url)

        embed.add_field(
            name="Username",
            value=f"[{member.name}](https://discordapp.com/users/{member.id})",
            inline=False)
        embed.add_field(name="User ID", value=member.id, inline=False)
        embed.add_field(name="Boosts Server",
                        value=boosts_server,
                        inline=False)
        embed.add_field(name="Account Created",
                        value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        inline=False)
        embed.add_field(name="Joined Server",
                        value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"),
                        inline=False)
        embed.add_field(name="Top Role", value=top_role, inline=False)
        embed.add_field(name="Highest Role Color",
                        value=f"{highest_role_color_hex}",
                        inline=False)
        activity_member = ctx.guild.get_member(member.id)
        if activity_member.activity is not None:
            if activity_member.activity.type == discord.ActivityType.listening:
                artist = activity_member.activity.artist
                song_title = activity_member.activity.title
                album = activity_member.activity.album
                activity_name = activity_member.activity.name
                embed.add_field(name="Activity",
                                value=activity_name,
                                inline=False)
                embed.add_field(
                    name="Listening to",
                    value=
                    f"- **Title:** `{song_title}` \n- **Artist:** `{artist}` \n- **Album:** `{album}`",
                    inline=False)

            elif activity_member.activity.type == discord.ActivityType.playing:
                embed.add_field(name="Activity",
                                value=f"{activity_member.activity.name}",
                                inline=False)
                embed.add_field(
                    name="Details",
                    value=
                    f"- {activity_member.activity.details} \n- {activity_member.activity.state}"
                    or "Not provided",
                    inline=False)

            elif activity_member.activity.type != discord.ActivityType.custom:
                activity_name = activity_member.activity.name
                embed.add_field(name="Activity",
                                value=activity_name,
                                inline=False)
            else:
                pass
        else:
            pass

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="serverinfo",
        description="Get some useful (or not) information about the server.")
    async def serverinfo(self, context: Context) -> None:
        """Get some useful (or not) information about the server."""
        guild = context.guild
        roles = [f"• {role.mention}" for role in guild.roles]
        num_roles = len(roles)
        max_roles_per_field = 15

        owner = guild.owner

        embed = discord.Embed(
            title="**Server Information**",
            description=
            f"**Server Name:** {guild.name} -> Owner: {owner.display_name}",
            color=0xBEBEFE)

        if guild.icon is not None:
            embed.set_thumbnail(url=guild.icon.url)

        for i in range(0, min(num_roles, 15 * 25), max_roles_per_field):
            chunk = roles[i:i + max_roles_per_field]
            embed.add_field(name=f"Roles {i + 1} to {i + len(chunk)}",
                            value="\n".join(chunk),
                            inline=True)

        if num_roles > 15 * 25:
            embed.add_field(name="Notice",
                            value=f"Displaying first {15 * 25} roles only.",
                            inline=False)

        embed.add_field(name="Server ID", value=guild.id)
        embed.add_field(name="Member Count", value=guild.member_count)
        embed.add_field(name="Text/Voice Channels",
                        value=f"{len(guild.channels)}")
        embed.set_footer(text=f"Created at: {guild.created_at}")

        await context.send(embed=embed)

    @commands.hybrid_command(
        name="botinfo", description="Shows detailed information about the bot")
    @app_commands.describe(show_commits="Whether to show recent commits",
                           show_system="Whether to show system information",
                           show_stats="Whether to show bot statistics")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True,
                                   dms=True,
                                   private_channels=True)
    async def botinfo(self,
                      ctx: commands.Context,
                      show_commits: Optional[bool] = True,
                      show_system: Optional[bool] = True,
                      show_stats: Optional[bool] = True) -> None:
        await ctx.defer()
        try:
            if self.bot.user is None:
                raise RuntimeError("Bot user is not initialized")

            try:
                app_info = await self.bot.application_info()
                owner = app_info.team.owner if app_info.team else app_info.owner
                owner_mention = owner.mention if owner else "Unknown"
            except Exception as e:
                print(f"Error fetching owner info: {e}")
                owner_mention = "Unknown"

            bot_name = self.bot.user.name
            bot_avatar = self.bot.user.display_avatar.url

            embed = discord.Embed(
                title="Bot Information",
                description=f"**{bot_name}** - Made by {owner_mention}",
                color=discord.Color.from_rgb(239, 158, 240),
                timestamp=datetime.datetime.utcnow())

            embed.set_thumbnail(url=bot_avatar)

            if show_stats:
                stats = self.get_bot_stats()
                stats_text = (f"**Servers:** {stats['servers']}\n"
                              f"**Users:** {stats['users']}\n"
                              f"**Channels:** {stats['channels']}\n"
                              f"**Commands:** {stats['commands']}\n"
                              f"**Latency:** {stats['latency']}")
                embed.add_field(name="📊 Bot Statistics",
                                value=stats_text,
                                inline=True)

            if show_system:
                sys_info = self.get_system_info()
                sys_text = (f"**Python:** {sys_info['python_version']}\n"
                            f"**Discord.py:** {sys_info['discord_version']}\n"
                            f"**OS:** {sys_info['os']}\n"
                            f"**CPU Usage:** {sys_info['cpu_usage']}\n"
                            f"**Memory Usage:** {sys_info['memory_usage']}\n"
                            f"**Uptime:** {sys_info['uptime']}")
                embed.add_field(name="💻 System Information",
                                value=sys_text,
                                inline=True)

            if show_commits:
                commits = await self.get_latest_commits()
                if commits and not commits[0].startswith(
                        "Error") and not commits[0].startswith("Unable"):
                    embed.add_field(name="📝 Latest Changes",
                                    value="\n".join(commits),
                                    inline=False)
                else:
                    embed.add_field(
                        name="📝 Latest Changes",
                        value="Unable to fetch recent changes at this time.",
                        inline=False)

            author_avatar = ctx.author.display_avatar.url if ctx.author.display_avatar else None
            embed.set_footer(text=f"Requested by {ctx.author}",
                             icon_url=author_avatar)

            await ctx.send(embed=embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="Error",
                description=
                f"An error occurred while fetching information: {str(e)}",
                color=discord.Color.red())
            await ctx.send(embed=error_embed)


async def setup(bot: commands.Bot) -> None:
    """Setup the Moderation cog."""
    await bot.add_cog(Moderation(bot))

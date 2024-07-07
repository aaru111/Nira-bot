# This cog provides functionalities for setting up and managing giveaways and drops in a Discord server.
# Users with the necessary permissions can configure, start, and end giveaways and drops.
# The cog includes modals for setting up giveaways and drops, as well as buttons for entering and managing them.

import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import random
import asyncio
import datetime

embed_colour = 0x2b2d31


class GiveawaySetupModal(Modal):

    def __init__(self,
                 bot: commands.Bot,
                 ctx: commands.Context,
                 giveaway_channel=None) -> None:
        super().__init__(title="Giveaway Setup")
        self.bot = bot
        self.ctx = ctx
        self.giveaway_channel = giveaway_channel
        self.add_item(
            TextInput(label="Giveaway Item",
                      placeholder="Enter the giveaway item"))
        self.add_item(
            TextInput(label="Giveaway Time",
                      placeholder="Enter time (1h, 1d, 1w)",
                      min_length=2,
                      max_length=2))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        item: str = self.children[0].value
        time: str = self.children[1].value

        # Validate time input
        time_seconds: int = 0
        if time.endswith('h'):
            time_seconds = int(time[:-1]) * 3600
        elif time.endswith('d'):
            time_seconds = int(time[:-1]) * 86400
        elif time.endswith('w'):
            time_seconds = int(time[:-1]) * 604800

        if time_seconds < 3600:
            await interaction.response.send_message(embed=discord.Embed(
                description="Giveaway time must be at least 1 hour.",
                color=embed_colour),
                                                    ephemeral=True)
            return

        end_time = datetime.datetime.utcnow() + datetime.timedelta(
            seconds=time_seconds)
        giveaway_embed = discord.Embed(
            title="🎉 Giveaway 🎉",
            description=
            f"Item: **{item}**\nTime: **{time}**\nParticipants: **0**\nTime Left: **{time}**",
            color=embed_colour)
        giveaway_embed.set_footer(text="React with 🎉 to enter!")

        enter_button = Button(label="Enter Giveaway",
                              style=discord.ButtonStyle.green,
                              emoji="🎉")
        end_button = Button(label="End Giveaway",
                            style=discord.ButtonStyle.red,
                            emoji="⏹️")
        participants_button = Button(label="Participants",
                                     style=discord.ButtonStyle.blurple,
                                     emoji="👥")

        view = View()
        view.add_item(enter_button)
        view.add_item(end_button)
        view.add_item(participants_button)

        async def enter_giveaway(interaction: discord.Interaction) -> None:
            if "participants" not in self.bot.giveaways:
                self.bot.giveaways["participants"] = []
            if interaction.user.id not in self.bot.giveaways["participants"]:
                self.bot.giveaways["participants"].append(interaction.user.id)
                updated_embed = giveaway_embed.copy()
                updated_embed.description = f"Item: **{item}**\nTime: **{time}**\nParticipants: **{len(self.bot.giveaways['participants'])}**\nTime Left: **{await get_time_left(end_time)}**"
                await message.edit(embed=updated_embed)
                await interaction.response.send_message(embed=discord.Embed(
                    description=
                    f"{interaction.user.mention} entered the giveaway!",
                    color=embed_colour),
                                                        ephemeral=True)
            else:
                await interaction.response.send_message(embed=discord.Embed(
                    description=
                    f"{interaction.user.mention}, you have already entered the giveaway.",
                    color=embed_colour),
                                                        ephemeral=True)

        async def end_giveaway(interaction: discord.Interaction) -> None:
            if interaction.user.id == self.ctx.author.id or interaction.user.guild_permissions.manage_messages:
                if "participants" in self.bot.giveaways and self.bot.giveaways[
                        "participants"]:
                    winner = random.choice(self.bot.giveaways["participants"])
                    winner_embed = discord.Embed(
                        description=
                        f"Congratulations <@{winner}>! You won the **{item}**!",
                        color=embed_colour)
                    reroll_button = Button(label="Reroll",
                                           style=discord.ButtonStyle.secondary,
                                           emoji="🔄")

                    async def reroll_giveaway(
                            interaction: discord.Interaction) -> None:
                        if self.bot.giveaways["participants"]:
                            new_winner = random.choice(
                                self.bot.giveaways["participants"])
                            await interaction.response.send_message(
                                embed=discord.Embed(
                                    description=
                                    f"The new winner is <@{new_winner}>!",
                                    color=embed_colour),
                                ephemeral=False)
                        else:
                            await interaction.response.send_message(
                                embed=discord.Embed(
                                    description=
                                    "There are no participants to reroll.",
                                    color=embed_colour),
                                ephemeral=True)

                    reroll_button.callback = reroll_giveaway
                    reroll_view = View()
                    reroll_view.add_item(reroll_button)

                    await self.ctx.send(embed=winner_embed, view=reroll_view)
                    del self.bot.giveaways["participants"]
                else:
                    await interaction.response.send_message(embed=discord.Embed(
                        description="No participants to choose a winner from.",
                        color=embed_colour),
                                                            ephemeral=True)
                # Disable all buttons after the giveaway ends
                for item in view.children:
                    item.disabled = True
                await message.edit(embed=giveaway_embed, view=view)
            else:
                await interaction.response.send_message(embed=discord.Embed(
                    description=
                    "You do not have permission to end this giveaway.",
                    color=embed_colour),
                                                        ephemeral=True)

        async def list_participants(interaction: discord.Interaction) -> None:
            if "participants" in self.bot.giveaways:
                participants_list = "\n".join([
                    f"<@{user_id}>"
                    for user_id in self.bot.giveaways["participants"]
                ])
                await interaction.response.send_message(embed=discord.Embed(
                    description=f"Participants:\n{participants_list}",
                    color=embed_colour),
                                                        ephemeral=True)
            else:
                await interaction.response.send_message(embed=discord.Embed(
                    description="No one has entered the giveaway yet.",
                    color=embed_colour),
                                                        ephemeral=True)

        enter_button.callback = enter_giveaway
        end_button.callback = end_giveaway
        participants_button.callback = list_participants

        if self.giveaway_channel:
            message: discord.Message = await self.giveaway_channel.send(
                embed=giveaway_embed, view=view)
        else:
            message: discord.Message = await self.ctx.send(
                embed=giveaway_embed, view=view)

        await interaction.response.send_message(embed=discord.Embed(
            description="Giveaway setup complete!", color=embed_colour),
                                                ephemeral=True)

        # Update the timer in the embed message
        while time_seconds > 0:
            await asyncio.sleep(10)
            time_seconds -= 10
            updated_embed = giveaway_embed.copy()
            updated_embed.description = f"Item: **{item}**\nTime: **{time}**\nParticipants: **{len(self.bot.giveaways['participants'])}**\nTime Left: **{await get_time_left(end_time)}**"
            await message.edit(embed=updated_embed)

        if "participants" in self.bot.giveaways and self.bot.giveaways[
                "participants"]:
            winner = random.choice(self.bot.giveaways["participants"])
            winner_embed = discord.Embed(
                description=
                f"Time's up! The winner of the **{item}** is <@{winner}>!",
                color=embed_colour)
            reroll_button = Button(label="Reroll",
                                   style=discord.ButtonStyle.secondary,
                                   emoji="🔄")

            async def reroll_giveaway(
                    interaction: discord.Interaction) -> None:
                if self.bot.giveaways["participants"]:
                    new_winner = random.choice(
                        self.bot.giveaways["participants"])
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            description=f"The new winner is <@{new_winner}>!",
                            color=embed_colour),
                        ephemeral=False)
                else:
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            description="There are no participants to reroll.",
                            color=embed_colour),
                        ephemeral=True)

            reroll_button.callback = reroll_giveaway
            reroll_view = View()
            reroll_view.add_item(reroll_button)

            await self.ctx.send(embed=winner_embed, view=reroll_view)
            del self.bot.giveaways["participants"]
            # Disable all buttons after the giveaway ends
            for item in view.children:
                item.disabled = True
            await message.edit(embed=giveaway_embed, view=view)
        else:
            await self.ctx.send(embed=discord.Embed(
                description="No participants entered the giveaway.",
                color=embed_colour))


class DropSetupModal(Modal):

    def __init__(self,
                 bot: commands.Bot,
                 ctx: commands.Context,
                 drop_channel=None) -> None:
        super().__init__(title="Drop Setup")
        self.bot = bot
        self.ctx = ctx
        self.drop_channel = drop_channel
        self.add_item(
            TextInput(label="Drop Name", placeholder="Enter the drop name"))
        self.add_item(
            TextInput(label="Drop Time (0-180s)",
                      placeholder="Enter drop time in seconds",
                      min_length=1,
                      max_length=3))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        drop_name: str = self.children[0].value
        drop_time: str = self.children[1].value

        # Validate drop time input
        try:
            drop_time_seconds = int(drop_time)
            if not (0 <= drop_time_seconds <= 180):  # Updated max time to 180s
                raise ValueError
        except ValueError:
            await interaction.response.send_message(embed=discord.Embed(
                description="Drop time must be between 0 and 180 seconds.",
                color=embed_colour),
                                                    ephemeral=True)
            return

        end_time = datetime.datetime.utcnow() + datetime.timedelta(
            seconds=drop_time_seconds)
        drop_embed = discord.Embed(
            title="🎁 Drop 🎁",
            description=
            f"Item: **{drop_name}**\nTime: **{drop_time}s**\nParticipants: **0**\nTime Left: **{drop_time}s**",
            color=embed_colour)
        drop_embed.set_footer(text="React with 🎁 to enter!")

        enter_button = Button(label="Enter Drop",
                              style=discord.ButtonStyle.green,
                              emoji="🎁")
        end_button = Button(label="End Drop",
                            style=discord.ButtonStyle.red,
                            emoji="⏹️")

        view = View()
        view.add_item(enter_button)
        view.add_item(end_button)

        async def enter_drop(interaction: discord.Interaction) -> None:
            if "participants" not in self.bot.drops:
                self.bot.drops["participants"] = []
            if interaction.user.id not in self.bot.drops["participants"]:
                self.bot.drops["participants"].append(interaction.user.id)
                updated_embed = drop_embed.copy()
                updated_embed.description = f"Item: **{drop_name}**\nTime: **{drop_time}s**\nParticipants: **{len(self.bot.drops['participants'])}**\nTime Left: **{await get_time_left(end_time)}**"
                await message.edit(embed=updated_embed)
                await interaction.response.send_message(embed=discord.Embed(
                    description=f"{interaction.user.mention} entered the drop!",
                    color=embed_colour),
                                                        ephemeral=True)
            else:
                await interaction.response.send_message(embed=discord.Embed(
                    description=
                    f"{interaction.user.mention}, you have already entered the drop.",
                    color=embed_colour),
                                                        ephemeral=True)

        async def end_drop(interaction: discord.Interaction) -> None:
            if interaction.user.id == self.ctx.author.id or interaction.user.guild_permissions.manage_messages:
                if "participants" in self.bot.drops and self.bot.drops[
                        "participants"]:
                    winner = random.choice(self.bot.drops["participants"])
                    winner_embed = discord.Embed(
                        description=
                        f"Congratulations <@{winner}>! You won the **{drop_name}**!",
                        color=embed_colour)
                    reroll_button = Button(label="Reroll",
                                           style=discord.ButtonStyle.secondary,
                                           emoji="🔄")

                    async def reroll_drop(
                            interaction: discord.Interaction) -> None:
                        if self.bot.drops["participants"]:
                            new_winner = random.choice(
                                self.bot.drops["participants"])
                            await interaction.response.send_message(
                                embed=discord.Embed(
                                    description=
                                    f"The new winner is <@{new_winner}>!",
                                    color=embed_colour),
                                ephemeral=False)
                        else:
                            await interaction.response.send_message(
                                embed=discord.Embed(
                                    description=
                                    "There are no participants to reroll.",
                                    color=embed_colour),
                                ephemeral=True)

                    reroll_button.callback = reroll_drop
                    reroll_view = View()
                    reroll_view.add_item(reroll_button)

                    await self.ctx.send(embed=winner_embed, view=reroll_view)
                    del self.bot.drops["participants"]
                else:
                    await interaction.response.send_message(embed=discord.Embed(
                        description="No participants to choose a winner from.",
                        color=embed_colour),
                                                            ephemeral=True)
                # Disable all buttons after the drop ends
                for item in view.children:
                    item.disabled = True
                await message.edit(embed=drop_embed, view=view)
            else:
                await interaction.response.send_message(embed=discord.Embed(
                    description="You do not have permission to end this drop.",
                    color=embed_colour),
                                                        ephemeral=True)

        enter_button.callback = enter_drop
        end_button.callback = end_drop

        if self.drop_channel:
            message: discord.Message = await self.drop_channel.send(
                embed=drop_embed, view=view)
        else:
            message: discord.Message = await self.ctx.send(embed=drop_embed,
                                                           view=view)

        await interaction.response.send_message(embed=discord.Embed(
            description="Drop setup complete!", color=embed_colour),
                                                ephemeral=True)

        # Update the timer in the embed message
        while drop_time_seconds > 0:
            await asyncio.sleep(1)
            drop_time_seconds -= 1
            updated_embed = drop_embed.copy()
            updated_embed.description = f"Item: **{drop_name}**\nTime: **{drop_time}s**\nParticipants: **{len(self.bot.drops['participants'])}**\nTime Left: **{await get_time_left(end_time)}**"
            await message.edit(embed=updated_embed)

        if "participants" in self.bot.drops and self.bot.drops["participants"]:
            winner = random.choice(self.bot.drops["participants"])
            winner_embed = discord.Embed(
                description=
                f"Time's up! The winner of the **{drop_name}** is <@{winner}>!",
                color=embed_colour)
            reroll_button = Button(label="Reroll",
                                   style=discord.ButtonStyle.secondary,
                                   emoji="🔄")

            async def reroll_drop(interaction: discord.Interaction) -> None:
                if self.bot.drops["participants"]:
                    new_winner = random.choice(self.bot.drops["participants"])
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            description=f"The new winner is <@{new_winner}>!",
                            color=embed_colour),
                        ephemeral=False)
                else:
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            description="There are no participants to reroll.",
                            color=embed_colour),
                        ephemeral=True)

            reroll_button.callback = reroll_drop
            reroll_view = View()
            reroll_view.add_item(reroll_button)

            await self.ctx.send(embed=winner_embed, view=reroll_view)
            del self.bot.drops["participants"]
            # Disable all buttons after the drop ends
            for item in view.children:
                item.disabled = True
            await message.edit(embed=drop_embed, view=view)
        else:
            await self.ctx.send(embed=discord.Embed(
                description="No participants entered the drop.",
                color=embed_colour))


class ConfigureModal(Modal):

    def __init__(self, bot: commands.Bot, ctx: commands.Context) -> None:
        super().__init__(title="Configure Giveaway Manager")
        self.bot = bot
        self.ctx = ctx
        self.add_item(
            TextInput(label="Role ID",
                      placeholder="Enter the role ID for Giveaway Manager"))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        role_id: int = int(self.children[0].value)
        guild = self.ctx.guild
        role = guild.get_role(role_id)

        if role:
            self.bot.giveaway_manager_role = role_id
            await interaction.response.send_message(embed=discord.Embed(
                description=f"Giveaway Manager role set to {role.mention}",
                color=embed_colour),
                                                    ephemeral=True)
        else:
            await interaction.response.send_message(embed=discord.Embed(
                description="Invalid role ID.", color=embed_colour),
                                                    ephemeral=True)


class Giveaway(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.bot.giveaways = {}
        self.bot.drops = {}
        self.bot.giveaway_manager_role = None

    @commands.hybrid_command(name="setup_giveaway",
                             description="Set up a giveaway")
    @commands.has_permissions(manage_messages=True)
    async def setup_giveaway(
            self,
            ctx: commands.Context,
            giveaway_channel: discord.TextChannel = None) -> None:
        await ctx.defer(ephemeral=True)

        configure_button = Button(label="Configure",
                                  style=discord.ButtonStyle.gray,
                                  emoji="⚙️")
        setup_button = Button(label="Setup",
                              style=discord.ButtonStyle.green,
                              emoji="🎉")
        drop_button = Button(label="Drop",
                             style=discord.ButtonStyle.blurple,
                             emoji="🎁")

        view = View()
        view.add_item(configure_button)
        view.add_item(setup_button)
        view.add_item(drop_button)

        async def configure(interaction: discord.Interaction) -> None:
            if interaction.user.guild_permissions.administrator:
                modal = ConfigureModal(self.bot, ctx)
                await interaction.response.send_modal(modal)
            else:
                await interaction.response.send_message(embed=discord.Embed(
                    description=
                    "You do not have permission to configure the giveaway manager role.",
                    color=embed_colour),
                                                        ephemeral=True)

        async def setup(interaction: discord.Interaction) -> None:
            if self.bot.giveaway_manager_role is None or self.bot.giveaway_manager_role in [
                    role.id for role in interaction.user.roles
            ]:
                modal = GiveawaySetupModal(self.bot, ctx, giveaway_channel)
                await interaction.response.send_modal(modal)
            else:
                await interaction.response.send_message(embed=discord.Embed(
                    description="You do not have the Giveaway Manager role.",
                    color=embed_colour),
                                                        ephemeral=True)

        async def drop(interaction: discord.Interaction) -> None:
            if self.bot.giveaway_manager_role is None or self.bot.giveaway_manager_role in [
                    role.id for role in interaction.user.roles
            ]:
                modal = DropSetupModal(self.bot, ctx, giveaway_channel)
                await interaction.response.send_modal(modal)
            else:
                await interaction.response.send_message(embed=discord.Embed(
                    description="You do not have the Giveaway Manager role.",
                    color=embed_colour),
                                                        ephemeral=True)

        configure_button.callback = configure
        setup_button.callback = setup
        drop_button.callback = drop

        embed = discord.Embed(
            title="Giveaway Setup",
            description=
            "Choose an option below to configure or set up a giveaway or drop.",
            color=embed_colour)
        await ctx.interaction.followup.send(embed=embed, view=view)


async def get_time_left(end_time: datetime.datetime) -> str:
    now = datetime.datetime.utcnow()
    remaining_time = end_time - now
    days, seconds = remaining_time.days, remaining_time.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Giveaway(bot))

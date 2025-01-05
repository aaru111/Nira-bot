import discord
import datetime
from discord.ext import commands

# Customizable constants remain the same
MAIN_COLOR = discord.Color.blurple()
EMOJIS = {
    'tick_no': '❌',
    'cmd_arrow': '▶️'
}
WEBSITE_LINK = "https://your-bot-website.com"
SUPPORT_SERVER_LINK = "https://discord.gg/your-server"
EMPTY_CHARACTER = "⠀"

EMOJIS_FOR_COGS = {
    'admin': '⚙️',
    'moderation': '🛡️',
    'fun': '🎮',
    'utility': '🛠️',
    'music': '🎵',
    'economy': '💰',
    'leveling': '📈',
    'nsfw': '🔞',
}

class HelpSelect(discord.ui.Select):
    def __init__(self, ctx: commands.Context, options: list[discord.SelectOption]):
        super().__init__(placeholder="Please select a category.", options=options)
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This menu is not for you!", ephemeral=True)

        self.view.children[0].disabled = False
        cog = self.ctx.bot.get_cog(self.values[0])
        if not cog:
            return await interaction.response.send_message("This category no longer exists!", ephemeral=True)

        embed = await HelpCog.make_cog_help(self.ctx, cog)
        await interaction.response.edit_message(embed=embed, view=self.view)

class HelpMenu(discord.ui.View):
    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=300)
        self.ctx = ctx

    @discord.ui.button(label="Home", emoji="🏠", style=discord.ButtonStyle.blurple, disabled=True)
    async def home(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This menu is not for you!", ephemeral=True)

        for item in self.children:
            item.disabled = False
        button.disabled = True
        embed = await HelpCog.make_bot_help(self.ctx)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="All Commands", emoji="📜", style=discord.ButtonStyle.blurple)
    async def commands_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This menu is not for you!", ephemeral=True)

        for item in self.children:
            item.disabled = False
        button.disabled = True
        embed = await HelpCog.make_commands_list(self.ctx)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Close", emoji="✖️", style=discord.ButtonStyle.danger)
    async def close_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This menu is not for you!", ephemeral=True)
        await interaction.message.delete()

class HelpCog(commands.Cog):
    """Help command implementation"""

    def __init__(self, bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = None

    def cog_unload(self):
        self.bot.help_command = self._original_help_command

    @staticmethod
    def make_error_embed(title: str, description: str) -> discord.Embed:
        return discord.Embed(title=title, description=description, color=discord.Color.red())

    @staticmethod
    async def make_cog_help(ctx: commands.Context, cog: commands.Cog) -> discord.Embed:
        """Generates help embed for a specific cog."""
        if cog.qualified_name.lower() == "nsfw" and not ctx.channel.is_nsfw():
            return HelpCog.make_error_embed(
                f"{EMOJIS['tick_no']} Not Allowed!",
                "Please go to a **NSFW** channel to see these commands."
            )

        # Include all commands, including hidden ones if the user has manage_messages permission
        if ctx.author.guild_permissions.manage_messages:
            commands_list = cog.get_commands()
        else:
            commands_list = [cmd for cmd in cog.get_commands() if not cmd.hidden]

        if not commands_list:
            return HelpCog.make_error_embed(
                f"{EMOJIS['tick_no']} Empty Category",
                "This category has no available commands."
            )

        embed = discord.Embed(
            title=f"{cog.qualified_name.title()} Commands",
            description=f"{cog.description}\n\n**Commands:**\n" + "\n".join(
                f"{EMOJIS['cmd_arrow']} `{cmd.name}` • {cmd.help or 'No description available'}" 
                for cmd in sorted(commands_list, key=lambda x: x.name)
            ),
            color=MAIN_COLOR
        )
        embed.set_thumbnail(url=ctx.bot.user.display_avatar.url)
        return embed

    @staticmethod
    async def make_bot_help(ctx: commands.Context) -> discord.Embed:
        """Generates the main help embed with all categories."""
        embed = discord.Embed(
            title=f"{ctx.bot.user.name} Help",
            description="Here are all my command categories:",
            color=MAIN_COLOR,
            timestamp=datetime.datetime.utcnow()
        )

        # Sort cogs alphabetically and process them
        sorted_cogs = sorted(ctx.bot.cogs.values(), key=lambda x: x.qualified_name)

        for cog in sorted_cogs:
            # Skip NSFW cog in non-NSFW channels
            if cog.qualified_name.lower() == "nsfw" and not ctx.channel.is_nsfw():
                continue

            # Include hidden commands for users with manage_messages permission
            if ctx.author.guild_permissions.manage_messages:
                commands_list = list(cog.get_commands())
            else:
                commands_list = [cmd for cmd in cog.get_commands() if not cmd.hidden]

            # Show cog even if it has no commands
            emoji = EMOJIS_FOR_COGS.get(cog.qualified_name.lower(), '📁')
            embed.add_field(
                name=f"{emoji} {cog.qualified_name}",
                value=f"{cog.description or 'No description'}\nCommands: `{len(commands_list)}`",
                inline=False
            )

        embed.set_footer(text=f"Use {ctx.clean_prefix}help <command/category> for more info")
        embed.set_thumbnail(url=ctx.bot.user.display_avatar.url)
        return embed

    @staticmethod
    async def make_commands_list(ctx: commands.Context) -> discord.Embed:
        """Generates an embed with all commands listed by category."""
        embed = discord.Embed(
            title="All Commands",
            description=f"Use `{ctx.clean_prefix}help <command>` for more details",
            color=MAIN_COLOR,
            timestamp=datetime.datetime.utcnow()
        )

        # Sort cogs alphabetically
        sorted_cogs = sorted(ctx.bot.cogs.values(), key=lambda x: x.qualified_name)

        for cog in sorted_cogs:
            if cog.qualified_name.lower() == "nsfw" and not ctx.channel.is_nsfw():
                continue

            # Include hidden commands for users with manage_messages permission
            if ctx.author.guild_permissions.manage_messages:
                commands_list = list(cog.get_commands())
            else:
                commands_list = [cmd for cmd in cog.get_commands() if not cmd.hidden]

            if commands_list:
                emoji = EMOJIS_FOR_COGS.get(cog.qualified_name.lower(), '📁')
                embed.add_field(
                    name=f"{emoji} {cog.qualified_name}",
                    value=", ".join(f"`{cmd.name}`" for cmd in sorted(commands_list, key=lambda x: x.name)),
                    inline=False
                )

        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        return embed

    @commands.hybrid_command(name="help", description="Shows the help menu")
    async def help_command(self, ctx: commands.Context, *, query: str = None):
        """Shows help about the bot, a command, or a category"""

        if query is None:
            # Show main help menu
            embed = await self.make_bot_help(ctx)
            view = HelpMenu(ctx)

            # Add category select menu
            # Include all cogs except NSFW in non-NSFW channels
            valid_cogs = [
                cog for cog in sorted(self.bot.cogs.values(), key=lambda x: x.qualified_name)
                if not (cog.qualified_name.lower() == "nsfw" and not ctx.channel.is_nsfw())
            ]

            if valid_cogs:
                select = HelpSelect(
                    ctx,
                    [discord.SelectOption(
                        label=cog.qualified_name,
                        emoji=EMOJIS_FOR_COGS.get(cog.qualified_name.lower(), '📁'),
                        value=cog.qualified_name,
                        description=(cog.description or "No description")[:100]
                    ) for cog in valid_cogs]
                )
                view.add_item(select)

            await ctx.send(embed=embed, view=view)
            return

        # Check if it's a command
        if command := self.bot.get_command(query.lower()):
            embed = await self.make_command_help(ctx, command)
            await ctx.send(embed=embed)
            return

        # Check if it's a cog
        if cog := self.bot.get_cog(query.title()):
            embed = await self.make_cog_help(ctx, cog)
            await ctx.send(embed=embed)
            return

        # Neither command nor cog found
        embed = self.make_error_embed(
            f"{EMOJIS['tick_no']} Not Found",
            f"No command or category called `{query}` found."
        )
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
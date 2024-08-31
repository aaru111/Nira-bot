import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Optional, Union, Any, Dict
import inspect
import math
import asyncio

# Global variables for easy modification
DEFAULT_EMBED_COLOR = discord.Color.brand_red()
DEFAULT_EMBED_TITLE = "<:nira_ai2:1267876148201914560> N.I.R.A™ HelpDesk"
DEFAULT_EMBED_FOOTER = "Type {prefix}help <command> for more info on a command."
DEFAULT_OWNER_ONLY_MESSAGE = "This command does not exist or you don't have permission to view its details."
DEFAULT_NO_CATEGORY_NAME = "No Category"
COMMANDS_PER_PAGE = 6
VIEW_TIMEOUT = 40

CommandType = Union[commands.Command[Any, Any, Any], app_commands.Command]
ContextType = Union[commands.Context, discord.Interaction]


class HelpView(discord.ui.View):

    def __init__(self, cog: 'HelpCog', ctx: ContextType,
                 categories: Dict[str, List[CommandType]]):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.cog = cog
        self.ctx = ctx
        self.categories = categories
        self.current_category = None
        self.current_page = 0
        self.last_interaction_time = asyncio.get_event_loop().time()

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

    async def interaction_check(self,
                                interaction: discord.Interaction) -> bool:
        if interaction.user != self.get_user():
            await interaction.response.send_message(
                "This menu is not for you.", ephemeral=True)
            return False
        self.last_interaction_time = asyncio.get_event_loop().time()
        return True

    @discord.ui.select(placeholder="Select a category",
                       min_values=1,
                       max_values=1)
    async def category_select(self, interaction: discord.Interaction,
                              select: discord.ui.Select):
        self.current_category = select.values[0]
        self.current_page = 0
        await self.update_message(interaction)

    @discord.ui.button(label="Previous",
                       style=discord.ButtonStyle.primary,
                       disabled=True)
    async def previous_button(self, interaction: discord.Interaction,
                              button: discord.ui.Button):
        self.current_page = max(0, self.current_page - 1)
        await self.update_message(interaction)

    @discord.ui.button(label="Next",
                       style=discord.ButtonStyle.primary,
                       disabled=True)
    async def next_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        if self.current_category:
            max_pages = math.ceil(
                len(self.categories[self.current_category]) /
                COMMANDS_PER_PAGE)
            self.current_page = min(max_pages - 1, self.current_page + 1)
        await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        if self.current_category == "Home" or not self.current_category:
            embed = self.create_home_embed()
            self.previous_button.disabled = True
            self.next_button.disabled = True
        else:
            embed = self.create_category_embed(self.current_category)
            self.update_button_states()

        await interaction.response.edit_message(embed=embed, view=self)
        self.message = await interaction.original_response()

    def update_button_states(self):
        if self.current_category and self.current_category != "Home":
            max_pages = math.ceil(
                len(self.categories[self.current_category]) /
                COMMANDS_PER_PAGE)
            self.previous_button.disabled = self.current_page == 0
            self.next_button.disabled = self.current_page >= max_pages - 1
        else:
            self.previous_button.disabled = True
            self.next_button.disabled = True

    def create_home_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"**{self.cog.embed_title}**",
            description=
            "Welcome to the help menu! Select a category from the dropdown to view commands.",
            color=self.cog.embed_color)
        for category in self.categories.keys():
            if category != "Home":
                embed.add_field(
                    name=f"**{category}**",
                    value=f"`{len(self.categories[category])}` commands",
                    inline=True)
        embed.set_footer(text=self.cog.embed_footer.format(
            prefix=self.get_prefix()))
        return embed

    def create_category_embed(self, category: str) -> discord.Embed:
        commands = self.categories[category]
        start_idx = self.current_page * COMMANDS_PER_PAGE
        end_idx = start_idx + COMMANDS_PER_PAGE
        page_commands = commands[start_idx:end_idx]

        embed = discord.Embed(title=f"**{category} Commands**",
                              color=self.cog.embed_color)

        for command in page_commands:
            cmd_name = self.get_command_name(command)
            embed.add_field(name=f"**`{cmd_name}`**",
                            value=command.description
                            or "No description available.",
                            inline=False)

        total_pages = math.ceil(len(commands) / COMMANDS_PER_PAGE)
        embed.set_footer(
            text=
            f"Page {self.current_page + 1}/{total_pages} • {self.cog.embed_footer.format(prefix=self.get_prefix())}"
        )
        return embed

    def get_prefix(self) -> str:
        if isinstance(self.ctx, commands.Context):
            return self.ctx.prefix or '/'
        return '/'

    def get_command_name(self, command: CommandType) -> str:
        if isinstance(command, app_commands.Command) or (isinstance(
                command, commands.Command) and command.parent is None):
            return f"/{command.name}"
        return f"{self.get_prefix()}{command.name}"

    def get_user(self) -> Union[discord.User, discord.Member]:
        return self.ctx.author if isinstance(
            self.ctx, commands.Context) else self.ctx.user


class HelpCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self._original_help_command: Optional[
            commands.HelpCommand] = bot.help_command
        bot.help_command = None

        # Instance variables that can be overridden
        self.embed_color: discord.Color = DEFAULT_EMBED_COLOR
        self.embed_title: str = DEFAULT_EMBED_TITLE
        self.embed_footer: str = DEFAULT_EMBED_FOOTER
        self.owner_only_message: str = DEFAULT_OWNER_ONLY_MESSAGE
        self.no_category_name: str = DEFAULT_NO_CATEGORY_NAME

    def cog_unload(self) -> None:
        self.bot.help_command = self._original_help_command

    @staticmethod
    def generate_usage(command: Union[commands.Command[Any, Any, Any],
                                      app_commands.Command],
                       flag_converter: Optional[type[
                           commands.FlagConverter]] = None,
                       prefix: str = '/') -> str:
        command_name = command.qualified_name

        # Add appropriate prefix based on command type
        if isinstance(command, commands.Command):
            if command.parent is None:  # Top-level command
                if isinstance(command, commands.HybridCommand):
                    usage = f"[/{command_name} | {prefix}{command_name}]"
                else:
                    usage = f"{prefix}{command_name}"
            else:  # Subcommand
                usage = f"{prefix}{command_name}"
        else:  # Application command
            usage = f"/{command_name}"

        if isinstance(command, commands.Command):
            try:
                parameters = inspect.signature(command.callback).parameters
            except ValueError:
                parameters = {}
        else:
            parameters = getattr(command, '_params', {})

        if flag_converter:
            flag_prefix = getattr(flag_converter, "__commands_flag_prefix__",
                                  "-")
            flags: dict[str, commands.Flag] = flag_converter.get_flags()
        else:
            flags = {}

        for param_name, param in parameters.items():
            if param_name in ["self", "ctx", "interaction", "flags"]:
                continue
            is_required = param.default == inspect.Parameter.empty
            usage += f" <{param_name}>" if is_required else f" [{param_name}]"

        for flag_name, flag_obj in flags.items():
            if flag_obj.required:
                usage += f" {flag_prefix}<{flag_name}>"
            else:
                usage += f" {flag_prefix}[{flag_name}]"

        return usage

    def is_owner_only(self, command: CommandType) -> bool:
        return command.checks and any(
            check.__qualname__.startswith('is_owner')
            for check in command.checks)

    def is_jishaku_command(self, command: CommandType) -> bool:
        if isinstance(command, commands.Command):
            return command.cog and command.cog.qualified_name.lower(
            ) == "jishaku"
        elif isinstance(command, app_commands.Command):
            return command.module and "jishaku" in command.module.lower()
        return False

    async def is_owner(self, user: Union[discord.User,
                                         discord.Member]) -> bool:
        return await self.bot.is_owner(user)

    @commands.hybrid_command(name="help",
                             description="Shows help for bot commands")
    @app_commands.describe(command="The command to get help for")
    async def help_command(self,
                           ctx: commands.Context,
                           command: Optional[str] = None) -> None:
        prefix = await self.bot.get_prefix(ctx.message)
        prefix = prefix[0] if isinstance(prefix, list) else prefix
        if command:
            await self.send_command_help(ctx, command.lstrip('/'), prefix)
        else:
            await self.send_interactive_help(ctx, prefix)

    @help_command.autocomplete("command")
    async def command_autocomplete(
            self, interaction: discord.Interaction,
            current: str) -> List[app_commands.Choice[str]]:
        choices: List[app_commands.Choice[str]] = []
        is_owner = await self.is_owner(interaction.user)
        seen_commands = set()

        for cmd in self.bot.walk_commands():
            if current.lower() in cmd.qualified_name.lower() and (
                    not self.is_owner_only(cmd) or is_owner):
                if cmd.qualified_name not in seen_commands:
                    choices.append(
                        app_commands.Choice(name=f"/{cmd.qualified_name}",
                                            value=cmd.qualified_name))
                    seen_commands.add(cmd.qualified_name)

        for cmd in self.bot.tree.walk_commands():
            if current.lower() in cmd.qualified_name.lower() and (
                    not self.is_owner_only(cmd) or is_owner):
                if cmd.qualified_name not in seen_commands:
                    choices.append(
                        app_commands.Choice(name=f"/{cmd.qualified_name}",
                                            value=cmd.qualified_name))
                    seen_commands.add(cmd.qualified_name)

        return sorted(choices, key=lambda c: c.name)[:25]

    async def send_command_help(self, ctx: ContextType, command_name: str,
                                prefix: str) -> None:
        embed = discord.Embed(title=self.embed_title, color=self.embed_color)
        is_owner = await self.is_owner(
            ctx.author if isinstance(ctx, commands.Context) else ctx.user)

        command = self.bot.get_command(
            command_name) or self.bot.tree.get_command(command_name)
        if command:
            if (self.is_owner_only(command)
                    or self.is_jishaku_command(command)) and not is_owner:
                await self.send_owner_only_message(ctx)
                return
            embed.title = f"**Help for /{command.qualified_name}**"
            embed.description = f"> {command.description or 'No description available.'}"
            flag_converter = getattr(command, 'flags', None)
            usage = self.generate_usage(command, flag_converter, prefix)
            embed.add_field(name="**Usage**",
                            value=f"```\n{usage}\n```",
                            inline=False)
            if isinstance(command, commands.Command) and command.aliases:
                embed.add_field(name="**Aliases**",
                                value=", ".join(f"`{prefix}{alias}`"
                                                for alias in command.aliases),
                                inline=False)
        else:
            embed.description = self.owner_only_message

        embed.set_footer(text=self.embed_footer.format(prefix=prefix))

        if isinstance(ctx, commands.Context):
            await ctx.send(embed=embed, ephemeral=True)
        else:
            await ctx.response.send_message(embed=embed, ephemeral=True)

    async def send_interactive_help(self, ctx: ContextType,
                                    prefix: str) -> None:
        is_owner = await self.is_owner(
            ctx.author if isinstance(ctx, commands.Context) else ctx.user)
        cog_commands: Dict[str, List[CommandType]] = {"Home": []}
        seen_commands = set()

        # Process application commands first
        for command in sorted(self.bot.tree.walk_commands(),
                              key=lambda c: c.name):
            if isinstance(command, app_commands.Command) and (
                    not self.is_owner_only(command) or is_owner):
                cog_name = command.binding.__class__.__name__ if command.binding else self.no_category_name
                if cog_name not in cog_commands:
                    cog_commands[cog_name] = []
                cog_commands[cog_name].append(command)
                seen_commands.add(command.qualified_name)

        # Then process bot commands, skipping those already seen
        for command in sorted(self.bot.commands, key=lambda c: c.name):
            if command.qualified_name not in seen_commands and (
                    not self.is_owner_only(command) or is_owner):
                cog_name = command.cog.qualified_name if command.cog else self.no_category_name
                if cog_name not in cog_commands:
                    cog_commands[cog_name] = []
                cog_commands[cog_name].append(command)

        view = HelpView(self, ctx, cog_commands)
        view.category_select.options = [
            discord.SelectOption(label="Home",
                                 description="Return to the main help menu",
                                 emoji="🏠")
        ] + [
            discord.SelectOption(label=category,
                                 description=f"{len(commands)} commands")
            for category, commands in cog_commands.items()
            if category != "Home"
        ]

        initial_embed = view.create_home_embed()

        if isinstance(ctx, commands.Context):
            message = await ctx.send(embed=initial_embed, view=view)
        else:
            await ctx.response.send_message(embed=initial_embed, view=view)
            message = await ctx.original_response()

        view.message = message

        # Start a background task to check for timeout
        self.bot.loop.create_task(self.check_view_timeout(view))

    async def check_view_timeout(self, view: HelpView):
        while not view.is_finished():
            await asyncio.sleep(1)
            if asyncio.get_event_loop().time(
            ) - view.last_interaction_time > VIEW_TIMEOUT:
                for item in view.children:
                    item.disabled = True
                await view.message.edit(view=view)
                view.stop()
                break

    async def send_owner_only_message(self, ctx: ContextType) -> None:
        embed = discord.Embed(title=self.embed_title,
                              description=self.owner_only_message,
                              color=self.embed_color)
        embed.set_footer(text=self.embed_footer.format(
            prefix=ctx.prefix if isinstance(ctx, commands.Context) else '/'))

        if isinstance(ctx, commands.Context):
            await ctx.send(embed=embed, ephemeral=True)
        else:
            await ctx.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))

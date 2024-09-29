import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Optional, Union, Any, Dict, TypeVar
import inspect
import math
import asyncio
from utils.mentionable_tree import MentionableTree
import aiohttp

# Global variables for easy modification
DEFAULT_EMBED_COLOR: discord.Color = discord.Color.brand_red()
DEFAULT_EMBED_TITLE: str = "<:nira_ai2:1267876148201914560> N.I.R.A™ HelpDesk"
DEFAULT_EMBED_FOOTER: str = "Type {prefix}help <command> for more info on a command."
DEFAULT_OWNER_ONLY_MESSAGE: str = "This command does not exist or you don't have permission to view its details."
DEFAULT_NO_CATEGORY_NAME: str = "No Category"
COMMANDS_PER_PAGE: int = 6
VIEW_TIMEOUT: int = 40

arrow_emoji: str = "<a:arrow:1289933782291447818>"

# Category emojis
CATEGORY_EMOJIS: Dict[str, str] = {
    "Home": "<a:home:1289933914898436127>",
    "Moderation": "<a:Moderator:1289933964429103134>",
    "Fun": "<a:fun:1289933886079373344>",
    "Utilities": "<a:utility:1289934048445071390>",
    "Jishaku": "<a:coding:1289933802612981760>",
    "Sync": "<a:loading:1289933948880814150>",
    "Games": "<a:controller:1289933810787549348>",
    "NSFW": "🔞",
    "Leveling": "<a:up_level_up:1289934037292679248>",
    "MangaReaderCog": "<a:Book:1289933794908045412>",
    "Imagery": "<a:Images_Icon:1289933928261484635>",
    "Premium": "<a:premium:1289933987850227803>",
    "PrefixCog": "<a:prefix:1289933972922568756>",
    "AutoMod": "<a:Moderator:1289933964429103134>",
    "ReactionRole": "<a:SelfRoles:1289934024776618115>",
    "WelcomeCmds": "<a:welcome_pepe:1289934059170172928>",
    "EmbedCreator": "<:embed:1289933863363018752>",
    "AniListCog": "<a:anime:1289933771470143562>",
    "No Category": "<a:question_mark:1289934011246055424>"
}

CommandType = Union[commands.Command[Any, Any, Any], app_commands.Command]
ContextType = Union[commands.Context[Any], discord.Interaction]
BotT = TypeVar('BotT', bound=commands.Bot)


class HelpView(discord.ui.View):

    def __init__(self, cog: 'HelpCog', ctx: ContextType,
                 categories: Dict[str, List[CommandType]]) -> None:
        super().__init__(timeout=VIEW_TIMEOUT)
        self.cog: HelpCog = cog
        self.ctx: ContextType = ctx
        self.categories: Dict[str, List[CommandType]] = categories
        self.current_category: Optional[str] = None
        self.current_page: int = 0
        self.last_interaction_time: float = asyncio.get_event_loop().time()
        self.message: Optional[discord.Message] = None

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
            except discord.HTTPException:
                pass

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
                              select: discord.ui.Select) -> None:
        self.current_category = select.values[0]
        self.current_page = 0
        await self.update_message(interaction)

    @discord.ui.button(label="Previous",
                       style=discord.ButtonStyle.primary,
                       disabled=True)
    async def previous_button(self, interaction: discord.Interaction,
                              button: discord.ui.Button) -> None:
        self.current_page = max(0, self.current_page - 1)
        await self.update_message(interaction)

    @discord.ui.button(label="Next",
                       style=discord.ButtonStyle.primary,
                       disabled=True)
    async def next_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button) -> None:
        if self.current_category:
            max_pages = math.ceil(
                len(self.categories[self.current_category]) /
                COMMANDS_PER_PAGE)
            self.current_page = min(max_pages - 1, self.current_page + 1)
        await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction) -> None:
        if self.current_category == "Home" or not self.current_category:
            embed = self.create_home_embed()
            self.previous_button.disabled = True
            self.next_button.disabled = True
        else:
            embed = await self.create_category_embed(self.current_category)
            self.update_button_states()

        await interaction.response.edit_message(embed=embed, view=self)
        self.message = await interaction.original_response()

    def update_button_states(self) -> None:
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
        for category, commands_list in self.categories.items():
            if category not in ["Home", "HelpCog"]:
                emoji = CATEGORY_EMOJIS.get(category, "❓")
                embed.add_field(name=f"**{emoji} {category}**",
                                value=f"-# ╰>`{len(commands_list)}` commands",
                                inline=True)
        embed.set_footer(text=self.cog.embed_footer.format(
            prefix=self.get_prefix()))
        return embed

    async def create_category_embed(self, category: str) -> discord.Embed:
        commands = self.categories[category]
        start_idx = self.current_page * COMMANDS_PER_PAGE
        end_idx = start_idx + COMMANDS_PER_PAGE
        page_commands = commands[start_idx:end_idx]

        emoji = CATEGORY_EMOJIS.get(category, "❓")
        embed = discord.Embed(title=f"**{emoji} {category} Commands**",
                              color=self.cog.embed_color)

        for command in page_commands:
            mention = await self.cog.bot.tree.find_mention_for(
                command) if isinstance(self.cog.bot.tree,
                                       MentionableTree) else None
            embed.add_field(
                name=
                f"{arrow_emoji}{mention or self.get_command_name(command)}",
                value=
                f"-# ╰> {command.description or 'No description available.'}",
                inline=False)

        total_pages = math.ceil(len(commands) / COMMANDS_PER_PAGE)
        embed.set_footer(
            text=
            f"Page {self.current_page + 1}/{total_pages} • {self.cog.embed_footer.format(prefix=self.get_prefix())}"
        )
        return embed

    def get_prefix(self) -> str:
        if isinstance(self.ctx, commands.Context):
            return self.ctx.prefix or '.'
        return '/'

    def get_command_name(self, command: CommandType) -> str:
        if isinstance(command, app_commands.Command) or (isinstance(
                command, commands.Command) and command.parent is None):
            if isinstance(command, app_commands.Command):
                return f"/{command.name}"
            else:
                return f"{self.get_prefix()}{command.name}"
        return f"{self.get_prefix()}{command.name}"

    def get_user(self) -> Union[discord.User, discord.Member]:
        return self.ctx.author if isinstance(
            self.ctx, commands.Context) else self.ctx.user


class HelpCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
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
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        self.bot.help_command = self._original_help_command
        await self.session.close()

    @staticmethod
    def generate_usage(command: CommandType,
                       flag_converter: Optional[type[
                           commands.FlagConverter]] = None,
                       prefix: str = '.') -> str:
        command_name = command.qualified_name

        if isinstance(command, commands.Command):
            if command.parent is None:
                if isinstance(command, commands.HybridCommand):
                    usage = f"[/{command_name} | {prefix}{command_name}]"
                else:
                    usage = f"{prefix}{command_name}"
            else:
                usage = f"{prefix}{command_name}"
        else:
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
            flags: Dict[str, commands.Flag] = flag_converter.get_flags()
        else:
            flag_prefix = "-"
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
        if isinstance(command.checks, list):
            return any(
                check.__qualname__.startswith('is_owner')
                for check in command.checks)
        return bool(command.checks)

    def is_jishaku_command(self, command: CommandType) -> bool:
        if isinstance(command, commands.Command):
            return command.cog and command.cog.qualified_name.lower(
            ) == "jishaku"
        elif isinstance(command, app_commands.Command):
            return command.module is not None and "jishaku" in command.module.lower(
            )
        return False

    async def is_owner(self, user: Union[discord.User,
                                         discord.Member]) -> bool:
        return await self.bot.is_owner(user)

    @commands.hybrid_command(name="help",
                             description="Shows help for bot commands")
    @app_commands.describe(command="The command to get help for")
    async def help_command(self,
                           ctx: commands.Context[BotT],
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
            if isinstance(cmd, (commands.Command, app_commands.Command)) and \
               current.lower() in cmd.qualified_name.lower() and \
               (not self.is_owner_only(cmd) or is_owner) and \
               (not self.is_jishaku_command(cmd) or is_owner) and \
               cmd.cog and cmd.cog.qualified_name != "HelpCog":
                if cmd.qualified_name not in seen_commands:
                    choices.append(
                        app_commands.Choice(name=f"{cmd.qualified_name}",
                                            value=cmd.qualified_name))
                    seen_commands.add(cmd.qualified_name)

        for cmd in self.bot.tree.walk_commands():
            if isinstance(cmd, (commands.Command, app_commands.Command)) and \
               current.lower() in cmd.qualified_name.lower() and \
               (not self.is_owner_only(cmd) or is_owner) and \
               (not self.is_jishaku_command(cmd) or is_owner) and \
               cmd.binding and cmd.binding.__class__.__name__ != "HelpCog":
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
        if isinstance(command, (commands.Command, app_commands.Command)):
            if (self.is_owner_only(command)
                    or self.is_jishaku_command(command)) and not is_owner:
                await self.send_owner_only_message(ctx)
                return
            embed.title = f"**Help for {'/' if isinstance(command, app_commands.Command) else prefix}{command.qualified_name}**"

            mention = await self.bot.tree.find_mention_for(
                command
            ) if isinstance(
                self.bot.tree, MentionableTree
            ) else f"{'/' if isinstance(command, app_commands.Command) else prefix}{command.qualified_name}"

            # Add the command description here
            description = command.description or command.help or 'No description available.'
            embed.description = f"{arrow_emoji}{mention}\n-# ╰> {description}"

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

        for command in sorted(self.bot.tree.walk_commands(),
                              key=lambda c: c.name):
            if isinstance(command, app_commands.Command) and \
               (not self.is_owner_only(command) or is_owner) and \
               (not self.is_jishaku_command(command) or is_owner) and \
               command.binding and command.binding.__class__.__name__ != "HelpCog":
                cog_name = command.binding.__class__.__name__ if command.binding else self.no_category_name
                if cog_name not in cog_commands:
                    cog_commands[cog_name] = []
                cog_commands[cog_name].append(command)
                seen_commands.add(command.qualified_name)

        for command in sorted(self.bot.commands, key=lambda c: c.name):
            if command.qualified_name not in seen_commands and \
               (not self.is_owner_only(command) or is_owner) and \
               (not self.is_jishaku_command(command) or is_owner) and \
               command.cog and command.cog.qualified_name != "HelpCog":
                cog_name = command.cog.qualified_name if command.cog else self.no_category_name
                if cog_name not in cog_commands:
                    cog_commands[cog_name] = []
                cog_commands[cog_name].append(command)

        view = HelpView(self, ctx, cog_commands)
        view.category_select.options = [
            discord.SelectOption(label="Home",
                                 description="Return to the main help menu",
                                 emoji=CATEGORY_EMOJIS["Home"])
        ] + [
            discord.SelectOption(label=category,
                                 description=f"{len(commands)} commands",
                                 emoji=CATEGORY_EMOJIS.get(category, "❓"))
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

    async def check_view_timeout(self, view: HelpView) -> None:
        while not view.is_finished():
            await asyncio.sleep(1)
            if asyncio.get_event_loop().time(
            ) - view.last_interaction_time > VIEW_TIMEOUT:
                for item in view.children:
                    if isinstance(item,
                                  (discord.ui.Button, discord.ui.Select)):
                        item.disabled = True
                if view.message:
                    try:
                        await view.message.edit(view=view)
                    except discord.errors.NotFound:
                        pass
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

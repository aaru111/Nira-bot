import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Optional, Union, Any, Dict
import inspect

# Global variables for easy modification
DEFAULT_EMBED_COLOR = discord.Color.blue()
DEFAULT_EMBED_TITLE = "<:nira_ai2:1267876148201914560> N.I.R.A™ HelpDesk"
DEFAULT_EMBED_FOOTER = "Type {prefix}help <command> for more info on a command."
DEFAULT_OWNER_ONLY_MESSAGE = "This command does not exist or you don't have permission to view its details."
DEFAULT_NO_CATEGORY_NAME = "No Category"


class BaseHelpCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = None

        # Instance variables that can be overridden
        self.embed_color = DEFAULT_EMBED_COLOR
        self.embed_title = DEFAULT_EMBED_TITLE
        self.embed_footer = DEFAULT_EMBED_FOOTER
        self.owner_only_message = DEFAULT_OWNER_ONLY_MESSAGE
        self.no_category_name = DEFAULT_NO_CATEGORY_NAME

    def cog_unload(self) -> None:
        self.bot.help_command = self._original_help_command

    @staticmethod
    def generate_usage(
        command: Union[commands.Command[Any, Any, Any], app_commands.Command],
        flag_converter: Optional[type[commands.FlagConverter]] = None,
    ) -> str:
        command_name = command.qualified_name
        usage = f"{command_name}"

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

    def is_owner_only(
        self, command: Union[commands.Command[Any, Any, Any],
                             app_commands.Command]
    ) -> bool:
        if isinstance(command, commands.Command):
            return command.checks and any(
                check.__qualname__.startswith('is_owner')
                for check in command.checks)
        elif isinstance(command, app_commands.Command):
            return command.checks and any(
                check.__qualname__.startswith('is_owner')
                for check in command.checks)
        return False

    def is_jishaku_command(
        self, command: Union[commands.Command[Any, Any, Any],
                             app_commands.Command]
    ) -> bool:
        if isinstance(command, commands.Command):
            return command.cog and command.cog.qualified_name.lower(
            ) == "jishaku"
        elif isinstance(command, app_commands.Command):
            return command.module and "jishaku" in command.module.lower()
        return False

    async def is_owner(self, user: Union[discord.User,
                                         discord.Member]) -> bool:
        return await self.bot.is_owner(user)


class HelpCog(BaseHelpCog):

    @commands.hybrid_command(name="help",
                             description="Shows help for bot commands")
    @app_commands.describe(command="The command to get help for")
    async def help_command(self,
                           ctx: commands.Context,
                           command: Optional[str] = None) -> None:
        prefix = await self.bot.get_prefix(ctx.message)
        prefix = prefix[0] if isinstance(prefix, list) else prefix
        await self.send_help_embed(ctx, command, prefix)

    @help_command.autocomplete("command")
    async def command_autocomplete(
            self, interaction: discord.Interaction,
            current: str) -> List[app_commands.Choice[str]]:
        choices: List[app_commands.Choice[str]] = []
        is_owner = await self.is_owner(interaction.user)
        for cmd in self.bot.walk_commands():
            if current.lower() in cmd.qualified_name.lower() and (
                    not self.is_owner_only(cmd) or is_owner):
                choices.append(
                    app_commands.Choice(name=f"{cmd.qualified_name}",
                                        value=cmd.qualified_name))
        for cmd in self.bot.tree.walk_commands():
            if current.lower() in cmd.qualified_name.lower() and (
                    not self.is_owner_only(cmd) or is_owner):
                choices.append(
                    app_commands.Choice(name=f"{cmd.qualified_name}",
                                        value=cmd.qualified_name))
        return sorted(choices, key=lambda c: c.name)[:25]

    async def send_help_embed(self, ctx: Union[commands.Context,
                                               discord.Interaction],
                              command_name: Optional[str],
                              prefix: str) -> None:
        embed = discord.Embed(title=self.embed_title, color=self.embed_color)
        is_owner = await self.is_owner(
            ctx.author if isinstance(ctx, commands.Context) else ctx.user)

        if command_name:
            command = self.bot.get_command(
                command_name.lstrip('/')) or self.bot.tree.get_command(
                    command_name.lstrip('/'))
            if command:
                if (self.is_owner_only(command)
                        or self.is_jishaku_command(command)) and not is_owner:
                    await self.send_owner_only_message(ctx)
                    return
                embed.title = f"Help for /{command.qualified_name}"
                embed.description = command.description or "No description available."
                flag_converter = getattr(command, 'flags', None)
                usage = self.generate_usage(command, flag_converter)
                embed.add_field(name="Usage", value=f"`{usage}`", inline=False)
                if isinstance(command, commands.Command) and command.aliases:
                    embed.add_field(name="Aliases",
                                    value=", ".join(
                                        sorted(f"{prefix}{alias}"
                                               for alias in command.aliases)),
                                    inline=False)
            else:
                embed.description = self.owner_only_message
        else:
            embed.description = "Here are all available commands:"
            cog_commands: Dict[str, List[str]] = {}
            for command in sorted(self.bot.commands, key=lambda c: c.name):
                if (self.is_owner_only(command)
                        or self.is_jishaku_command(command)) and not is_owner:
                    continue
                cog_name = command.cog.qualified_name if command.cog else self.no_category_name
                if cog_name not in cog_commands:
                    cog_commands[cog_name] = []
                cmd_name = f"/{command.name}" if isinstance(
                    command,
                    commands.HybridCommand) else f"{prefix}{command.name}"
                cog_commands[cog_name].append(f"`{cmd_name}`")
            for command in sorted(self.bot.tree.walk_commands(),
                                  key=lambda c: c.name):
                if isinstance(command, app_commands.Command) and (
                        not self.is_owner_only(command) or is_owner):
                    cog_name = command.binding.__class__.__name__ if command.binding else self.no_category_name
                    if cog_name not in cog_commands:
                        cog_commands[cog_name] = []
                    cog_commands[cog_name].append(f"`/{command.name}`")

            for cog_name in sorted(cog_commands.keys()):
                commands_list = sorted(cog_commands[cog_name])
                embed.add_field(name=cog_name,
                                value=", ".join(commands_list),
                                inline=False)

        embed.set_footer(text=self.embed_footer.format(prefix=prefix))

        if isinstance(ctx, commands.Context):
            await ctx.send(embed=embed, ephemeral=True)
        else:
            await ctx.response.send_message(embed=embed, ephemeral=True)

    async def send_owner_only_message(
            self, ctx: Union[commands.Context, discord.Interaction]) -> None:
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

import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Optional, Union, Any, Dict
import inspect


class HelpCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = None

    def cog_unload(self) -> None:
        self.bot.help_command = self._original_help_command

    @staticmethod
    def generate_usage(
        command: Union[commands.Command[Any, Any, Any], app_commands.Command],
        prefix: str,
    ) -> str:
        if isinstance(command, app_commands.Command) or isinstance(
                command, commands.HybridCommand):
            return f"/{command.qualified_name} {' '.join([f'<{param.name}>' if param.required else f'[{param.name}]' for param in command.parameters])}"

        command_name = command.qualified_name
        usage = f"{prefix}{command_name}"
        parameters: Dict[str, commands.Parameter] = command.clean_params

        for param_name, param in parameters.items():
            if param_name in ["ctx", "self"]:
                continue
            is_optional = param.default != inspect.Parameter.empty
            usage += f" {'[' if is_optional else '<'}{param_name}{'>' if not is_optional else ']'}"

        if isinstance(command, commands.Group):
            usage += " <subcommand>"

        return usage

    @app_commands.command(name="help",
                          description="Shows help for bot commands")
    @app_commands.describe(command="The command to get help for")
    async def help_slash(self,
                         interaction: discord.Interaction,
                         command: Optional[str] = None) -> None:
        prefix = await self.bot.get_prefix(interaction)
        await self.send_help_embed(interaction, command, prefix)

    @help_slash.autocomplete("command")
    async def command_autocomplete(
            self, interaction: discord.Interaction,
            current: str) -> List[app_commands.Choice[str]]:
        choices: List[app_commands.Choice[str]] = []
        prefix = await self.bot.get_prefix(interaction)

        for cmd in self.bot.walk_commands():
            if current.lower() in cmd.qualified_name.lower():
                if isinstance(cmd, commands.HybridCommand):
                    choices.append(
                        app_commands.Choice(name=f"/{cmd.qualified_name}",
                                            value=f"/{cmd.qualified_name}"))
                else:
                    choices.append(
                        app_commands.Choice(
                            name=f"{prefix}{cmd.qualified_name}",
                            value=cmd.qualified_name))

        for cmd in self.bot.tree.walk_commands():
            if current.lower() in cmd.qualified_name.lower():
                choices.append(
                    app_commands.Choice(name=f"/{cmd.qualified_name}",
                                        value=f"/{cmd.qualified_name}"))

        return choices[:25]

    async def send_help_embed(self, interaction: discord.Interaction,
                              command_name: Optional[str],
                              prefix: str) -> None:
        embed = discord.Embed(title="Bot Help", color=discord.Color.blue())

        if command_name:
            command = self.bot.get_command(command_name.lstrip('/'))
            if not command:
                command = self.bot.tree.get_command(command_name.lstrip('/'))

            if command:
                is_hybrid = isinstance(command, commands.HybridCommand)
                embed.title = f"Help for {'/' if is_hybrid else prefix}{command.qualified_name}"
                embed.description = command.description or "No description available."

                usage = self.generate_usage(command, prefix)
                embed.add_field(name="Usage", value=f"`{usage}`", inline=False)

                if isinstance(command, commands.Command
                              ) and command.aliases and not is_hybrid:
                    embed.add_field(name="Aliases",
                                    value=", ".join(
                                        f"{prefix}{alias}"
                                        for alias in command.aliases),
                                    inline=False)
            else:
                embed.description = f"No command found named '{command_name}'."
        else:
            embed.description = "Here are all available commands:"

            cog_commands: Dict[str, List[str]] = {}

            for command in self.bot.commands:
                if command.cog:
                    if command.cog.qualified_name not in cog_commands:
                        cog_commands[command.cog.qualified_name] = []
                    if isinstance(command, commands.HybridCommand):
                        cog_commands[command.cog.qualified_name].append(
                            f"`/{command.name}`")
                    else:
                        cog_commands[command.cog.qualified_name].append(
                            f"`{prefix}{command.name}`")

            for command in self.bot.tree.walk_commands():
                if isinstance(command, app_commands.Command):
                    cog_name = command.binding.__class__.__name__ if command.binding else "No Category"
                    if cog_name not in cog_commands:
                        cog_commands[cog_name] = []
                    if not any(
                            cmd.startswith(f"`/{command.name}`")
                            for cmd in cog_commands[cog_name]):
                        cog_commands[cog_name].append(f"`/{command.name}`")

            for cog_name, commands_list in cog_commands.items():
                embed.add_field(name=cog_name,
                                value=", ".join(commands_list),
                                inline=False)

        embed.set_footer(
            text=
            f"Type {prefix}help <command> or /help command:<command> for more info on a command."
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))

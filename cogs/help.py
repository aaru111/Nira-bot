import discord
from discord.ext import commands
from typing import List, Dict, Optional


class HelpDropdown(discord.ui.Select):

    def __init__(self, help_command: 'HelpCommand',
                 options: List[discord.SelectOption]):
        super().__init__(placeholder="Choose a category...", options=options)
        self.help_command = help_command

    async def callback(self, interaction: discord.Interaction):
        embed = await self.help_command.create_category_embed(self.values[0])
        await interaction.response.edit_message(embed=embed)


class HelpView(discord.ui.View):

    def __init__(self,
                 help_command: 'HelpCommand',
                 options: List[discord.SelectOption],
                 timeout: Optional[float] = 120.0):
        super().__init__(timeout=timeout)
        self.add_item(HelpDropdown(help_command, options))


class HelpCommand(commands.HelpCommand):

    def __init__(self):
        super().__init__()
        self.command_attrs[
            'help'] = 'Shows help about the bot, a command, or a category'

    async def send_bot_help(self, mapping: Dict[Optional[commands.Cog],
                                                List[commands.Command]]):
        embed = discord.Embed(title="Bot Help", color=discord.Color.blurple())
        embed.set_thumbnail(url=self.context.bot.user.avatar.url)
        embed.add_field(name="About",
                        value="Here's a list of all my commands:",
                        inline=False)

        options = []
        for cog, commands in mapping.items():
            if cog and commands:
                name = cog.qualified_name
                options.append(
                    discord.SelectOption(
                        label=name, description=f"{len(commands)} commands"))

        options.append(
            discord.SelectOption(label="Home",
                                 description="Go back to the main menu"))
        view = HelpView(self, options)
        await self.get_destination().send(embed=embed, view=view)

    async def send_cog_help(self, cog: commands.Cog):
        embed = await self.create_category_embed(cog.qualified_name)
        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command: commands.Command):
        embed = discord.Embed(title=f"Command: {command.name}",
                              color=discord.Color.blurple())
        embed.add_field(name="Description",
                        value=command.help or "No description provided.",
                        inline=False)
        embed.add_field(name="Usage",
                        value=f"`{self.get_command_signature(command)}`",
                        inline=False)
        if command.aliases:
            embed.add_field(name="Aliases",
                            value=", ".join(command.aliases),
                            inline=False)
        await self.get_destination().send(embed=embed)

    async def create_category_embed(self, category: str):
        cog = self.context.bot.get_cog(category)
        if cog is None:
            return await self.send_bot_help(self.get_bot_mapping())

        embed = discord.Embed(title=f"{category} Commands",
                              color=discord.Color.blurple())
        embed.set_thumbnail(url=self.context.bot.user.avatar.url)

        filtered = await self.filter_commands(cog.get_commands())
        for command in filtered:
            description = command.short_doc or "No description provided."
            embed.add_field(name=command.name, value=description, inline=False)

        return embed


class HelpCog(commands.Cog, name="Help"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = HelpCommand()
        bot.help_command.cog = self

    async def cog_unload(self):
        self.bot.help_command = self._original_help_command


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))

import discord
from discord.ext import commands
import traceback
import aiohttp
from typing import Optional, Union, List
from difflib import get_close_matches

# Define the embed color
EMBED_COLOR = 0x2f3131


class Errors(commands.Cog):
    """
    A cog to handle and report errors occurring during command execution.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """
        Initialize the Errors cog.

        Args:
            bot (commands.Bot): The instance of the bot.
        """
        self.bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

    async def send_error_embed(self, ctx: commands.Context, title: str,
                               description: str,
                               button_color: discord.ButtonStyle) -> None:
        """
        Send an embed with error information to the context channel.

        Args:
            ctx (commands.Context): The context in which the command was invoked.
            title (str): The title of the embed.
            description (str): The description of the embed.
            button_color (discord.ButtonStyle): The color of the help button.
        """
        embed = discord.Embed(title=title,
                              description=f"```py\n{description}```",
                              color=EMBED_COLOR)
        view = discord.ui.View()
        view.add_item(HelpButton(ctx, title, description, button_color))
        await ctx.send(embed=embed, view=view, ephemeral=True)

    async def close(self) -> None:
        """
        Close the aiohttp client session.
        """
        await self.session.close()

    @commands.Cog.listener()
    async def on_shutdown(self):
        await self.close()

    @commands.Cog.listener()
    async def on_disconnect(self):
        await self.close()

    async def handle_error(self, ctx: commands.Context, command_name: str,
                           description: str, title: str) -> None:
        """
        Send an error embed.

        Args:
            ctx (commands.Context): The context in which the command was invoked.
            command_name (str): The name of the command that triggered the error.
            description (str): The description of the error.
            title (str): The title of the error.
        """
        button_color = self.get_button_color(title)
        await self.send_error_embed(ctx, title, description, button_color)

    def get_button_color(self, title: str) -> discord.ButtonStyle:
        """
        Get the button color based on the seriousness of the error.

        Args:
            title (str): The title of the error.

        Returns:
            discord.ButtonStyle: The color of the button.
        """
        minor_errors = [
            "Missing Required Argument", "Command Not Found",
            "User Input Error", "Invalid End of Quoted String",
            "Expected Closing Quote", "Unexpected Quote", "Invalid Argument"
        ]

        major_errors = [
            "Missing Permissions", "Bot Missing Permissions",
            "Command on Cooldown", "No Private Message", "Bad Argument",
            "Check Failure", "Disabled Command", "NSFW Channel Required"
        ]

        critical_errors = [
            "Not Owner", "Forbidden", "Not Found", "HTTP Exception",
            "Max Concurrency Reached", "Unexpected Error"
        ]

        if title in minor_errors:
            return discord.ButtonStyle.success  # Green
        elif title in major_errors:
            return discord.ButtonStyle.primary  # Blue
        elif title in critical_errors:
            return discord.ButtonStyle.danger  # Red
        else:
            return discord.ButtonStyle.secondary  # Grey

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context,
                               error: commands.CommandError) -> None:
        """
        Handle errors that occur during command execution.

        Args:
            ctx (commands.Context): The context in which the command was invoked.
            error (commands.CommandError): The error that was raised.
        """
        command_name = ctx.command.qualified_name if ctx.command else "Unknown Command"
        command_signature = getattr(ctx.command, 'signature',
                                    '') if ctx.command else ""

        if isinstance(error, commands.MissingRequiredArgument):
            description = f"Argument: '{error.param.name}'\nUsage: {ctx.prefix}{command_name} {command_signature}"
            await self.handle_error(ctx, command_name, description,
                                    "Missing Required Argument")

        elif isinstance(error, commands.CommandNotFound):
            description = "Command not found. Please check your command and try again."
            similar_commands = get_close_matches(
                error.args[0].split()[0],
                [cmd.name for cmd in self.bot.commands],
                n=3,
                cutoff=0.6)
            if similar_commands:
                description += "\n\nDid you mean?\n" + '\n'.join(
                    similar_commands)
            await self.handle_error(ctx, command_name, description,
                                    "Command Not Found")

        elif isinstance(error, commands.MissingPermissions):
            perms = ', '.join(error.missing_permissions)
            description = f"You need the following permissions to execute this command: {perms}"
            await self.handle_error(ctx, command_name, description,
                                    "Missing Permissions")

        elif isinstance(error, commands.BotMissingPermissions):
            perms = ', '.join(error.missing_permissions)
            description = f"I need the following permissions to execute this command: {perms}"
            await self.handle_error(ctx, command_name, description,
                                    "Bot Missing Permissions")

        elif isinstance(error, commands.CommandOnCooldown):
            description = f"This command is on cooldown. Try again after {error.retry_after:.2f} seconds."
            await self.handle_error(ctx, command_name, description,
                                    "Command on Cooldown")

        elif isinstance(error, commands.NotOwner):
            description = "Only the bot owner can use this command."
            await self.handle_error(ctx, command_name, description,
                                    "Not Owner")

        elif isinstance(error, commands.NoPrivateMessage):
            description = "This command cannot be used in private messages. Please use it in a server channel."
            await self.handle_error(ctx, command_name, description,
                                    "No Private Message")

        elif isinstance(error, commands.BadArgument):
            await self.handle_error(ctx, command_name, str(error),
                                    "Bad Argument")

        elif isinstance(error, commands.CheckFailure):
            description = "You do not have permission to execute this command."
            await self.handle_error(ctx, command_name, description,
                                    "Check Failure")

        elif isinstance(error, commands.DisabledCommand):
            description = "This command is currently disabled."
            await self.handle_error(ctx, command_name, description,
                                    "Disabled Command")

        elif isinstance(error, commands.UserInputError):
            await self.handle_error(ctx, command_name, str(error),
                                    "User Input Error")

        elif isinstance(error, commands.InvalidEndOfQuotedStringError):
            await self.handle_error(ctx, command_name, str(error),
                                    "Invalid End of Quoted String")

        elif isinstance(error, commands.ExpectedClosingQuoteError):
            await self.handle_error(ctx, command_name, str(error),
                                    "Expected Closing Quote")

        elif isinstance(error, commands.MaxConcurrencyReached):
            description = f"This command can only be used {error.number} times concurrently."
            await self.handle_error(ctx, command_name, description,
                                    "Max Concurrency Reached")

        elif isinstance(error, commands.UnexpectedQuoteError):
            await self.handle_error(ctx, command_name, str(error),
                                    "Unexpected Quote")

        elif isinstance(error, commands.InvalidArgument):
            await self.handle_error(ctx, command_name, str(error),
                                    "Invalid Argument")

        elif isinstance(error, commands.NSFWChannelRequired):
            description = "This command can only be used in NSFW channels."
            await self.handle_error(ctx, command_name, description,
                                    "NSFW Channel Required")

        elif isinstance(error, discord.Forbidden):
            description = "I do not have permission to do that."
            await self.handle_error(ctx, command_name, description,
                                    "Forbidden")

        elif isinstance(error, discord.NotFound):
            description = "The requested resource was not found."
            await self.handle_error(ctx, command_name, description,
                                    "Not Found")

        elif isinstance(error, discord.HTTPException):
            description = "An HTTP exception occurred."
            await self.handle_error(ctx, command_name, description,
                                    "HTTP Exception")

        else:
            # Log the error with traceback
            traceback_str = ''.join(
                traceback.format_exception(type(error), error,
                                           error.__traceback__))
            await self.handle_error(ctx, command_name, traceback_str,
                                    "Unexpected Error")


class HelpButton(discord.ui.Button):

    def __init__(self, ctx: commands.Context, title: str, description: str,
                 button_color: discord.ButtonStyle):
        super().__init__(label='Help', emoji='❓', style=button_color)
        self.ctx = ctx
        self.title = title
        self.description = description
    
    async def callback(self, interaction: discord.Interaction):
        help_message = self.get_help_message(self.title)
        embed = discord.Embed(title=f'Help: {self.title}',
                              description=help_message,
                              color=EMBED_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def get_help_message(self, error_title: str) -> str:
        help_messages = {
            "Missing Required Argument":
            "You missed a required argument for the command. Please check the command syntax and try again.",
            "Command Not Found":
            "The command you entered was not found. Please check the command and try again.",
            "Missing Permissions":
            "You do not have the necessary permissions to execute this command. Please contact a server administrator if you believe this is an error.",
            "Bot Missing Permissions":
            "The bot does not have the necessary permissions to execute this command. Please ensure the bot has the correct permissions.",
            "Command on Cooldown":
            "This command is on cooldown. Please wait a few moments and try again.",
            "Not Owner":
            "Become the owner of the bot to use owner only commands.\nApply here - https://blogs.mtdv.me/articles/owner-applications",
            "No Private Message":
            "This command cannot be used in private messages. Please use it in a server channel.",
            "Bad Argument":
            "There was an issue with the arguments you provided. Please check the command syntax and try again.",
            "Check Failure":
            "You do not meet the requirements to use this command.",
            "Disabled Command":
            "This command is currently disabled.",
            "User Input Error":
            "There was an error with the input you provided. Please check the command syntax and try again.",
            "Invalid End of Quoted String":
            "There was an issue with the quoted string in your command. Please check the command syntax and try again.",
            "Expected Closing Quote":
            "A closing quote was expected but not found. Please check the command syntax and try again.",
            "Max Concurrency Reached":
            "This command can only be used a limited number of times concurrently. Please wait and try again.",
            "Unexpected Quote":
            "An unexpected quote was found in your command. Please check the command syntax and try again.",
            "Invalid Argument":
            "An invalid argument was provided. Please check the command syntax and try again.",
            "NSFW Channel Required":
            "This command can only be used in NSFW channels.",
            "Forbidden":
            "The bot does not have permission to perform this action.",
            "Not Found":
            "The requested resource was not found.",
            "HTTP Exception":
            "An HTTP exception occurred. Please try again later.",
            "Unexpected Error":
            "An unexpected error occurred. Please report the issue to the developers."
        }
    
        return help_messages.get(
            error_title,
            "This error cannot be fixed by the user. Please report the issue to the developers."
        )



async def setup(bot: commands.Bot) -> None:
    """
    Load the Errors cog.

    Args:
        bot (commands.Bot): The instance of the bot.
    """
    await bot.add_cog(Errors(bot))

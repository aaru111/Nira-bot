import discord
from discord.ext import commands
import traceback
import aiohttp
import asyncio
from difflib import get_close_matches
from typing import List
from loguru import logger
import sys
import ipdb

DELETE_AFTER: int = 10  # Time in seconds after which the error message will delete itself
DEFAULT_EMBED_COLOR: int = 0x2f3131  # Default embed color

# Enable/disable interactive debugging
DEBUG_MODE = False


def custom_excepthook(type, value, tb):
    """Custom exception hook to trigger ipdb for debugging."""
    traceback.print_exception(type, value, tb)
    if DEBUG_MODE:
        ipdb.post_mortem(tb)


sys.excepthook = custom_excepthook


class Errors(commands.Cog):
    """Cog to handle and report errors during command execution."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        """Clean up resources when the cog is unloaded."""
        await self.session.close()

    async def send_error_embed(self, ctx: commands.Context, title: str,
                               description: str,
                               button_color: discord.ButtonStyle) -> None:
        """Send an embed with error information to the context channel."""
        embed_color: int = self.get_embed_color(title)
        embed: discord.Embed = discord.Embed(
            title=title,
            description=f"```py\n{description}```",
            color=embed_color)
        view: discord.ui.View = discord.ui.View()
        view.add_item(HelpButton(ctx, title, description, button_color))

        try:
            message: discord.Message = await ctx.send(embed=embed,
                                                      view=view,
                                                      ephemeral=True)
            await message.delete(delay=DELETE_AFTER)
        except discord.errors.NotFound:
            logger.warning(
                "Failed to send or delete an error embed: message or channel not found."
            )
        except discord.errors.Forbidden:
            logger.warning(
                "Failed to delete the error embed: insufficient permissions.")

    async def handle_error(self, ctx: commands.Context,
                           error: commands.CommandError, description: str,
                           title: str) -> None:
        """Handle sending an error embed based on the error type."""
        button_color: discord.ButtonStyle = self.get_button_color(title)
        await self.send_error_embed(ctx, title, description, button_color)

        if not isinstance(error,
                          (commands.CommandNotFound, commands.UserInputError,
                           commands.CheckFailure)):
            logger.error(
                f"Error in command {ctx.command}: {error}\n{description}")

        if DEBUG_MODE:
            ipdb.set_trace()

    def get_button_color(self, title: str) -> discord.ButtonStyle:
        """Determine button color based on the error severity."""
        match title:
            case "Missing Required Argument" | "Command Not Found" | \
                 "User Input Error" | "Invalid End of Quoted String" | \
                 "Expected Closing Quote" | "Unexpected Quote" | "Bad Argument":
                return discord.ButtonStyle.success  # Green
            case "Missing Permissions" | "Bot Missing Permissions" | \
                 "Command on Cooldown" | "No Private Message" | \
                 "Check Failure" | "Disabled Command" | "NSFW Channel Required":
                return discord.ButtonStyle.primary  # Blue
            case "Not Owner" | "Forbidden" | "Not Found" | "HTTP Exception" | \
                 "Max Concurrency Reached" | "Unexpected Error":
                return discord.ButtonStyle.danger  # Red
            case _:
                return discord.ButtonStyle.secondary  # Grey

    def get_embed_color(self, title: str) -> int:
        """Determine embed color based on the error severity."""
        match title:
            case "Missing Required Argument" | "Command Not Found" | \
                 "User Input Error" | "Invalid End of Quoted String" | \
                 "Expected Closing Quote" | "Unexpected Quote" | "Bad Argument":
                return 0x57F287  # Green
            case "Missing Permissions" | "Bot Missing Permissions" | \
                 "Command on Cooldown" | "No Private Message" | \
                 "Check Failure" | "Disabled Command" | "NSFW Channel Required":
                return 0x5865F2  # Blue
            case "Not Owner" | "Forbidden" | "Not Found" | "HTTP Exception" | \
                 "Max Concurrency Reached" | "Unexpected Error":
                return 0xED4245  # Red
            case _:
                return DEFAULT_EMBED_COLOR  # Default Grey

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context,
                               error: commands.CommandError) -> None:
        """Handle errors that occur during command execution."""
        if isinstance(error,
                      discord.errors.HTTPException) and error.status == 429:
            retry_after: float = float(
                error.response.headers.get("Retry-After", 5))
            for attempt in range(MAX_RETRIES):
                await ctx.send(
                    f"Rate limit hit! Retrying after {retry_after:.2f} seconds... (Attempt {attempt + 1}/{MAX_RETRIES})",
                    delete_after=DELETE_AFTER)
                await asyncio.sleep(retry_after)

                try:
                    await ctx.reinvoke()
                    return  # If successful, exit the method
                except discord.errors.HTTPException as e:
                    if e.status == 429:
                        retry_after = float(
                            e.response.headers.get("Retry-After",
                                                   retry_after * 2))
                        logger.warning(
                            f"Hit rate limit again. Retrying in {retry_after:.2f} seconds."
                        )
                    else:
                        await self.handle_error(ctx, e, str(e),
                                                "HTTP Exception")
                        return

            logger.error(
                f"Failed to execute command after {MAX_RETRIES} attempts due to rate limiting."
            )
            await ctx.send(
                f"Command failed after {MAX_RETRIES} attempts due to rate limiting. Please try again later.",
                delete_after=DELETE_AFTER)
            return

        command_name: str = ctx.command.qualified_name if ctx.command else "Unknown Command"
        command_signature: str = getattr(ctx.command, 'signature',
                                         '') if ctx.command else ""

        title, description = self.get_error_title_and_description(
            ctx, error, command_name, command_signature)
        await self.handle_error(ctx, error, description, title)

        if DEBUG_MODE:
            ipdb.set_trace()

    def get_error_title_and_description(
            self, ctx: commands.Context, error: commands.CommandError,
            command_name: str, command_signature: str) -> tuple[str, str]:
        """Get the title and description for the error embed based on the error type."""
        match error:
            case commands.MissingRequiredArgument():
                return (
                    "Missing Required Argument",
                    f"Argument: '{error.param.name}'\nUsage: {ctx.prefix}{command_name} {command_signature}"
                )
            case commands.CommandNotFound():
                attempted_command = ctx.message.content.split(
                )[0][len(ctx.prefix):]
                similar_commands: List[str] = get_close_matches(
                    attempted_command, [cmd.name for cmd in self.bot.commands],
                    n=1,
                    cutoff=0.6)
                if similar_commands:
                    suggestion: str = similar_commands[0]
                    description: str = f"Command not found. Did you mean `{ctx.prefix}{suggestion}`?"
                else:
                    description = "Command not found. Please check your command and try again."
                return ("Command Not Found", description)
            case commands.MissingPermissions():
                perms: str = ', '.join(error.missing_permissions)
                return (
                    "Missing Permissions",
                    f"You need the following permissions to execute this command: {perms}"
                )
            case commands.BotMissingPermissions():
                perms: str = ', '.join(error.missing_permissions)
                return (
                    "Bot Missing Permissions",
                    f"I need the following permissions to execute this command: {perms}"
                )
            case commands.CommandOnCooldown():
                return (
                    "Command on Cooldown",
                    f"This command is on cooldown. Try again after {error.retry_after:.2f} seconds."
                )
            case commands.NotOwner():
                return ("Not Owner",
                        "Only the bot owner can use this command.")
            case commands.NoPrivateMessage():
                return (
                    "No Private Message",
                    "This command cannot be used in private messages. Please use it in a server channel."
                )
            case commands.BadArgument():
                return ("Bad Argument", str(error))
            case commands.CheckFailure():
                return ("Check Failure",
                        "You do not have permission to execute this command.")
            case commands.DisabledCommand():
                return ("Disabled Command",
                        "This command is currently disabled.")
            case commands.UserInputError():
                return ("User Input Error", str(error))
            case commands.InvalidEndOfQuotedStringError():
                return ("Invalid End of Quoted String", str(error))
            case commands.ExpectedClosingQuoteError():
                return ("Expected Closing Quote", str(error))
            case commands.MaxConcurrencyReached():
                return (
                    "Max Concurrency Reached",
                    f"This command can only be used {error.number} times concurrently."
                )
            case commands.UnexpectedQuoteError():
                return ("Unexpected Quote", str(error))
            case discord.Forbidden():
                return ("Forbidden", "I do not have permission to do that.")
            case discord.NotFound():
                return ("Not Found", "The requested resource was not found.")
            case discord.HTTPException():
                return ("HTTP Exception", "An HTTP exception occurred.")
            case _:
                tb_str = traceback.format_exception(type(error), error,
                                                    error.__traceback__)
                simplified_tb = ''.join(tb_str[-3:])
                return ("Unexpected Error", simplified_tb)


class HelpButton(discord.ui.Button):

    def __init__(self, ctx: commands.Context, title: str, description: str,
                 button_color: discord.ButtonStyle) -> None:
        super().__init__(label='Help', emoji='❓', style=button_color)
        self.ctx: commands.Context = ctx
        self.title: str = title
        self.description: str = description

    async def callback(self, interaction: discord.Interaction) -> None:
        help_message: str = self.get_help_message(self.title)
        embed: discord.Embed = discord.Embed(title=f'Help: {self.title}',
                                             description=help_message,
                                             color=DEFAULT_EMBED_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def get_help_message(self, error_title: str) -> str:
        help_messages: dict[str, str] = {
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
            "Only the bot owner can use this command.",
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
    """Load the Errors cog."""
    await bot.add_cog(Errors(bot))

import discord
from discord.ext import commands
import traceback
import aiohttp
import asyncio
from difflib import get_close_matches
from typing import List, Tuple
from loguru import logger
import sys
from discord.ext.commands import CommandInvokeError
from discord.errors import Forbidden, HTTPException

DELETE_AFTER: int = 10  # Time in seconds after which the error message will delete itself
DEFAULT_EMBED_COLOR: int = 0x2f3131  # Default embed color
MAX_RETRIES: int = 3  # Number of retries for rate limit handling

logger.remove()
logger.add(
    sys.stderr,
    format=
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    backtrace=True,
    diagnose=True)


def custom_excepthook(type, value, tb):
    """Custom exception hook for debugging."""
    traceback.print_exception(type, value, tb)


sys.excepthook = custom_excepthook


def format_cooldown(seconds: float) -> str:
    """Format cooldown time into a more readable string."""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"


class Errors(commands.Cog):
    """Cog to handle and report errors during command execution."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

    async def cog_unload(self):
        """Cleanup resources when the cog is unloaded."""
        await self.session.close()

    async def send_error_embed(self, ctx: commands.Context, title: str,
                               description: str) -> None:
        """Send an embed with error information to the context channel."""
        _, embed_color = self.get_error_style(title)
        embed: discord.Embed = discord.Embed(
            title=title,
            description=f"```py\n{description}```",
            color=embed_color)

        try:
            message: discord.Message = await ctx.send(embed=embed,
                                                      ephemeral=True)
            await self.delete_message_with_retry(message)
        except discord.NotFound:
            logger.warning(
                "Channel or message not found when sending error embed.")
        except discord.Forbidden:
            logger.warning(
                "Bot doesn't have permission to send messages in this channel."
            )
        except discord.HTTPException as e:
            logger.warning(f"Failed to send or delete an error embed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error when sending error embed: {e}")

    async def delete_message_with_retry(self,
                                        message: discord.Message,
                                        max_retries: int = 3) -> None:
        """Attempt to delete a message with retries."""
        for attempt in range(max_retries):
            try:
                await asyncio.sleep(DELETE_AFTER)
                await message.delete()
                return
            except discord.NotFound:
                logger.info("Message already deleted.")
                return
            except discord.HTTPException as e:
                if e.code == 10008:  # Unknown Message error
                    logger.info("Message no longer exists.")
                    return
                if attempt == max_retries - 1:
                    logger.warning(
                        f"Failed to delete message after {max_retries} attempts: {e}"
                    )
                else:
                    await asyncio.sleep(2**attempt)  # Exponential backoff
            except Exception as e:
                logger.error(f"Unexpected error while deleting message: {e}")
                return

    async def handle_error(self, ctx: commands.Context,
                           error: commands.CommandError, description: str,
                           title: str) -> None:
        """Handle sending an error embed based on the error type."""
        await self.send_error_embed(ctx, title, description)

        if not isinstance(error,
                          (commands.CommandNotFound, commands.UserInputError,
                           commands.CheckFailure)):
            logger.error(
                f"Error in command {ctx.command}: {error}\n{description}")

    def get_error_style(self, title: str) -> Tuple[discord.ButtonStyle, int]:
        """Determine button color and embed color based on the error severity."""
        match title:
            case "Missing Required Argument" | "Command Not Found" | "User Input Error" | "Invalid End of Quoted String" | "Expected Closing Quote" | "Unexpected Quote" | "Bad Argument":
                return discord.ButtonStyle.success, 0x57F287  # Green
            case "Missing Permissions" | "Bot Missing Permissions" | "Command on Cooldown" | "No Private Message" | "Check Failure" | "Disabled Command" | "NSFW Channel Required":
                return discord.ButtonStyle.primary, 0x5865F2  # Blue
            case "Not Owner" | "Forbidden" | "Not Found" | "HTTP Exception" | "Max Concurrency Reached" | "Unexpected Error":
                return discord.ButtonStyle.danger, 0xED4245  # Red
            case _:
                return discord.ButtonStyle.secondary, DEFAULT_EMBED_COLOR  # Default Grey

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context,
                               error: commands.CommandError) -> None:
        # List of error types that should not be logged
        non_logging_errors = (commands.MissingRequiredArgument,
                              commands.CommandNotFound,
                              commands.UserInputError, commands.CheckFailure)

        if not isinstance(error, non_logging_errors):
            logger.error(f"Error occurred in command {ctx.command}: {error}")

        if hasattr(ctx.command, 'on_error'):
            return  # Don't interfere with custom error handlers

        if isinstance(error, commands.CommandInvokeError):
            error = error.original  # Get the original error

        if isinstance(error, discord.HTTPException) and error.status == 429:
            await self.handle_rate_limit(ctx, error)
            return

        try:
            if not ctx.channel.permissions_for(ctx.me).send_messages:
                try:
                    await ctx.author.send(
                        "I don't have permission to send messages in that channel. "
                        "Please give me the 'Send Messages' permission and try again."
                    )
                except discord.Forbidden:
                    # If we can't send a DM, we can't communicate the error at all
                    pass
                return
        except AttributeError:
            # This can happen in DMs where ctx.channel.permissions_for() doesn't exist
            pass

        # Fallback for other errors
        command_name: str = ctx.command.qualified_name if ctx.command else "Unknown Command"
        command_signature: str = getattr(ctx.command, 'signature',
                                         '') if ctx.command else ""

        title, description = self.get_error_title_and_description(
            ctx, error, command_name, command_signature)
        await self.handle_error(ctx, error, description, title)

    async def handle_rate_limit(self, ctx: commands.Context,
                                error: discord.HTTPException) -> None:
        retry_after: float = float(error.response.headers.get(
            "Retry-After", 5))
        base_retry_time: float = retry_after
        for attempt in range(MAX_RETRIES):
            await ctx.send(
                f"Rate limit hit! Retrying after {format_cooldown(retry_after)}... (Attempt {attempt + 1}/{MAX_RETRIES})",
                delete_after=DELETE_AFTER)
            await asyncio.sleep(retry_after)

            try:
                await ctx.reinvoke()
                return
            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = min(base_retry_time * (2**attempt),
                                      600)  # Cap at 10 minutes
                    logger.warning(
                        f"Rate limit hit again. Retrying in {format_cooldown(retry_after)}."
                    )
                else:
                    await self.handle_error(ctx, e, str(e), "HTTP Exception")
                    return

        logger.error(
            f"Command failed after {MAX_RETRIES} attempts due to rate limiting."
        )
        await ctx.send(
            f"Command failed after {MAX_RETRIES} attempts due to rate limiting. Please try again later.",
            delete_after=DELETE_AFTER)

    def get_error_title_and_description(
            self, ctx: commands.Context, error: commands.CommandError,
            command_name: str, command_signature: str) -> Tuple[str, str]:
        """Get the title and description for the error embed based on the error type."""
        match error:

            case commands.NSFWChannelRequired():
                return (
                    "NSFW Channel Required",
                    f"The command '{command_name}' can only be used in NSFW channels. Please use this command in an appropriate channel."
                )
            case commands.MissingRequiredArgument():
                return (
                    "Missing Required Argument",
                    f"Argument: '{error.param.name}'\nUsage: {ctx.prefix}{command_name} {command_signature}"
                )
            case commands.CommandNotFound():
                return ("Command Not Found",
                        self.get_command_not_found_description(ctx))
            case commands.MissingPermissions():
                return (
                    "Missing Permissions",
                    f"You need the following permissions to execute this command: {', '.join(error.missing_permissions)}"
                )
            case commands.BotMissingPermissions():
                return (
                    "Bot Missing Permissions",
                    f"I need the following permissions to execute this command: {', '.join(error.missing_permissions)}"
                )
            case commands.CommandOnCooldown():
                return (
                    "Command on Cooldown",
                    f"This command is on cooldown. Try again after {format_cooldown(error.retry_after)}."
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
                return ("Bad Argument",
                        f"Invalid argument provided: {str(error)}")
            case commands.CheckFailure():
                return ("Check Failure",
                        "You do not have permission to execute this command.")
            case commands.DisabledCommand():
                return ("Disabled Command",
                        "This command is currently disabled.")
            case commands.UserInputError():
                return (
                    "User Input Error",
                    f"There was an error processing your input: {str(error)}")
            case commands.InvalidEndOfQuotedStringError():
                return (
                    "Invalid End of Quoted String",
                    f"There was an issue with quotes in your command: {str(error)}"
                )
            case commands.ExpectedClosingQuoteError():
                return ("Expected Closing Quote",
                        f"A closing quote was expected: {str(error)}")
            case commands.MaxConcurrencyReached():
                return (
                    "Max Concurrency Reached",
                    f"This command can only be used {error.number} times concurrently. Please wait and try again."
                )
            case commands.UnexpectedQuoteError():
                return ("Unexpected Quote",
                        f"An unexpected quote was found: {str(error)}")
            case discord.Forbidden():
                return ("Forbidden",
                        f"I do not have permission to do that: {str(error)}")
            case discord.NotFound():
                return ("Not Found",
                        f"The requested resource was not found: {str(error)}")
            case discord.HTTPException():
                return ("HTTP Exception",
                        f"An HTTP exception occurred: {str(error)}")
            case CommandInvokeError():
                return ("Command Error",
                        self.get_command_invoke_error_description(error))
            case commands.NSFWChannelRequired():
                return ("NSFW Channel Required",
                        "This command can only be used in NSFW channels.")
            case commands.MemberNotFound():
                return (
                    "Member Not Found",
                    f"Could not find the specified member: {error.argument}")
            case commands.RoleNotFound():
                return ("Role Not Found",
                        f"Could not find the specified role: {error.argument}")
            case commands.ChannelNotFound():
                return (
                    "Channel Not Found",
                    f"Could not find the specified channel: {error.argument}")
            case commands.ChannelNotReadable():
                return (
                    "Channel Not Readable",
                    "I don't have permission to read messages in the specified channel."
                )
            case commands.BadUnionArgument():
                return (
                    "Bad Argument",
                    f"Could not parse argument: {error.param.name}. {str(error)}"
                )
            case commands.ArgumentParsingError():
                return (
                    "Argument Parsing Error",
                    f"There was an error parsing your command: {str(error)}")
            case commands.FlagError():
                return ("Flag Error",
                        f"There was an issue with command flags: {str(error)}")

            case Forbidden():
                if error.code == 50013:  # Missing Permissions
                    return (
                        "Missing Bot Permissions",
                        "I don't have the necessary permissions to perform this action. "
                        "Please make sure I have the correct permissions in this channel and try again."
                    )
                else:
                    return (
                        "Forbidden Action",
                        f"I'm not allowed to perform this action: {error.text}"
                    )

            case HTTPException():
                if error.code == 50006:  # Cannot send an empty message
                    return (
                        "Empty Message Error",
                        "An attempt was made to send an empty message. This is likely due to an issue with the command's response generation."
                    )
                else:
                    return ("HTTP Exception",
                            f"An HTTP error occurred: {error.text}")
            case _:
                tb_str = traceback.format_exception(type(error), error,
                                                    error.__traceback__)
                simplified_tb = ''.join(tb_str[-3:])
                logger.error(
                    f"Unhandled error in command {command_name}: {simplified_tb}"
                )
                return "Unexpected Error", f"An unexpected error occurred: {simplified_tb}"

    def get_command_not_found_description(self, ctx: commands.Context) -> str:
        attempted_command = ctx.message.content.split()[0][len(ctx.prefix):]
        similar_commands: List[str] = get_close_matches(
            attempted_command, [cmd.name for cmd in self.bot.commands],
            n=1,
            cutoff=0.6)
        if similar_commands:
            suggestion: str = similar_commands[0]
            return f"Command not found. Did you mean `{ctx.prefix}{suggestion}`?"
        else:
            return "Command not found. Please check your command and try again."

    def get_command_invoke_error_description(self,
                                             error: CommandInvokeError) -> str:
        original = error.original
        if isinstance(original, TypeError) and 'NoneType' in str(original):
            return "A command raised an exception: 'NoneType' object is not iterable. Please check your input and try again."
        else:
            tb_str = traceback.format_exception(type(original), original,
                                                original.__traceback__)
            simplified_tb = ''.join(tb_str[-3:])
            logger.error(
                f"Error in command {error.__cause__}: {simplified_tb}")
            return f"An error occurred: {simplified_tb}"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Errors(bot))

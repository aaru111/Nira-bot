import discord
from discord.ext import commands
import traceback
import aiohttp
import asyncio
from difflib import get_close_matches
from typing import List, Tuple
from loguru import logger
import sys
import ipdb
from discord.ext.commands import CommandInvokeError

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

# Enable/disable interactive debugging
DEBUG_MODE = False


def custom_excepthook(type, value, tb):
    """Custom exception hook to trigger ipdb for debugging."""
    traceback.print_exception(type, value, tb)
    if DEBUG_MODE:
        ipdb.post_mortem(tb)


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

        if DEBUG_MODE:
            ipdb.set_trace()

    def get_error_style(self, title: str) -> Tuple[discord.ButtonStyle, int]:
        """Determine button color and embed color based on the error severity."""
        if title in {
                "Missing Required Argument", "Command Not Found",
                "User Input Error", "Invalid End of Quoted String",
                "Expected Closing Quote", "Unexpected Quote", "Bad Argument"
        }:
            return discord.ButtonStyle.success, 0x57F287  # Green
        elif title in {
                "Missing Permissions", "Bot Missing Permissions",
                "Command on Cooldown", "No Private Message", "Check Failure",
                "Disabled Command", "NSFW Channel Required"
        }:
            return discord.ButtonStyle.primary, 0x5865F2  # Blue
        elif title in {
                "Not Owner", "Forbidden", "Not Found", "HTTP Exception",
                "Max Concurrency Reached", "Unexpected Error"
        }:
            return discord.ButtonStyle.danger, 0xED4245  # Red
        else:
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

        # Rest of the error handling logic...
        if hasattr(ctx.command, 'on_error'):
            return  # Don't interfere with custom error handlers

        if isinstance(error, commands.CommandInvokeError):
            error = error.original  # Get the original error

        if isinstance(error, discord.HTTPException) and error.status == 429:
            await self.handle_rate_limit(ctx, error)
            return

        # Fallback for other errors
        command_name: str = ctx.command.qualified_name if ctx.command else "Unknown Command"
        command_signature: str = getattr(ctx.command, 'signature',
                                         '') if ctx.command else ""

        title, description = self.get_error_title_and_description(
            ctx, error, command_name, command_signature)
        await self.handle_error(ctx, error, description, title)

        if DEBUG_MODE:
            ipdb.set_trace()

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
        error_handlers = {
            commands.MissingRequiredArgument:
            lambda e:
            ("Missing Required Argument",
             f"Argument: '{e.param.name}'\nUsage: {ctx.prefix}{command_name} {command_signature}"
             ),
            commands.CommandNotFound:
            lambda e:
            ("Command Not Found", self.get_command_not_found_description(ctx)),
            commands.MissingPermissions:
            lambda e:
            ("Missing Permissions",
             f"You need the following permissions to execute this command: {', '.join(e.missing_permissions)}"
             ),
            commands.BotMissingPermissions:
            lambda e:
            ("Bot Missing Permissions",
             f"I need the following permissions to execute this command: {', '.join(e.missing_permissions)}"
             ),
            commands.CommandOnCooldown:
            lambda e:
            ("Command on Cooldown",
             f"This command is on cooldown. Try again after {format_cooldown(e.retry_after)}."
             ),
            commands.NotOwner:
            lambda e:
            ("Not Owner", "Only the bot owner can use this command."),
            commands.NoPrivateMessage:
            lambda e:
            ("No Private Message",
             "This command cannot be used in private messages. Please use it in a server channel."
             ),
            commands.BadArgument:
            lambda e: ("Bad Argument", f"Invalid argument provided: {str(e)}"),
            commands.CheckFailure:
            lambda e: ("Check Failure",
                       "You do not have permission to execute this command."),
            commands.DisabledCommand:
            lambda e:
            ("Disabled Command", "This command is currently disabled."),
            commands.UserInputError:
            lambda e: ("User Input Error",
                       f"There was an error processing your input: {str(e)}"),
            commands.InvalidEndOfQuotedStringError:
            lambda e:
            ("Invalid End of Quoted String",
             f"There was an issue with quotes in your command: {str(e)}"),
            commands.ExpectedClosingQuoteError:
            lambda e: ("Expected Closing Quote",
                       f"A closing quote was expected: {str(e)}"),
            commands.MaxConcurrencyReached:
            lambda e:
            ("Max Concurrency Reached",
             f"This command can only be used {e.number} times concurrently. Please wait and try again."
             ),
            commands.UnexpectedQuoteError:
            lambda e:
            ("Unexpected Quote", f"An unexpected quote was found: {str(e)}"),
            discord.Forbidden:
            lambda e:
            ("Forbidden", f"I do not have permission to do that: {str(e)}"),
            discord.NotFound:
            lambda e:
            ("Not Found", f"The requested resource was not found: {str(e)}"),
            discord.HTTPException:
            lambda e:
            ("HTTP Exception", f"An HTTP exception occurred: {str(e)}"),
            CommandInvokeError:
            lambda e:
            ("Command Error", self.get_command_invoke_error_description(e)),
            commands.NSFWChannelRequired:
            lambda e: ("NSFW Channel Required",
                       "This command can only be used in NSFW channels."),
            commands.MemberNotFound:
            lambda e: ("Member Not Found",
                       f"Could not find the specified member: {e.argument}"),
            commands.RoleNotFound:
            lambda e: ("Role Not Found",
                       f"Could not find the specified role: {e.argument}"),
            commands.ChannelNotFound:
            lambda e: ("Channel Not Found",
                       f"Could not find the specified channel: {e.argument}"),
            commands.ChannelNotReadable:
            lambda e:
            ("Channel Not Readable",
             "I don't have permission to read messages in the specified channel."
             ),
            commands.BadUnionArgument:
            lambda e: ("Bad Argument",
                       f"Could not parse argument: {e.param.name}. {str(e)}"),
            commands.ArgumentParsingError:
            lambda e: ("Argument Parsing Error",
                       f"There was an error parsing your command: {str(e)}"),
            commands.FlagError:
            lambda e:
            ("Flag Error", f"There was an issue with command flags: {str(e)}"),
        }

        error_type = type(error)
        if error_type in error_handlers:
            return error_handlers[error_type](error)
        else:
            tb_str = traceback.format_exception(type(error), error,
                                                error.__traceback__)
            simplified_tb = ''.join(tb_str[-3:])
            logger.error(
                f"Unhandled error in command {command_name}: {simplified_tb}")
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
    """Load the Errors cog."""
    await bot.add_cog(Errors(bot))

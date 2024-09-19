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
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

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
        view: HelpView = HelpView()
        view.add_item(HelpButton(ctx, title, description, button_color))

        try:
            message: discord.Message = await ctx.send(embed=embed,
                                                      view=view,
                                                      ephemeral=True)
            view.message = message
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
        if title in {
                "Missing Required Argument", "Command Not Found",
                "User Input Error", "Invalid End of Quoted String",
                "Expected Closing Quote", "Unexpected Quote", "Bad Argument"
        }:
            return discord.ButtonStyle.success
        elif title in {
                "Missing Permissions", "Bot Missing Permissions",
                "Command on Cooldown", "No Private Message", "Check Failure",
                "Disabled Command", "NSFW Channel Required"
        }:
            return discord.ButtonStyle.primary
        elif title in {
                "Not Owner", "Forbidden", "Not Found", "HTTP Exception",
                "Max Concurrency Reached", "Unexpected Error"
        }:
            return discord.ButtonStyle.danger
        else:
            return discord.ButtonStyle.secondary

    def get_embed_color(self, title: str) -> int:
        """Determine embed color based on the error severity."""
        if title in {
                "Missing Required Argument", "Command Not Found",
                "User Input Error", "Invalid End of Quoted String",
                "Expected Closing Quote", "Unexpected Quote", "Bad Argument"
        }:
            return 0x57F287  # Green
        elif title in {
                "Missing Permissions", "Bot Missing Permissions",
                "Command on Cooldown", "No Private Message", "Check Failure",
                "Disabled Command", "NSFW Channel Required"
        }:
            return 0x5865F2  # Blue
        elif title in {
                "Not Owner", "Forbidden", "Not Found", "HTTP Exception",
                "Max Concurrency Reached", "Unexpected Error"
        }:
            return 0xED4245  # Red
        else:
            return DEFAULT_EMBED_COLOR  # Default Grey

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context,
                               error: commands.CommandError) -> None:
        """Handle errors that occur during command execution."""
        if hasattr(ctx.command, 'on_error'):
            return  # Don't interfere with custom error handlers

        if isinstance(error, commands.CommandInvokeError):
            error = error.original  # Get the original error

        if isinstance(error,
                      discord.errors.HTTPException) and error.status == 429:
            retry_after: float = float(
                error.response.headers.get("Retry-After", 5))
            base_retry_time = retry_after

            for attempt in range(MAX_RETRIES):
                await ctx.send(
                    f"Rate limit hit! Retrying after {retry_after:.2f} seconds... (Attempt {attempt + 1}/{MAX_RETRIES})",
                    delete_after=DELETE_AFTER)
                await asyncio.sleep(retry_after)

                try:
                    await ctx.reinvoke(
                    )  # Try re-running the command after the delay
                    return  # Exit the method if successful
                except discord.errors.HTTPException as e:
                    if e.status == 429:
                        retry_after = float(
                            e.response.headers.get("Retry-After",
                                                   retry_after * 2))
                        logger.warning(
                            f"Rate limit hit again. Retrying in {retry_after:.2f} seconds."
                        )
                    else:
                        await self.handle_error(ctx, e, str(e),
                                                "HTTP Exception")
                        return  # Exit if a non-429 error occurs

            logger.error(
                f"Command failed after {MAX_RETRIES} attempts due to rate limiting."
            )
            await ctx.send(
                f"Command failed after {MAX_RETRIES} attempts due to rate limiting. Please try again later.",
                delete_after=DELETE_AFTER)
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
             f"This command is on cooldown. Try again after {e.retry_after:.2f} seconds."
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
            lambda e: ("Bad Argument", str(e)),
            commands.CheckFailure:
            lambda e: ("Check Failure",
                       "You do not have permission to execute this command."),
            commands.DisabledCommand:
            lambda e:
            ("Disabled Command", "This command is currently disabled."),
            commands.UserInputError:
            lambda e: ("User Input Error", str(e)),
            commands.InvalidEndOfQuotedStringError:
            lambda e: ("Invalid End of Quoted String", str(e)),
            commands.ExpectedClosingQuoteError:
            lambda e: ("Expected Closing Quote", str(e)),
            commands.MaxConcurrencyReached:
            lambda e:
            ("Max Concurrency Reached",
             f"This command can only be used {e.number} times concurrently."),
            commands.UnexpectedQuoteError:
            lambda e: ("Unexpected Quote", str(e)),
            discord.Forbidden:
            lambda e: ("Forbidden", "I do not have permission to do that."),
            discord.NotFound:
            lambda e: ("Not Found", "The requested resource was not found."),
            discord.HTTPException:
            lambda e: ("HTTP Exception", "An HTTP exception occurred."),
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
            lambda e: ("Argument Parsing Error", str(e)),
            commands.FlagError:
            lambda e: ("Flag Error", str(e)),
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


class HelpView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=60)  # Set your desired timeout
        self.message = None  # Initialize the message attribute

    async def on_timeout(self):
        # This method will be called when the view times out
        if self.message:  # Check if message is set
            try:
                await self.message.delete()
            except discord.errors.NotFound:
                logger.warning("Message not found for timeout handling.")


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
            "Member Not Found":
            "The specified member could not be found. Please check the member name or ID and try again.",
            "Role Not Found":
            "The specified role could not be found. Please check the role name or ID and try again.",
            "Channel Not Found":
            "The specified channel could not be found. Please check the channel name or ID and try again.",
            "Channel Not Readable":
            "The bot doesn't have permission to read messages in the specified channel.",
            "Bad Union Argument":
            "There was an issue parsing one of the command arguments. Please check the command syntax and try again.",
            "Argument Parsing Error":
            "There was an error parsing the command arguments. Please check the command syntax and try again.",
            "Flag Error":
            "There was an issue with the command flags. Please check the command syntax and try again.",
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

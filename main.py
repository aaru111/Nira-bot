import os
import logging
import discord
from discord.ext import commands
import asyncio
from aiohttp import ClientSession
from typing import Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# -------------------------
# Bot Class Definition
# -------------------------


class Bot(commands.Bot):
    """
    Custom Bot class inheriting from commands.Bot.
    Handles setup, logging, and event management for the Discord bot.
    """

    def __init__(self, command_prefix: str, intents: discord.Intents,
                 session: ClientSession, **kwargs: Any) -> None:
        """
        Initializes the bot with a command prefix and intents.

        Args:
            command_prefix (str): The prefix for bot commands.
            intents (discord.Intents): The intents required for the bot.
            session (ClientSession): The aiohttp ClientSession for HTTP requests.
            **kwargs (Any): Additional keyword arguments for the Bot class.
        """
        super().__init__(command_prefix=command_prefix,
                         intents=intents,
                         **kwargs)
        self.session = session
        self.command_prefix = command_prefix

    async def setup_hook(self) -> None:
        """
        Performs initial setup tasks for the bot.
        Loads extensions and cogs as part of the setup process.
        """
        try:
            await self.load_extension("jishaku")
            logger.info("Extension 'jishaku' loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load extension 'jishaku': {e}")

        await self.load_all_cogs()

    async def load_all_cogs(self) -> None:
        """
        Loads all cog extensions from the 'cogs' directory.
        Logs the status of each cog loading attempt.
        """

        async def load_cog(filename: str) -> None:
            """
            Loads a single cog extension.

            Args:
                filename (str): The filename of the cog to be loaded.
            """
            cog_name = f'cogs.{filename[:-3]}'
            try:
                await self.load_extension(cog_name)
                logger.info(f"{cog_name} loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load {cog_name}: {e}")

        await asyncio.gather(*(load_cog(filename)
                               for filename in os.listdir('./cogs')
                               if filename.endswith('.py')))

    async def on_ready(self) -> None:
        """
        Event handler triggered when the bot is ready.
        Logs bot readiness status and user details.
        """
        if self.user:
            logger.info(f'Bot is ready as {self.user} (ID: {self.user.id}).')
        else:
            logger.error('Bot user is not available.')

    async def on_error(self, event_method: str, *args: Any,
                       **kwargs: Any) -> None:
        """
        Error handler for unhandled exceptions.
        Logs error details and traceback information.

        Args:
            event_method (str): The name of the event method where the error occurred.
            *args (Any): Additional arguments.
            **kwargs (Any): Additional keyword arguments.
        """
        logger.error('Unhandled exception occurred in %s.',
                     event_method,
                     exc_info=True)


# -------------------------
# Main Function and Execution
# -------------------------


async def main() -> None:
    """
    Main function to set up and start the Discord bot.
    Defines bot intents, creates the bot instance, and starts the bot.
    """
    # Define the necessary intents for the bot
    intents = discord.Intents.all()
    intents.message_content = True  # Enable if your bot needs to read message content

    # Load environment variables
    token = os.getenv('DISCORD_BOT_TOKEN')

    # Check if token is provided
    if not token:
        logger.error("DISCORD_BOT_TOKEN environment variable not set.")
        return

    # Create a single aiohttp ClientSession for the bot
    async with ClientSession() as session:
        # Create bot instance
        bot = Bot(command_prefix=".",
                  case_insensitive=True,
                  intents=intents,
                  session=session)

        # Attempt to start the bot
        try:
            await bot.start(token)
        except discord.LoginFailure:
            logger.error("Invalid bot token provided.")
        except Exception as e:
            logger.error(f"An error occurred during bot startup: {e}")
        finally:
            if bot.is_closed():
                logger.warning("Bot has been disconnected.")


if __name__ == "__main__":
    """
    Entry point for the script.
    Runs the main function asynchronously.
    """
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown initiated by user.")
    except Exception as e:
        logger.critical(f"Critical error: {e}", exc_info=True)

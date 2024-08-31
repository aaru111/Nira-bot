import os
import logging
from typing import List, Union, Any, Callable, Protocol, runtime_checkable
import asyncio
import discord
from discord.ext import commands
from aiohttp import ClientSession
from collections import Counter
from webserver import keep_alive
from abc import ABC, abstractmethod

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)


@runtime_checkable
class PrefixCogProtocol(Protocol):
    """Protocol for a Cog that provides dynamic prefixes."""

    async def get_prefix(self,
                         message: discord.Message) -> Union[List[str], str]:
        ...


class BotBase(ABC):
    """Abstract base class for the Bot to enforce certain methods."""

    @abstractmethod
    async def setup_hook(self) -> None:
        pass

    @abstractmethod
    async def load_all_cogs(self) -> None:
        pass

    @abstractmethod
    async def on_ready(self) -> None:
        pass

    @abstractmethod
    async def on_error(self, event_method: str, *args: Any,
                       **kwargs: Any) -> None:
        pass


class Bot(commands.Bot, BotBase):

    def __init__(self, command_prefix: Callable, intents: discord.Intents,
                 session: ClientSession, **kwargs: Any) -> None:
        super().__init__(command_prefix=command_prefix,
                         intents=intents,
                         **kwargs)
        self.session = session
        self.default_prefix = command_prefix if isinstance(
            command_prefix, str) else "."

    async def setup_hook(self) -> None:
        """Sets up necessary extensions and cogs."""
        await self._load_extension("jishaku")
        await self.load_all_cogs()

    async def load_all_cogs(self) -> None:
        """Loads all cogs from the cogs directory."""
        cog_dir = './cogs'
        cog_files = self._get_cog_files(cog_dir)
        results = await asyncio.gather(*(self._load_extension(f'cogs.{cog}')
                                         for cog in cog_files),
                                       return_exceptions=True)

        self._log_cog_load_results(cog_files, results)

    async def _load_extension(self, name: str) -> None:
        """Loads a single extension by name."""
        try:
            await self.load_extension(name)
            logger.info(f"Extension '{name}' loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load extension '{name}': {e}")
            # Optionally continue without raising to keep loading other extensions

    async def on_ready(self) -> None:
        """Triggered when the bot is ready."""
        if self.user:
            logger.info(f'Bot is ready as {self.user} (ID: {self.user.id}).')
        else:
            logger.error("Bot user is not set. This should not happen.")

    async def on_error(self, event_method: str, *args: Any,
                       **kwargs: Any) -> None:
        """Handles errors raised in event methods."""
        logger.exception(f'Unhandled exception in {event_method}')

    @staticmethod
    def _get_cog_files(cog_dir: str) -> List[str]:
        """Retrieves a list of cog files from the specified directory."""
        with os.scandir(cog_dir) as entries:
            return [
                entry.name[:-3] for entry in entries
                if entry.is_file() and entry.name.endswith('.py')
            ]

    @staticmethod
    def _log_cog_load_results(cog_files: List[str],
                              results: List[Any]) -> None:
        """Logs the results of loading cogs."""
        status = Counter(type(result).__name__ for result in results)
        logger.info(
            f"Cog loading complete. Success: {status.get('NoneType', 0)}, Failed: {sum(status.values()) - status.get('NoneType', 0)}"
        )

        for cog, result in zip(cog_files, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to load cog 'cogs.{cog}': {result}")


async def get_prefix(bot: Bot,
                     message: discord.Message) -> Union[List[str], str, None]:
    """Determines the prefix for commands based on the message context."""
    if not message.guild:
        return bot.default_prefix
    prefix_cog = bot.get_cog('PrefixCog')
    if isinstance(prefix_cog, PrefixCogProtocol):
        return await prefix_cog.get_prefix(message)
    return bot.default_prefix


async def main() -> None:
    """Main entry point for starting the bot."""
    intents = discord.Intents.all()
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("DISCORD_BOT_TOKEN environment variable not set.")
        return

    async with ClientSession() as session:
        bot = Bot(command_prefix=get_prefix,
                  case_insensitive=True,
                  intents=intents,
                  session=session)
        try:
            await bot.start(token)
        except discord.LoginFailure:
            logger.error("Invalid bot token provided.")
        except Exception:
            logger.exception("An error occurred during bot startup")
        finally:
            if not bot.is_closed():
                await bot.close()
            await session.close()  # Ensure the session is closed properly


if __name__ == "__main__":
    keep_alive()  # Start the webserver for keeping the bot alive
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown initiated by user.")
    except Exception:
        logger.exception("Critical error occurred")

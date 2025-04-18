import os
from typing import List, Union, Any, Callable, Protocol, runtime_checkable, Optional, TypeVar
import asyncio
import discord
from discord.ext import commands, tasks
from aiohttp import ClientSession
from abc import ABC, abstractmethod
from glob import glob
from loguru import logger
import itertools
import importlib.util
import sys

from cogs.help.utils.mentionable_tree import MentionableTree
from helpers.persistent import PersistentViewManager
from helpers.webserver import keep_alive

T = TypeVar('T')

@runtime_checkable
class PrefixCogProtocol(Protocol):
    async def get_prefix(self, message: discord.Message) -> Union[List[str], str]:
        ...

class BotBase(ABC):
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
    async def on_error(self, event_method: str, *args: Any, **kwargs: Any) -> None:
        pass

class Bot(commands.Bot, BotBase):
    def __init__(self, command_prefix: Union[str, Callable[[commands.Bot, discord.Message], Union[List[str], str]]], 
                 intents: discord.Intents, **kwargs: Any) -> None:
        super().__init__(command_prefix=command_prefix, intents=intents, **kwargs)
        self.session: Optional[ClientSession] = None
        self.http_session: Optional[ClientSession] = None
        self.default_prefix: str = command_prefix if isinstance(command_prefix, str) else "."
        self.status_list: itertools.cycle = itertools.cycle([
            discord.Activity(type=discord.ActivityType.streaming, name="Anime 🎥", 
                           url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            discord.Activity(type=discord.ActivityType.streaming, name="Cat Videos 🐱", 
                           url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            discord.Activity(type=discord.ActivityType.streaming, name="Call Of Duty 🎮", 
                           url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        ])
        self._persistent_views = PersistentViewManager(self)

    async def setup_hook(self) -> None:
        self.session = ClientSession()
        await self.load_extension("jishaku")
        await self.load_all_cogs()
        self.change_status.start()
        await self._persistent_views.setup_all_views()

    async def load_all_cogs(self) -> None:
        cog_path: str = os.path.join(os.path.dirname(__file__), 'cogs')
        cog_files: List[str] = glob(os.path.join(cog_path, '**', '[!_]*.py'), recursive=True)

        loaded_count: int = 0
        failed_count: int = 0

        for file in cog_files:
            try:
                module_path: str = os.path.relpath(file, os.path.dirname(__file__))
                module_name: str = os.path.splitext(module_path)[0].replace(os.path.sep, '.')

                spec = importlib.util.spec_from_file_location(module_name, file)
                if spec is None or spec.loader is None:
                    continue

                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

                if hasattr(module, 'setup'):
                    await self.load_extension(module_name)
                    logger.success(f"Successfully loaded extension: {module_name}")
                    loaded_count += 1

            except Exception as e:
                logger.error(f"Failed to load extension {module_name}: {e}")
                failed_count += 1

        logger.info(f"Cog loading completed: {loaded_count} loaded, {failed_count} failed.")

    async def on_ready(self) -> None:
        if self.user:
            logger.info(f'Bot is ready as {self.user} (ID: {self.user.id}).')
        else:
            logger.error("Bot user is not set. This should not happen.")

    async def on_error(self, event_method: str, *args: Any, **kwargs: Any) -> None:
        logger.exception(f'Unhandled exception in {event_method}')

    @tasks.loop(seconds=30)
    async def change_status(self) -> None:
        await self.change_presence(activity=next(self.status_list))

    @change_status.before_loop
    async def before_change_status(self) -> None:
        await self.wait_until_ready()

    async def close(self) -> None:
        logger.info("Closing bot and cleaning up resources...")
        if self.session:
            await self.session.close()
        await super().close()

async def get_prefix(bot: Bot, message: discord.Message) -> Union[List[str], str]:
    if not message.guild:
        return bot.default_prefix

    prefix_cog = bot.get_cog('PrefixCog')
    if isinstance(prefix_cog, PrefixCogProtocol):
        return await prefix_cog.get_prefix(message)
    return bot.default_prefix

async def main() -> None:
    intents: discord.Intents = discord.Intents.all()
    token: Optional[str] = os.getenv('DISCORD_BOT_TOKEN')

    if not token:
        logger.error("DISCORD_BOT_TOKEN environment variable not set.")
        return

    bot = Bot(command_prefix=get_prefix, 
             case_insensitive=True, 
             intents=intents, 
             tree_cls=MentionableTree)

    try:
        await bot.start(token)
    except discord.LoginFailure:
        logger.error("Invalid bot token provided.")
    except Exception:
        logger.exception("An error occurred during bot startup")
    finally:
        await bot.close()

if __name__ == "__main__":
    keep_alive()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown initiated by user.")
    except Exception:
        logger.exception("Critical error occurred")
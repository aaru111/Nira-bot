import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import datetime
import psutil
import platform
from typing import List, Optional
import time


class BotInfo(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.start_time = time.time()

    async def cog_unload(self) -> None:
        await self.session.close()

    def format_commit(self, commit_data: dict) -> str:
        sha = commit_data['sha'][:7]
        message = commit_data['commit']['message'].split('\n')[0]
        commit_url = commit_data['html_url']
        commit_time = datetime.datetime.strptime(
            commit_data['commit']['author']['date'], "%Y-%m-%dT%H:%M:%SZ")
        timestamp = discord.utils.format_dt(commit_time, "R")
        return f"[`{sha}`]({commit_url}) {timestamp} | {message}"

    async def get_latest_commits(self, limit: int = 5) -> List[str]:
        url = "https://api.github.com/repos/aaru111/Nira-bot/commits"
        async with self.session.get(url) as response:
            if response.status == 200:
                commits = await response.json()
                return [
                    self.format_commit(commit) for commit in commits[:limit]
                ]
            return ["Unable to fetch commit history"]

    def get_system_info(self) -> dict:
        return {
            'python_version':
            platform.python_version(),
            'discord_version':
            discord.__version__,
            'os':
            f"{platform.system()} {platform.release()}",
            'cpu_usage':
            f"{psutil.cpu_percent()}%",
            'memory_usage':
            f"{psutil.Process().memory_percent():.2f}%",
            'uptime':
            str(datetime.timedelta(seconds=int(time.time() - self.start_time)))
        }

    def get_bot_stats(self) -> dict:
        total_members = sum(guild.member_count or 0
                            for guild in self.bot.guilds)
        total_channels = sum(len(guild.channels) for guild in self.bot.guilds)

        return {
            'servers': len(self.bot.guilds),
            'users': total_members,
            'channels': total_channels,
            'commands': len(self.bot.commands),
            'latency': f"{round(self.bot.latency * 1000)}ms"
        }

    @commands.hybrid_command(
        name="botinfo", description="Shows detailed information about the bot")
    @app_commands.describe(show_commits="Whether to show recent commits",
                           show_system="Whether to show system information",
                           show_stats="Whether to show bot statistics")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True,
                                   dms=True,
                                   private_channels=True)
    async def botinfo(self,
                      ctx: commands.Context,
                      show_commits: Optional[bool] = True,
                      show_system: Optional[bool] = True,
                      show_stats: Optional[bool] = True) -> None:
        await ctx.defer()
        try:
            if self.bot.user is None:
                raise RuntimeError("Bot user is not initialized")

            app_info = await self.bot.application_info()
            bot_name = self.bot.user.name
            bot_avatar = self.bot.user.display_avatar.url

            embed = discord.Embed(
                title="Bot Information",
                description=
                f"**{bot_name}** - Made by {app_info.owner.mention}",
                color=discord.Color.from_rgb(239, 158, 240),
                timestamp=datetime.datetime.utcnow())

            embed.set_thumbnail(url=bot_avatar)

            if show_stats:
                stats = self.get_bot_stats()
                stats_text = (f"**Servers:** {stats['servers']}\n"
                              f"**Users:** {stats['users']}\n"
                              f"**Channels:** {stats['channels']}\n"
                              f"**Commands:** {stats['commands']}\n"
                              f"**Latency:** {stats['latency']}")
                embed.add_field(name="📊 Bot Statistics",
                                value=stats_text,
                                inline=True)

            if show_system:
                sys_info = self.get_system_info()
                sys_text = (f"**Python:** {sys_info['python_version']}\n"
                            f"**Discord.py:** {sys_info['discord_version']}\n"
                            f"**OS:** {sys_info['os']}\n"
                            f"**CPU Usage:** {sys_info['cpu_usage']}\n"
                            f"**Memory Usage:** {sys_info['memory_usage']}\n"
                            f"**Uptime:** {sys_info['uptime']}")
                embed.add_field(name="💻 System Information",
                                value=sys_text,
                                inline=True)

            if show_commits:
                latest_commits = await self.get_latest_commits()
                embed.add_field(name="📝 Latest Changes",
                                value="\n".join(latest_commits),
                                inline=False)

            author_avatar = ctx.author.display_avatar.url if ctx.author.display_avatar else None

            embed.set_footer(text=f"Requested by {ctx.author}",
                             icon_url=author_avatar)

            await ctx.send(embed=embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="Error",
                description=
                f"An error occurred while fetching information: {str(e)}",
                color=discord.Color.red())
            await ctx.send(embed=error_embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BotInfo(bot))

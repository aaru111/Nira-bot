import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List, Literal
from database import db, Database
import asyncpg
import aiohttp


class TableSelect(discord.ui.Select):

    def __init__(self, tables: List[str], placeholder: str):
        options = [discord.SelectOption(label=table) for table in tables]
        super().__init__(placeholder=placeholder,
                         min_values=1,
                         max_values=1,
                         options=options)

    async def callback(self, interaction: discord.Interaction):
        table = self.values[0]
        view = ActionView(table, self.view.tables)  # type: ignore
        await interaction.response.edit_message(
            content=f"Selected table: {table}\nChoose an action:", view=view)


class TableView(discord.ui.View):

    def __init__(self, tables: List[str]):
        super().__init__()
        self.tables = tables
        for i in range(0, len(tables), 25):
            self.add_item(
                TableSelect(
                    tables[i:i + 25],
                    f"Select a table ({i+1}-{min(i+25, len(tables))})"))


class ActionSelect(discord.ui.Select):

    def __init__(self, table: str):
        self.table = table
        options = [
            discord.SelectOption(label="Delete all rows", value="delete"),
            discord.SelectOption(label="Drop table", value="drop"),
            discord.SelectOption(label="Show table structure",
                                 value="structure")
        ]
        super().__init__(placeholder="Choose an action",
                         min_values=1,
                         max_values=1,
                         options=options)

    async def callback(self, interaction: discord.Interaction):
        action = self.values[0]
        try:
            if action == "delete":
                query = f"DELETE FROM {self.table};"
                await db.execute(query)
                await interaction.response.edit_message(
                    content=f"All rows from {self.table} have been deleted.",
                    view=self.view)

            elif action == "drop":
                query = f"DROP TABLE IF EXISTS {self.table};"
                await db.execute(query)
                self.view.tables.remove(self.table)  # type: ignore

                if self.view.tables:  # type: ignore
                    new_view = TableView(self.view.tables)  # type: ignore
                    await interaction.response.edit_message(
                        content=
                        f"The table {self.table} has been dropped. Select another table:",
                        view=new_view)
                else:
                    await interaction.response.edit_message(
                        content=
                        f"The table {self.table} has been dropped. No more tables available.",
                        view=None)

            elif action == "structure":
                query = """
                SELECT column_name, data_type, character_maximum_length
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE table_name = $1;
                """
                results = await db.fetch(query, self.table)
                structure = "\n".join([
                    f"{r['column_name']} - {r['data_type']}({r['character_maximum_length'] or ''})"
                    for r in results
                ])
                await interaction.response.edit_message(
                    content=
                    f"Structure of {self.table}:\n```\n{structure}\n```",
                    view=self.view)

        except Exception as e:
            await interaction.response.edit_message(
                content=f"An error occurred: {str(e)}", view=self.view)


class ActionView(discord.ui.View):

    def __init__(self, table: str, tables: List[str]):
        super().__init__()
        self.add_item(ActionSelect(table))
        self.tables = tables

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey)
    async def back_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        view = TableView(self.tables)
        await interaction.response.edit_message(
            content="Select a table to manage:", view=view)


class Owner(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = db
        self.session = aiohttp.ClientSession()

    async def cog_load(self) -> None:
        await self.db.initialize()
        await self.create_tables()

    async def cog_unload(self):
        await self.db.close()
        await self.session.close()

    async def create_tables(self) -> None:
        query = """
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            is_premium BOOLEAN DEFAULT FALSE
        );
        """
        await self.db.execute(query)

    async def is_premium(self, user_id: int) -> bool:
        if user_id == self.bot.owner_id:
            return True
        query = "SELECT is_premium FROM users WHERE user_id = $1;"
        result = await self.db.fetch(query, user_id)
        return bool(result[0]['is_premium']) if result else False

    @commands.command()
    @commands.is_owner()
    async def set_premium(self, ctx: commands.Context,
                          user: discord.Member) -> None:
        """Set a user as premium (Owner only)"""
        try:
            if user.id == self.bot.owner_id:
                embed = discord.Embed(
                    title="Premium Status",
                    description=
                    f"{user.mention} is already a premium user as the bot owner!",
                    color=discord.Color.blue())
                await ctx.send(embed=embed)
                return

            is_already_premium = await self.is_premium(user.id)
            if is_already_premium:
                embed = discord.Embed(
                    title="Premium Status",
                    description=f"{user.mention} is already a premium user.",
                    color=discord.Color.blue())
                await ctx.send(embed=embed)
                return

            query = """
            INSERT INTO users (user_id, is_premium)
            VALUES ($1, TRUE)
            ON CONFLICT (user_id)
            DO UPDATE SET is_premium = TRUE;
            """
            await self.db.execute(query, user.id)

            embed = discord.Embed(
                title="Premium Status Updated",
                description=f"{user.mention} is now a premium user!",
                color=discord.Color.green())
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    @commands.command()
    @commands.is_owner()
    async def remove_premium(self, ctx: commands.Context,
                             user: discord.Member) -> None:
        """Remove premium status from a user (Owner only)"""
        try:
            if user.id == self.bot.owner_id:
                embed = discord.Embed(
                    title="Premium Status",
                    description=
                    "Cannot remove premium status from the bot owner.",
                    color=discord.Color.red())
                await ctx.send(embed=embed)
                return

            is_premium = await self.is_premium(user.id)
            if not is_premium:
                embed = discord.Embed(
                    title="Premium Status",
                    description=
                    f"{user.mention} is not currently a premium user.",
                    color=discord.Color.blue())
                await ctx.send(embed=embed)
                return

            query = "DELETE FROM users WHERE user_id = $1;"
            await self.db.execute(query, user.id)

            embed = discord.Embed(
                title="Premium Status Updated",
                description=f"{user.mention} is no longer a premium user.",
                color=discord.Color.orange())
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    @commands.command()
    @commands.is_owner()
    async def list_premium(self, ctx: commands.Context) -> None:
        """List all premium users (Owner only)"""
        try:
            query = "SELECT user_id FROM users WHERE is_premium = TRUE;"
            results = await self.db.fetch(query)

            premium_users = []
            if self.bot.owner_id:
                premium_users.append(f"Bot Owner (ID: {self.bot.owner_id})")

            for row in results:
                user = self.bot.get_user(row['user_id'])
                if user:
                    premium_users.append(f"{user.mention} (ID: {user.id})")
                else:
                    premium_users.append(
                        f"Unknown User (ID: {row['user_id']})")

            if not premium_users:
                embed = discord.Embed(
                    title="Premium Users",
                    description="There are no premium users at the moment.",
                    color=discord.Color.light_gray())
            else:
                premium_list = "\n".join(premium_users)
                embed = discord.Embed(title="Premium Users",
                                      description=premium_list,
                                      color=discord.Color.gold())
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    @commands.command()
    async def premium_status(self,
                             ctx: commands.Context,
                             user: Optional[discord.Member] = None) -> None:
        """Check premium status of a user"""
        try:
            target_user = user or ctx.author
            is_premium = await self.is_premium(target_user.id)
            status = "is" if is_premium else "is not"

            embed = discord.Embed(
                title="Premium Status",
                description=f"{target_user.mention} {status} a premium user.",
                color=discord.Color.blue()
                if is_premium else discord.Color.light_gray())
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def sync(self,
                   ctx: commands.Context,
                   guilds: commands.Greedy[discord.Object],
                   spec: Optional[Literal["~", "*", "^"]] = None) -> None:
        """Sync slash commands"""
        try:
            if not guilds:
                if spec == "~":
                    synced = await ctx.bot.tree.sync(guild=ctx.guild)
                elif spec == "*":
                    ctx.bot.tree.copy_global_to(guild=ctx.guild)
                    synced = await ctx.bot.tree.sync(guild=ctx.guild)
                elif spec == "^":
                    ctx.bot.tree.clear_commands(guild=ctx.guild)
                    await ctx.bot.tree.sync(guild=ctx.guild)
                    synced = []
                else:
                    synced = await ctx.bot.tree.sync()
                await ctx.send(
                    f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
                )
                return

            ret = 0
            for guild in guilds:
                try:
                    await ctx.bot.tree.sync(guild=guild)
                    ret += 1
                except discord.HTTPException:
                    pass
            await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    @app_commands.command()
    async def manage_database(self, interaction: discord.Interaction):
        """Manage database tables (Owner only)"""
        try:
            if interaction.user.id != self.bot.owner_id:
                await interaction.response.send_message(
                    "This command is only available to the bot owner.",
                    ephemeral=True)
                return

            query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE';
            """
            tables = await self.db.fetch(query)
            table_names = [table['table_name'] for table in tables]

            view = TableView(table_names)
            await interaction.response.send_message(
                "Select a table to manage:", view=view)
        except Exception as e:
            await interaction.response.send_message(
                f"An error occurred: {str(e)}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Owner(bot))

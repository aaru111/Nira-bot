import discord
from discord import app_commands
from discord.ext import commands
import random
from PIL import Image, ImageDraw, ImageFont
import io
from typing import Optional, Dict
from database import db
import time


class XPRateSelect(discord.ui.Select):

    def __init__(self, current_min, current_max):
        options = [
            discord.SelectOption(label='Low (5-15 XP)',
                                 description='Slower progression',
                                 value='5,15'),
            discord.SelectOption(label='Medium (10-20 XP)',
                                 description='Balanced progression',
                                 value='10,20'),
            discord.SelectOption(label='High (15-25 XP)',
                                 description='Faster progression',
                                 value='15,25')
        ]
        super().__init__(
            placeholder=f'XP Rate (Current: {current_min}-{current_max})',
            options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.xp_min, self.view.xp_max = map(int,
                                                 self.values[0].split(','))
        await self.view.update_message(interaction)


class XPCooldownSelect(discord.ui.Select):

    def __init__(self, current_cooldown):
        options = [
            discord.SelectOption(label='Short (30 seconds)',
                                 description='More frequent XP gains',
                                 value='30'),
            discord.SelectOption(label='Medium (60 seconds)',
                                 description='Balanced XP gains',
                                 value='60'),
            discord.SelectOption(label='Long (120 seconds)',
                                 description='Less frequent XP gains',
                                 value='120')
        ]
        super().__init__(
            placeholder=f'XP Cooldown (Current: {current_cooldown}s)',
            options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.xp_cooldown = int(self.values[0])
        await self.view.update_message(interaction)


class ToggleButton(discord.ui.Button):

    def __init__(self, is_enabled: bool):
        super().__init__(style=discord.ButtonStyle.green
                         if is_enabled else discord.ButtonStyle.red,
                         label='Enabled' if is_enabled else 'Disabled',
                         custom_id='toggle')

    async def callback(self, interaction: discord.Interaction):
        self.view.is_enabled = not self.view.is_enabled
        self.style = discord.ButtonStyle.green if self.view.is_enabled else discord.ButtonStyle.red
        self.label = 'Enabled' if self.view.is_enabled else 'Disabled'
        await self.view.update_message(interaction)


class ResetButton(discord.ui.Button):

    def __init__(self):
        super().__init__(style=discord.ButtonStyle.danger,
                         label='Reset All Levels')

    async def callback(self, interaction: discord.Interaction):
        confirm_view = ConfirmView()
        await interaction.response.send_message(
            "Are you sure you want to reset all levels?",
            view=confirm_view,
            ephemeral=True)
        await confirm_view.wait()
        if confirm_view.value:
            query = "DELETE FROM user_levels WHERE guild_id = $1;"
            await db.execute(query, interaction.guild_id)
            await interaction.followup.send("All levels have been reset.",
                                            ephemeral=True)
        else:
            await interaction.followup.send("Level reset cancelled.",
                                            ephemeral=True)


class ConfirmView(discord.ui.View):

    def __init__(self):
        super().__init__()
        self.value = None

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction,
                      button: discord.ui.Button):
        self.value = True
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        self.value = False
        self.stop()


class ConfirmButton(discord.ui.Button):

    def __init__(self):
        super().__init__(style=discord.ButtonStyle.blurple, label='Confirm')

    async def callback(self, interaction: discord.Interaction):
        self.view.confirmed = True
        await interaction.response.edit_message(content='Setup confirmed!',
                                                view=None)
        self.view.stop()


class SetupView(discord.ui.View):

    def __init__(self, guild_settings: Dict):
        super().__init__()
        self.add_item(
            XPRateSelect(guild_settings['xp_min'], guild_settings['xp_max']))
        self.add_item(XPCooldownSelect(guild_settings['xp_cooldown']))
        self.add_item(ToggleButton(guild_settings['enabled']))
        self.add_item(ResetButton())
        self.add_item(ConfirmButton())
        self.xp_min = guild_settings['xp_min']
        self.xp_max = guild_settings['xp_max']
        self.xp_cooldown = guild_settings['xp_cooldown']
        self.is_enabled = guild_settings['enabled']
        self.confirmed = False

    async def update_message(self, interaction: discord.Interaction):
        content = f"Current Configuration:\n" \
                  f"Status: {'Enabled' if self.is_enabled else 'Disabled'}\n" \
                  f"XP Range: {self.xp_min}-{self.xp_max}\n" \
                  f"XP Cooldown: {self.xp_cooldown} seconds\n\n" \
                  f"Please select your preferences:"
        await interaction.response.edit_message(content=content, view=self)


class Leveling(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.leveling_settings: Dict[int, Dict] = {}
        self.cooldowns: Dict[int, Dict[int, float]] = {}

    async def cog_load(self):
        await self.create_tables()
        await self.load_settings()

    async def create_tables(self):
        query = """
        CREATE TABLE IF NOT EXISTS user_levels (
            user_id BIGINT,
            guild_id BIGINT,
            xp INT DEFAULT 0,
            level INT DEFAULT 0,
            PRIMARY KEY (user_id, guild_id)
        );
        CREATE TABLE IF NOT EXISTS guild_leveling_settings (
            guild_id BIGINT PRIMARY KEY,
            enabled BOOLEAN DEFAULT FALSE,
            xp_min INT DEFAULT 10,
            xp_max INT DEFAULT 20,
            xp_cooldown INT DEFAULT 60
        );
        """
        await db.execute(query)

    async def load_settings(self):
        query = "SELECT * FROM guild_leveling_settings;"
        results = await db.fetch(query)
        for row in results:
            self.leveling_settings[row['guild_id']] = {
                'enabled': row['enabled'],
                'xp_min': row['xp_min'],
                'xp_max': row['xp_max'],
                'xp_cooldown': row['xp_cooldown']
            }

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild_settings = self.leveling_settings.get(message.guild.id)
        if not guild_settings or not guild_settings['enabled']:
            return

        user_id = message.author.id
        guild_id = message.guild.id

        current_time = time.time()
        if guild_id not in self.cooldowns:
            self.cooldowns[guild_id] = {}
        last_message_time = self.cooldowns[guild_id].get(user_id, 0)
        if current_time - last_message_time < guild_settings['xp_cooldown']:
            return

        xp_gained = random.randint(guild_settings['xp_min'],
                                   guild_settings['xp_max'])
        await self.add_xp(user_id, guild_id, xp_gained)
        self.cooldowns[guild_id][user_id] = current_time

    async def add_xp(self, user_id: int, guild_id: int, xp: int) -> bool:
        query = """
        INSERT INTO user_levels (user_id, guild_id, xp, level)
        VALUES ($1, $2, $3, 0)
        ON CONFLICT (user_id, guild_id)
        DO UPDATE SET xp = user_levels.xp + $3
        RETURNING xp, level;
        """
        result = await db.fetch(query, user_id, guild_id, xp)
        new_xp, current_level = result[0]['xp'], result[0]['level']

        new_level = self.calculate_level(new_xp)
        if new_level > current_level:
            await self.update_level(user_id, guild_id, new_level)
            return True
        return False

    def calculate_level(self, xp: int) -> int:
        return int((xp // 100)**0.5)

    async def update_level(self, user_id: int, guild_id: int, new_level: int):
        query = """
        UPDATE user_levels
        SET level = $3
        WHERE user_id = $1 AND guild_id = $2;
        """
        await db.execute(query, user_id, guild_id, new_level)

    async def get_level(self, user_id: int, guild_id: int) -> int:
        query = "SELECT level FROM user_levels WHERE user_id = $1 AND guild_id = $2;"
        result = await db.fetch(query, user_id, guild_id)
        return result[0]['level'] if result else 0

    level_group = app_commands.Group(name="level",
                                     description="Leveling system commands")

    @level_group.command(name="rank")
    async def rank(self,
                   interaction: discord.Interaction,
                   member: Optional[discord.Member] = None):
        """Check your or another member's rank"""
        await interaction.response.defer()
        try:
            guild_settings = self.leveling_settings.get(interaction.guild_id)
            if not guild_settings or not guild_settings['enabled']:
                return await interaction.followup.send(
                    "Leveling system is not enabled in this server.",
                    ephemeral=True)

            member = member or interaction.user
            user_id, guild_id = member.id, interaction.guild_id

            query = """
            SELECT xp, level,
                   ROW_NUMBER() OVER (ORDER BY xp DESC) as rank
            FROM user_levels
            WHERE guild_id = $1 AND user_id = $2;
            """
            result = await db.fetch(query, guild_id, user_id)

            if not result:
                return await interaction.followup.send(
                    f"{member.display_name} has not gained any XP yet.",
                    ephemeral=True)

            xp, level, rank = result[0]['xp'], result[0]['level'], result[0][
                'rank']
            card = await self.create_rank_card(member, xp, level, rank)

            await interaction.followup.send(
                file=discord.File(card, filename="rank_card.png"))
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}",
                                            ephemeral=True)

    async def create_rank_card(self, member: discord.Member, xp: int,
                               level: int, rank: int) -> io.BytesIO:
        card_width, card_height = 400, 150
        card = Image.new('RGBA', (card_width, card_height), (0, 0, 0, 0))

        # Fetch and process avatar
        avatar_size = 100
        avatar_url = member.display_avatar.replace(format='png', size=128)
        avatar_data = io.BytesIO(await avatar_url.read())
        avatar_image = Image.open(avatar_data).convert('RGBA')
        avatar_image = avatar_image.resize((avatar_size, avatar_size),
                                           Image.Resampling.LANCZOS)

        # Create circular mask for avatar
        mask = Image.new('L', (avatar_size, avatar_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)

        # Create gradient background
        gradient = Image.new('RGBA', (card_width, card_height), (0, 0, 0, 0))
        gradient_draw = ImageDraw.Draw(gradient)

        # Use a default color if we can't get a dominant color from the avatar
        try:
            avatar_colors = avatar_image.getcolors(avatar_image.size[0] *
                                                   avatar_image.size[1])
            dominant_color = max(avatar_colors, key=lambda x: x[0])[1][:3]
        except:
            dominant_color = (100, 100, 100
                              )  # Default gray if color extraction fails

        for y in range(card_height):
            alpha = int(255 * (1 - y / card_height))
            gradient_draw.line([(0, y), (card_width, y)],
                               fill=dominant_color + (alpha, ))

        # Composite gradient onto card
        card = Image.alpha_composite(card, gradient)

        # Paste avatar onto card
        card.paste(avatar_image, (20, 25), mask)

        draw = ImageDraw.Draw(card)

        # Load fonts (adjust paths as needed)
        try:
            title_font = ImageFont.truetype("fonts/ndot47.ttf", 30)
            text_font = ImageFont.truetype("fonts/InterVariable.ttf", 20)
        except IOError:
            # Fallback to default font if custom fonts are not available
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()

        # Draw text
        draw.text((140, 20),
                  member.display_name,
                  font=title_font,
                  fill=(255, 255, 255, 255))
        draw.text((140, 60),
                  f"Rank: #{rank}",
                  font=text_font,
                  fill=(255, 255, 255, 255))
        draw.text((140, 90),
                  f"Level: {level}",
                  font=text_font,
                  fill=(255, 255, 255, 255))

        # Draw XP progress bar
        xp_to_next_level = (level + 1)**2 * 100
        progress = xp / xp_to_next_level
        bar_width, bar_height = 200, 20
        bar_background = Image.new('RGBA', (bar_width, bar_height),
                                   (44, 47, 51, 180))
        bar_foreground = Image.new('RGBA',
                                   (int(bar_width * progress), bar_height),
                                   dominant_color + (180, ))

        # Create rounded corners for progress bar
        def round_corner(radius, fill):
            corner = Image.new('RGBA', (radius, radius), (0, 0, 0, 0))
            draw = ImageDraw.Draw(corner)
            draw.pieslice((0, 0, radius * 2, radius * 2), 180, 270, fill=fill)
            return corner

        radius = 10
        corner = round_corner(radius, (44, 47, 51, 180))
        bar_background.paste(corner, (0, 0))
        bar_background.paste(corner.rotate(90), (0, bar_height - radius))
        bar_background.paste(corner.rotate(180),
                             (bar_width - radius, bar_height - radius))
        bar_background.paste(corner.rotate(270), (bar_width - radius, 0))

        # Paste progress bars
        card.paste(bar_background, (180, 120), bar_background)
        card.paste(bar_foreground, (180, 120), bar_foreground)

        # Draw XP text
        xp_text = f"XP: {xp}/{xp_to_next_level}"
        text_width = draw.textlength(xp_text, font=text_font)
        draw.text((180 + (bar_width - text_width) / 2, 120),
                  xp_text,
                  font=text_font,
                  fill=(255, 255, 255, 255))

        # Save and return
        buffer = io.BytesIO()
        card.save(buffer, 'PNG')
        buffer.seek(0)
        return buffer

    @level_group.command(name="setup")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_wizard(self, interaction: discord.Interaction):
        """Setup wizard for the leveling system"""
        guild_settings = self.leveling_settings.get(interaction.guild_id, {
            'enabled': False,
            'xp_min': 10,
            'xp_max': 20,
            'xp_cooldown': 60
        })

        view = SetupView(guild_settings)

        content = f"Current Configuration:\n" \
                  f"Status: {'Enabled' if guild_settings['enabled'] else 'Disabled'}\n" \
                  f"XP Range: {guild_settings['xp_min']}-{guild_settings['xp_max']}\n" \
                  f"XP Cooldown: {guild_settings['xp_cooldown']} seconds\n\n" \
                  f"Please select your preferences:"

        await interaction.response.send_message(content=content, view=view)

        timeout = await view.wait()
        if timeout:
            await interaction.edit_original_message(
                content="Setup wizard timed out. No changes were made.",
                view=None)
            return

        if view.confirmed:
            self.leveling_settings[interaction.guild_id] = {
                'enabled': view.is_enabled,
                'xp_min': view.xp_min,
                'xp_max': view.xp_max,
                'xp_cooldown': view.xp_cooldown
            }

            query = """
            INSERT INTO guild_leveling_settings (guild_id, enabled, xp_min, xp_max, xp_cooldown)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (guild_id)
            DO UPDATE SET enabled = $2, xp_min = $3, xp_max = $4, xp_cooldown = $5;
            """
            await db.execute(query, interaction.guild_id, view.is_enabled,
                             view.xp_min, view.xp_max, view.xp_cooldown)

            status = "enabled" if view.is_enabled else "disabled"
            await interaction.edit_original_message(
                content=f"Leveling system setup complete!\n"
                f"Status: {status}\n"
                f"XP Range: {view.xp_min}-{view.xp_max}\n"
                f"XP Cooldown: {view.xp_cooldown} seconds",
                view=None)
        else:
            await interaction.edit_original_message(
                content="Setup cancelled. No changes were made.", view=None)

    @level_group.command(name="leaderboard")
    async def leaderboard(self,
                          interaction: discord.Interaction,
                          top: int = 10):
        """Show the server's XP leaderboard"""
        await interaction.response.defer()
        try:
            guild_settings = self.leveling_settings.get(interaction.guild_id)
            if not guild_settings or not guild_settings['enabled']:
                return await interaction.followup.send(
                    "Leveling system is not enabled in this server.",
                    ephemeral=True)

            query = """
            SELECT user_id, xp, level,
                   ROW_NUMBER() OVER (ORDER BY xp DESC) as rank
            FROM user_levels
            WHERE guild_id = $1
            ORDER BY xp DESC
            LIMIT $2;
            """
            results = await db.fetch(query, interaction.guild_id, top)

            if not results:
                return await interaction.followup.send(
                    "No one has gained any XP yet.", ephemeral=True)

            leaderboard = "XP Leaderboard:\n\n"
            for row in results:
                user = interaction.guild.get_member(row['user_id'])
                if user:
                    leaderboard += f"{row['rank']}. {user.display_name}: Level {row['level']} (XP: {row['xp']})\n"

            await interaction.followup.send(leaderboard)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}",
                                            ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leveling(bot))

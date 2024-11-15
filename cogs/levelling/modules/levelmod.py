__all__ = [
    "XPRateSelect",
    "XPCooldownSelect",
    "ToggleButton",
    "AnnouncementChannelSelect",
    "LevelUpMessageModal",
    "ConfirmView",
    "BackgroundView",
    "BackgroundSelect",
    "SetupView",
]
import discord
from typing import Optional, Dict, List
import os
import base64

from helpers.database import db



class SetupView(discord.ui.View):

  def __init__(self, guild_settings: Dict[str, int | bool | Optional[int]],
               role_rewards: Dict[int, int]):
    super().__init__()
    self.xp_min: int = guild_settings['xp_min']
    self.xp_max: int = guild_settings['xp_max']
    self.xp_cooldown: int = guild_settings['xp_cooldown']
    self.is_enabled: bool = guild_settings['enabled']
    self.announcement_channel: Optional[int] = guild_settings.get(
        'announcement_channel')
    self.level_up_message: str = guild_settings.get(
        'level_up_message',
        "Congratulations {user_mention}! You've reached level {new_level}!")
    self.confirmed: bool = False
    self.role_rewards: Dict[int, int] = role_rewards
    self.message = None

    self.add_item(ToggleButton(self.is_enabled))
    self.add_item(XPRateSelect(self.xp_min, self.xp_max))
    self.add_item(XPCooldownSelect(self.xp_cooldown))
    self.add_item(AnnouncementChannelSelect(self.announcement_channel))

  async def on_timeout(self):
    if self.message:
      for item in self.children:
        item.disabled = True
      await self.message.edit(view=self)

  @discord.ui.button(label='Edit Level Up Message',
                     style=discord.ButtonStyle.blurple)
  async def edit_message_button(self, interaction: discord.Interaction,
                                button: discord.ui.Button):
    modal = LevelUpMessageModal(self.level_up_message, self)
    await interaction.response.send_modal(modal)
    await modal.wait()

  @discord.ui.button(label='Reset All Levels',
                     style=discord.ButtonStyle.danger)
  async def reset_levels_button(self, interaction: discord.Interaction,
                                button: discord.ui.Button):
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
      await interaction.followup.send("Level reset cancelled.", ephemeral=True)

  @discord.ui.button(label='Save Changes', style=discord.ButtonStyle.green)
  async def confirm_button(self, interaction: discord.Interaction,
                           button: discord.ui.Button):
    self.confirmed = True
    await interaction.response.edit_message(content='Setup confirmed!',
                                            view=None,
                                            embed=None)
    self.stop()

  async def update_embed(self, interaction: discord.Interaction):
    embed = discord.Embed(title="🛠️ Leveling System Configuration",
                          color=discord.Color.blue())
    embed.add_field(name="Status",
                    value="🟢 Enabled" if self.is_enabled else "🔴 Disabled",
                    inline=False)
    embed.add_field(name="XP Range",
                    value=f"{self.xp_min}-{self.xp_max}",
                    inline=True)
    embed.add_field(name="XP Cooldown",
                    value=f"{self.xp_cooldown} seconds",
                    inline=True)
    embed.add_field(name="Announcement Channel",
                    value=f"<#{self.announcement_channel}>"
                    if self.announcement_channel else "Not set",
                    inline=False)
    embed.add_field(name="Level Up Message",
                    value=f"```{self.level_up_message}```",
                    inline=False)

    # Add role rewards fields
    sorted_rewards = sorted(self.role_rewards.items())
    for i in range(0, len(sorted_rewards), 6):
      chunk = sorted_rewards[i:i + 6]
      value = "\n".join(
          [f"Level {level}: <@&{role_id}>" for level, role_id in chunk])
      embed.add_field(name=f"Role Rewards {i//6 + 1}",
                      value=value or "No rewards set",
                      inline=True)

    await interaction.response.edit_message(embed=embed, view=self)


class XPRateSelect(discord.ui.Select):

  def __init__(self, current_min: int, current_max: int):
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
    current_option = next(
        (opt
         for opt in options if opt.value == f"{current_min},{current_max}"),
        None)
    placeholder = f'XP Rate: {current_min}-{current_max}'
    if current_option:
      placeholder = f'XP Rate: {current_option.label}'
    super().__init__(placeholder=placeholder, options=options)

  async def callback(self, interaction: discord.Interaction):
    self.view.xp_min, self.view.xp_max = map(int, self.values[0].split(','))
    selected_option = next(opt for opt in self.options
                           if opt.value == self.values[0])
    self.placeholder = f'XP Rate: {selected_option.label}'
    await self.view.update_embed(interaction)


class XPCooldownSelect(discord.ui.Select):

  def __init__(self, current_cooldown: int):
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
    current_option = next(
        (opt for opt in options if opt.value == str(current_cooldown)), None)
    placeholder = f'XP Cooldown: {current_cooldown}s'
    if current_option:
      placeholder = f'XP Cooldown: {current_option.label}'
    super().__init__(placeholder=placeholder, options=options)

  async def callback(self, interaction: discord.Interaction):
    self.view.xp_cooldown = int(self.values[0])
    selected_option = next(opt for opt in self.options
                           if opt.value == self.values[0])
    self.placeholder = f'XP Cooldown: {selected_option.label}'
    await self.view.update_embed(interaction)


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
    await self.view.update_embed(interaction)


class AnnouncementChannelSelect(discord.ui.ChannelSelect):

  def __init__(self, current_channel_id: Optional[int]):
    super().__init__(
        channel_types=[discord.ChannelType.text],
        placeholder=f'Announcement Channel: {current_channel_id or "Not set"}',
        min_values=0,
        max_values=1)

  async def callback(self, interaction: discord.Interaction):
    self.view.announcement_channel = self.values[0].id if self.values else None
    await self.view.update_embed(interaction)


class LevelUpMessageModal(discord.ui.Modal, title='Edit Level Up Message'):
  message = discord.ui.TextInput(
      label='New Level Up Message',
      style=discord.TextStyle.paragraph,
      placeholder=
      'Enter the new level up message... Use {user_mention}, {new_level}, and {role_rewards} as placeholders.',
      required=True,
      max_length=1000)

  def __init__(self, current_message: str, view: 'SetupView'):
    super().__init__()
    self.message.default = current_message
    self.view = view

  async def on_submit(self, interaction: discord.Interaction):
    self.view.level_up_message = self.message.value
    await self.view.update_embed(interaction)
    self.stop()


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


class BackgroundSelect(discord.ui.Select):

  def __init__(self, options: List[discord.SelectOption], user_id: int,
               guild_id: int):
    super().__init__(placeholder="Choose a background", options=options)
    self.user_id = user_id
    self.guild_id = guild_id

  async def callback(self, interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    background = self.values[0]

    with open(os.path.join("backgrounds", background), "rb") as image_file:
      image_data = image_file.read()
      image_base64 = base64.b64encode(image_data).decode('utf-8')

    query = """
        INSERT INTO user_backgrounds (user_id, guild_id, background)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, guild_id)
        DO UPDATE SET background = $3;
        """
    await db.execute(query, self.user_id, self.guild_id, image_base64)

    await interaction.followup.send(
        f"Your rank card background has been updated to {background}.",
        ephemeral=True)


class BackgroundView(discord.ui.View):

  def __init__(self, options: List[discord.SelectOption], user_id: int,
               guild_id: int):
    super().__init__()
    self.add_item(BackgroundSelect(options, user_id, guild_id))

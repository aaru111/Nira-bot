import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal, List, Optional, Union


class AutoMod(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot

    automod_group: app_commands.Group = app_commands.Group(
        name="automod", description="AutoMod commands")

    @automod_group.command(name="create_rule")
    @app_commands.describe(
        name="The name of the AutoMod rule",
        preset="Preset for the AutoMod rule",
        custom_keywords="Custom keywords to filter (comma-separated)")
    @app_commands.choices(preset=[
        app_commands.Choice(name="Profanity Filter", value="profanity"),
        app_commands.Choice(name="Spam Prevention", value="spam"),
        app_commands.Choice(name="Scam Links", value="scam"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def create_automod_rule(
            self,
            interaction: discord.Interaction,
            name: str,
            preset: Literal["profanity", "spam", "scam"],
            custom_keywords: Optional[str] = None) -> None:
        """Create an AutoMod rule using presets or custom keywords"""
        preset_keywords: dict[str, List[str]] = {
            "profanity": [
                "bad_word1", "bad_word2", "bad_word3", "swear1", "swear2",
                "offensive1", "offensive2"
            ],
            "spam": [
                "discord.gg", "http://", "https://", "www.", ".com", ".net",
                ".org", "join my server"
            ],
            "scam": [
                "free nitro", "steam gift", "click here", "limited offer",
                "exclusive deal", "claim your prize", "you've won"
            ]
        }

        keywords: List[str] = preset_keywords.get(preset, [])
        if custom_keywords:
            keywords.extend([kw.strip() for kw in custom_keywords.split(',')])

        try:
            rule: discord.AutoModRule = await interaction.guild.create_automod_rule(
                name=name,
                event_type=discord.AutoModRuleEventType.message_send,
                trigger=discord.AutoModTrigger(keyword_filter=keywords),
                actions=[
                    discord.AutoModRuleAction(
                        type=discord.AutoModRuleActionType.block_message,
                        custom_message="This message was blocked by AutoMod.")
                ],
                enabled=True,
                exempt_roles=[],
                exempt_channels=[])
            await interaction.response.send_message(
                f"AutoMod rule '{name}' created successfully! Rule ID: {rule.id}"
            )
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"Failed to create AutoMod rule: {e}")

    @automod_group.command(name="view_rule")
    @app_commands.describe(rule_id="The ID of the AutoMod rule to view")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def view_automod_rule(self, interaction: discord.Interaction,
                                rule_id: int) -> None:
        """View details of an existing AutoMod rule"""
        try:
            rule: discord.AutoModRule = await interaction.guild.fetch_automod_rule(
                rule_id)
            embed: discord.Embed = discord.Embed(
                title=f"AutoMod Rule: {rule.name}", color=discord.Color.blue())
            embed.add_field(name="Rule ID", value=rule.id, inline=False)
            embed.add_field(name="Creator", value=rule.creator, inline=False)
            embed.add_field(name="Event Type",
                            value=rule.event_type,
                            inline=False)
            embed.add_field(name="Trigger Type",
                            value=rule.trigger.type,
                            inline=False)
            if rule.trigger.keyword_filter:
                embed.add_field(name="Keywords",
                                value=", ".join(rule.trigger.keyword_filter),
                                inline=False)
            embed.add_field(name="Actions",
                            value="\n".join(
                                [str(action) for action in rule.actions]),
                            inline=False)
            await interaction.response.send_message(embed=embed)
        except discord.NotFound:
            await interaction.response.send_message("AutoMod rule not found.")
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"Failed to fetch AutoMod rule: {e}")

    @automod_group.command(name="delete_rule")
    @app_commands.describe(rule_id="The ID of the AutoMod rule to delete")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def delete_automod_rule(self, interaction: discord.Interaction,
                                  rule_id: int) -> None:
        """Delete an existing AutoMod rule"""
        try:
            await interaction.guild.delete_automod_rule(rule_id)
            await interaction.response.send_message(
                f"AutoMod rule with ID {rule_id} has been deleted successfully."
            )
        except discord.NotFound:
            await interaction.response.send_message("AutoMod rule not found.")
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"Failed to delete AutoMod rule: {e}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoMod(bot))

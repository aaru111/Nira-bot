import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal, List, Dict, Optional, Union


class AutoMod(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    automod_group = app_commands.Group(name="automod",
                                       description="AutoMod commands")

    @automod_group.command(name="create_rule")
    @app_commands.describe(
        name="The name of the AutoMod rule",
        preset="Preset for the AutoMod rule",
        custom_keywords="Custom keywords to filter (comma-separated)")
    @app_commands.choices(preset=[
        app_commands.Choice(name="Profanity Filter", value="profanity"),
        app_commands.Choice(name="Spam Prevention", value="spam"),
        app_commands.Choice(name="Scam Links", value="scam"),
        app_commands.Choice(name="Personal Information",
                            value="personal_info"),
        app_commands.Choice(name="Toxic Behavior", value="toxic"),
        app_commands.Choice(name="Regex Patterns", value="regex"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def create_automod_rule(
            self,
            interaction: discord.Interaction,
            name: str,
            preset: str,
            custom_keywords: Optional[str] = None) -> None:
        """Create an AutoMod rule using presets or custom keywords"""
        preset_keywords: Dict[str, Union[
            List[str], List[discord.AutoModRegexPattern]]] = {
                "profanity": [
                    "fuck", "shit", "ass", "bitch", "dick", "pussy", "cunt",
                    "asshole", "bastard", "damn", "hell", "motherfucker",
                    "piss", "slut", "whore", "cock", "penis", "vagina", "twat",
                    "bollocks", "wanker", "bloody", "bugger", "tosser", "git",
                    "prick", "fanny"
                ],
                "spam": [
                    "discord.gg", "http://", "https://", "@everyone", "@here",
                    "🚨", "⚠️", "🔥", "💯", "free", "giveaway", "winner", "claim",
                    "limited time", "act now", "click here", "urgent",
                    "important", "don't miss out", "exclusive offer",
                    "one time only"
                ],
                "scam": [
                    "free nitro", "steam gift", "click here", "free robux",
                    "free vbucks", "account giveaway", "login now",
                    "verify your account", "you've won", "inheritance",
                    "lottery winner", "double your money",
                    "investment opportunity", "get rich quick", "miracle cure",
                    "lose weight fast", "work from home", "earn money online",
                    "bitcoin investment"
                ],
                "personal_info": [
                    r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
                    r"\b\d{16}\b",  # Credit card
                    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
                    r"\b\d{3}-\d{3}-\d{4}\b",  # Phone number
                    "social security",
                    "credit card",
                    "bank account",
                    "password",
                    "address"
                ],
                "toxic": [
                    "idiot", "stupid", "dumb", "moron", "retard", "loser",
                    "noob", "trash", "garbage", "worthless", "useless",
                    "kill yourself", "kys", "die", "hate you", "suck",
                    "go to hell", "pathetic", "braindead", "toxic", "cancer",
                    "aids", "kys", "kys", "neck yourself"
                ],
                "regex": [
                    discord.AutoModRegexPattern(
                        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
                    ),  # Email
                    discord.AutoModRegexPattern(
                        r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
                    discord.AutoModRegexPattern(r"\b\d{16}\b"),  # Credit card
                    discord.AutoModRegexPattern(
                        r"\b\d{3}-\d{3}-\d{4}\b"),  # Phone number
                    discord.AutoModRegexPattern(
                        r"https?://(?:www\.)?[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/\S*)?"
                    )  # URLs
                ]
            }

        keywords: List[Union[
            str,
            discord.AutoModRegexPattern]] = preset_keywords.get(preset, [])
        if custom_keywords:
            if preset == "regex":
                keywords.extend([
                    discord.AutoModRegexPattern(kw.strip())
                    for kw in custom_keywords.split(',')
                ])
            else:
                keywords.extend(
                    [kw.strip() for kw in custom_keywords.split(',')])

        try:
            rule: discord.AutoModRule = await interaction.guild.create_automod_rule(
                name=name,
                event_type=discord.AutoModRuleEventType.message_send,
                trigger=discord.AutoModTrigger(
                    keyword_filter=keywords if preset != "regex" else None,
                    regex_patterns=keywords if preset == "regex" else None),
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
            embed = discord.Embed(title=f"AutoMod Rule: {rule.name}",
                                  color=discord.Color.blue())
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
            if rule.trigger.regex_patterns:
                embed.add_field(name="Regex Patterns",
                                value="\n".join([
                                    pattern.pattern
                                    for pattern in rule.trigger.regex_patterns
                                ]),
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

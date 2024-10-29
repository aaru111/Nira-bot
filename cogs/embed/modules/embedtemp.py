import discord


def get_announcement_template():
    """
    Creates a Discord Embed template for an important announcement.
    """
    return discord.Embed(
        title="📢 Important Announcement",
        description=
        "Please read this important update from the server staff. Stay informed to make the most of your time here!",
        color=discord.Color.blue()
    ).add_field(
        name="What's New",
        value=
        "Details of the announcement go here. Make sure to check this section regularly for updates about server changes, events, or other news.",
        inline=False
    ).add_field(
        name="Why This Matters",
        value=
        "Find out how this announcement impacts you and the community. Your awareness helps keep the server a fun and engaging place!",
        inline=False)


def get_welcome_template():
    """
    Creates a Discord Embed template for welcoming new members.
    """
    return discord.Embed(
        title="👋 Welcome to the Server!",
        description=
        "We're thrilled to have you here! This server is a place where you can connect with others, share ideas, and have a good time. Let's make your experience here amazing!",
        color=discord.Color.green()
    ).add_field(
        name="Getting Started",
        value=
        "1. **Read the rules**: Familiarize yourself with our guidelines to keep the community safe and welcoming.\n"
        "2. **Introduce yourself**: Head over to the #introductions channel and tell us a bit about yourself!\n"
        "3. **Have fun!**: Explore the channels, join conversations, and enjoy your stay!",
        inline=False
    ).add_field(
        name="Useful Channels",
        value="🔗 **#announcements**: Stay updated with the latest news.\n"
        "🗨️ **#general-chat**: Jump into the main conversation with other members.\n"
        "🎮 **#gaming**: Connect with fellow gamers and arrange some co-op fun!\n"
        "❓ **#support**: Need help? Ask here!",
        inline=False)


def get_rules_template():
    """
    Creates a Discord Embed template for server rules.
    """
    return discord.Embed(
        title="📜 Server Rules",
        description=
        "To ensure a positive experience for all members, please follow these rules. Respect and consideration for one another are key to a thriving community!",
        color=discord.Color.red()
    ).add_field(
        name="1. Be Respectful",
        value=
        "Treat others with kindness and respect. Harassment, discrimination, or hate speech of any kind will not be tolerated.",
        inline=False
    ).add_field(
        name="2. No Spam or Self-Promotion",
        value=
        "Avoid excessive messages, disruptive content, or self-promotion without permission. This includes unsolicited DMs to members.",
        inline=False
    ).add_field(
        name="3. Follow Discord's Terms of Service",
        value=
        "Ensure that your behavior and content adhere to Discord's Terms of Service and Community Guidelines.",
        inline=False
    ).add_field(
        name="4. Keep Content Appropriate",
        value=
        "This is a friendly community; keep discussions and content safe-for-work and appropriate for all ages unless otherwise specified.",
        inline=False
    ).add_field(
        name="5. Use Channels Appropriately",
        value=
        "Make sure to post in the correct channels. Read the channel descriptions to understand where your content belongs.",
        inline=False
    ).add_field(
        name="6. No Cheating or Hacking",
        value=
        "Cheating, hacking, or exploiting in games or any community events is strictly prohibited.",
        inline=False)


def get_event_template():
    """
    Creates a Discord Embed template for announcing upcoming events.
    """
    return discord.Embed(
        title="🎉 Upcoming Event",
        description=
        "Join us for an exciting community event! Participate to connect with other members, have fun, and maybe even win some cool prizes!",
        color=discord.Color.purple()
    ).add_field(
        name="Event Details",
        value="🗓️ **Date**: TBA\n"
        "🕒 **Time**: TBA\n"
        "📍 **Location**: TBA\n"
        "🎁 **Rewards**: Prizes or special roles might be up for grabs!",
        inline=False
    ).add_field(
        name="How to Participate",
        value=
        "To join the event, simply react to this message with the event emoji or follow the instructions provided. More details will be shared soon!",
        inline=False
    ).add_field(
        name="Stay Tuned!",
        value=
        "Keep an eye on this channel for more information as the event date approaches. We hope to see you there!",
        inline=False)


# Dictionary to map template names to their respective functions
templates = {
    "announcement": get_announcement_template,
    "welcome": get_welcome_template,
    "rules": get_rules_template,
    "event": get_event_template
}


def get_template(template_name):
    """
    Retrieves the appropriate embed template based on the provided template name.

    Args:
        template_name (str): The name of the template to retrieve.

    Returns:
        discord.Embed: The embed template corresponding to the template name.
    """
    return templates.get(template_name, lambda: discord.Embed())()

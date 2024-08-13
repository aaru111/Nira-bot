import discord
import random
from utils.custom_colors import custom_colors


def get_help_embed(page: int) -> discord.Embed:
    """Return the help embed for the specified page."""
    total_pages = 10  # Updated total pages count
    help_pages = [
        {
            "title":
            "Embed Creator Wizard Help - Overview",
            "description": ("```yaml\n"
                            "Pages:\n"
                            "1. Overview (this page)\n"
                            "2. Author\n"
                            "3. Body\n"
                            "4. Images\n"
                            "5. Footer\n"
                            "6. Send Button\n"
                            "7. Reset Embed Button\n"
                            "8. Selective Reset Button\n"
                            "9. Example Embed\n"
                            "10. Additional Tips\n"
                            "```"),
        },
        {
            "title":
            "Embed Creator Wizard Help - Author",
            "description":
            ("```yaml\n"
             "Author:\n\n"
             "- Author Name: The name of the author.\n\n"
             "- Author URL: A URL to link the author's name.\n\n"
             "- Author Icon URL: A URL to an image to display as the author's icon.\n"
             "```"),
        },
        {
            "title":
            "Embed Creator Wizard Help - Body",
            "description":
            ("```yaml\n"
             "Body:\n\n"
             "- Title: The title of the embed.\n\n"
             "- Description: The main content of the embed.\n\n"
             "- URL: A URL to link the title.\n\n"
             "- Color: The color of the embed (hex code, color name, or 'random').\n"
             "```"),
        },
        {
            "title":
            "Embed Creator Wizard Help - Images",
            "description":
            ("```yaml\n"
             "Images:\n\n"
             "- Image URL: A URL to an image to display in the embed.\n\n"
             "- Thumbnail URL: A URL to a thumbnail image to display in the embed.\n"
             "```"),
        },
        {
            "title":
            "Embed Creator Wizard Help - Footer",
            "description":
            ("```yaml\n"
             "Footer:\n\n"
             "- Footer Text: The text to display in the footer.\n\n"
             "- Footer Icon URL: A URL to an image to display as the footer icon.\n\n"
             "- Timestamp: The timestamp to display in the footer (YYYY-MM-DD hh:mm or 'auto').\n"
             "```"),
        },
        {
            "title":
            "Embed Creator Wizard Help - Send Button",
            "description":
            ("```yaml\n"
             "Send Button:\n\n"
             "- Description: This button allows you to send the configured embed to the current channel. It checks if the embed is properly configured and, if valid, sends it as a message.\n\n"
             "- Note: Ensure that you have at least one part of the embed configured before attempting to send it.\n"
             "```"),
        },
        {
            "title":
            "Embed Creator Wizard Help - Reset Embed Button",
            "description":
            ("```yaml\n"
             "Reset Embed Button:\n\n"
             "- Description: This button resets the entire embed, clearing all the configurations you've made. It essentially gives you a fresh start to create a new embed.\n\n"
             "- Note: Be cautious when using this, as all your settings will be lost.\n"
             "```"),
        },
        {
            "title":
            "Embed Creator Wizard Help - Selective Reset Button",
            "description":
            ("```yaml\n"
             "Selective Reset Button:\n\n"
             "- Description: This button allows you to selectively reset parts of the embed (e.g., author, body, images, footer). A modal will appear where you can choose which parts to reset.\n\n"
             "- Note: This is useful if you want to clear specific sections without losing all your progress.\n"
             "```"),
        },
        {
            "title":
            "Embed Creator Wizard Help - Example Embed",
            "description":
            ("```yaml\n"
             "Example Embed:\n\n"
             "- Title: Example Title\n\n"
             "- Description: This is an example embed.\n\n"
             "- URL: https://example.com\n\n"
             "- Color: #FF5733\n\n"
             "- Image URL: https://example.com/image.png\n\n"
             "- Thumbnail URL: https://example.com/thumbnail.png\n\n"
             "- Footer Text: Example Footer\n\n"
             "- Footer Icon URL: https://example.com/footer-icon.png\n\n"
             "- Timestamp: 2024-08-11 12:00\n"
             "```"),
        },
        {
            "title":
            "Embed Creator Wizard Help - Additional Tips",
            "description":
            ("```yaml\n"
             "Additional Tips:\n\n"
             "- Tip 1: Use the preview feature to see how your embed will look before sending it.\n\n"
             "- Tip 2: Make sure all URLs are valid and accessible.\n\n"
             "- Tip 3: Use consistent colors and formatting for a professional appearance.\n\n"
             "- Tip 4: Test the embed with different data to ensure it displays correctly in various scenarios.\n"
             "```"),
        },
    ]
    embed = discord.Embed(title=help_pages[page - 1]["title"],
                          description=help_pages[page - 1]["description"],
                          color=discord.Color.from_rgb(
                              *random.choice(list(custom_colors.values()))))
    embed.set_footer(text=f"Page {page}/{total_pages}")
    return embed

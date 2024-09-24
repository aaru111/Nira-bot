import discord
from PIL import Image, ImageDraw, ImageFont
import io
import aiohttp
from urllib.parse import urlparse

async def get_welcome_card(member: discord.Member):
    # Create a new image with a size of 1045x450 pixels
    card = Image.new('RGB', (1045, 450), color='#2f3136')
    draw = ImageDraw.Draw(card)

    # Load fonts
    try:
        name_font = ImageFont.truetype("fonts/ndot47.ttf", 50)
        bottom_font = ImageFont.truetype("fonts/font.ttf", 25)
    except IOError:
        name_font = ImageFont.load_default()
        bottom_font = ImageFont.load_default()

    # Download and paste avatar
    avatar_size = 210
    avatar_position = ((1045 - avatar_size) // 2, 45)
    avatar_image = await download_avatar(str(member.display_avatar.url), avatar_size)
    card.paste(avatar_image, avatar_position, avatar_image)

    # Add member name
    member_name = str(member)
    name_bbox = draw.textbbox((0, 0), member_name, font=name_font)
    name_position = ((1045 - name_bbox[2]) // 2, 260)
    draw.text(name_position, member_name, font=name_font, fill='wheat')

    # Add welcome message
    welcome_text = f"Welcome to {member.guild.name}!"
    welcome_bbox = draw.textbbox((0, 0), welcome_text, font=bottom_font)
    welcome_position = ((1045 - welcome_bbox[2]) // 2, 330)

    # Draw text shadow
    shadow_offset = 1
    for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
        draw.text((welcome_position[0] + dx * shadow_offset, welcome_position[1] + dy * shadow_offset), 
                  welcome_text, font=bottom_font, fill='black')

    # Draw main text
    draw.text(welcome_position, welcome_text, font=bottom_font, fill='skyblue')

    # Save the image to a bytes buffer
    img_byte_arr = io.BytesIO()
    card.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)

    return img_byte_arr

async def download_avatar(url: str, size: int):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.read()
                avatar = Image.open(io.BytesIO(data))
                avatar = avatar.convert("RGBA")
                avatar = avatar.resize((size, size), Image.LANCZOS)

                # Create a circular mask
                mask = Image.new('L', (size, size), 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, size, size), fill=255)

                # Apply the mask to the avatar
                output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
                output.paste(avatar, (0, 0), mask)
                return output
            else:
                # Return a default avatar or placeholder if download fails
                return Image.new('RGBA', (size, size), (128, 128, 128, 255))
from PIL import Image
import colorsys

# Discord emoji mapping for pixel colors
COLORS = {
    (0, 0, 0): "⬛",
    (0, 0, 255): "🔵",
    (255, 0, 0): "🔴",
    (255, 255, 0): "🟡",
    (190, 100, 80): "🟫",
    (255, 165, 0): "🟠",
    (160, 140, 210): "🟣",
    (255, 255, 255): "⬜",
    (0, 255, 0): "🟢",
    (150, 75, 0): "🟤",
    (0, 128, 128): "🔷",
    (128, 0, 128): "🟪",
    (128, 128, 128): "⚪",
    (255, 192, 203): "🌸",
    (0, 255, 255): "🦋",
    (255, 0, 255): "💜",
    (128, 0, 0): "🍎",
    (255, 255, 128): "🌼",
    (0, 255, 128): "🍏",
    (128, 0, 255): "🟣",
    (255, 128, 0): "🎃",
    (128, 128, 0): "🌿",
    (0, 128, 0): "🍃",
    (0, 128, 255): "🌊",
    (255, 0, 128): "💖",
    (255, 128, 128): "🌹",
    (128, 255, 128): "🌿",
    (128, 128, 255): "🔷",
    (255, 128, 255): "🌸",
    (128, 255, 255): "🌼",
    (0, 0, 128): "🟦"
}

def rgb_to_hsv(r, g, b):
    return colorsys.rgb_to_hsv(r/255, g/255, b/255)

def calculate_color_difference(c1, c2):
    h1, s1, v1 = rgb_to_hsv(*c1)
    h2, s2, v2 = rgb_to_hsv(*c2)

    # Calculate differences in hue, saturation, and value
    h_diff = min(abs(h1 - h2), 1 - abs(h1 - h2))
    s_diff = abs(s1 - s2)
    v_diff = abs(v1 - v2)

    # Weighted sum of differences
    return h_diff * 0.5 + s_diff * 0.3 + v_diff * 0.2

def find_closest_emoji(color):
    return min(COLORS.items(), key=lambda x: calculate_color_difference(color, x[0]))[1]

def emojify_image(img, size=22):
    WIDTH, HEIGHT = size, size
    small_img = img.resize((WIDTH, HEIGHT), Image.LANCZOS)
    pixels = small_img.load()
    emoji = ""
    for y in range(HEIGHT):
        for x in range(WIDTH):
            emoji += find_closest_emoji(pixels[x, y])
        emoji += "\n"
    return emoji
import base64
import re
import binascii
from typing import Optional, Tuple

MAX_ENCODE_LAYERS = 5
MAX_INPUT_LENGTH = 10240
MAX_OUTPUT_LENGTH = 10240
CODE_BLOCK_RE = re.compile(r'```\w*\n?|\n?```')


def cleanup_text(text: str) -> str:
    return CODE_BLOCK_RE.sub('', text).strip()


def truncate_text(text: str, max_length: int = 1000) -> str:
    return text if len(text) <= max_length else f"{text[:max_length]}..."


def format_output(text: str) -> str:
    return f"```{text}```"


def text_to_hex(text: str) -> str:
    return text.encode('utf-8').hex()


def text_to_binary(text: str) -> str:
    return ''.join(format(ord(char), '08b') for char in text)


def binary_to_text(binary_str: str) -> str:
    binary_str = ''.join(binary_str.split())
    if len(binary_str) % 8 != 0:
        raise ValueError("Binary string length must be a multiple of 8")
    try:
        return ''.join(
            chr(int(binary_str[i:i + 8], 2))
            for i in range(0, len(binary_str), 8))
    except Exception as e:
        raise ValueError(f"Invalid binary string: {e}")


def hex_to_text(hex_str: str) -> str:
    try:
        return bytes.fromhex(hex_str).decode('utf-8')
    except (ValueError, binascii.Error) as e:
        raise ValueError(f"Invalid hex string: {e}")


def base64_to_text(text: str) -> str:
    try:
        return base64.b64decode(text, validate=True).decode('utf-8')
    except (binascii.Error, UnicodeDecodeError):
        raise ValueError("Invalid base64 string")


def try_decode(text: str) -> Tuple[Optional[str], Optional[str]]:
    decode_methods = {
        "binary": binary_to_text,
        "base64": base64_to_text,
        "hex": hex_to_text
    }

    for method, func in decode_methods.items():
        try:
            decoded = func(text)
            return decoded, method
        except ValueError:
            continue
    return None, None


async def encode_text(interaction, text: str, encoding: str, layers: int):
    text = cleanup_text(text)
    if len(text) > MAX_INPUT_LENGTH:
        return await interaction.followup.send(
            f"❌ Input text exceeds {MAX_INPUT_LENGTH} characters.",
            ephemeral=True)

    layers = min(max(1, layers), MAX_ENCODE_LAYERS)
    encode_funcs = {
        "base64": lambda x: base64.b64encode(x.encode()).decode(),
        "hex": text_to_hex,
        "binary": text_to_binary
    }

    current_text = text
    encode_steps = [f"**Original:** {truncate_text(text, 100)}"]

    try:
        encode_func = encode_funcs[encoding]
        for i in range(layers):
            current_text = encode_func(current_text)
            if len(current_text) > MAX_OUTPUT_LENGTH:
                return await interaction.followup.send(
                    "❌ Output text too long after encoding. Reduce layers.",
                    ephemeral=True)
            encode_steps.append(
                f"**Layer {i + 1}:** {truncate_text(current_text, 100)}")

    except Exception as e:
        return await interaction.followup.send(f"❌ Error during encoding: {e}",
                                               ephemeral=True)

    response = "\n".join(
        encode_steps
    ) + f"\n\n**Final Encoded Result:**\n{format_output(current_text)}"
    await interaction.followup.send(
        f"✅ Encoded {layers} layers successfully!\n\n{response}",
        ephemeral=True)


async def decode_text(interaction, encoded_text: str):
    encoded_text = cleanup_text(encoded_text)
    if len(encoded_text) > MAX_INPUT_LENGTH:
        return await interaction.followup.send(
            f"❌ Input text exceeds {MAX_INPUT_LENGTH} characters.",
            ephemeral=True)

    current_text = encoded_text
    decode_steps = []

    while True:
        decoded, method = try_decode(current_text)
        if decoded is None:
            break
        decode_steps.append(
            f"{len(decode_steps) + 1}. ({method}) {truncate_text(decoded, 100)}"
        )
        current_text = decoded
        if len(current_text) > MAX_OUTPUT_LENGTH:
            return await interaction.followup.send(
                "❌ Decoded output too long.", ephemeral=True)

    response = "❌ Unable to decode the provided text." if not decode_steps else \
        f"✅ Decoded {len(decode_steps)} layers:\n" + "\n".join(decode_steps) + \
        f"\n\n**Final Decoded Result:**\n{format_output(current_text)}"
    await interaction.followup.send(response, ephemeral=True)

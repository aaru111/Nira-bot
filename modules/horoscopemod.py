from enum import IntEnum
import discord
from aiohttp import ClientSession
from bs4 import BeautifulSoup, Tag
from typing import Optional, Tuple, List

HOROSCOPE_BASE_URL = "https://www.horoscope.com/us/horoscopes/general/horoscope-general-daily-today.aspx"
STAR_RATING_BASE_URL = "https://www.horoscope.com/star-ratings/today/"
PARSER = "html.parser"


class ZodiacSign(IntEnum):
    Aries = 1
    Taurus = 2
    Gemini = 3
    Cancer = 4
    Leo = 5
    Virgo = 6
    Libra = 7
    Scorpio = 8
    Sagittarius = 9
    Capricorn = 10
    Aquarius = 11
    Pisces = 12


class HoroscopeError(Exception):
    """Base exception for horoscope-related errors."""
    pass


class HoroscopeModule:

    def __init__(self):
        self.session: Optional[ClientSession] = None
        # Move ZODIAC_EMOJIS inside the class
        self.ZODIAC_EMOJIS = {
            zodiac_sign:
            f"https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/{hex(9799+zodiac_sign)[2:]}.png"
            for zodiac_sign in ZodiacSign
        }

    async def ensure_session(self) -> ClientSession:
        """Ensure we have a valid aiohttp session."""
        if self.session is None:
            self.session = ClientSession(
                headers={
                    'User-Agent':
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                })
        return self.session

    async def get_today_horoscope(self, zodiac_sign: ZodiacSign) -> str:
        """Get today's horoscope text from horoscope.com for the given zodiac sign."""
        session = await self.ensure_session()
        try:
            async with session.get(HOROSCOPE_BASE_URL,
                                   params={"sign": zodiac_sign.value}) as resp:
                if resp.status != 200:
                    raise HoroscopeError(
                        f"Failed to fetch horoscope: HTTP {resp.status}")

                soup = BeautifulSoup(await resp.text(), PARSER)
                data = soup.find("div", attrs={"class": "main-horoscope"})

                if not isinstance(data, Tag) or not data.p:
                    raise HoroscopeError("Failed to parse horoscope data")

                parts = data.p.text.split(" - ", 1)
                if len(parts) != 2:
                    raise HoroscopeError("Unexpected horoscope format")

                return parts[1].strip()
        except Exception as e:
            raise HoroscopeError(f"Error getting horoscope: {str(e)}")

    async def get_today_star_rating(
            self, zodiac_sign: ZodiacSign) -> List[Tuple[str, str]]:
        """Get today's star rating from horoscope.com for the given zodiac sign."""
        session = await self.ensure_session()
        try:
            async with session.get(
                    f"{STAR_RATING_BASE_URL}{zodiac_sign.name.lower()}"
            ) as resp:
                if resp.status != 200:
                    raise HoroscopeError(
                        f"Failed to fetch star ratings: HTTP {resp.status}")

                soup = BeautifulSoup(await resp.text(), PARSER)
                data = soup.find("div", attrs={"class": "module-skin"})

                if not isinstance(data, Tag):
                    raise HoroscopeError("Failed to parse star rating data")

                categories = data.find_all("h3")
                texts = data.find_all("p")[:5]  # Exclude the disclaimer

                star_ratings = []
                for category, text in zip(categories, texts):
                    stars = category.find_all("i",
                                              attrs={"class": "highlight"})
                    star_count = len(stars)
                    star_display = "⭐" * star_count
                    star_ratings.append((
                        f"{category.text.split('(')[0].strip()}: {star_display}",
                        text.text.strip()))

                return star_ratings
        except Exception as e:
            raise HoroscopeError(f"Error getting star ratings: {str(e)}")

    async def close(self):
        """Clean up the session."""
        if self.session:
            await self.session.close()

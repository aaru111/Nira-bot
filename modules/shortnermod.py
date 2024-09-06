import requests
import qrcode
import io
import time
import aiohttp
from urllib.parse import urlparse
from typing import Optional, Dict, Tuple


class URLShortenerCore:

    def __init__(self, bitly_token: str, rate_limit: int,
                 reset_interval: int) -> None:
        self.bitly_token = bitly_token
        self.rate_limit = rate_limit
        self.reset_interval = reset_interval
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

    async def close_session(self) -> None:
        """Clean up the aiohttp session."""
        await self.session.close()

    @staticmethod
    def is_already_shortened(url: str) -> bool:
        """Checks if the URL is already a shortened Bitly URL."""
        parsed_url = urlparse(url)
        return parsed_url.netloc in ["bit.ly", "j.mp", "bitly.is"]

    def shorten_url(self,
                    url: str,
                    expire_days: Optional[int] = None) -> Optional[str]:
        """Shortens the provided URL using the Bitly API with an optional expiration time."""
        headers = {
            "Authorization": f"Bearer {self.bitly_token}",
            "Content-Type": "application/json",
        }
        data = {"long_url": url, "domain": "bit.ly"}
        if expire_days:
            data["expires_at"] = time.time(
            ) + expire_days * 86400  # Convert days to seconds

        try:
            response = requests.post("https://api-ssl.bitly.com/v4/shorten",
                                     json=data,
                                     headers=headers)
            response.raise_for_status()
            return response.json().get("link")
        except requests.exceptions.RequestException as e:
            print(f"Error occurred: {e}")
            return None

    @staticmethod
    def format_shortened_url(url: str) -> str:
        """Formats the shortened URL to make it look more professional."""
        return f"<{url}>"

    @staticmethod
    def generate_qr_code(url: str) -> io.BytesIO:
        """Generates a QR code for the given URL."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    def is_within_rate_limit(
            self, user_id: int,
            user_rate_limits: Dict[int, Tuple[float, int]]) -> bool:
        """Checks if a user is within the rate limit."""
        current_time = time.time()
        if user_id in user_rate_limits:
            last_reset_time, count = user_rate_limits[user_id]
            if current_time - last_reset_time < self.reset_interval:
                if count >= self.rate_limit:
                    return False
                user_rate_limits[user_id] = (last_reset_time, count + 1)
            else:
                user_rate_limits[user_id] = (current_time, 1)
        else:
            user_rate_limits[user_id] = (current_time, 1)
        return True

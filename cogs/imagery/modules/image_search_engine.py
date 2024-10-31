import aiohttp
from typing import Dict
import urllib.parse
import logging


class ImageSearchEngine:

    def __init__(self):
        self.logger = logging.getLogger('image_search_engine')

    def _encode_image_url(self, url: str) -> str:
        """Properly encode image URL for search engines"""
        return urllib.parse.quote(url, safe='')

    async def search_image(self, image_url: str) -> Dict[str, str]:
        """
        Search for an image across multiple search engines
        Returns dict with search URLs for each engine
        """
        encoded_url = self._encode_image_url(image_url)

        search_urls = {
            'google': f"https://lens.google.com/uploadbyurl?url={encoded_url}",
            'yandex':
            f"https://yandex.com/images/search?rpt=imageview&url={encoded_url}",
            'tineye': f"https://tineye.com/search?url={encoded_url}",
            'bing':
            f"https://www.bing.com/images/search?view=detailv2&iss=sbi&form=SBIHMP&q=imgurl:{encoded_url}",
            'saucenao': f"https://saucenao.com/search.php?url={encoded_url}"
        }

        return search_urls

    async def validate_image(self, url: str) -> bool:
        """Validate if URL points to a valid image"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url) as response:
                    if response.status != 200:
                        return False
                    content_type = response.headers.get('content-type', '')
                    return content_type.startswith('image/')
        except Exception as e:
            self.logger.error(f"Error validating image URL: {str(e)}")
            return False

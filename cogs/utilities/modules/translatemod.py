
from typing import Dict, List
from discord import Embed, app_commands
from googletrans import Translator, LANGUAGES
from fuzzywuzzy import process


class LanguageMatcher:

    def __init__(self):
        # Create a searchable dictionary with both codes and names
        self.search_dict = {}
        for code, name in LANGUAGES.items():
            self.search_dict[code] = name
            self.search_dict[name.lower()] = code

    def get_matches(self, query: str, limit: int = 25) -> List[tuple]:
        """
        Get fuzzy matches for a language query
        Returns: List of tuples (language_code, language_name, match_score)
        """
        query = query.lower().strip()
        if not query:
            # If no query, return most common languages first
            common_langs = [
                'en', 'es', 'fr', 'de', 'it', 'pt', 'nl', 'ru', 'ja', 'ko',
                'zh-cn', 'ar', 'hi', 'tr', 'pl'
            ]
            return [(code, LANGUAGES[code], 100)
                    for code in common_langs[:limit]]

        # Get matches using fuzzywuzzy
        matches = process.extract(
            query,
            {
                k: v
                for k, v in LANGUAGES.items()
            },  # Search in language names
            limit=limit)

        # Format results
        results = []
        seen_codes = set()

        # First add exact matches if any
        if query in self.search_dict:
            code = self.search_dict[query] if query in LANGUAGES else query
            name = LANGUAGES[code]
            results.append((code, name, 100))
            seen_codes.add(code)

        # Then add fuzzy matches
        for name, score, code in matches:
            if code not in seen_codes and score > 60:  # Only include matches with score > 60
                results.append((code, name, score))
                seen_codes.add(code)

        return results[:limit]


class TranslationCore:

    def __init__(self):
        self.translator = Translator()
        self.language_matcher = LanguageMatcher()

    async def translate_text(self,
                             text: str,
                             target_lang: str,
                             source_lang: str = 'auto') -> Dict:
        """
        Translate text using Google Translate API
        """
        try:
            translation = self.translator.translate(text,
                                                    dest=target_lang,
                                                    src=source_lang)
            return {
                'translated_text': translation.text,
                'source_lang': translation.src,
                'target_lang': target_lang,
                'original_text': text
            }
        except Exception as e:
            raise Exception(f"Translation error: {str(e)}")

    def get_language_suggestions(
            self, current: str) -> List[app_commands.Choice[str]]:
        """
        Get language suggestions for autocomplete using fuzzy matching
        """
        matches = self.language_matcher.get_matches(current)
        return [
            app_commands.Choice(name=f"{name} ({code})", value=code)
            for code, name, score in matches
        ]

    def create_translation_embed(self, translation_data: Dict) -> Embed:
        """Create an embed for the translation result"""
        embed = Embed(title="Translation Result", color=0x2b2d31)

        source_lang_name = LANGUAGES.get(translation_data['source_lang'],
                                         translation_data['source_lang'])
        embed.add_field(name=f"From {source_lang_name}",
                        value=translation_data['original_text'],
                        inline=False)

        target_lang_name = LANGUAGES.get(translation_data['target_lang'],
                                         translation_data['target_lang'])
        embed.add_field(name=f"To {target_lang_name}",
                        value=translation_data['translated_text'],
                        inline=False)

        return embed

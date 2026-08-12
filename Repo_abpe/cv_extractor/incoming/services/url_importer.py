"""
url_importer.py — Kompatibilitäts-Wrapper
Leitet auf plattformspezifische Importer weiter.
"""
from .url_fl_importer import URLImporter as FLImporter
from pathlib import Path
import json

class URLImporter:
    def run(self, url: str, cookies: dict = None, **kwargs) -> dict:
        platform = self._detect_platform(url)
        if platform == 'fl':
            return FLImporter().run(url=url, cookies=cookies, **kwargs)
        elif platform == 'gu':
            from .url_gu_importer import GULPImporter
            return GULPImporter().run(url=url, cookies=cookies, **kwargs)
        else:
            return {'error': f'Plattform nicht unterstützt: {platform}'}

    def _detect_platform(self, url: str) -> str:
        if 'freelancermap.de' in url: return 'fl'
        if 'gulp.de'          in url: return 'gu'
        return 'other'

# Singleton
url_importer = URLImporter()

"""
ABpE Email Studio — HTML Kompatibilitäts-Check
"""
import re


class CompatibilityChecker:

    CHECKS = {
        'outlook':    [r'border-radius', r'display:\s*flex', r'display:\s*grid'],
        'gmail':      [r'<style>', r'position:\s*absolute'],
        'webde':      [r'<script'],
        'apple_mail': [],
        'txt':        [],
    }

    def check(self, html: str) -> dict:
        results  = {}
        warnings = []

        for client, patterns in self.CHECKS.items():
            client_warnings = []
            for pattern in patterns:
                if re.search(pattern, html, re.IGNORECASE):
                    client_warnings.append(f'{pattern} möglicherweise nicht unterstützt')
            results[client] = {
                'ok':       len(client_warnings) == 0,
                'warnings': client_warnings,
            }
            warnings.extend(client_warnings)

        results['txt'] = {'ok': True, 'warnings': []}
        return {
            'overall_ok': len(warnings) == 0,
            'clients':    results,
            'warnings':   warnings,
        }

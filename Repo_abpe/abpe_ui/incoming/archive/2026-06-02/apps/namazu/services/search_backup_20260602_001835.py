import subprocess, re
from pathlib import Path
import json

def _cfg():
    p = Path(__file__).parents[3] / 'settings.json'
    return json.load(open(p)).get('namazu', {})

def search(query: str, max_results: int = 20) -> dict:
    cfg    = _cfg()
    binary = cfg.get('binary', {}).get('namazu', '/usr/bin/namazu')
    index  = cfg.get('namazu_index', '/var/www/namazu/namazu-index/')
    try:
        r = subprocess.run(
            [binary, '-r', '-m', str(max_results), query, index],
            capture_output=True, text=True, timeout=30
        )
        return _parse(r.stdout, query)
    except Exception as e:
        return {'error': str(e), 'results': [], 'total': 0, 'query': query}

def _parse(output: str, query: str) -> dict:
    total   = 0
    results = []

    m = re.search(r'Total (\d+) documents', output)
    if m:
        total = int(m.group(1))

    # Jeden Block per Trennmuster splitten
    # Format pro Eintrag:
    #   N. Titel (score: X)
    #   Author: ...
    #   Date: ...
    #   Snippet-Zeile
    #   URL (bytes)
    block_pattern = re.compile(
        r'^\s*(\d+)\.\s+(.+?)\s+\(score:\s*(\d+)\)\s*$',
        re.MULTILINE
    )

    lines = output.splitlines()

    for bm in block_pattern.finditer(output):
        rank  = int(bm.group(1))
        title = bm.group(2).strip()
        score = int(bm.group(3))

        # Zeilennummer im Output finden
        start = output[:bm.start()].count('\n')

        # Nächste Zeilen lesen
        author  = ''
        date    = ''
        snippet = ''
        url     = ''

        for i in range(start + 1, min(start + 10, len(lines))):
            line = lines[i].strip()
            if line.startswith('Author:'):
                author = line[7:].strip()
            elif line.startswith('Date:'):
                date = line[5:].strip()
            elif line.startswith('http'):
                url = line.split(' ')[0].strip()
                break
            elif line and not line.startswith('Author') and not line.startswith('Date'):
                if not snippet:
                    snippet = line[:200]

        if not url:
            continue

        filename = url.split('/')[-1]
        nm = re.match(r'([^_]+)__([^_]+)__', filename)

        results.append({
            'rank':     rank,
            'title':    title,
            'score':    score,
            'snippet':  snippet,
            'filename': filename,
            'first':    nm.group(2) if nm else '',
            'last':     nm.group(1) if nm else '',
        })

    return {'total': total, 'results': results, 'query': query}

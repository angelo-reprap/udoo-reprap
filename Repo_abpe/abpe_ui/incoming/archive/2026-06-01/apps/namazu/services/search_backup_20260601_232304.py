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
    pattern = re.compile(
        r'(\d+)\.\s+(.+?)\s+\(score:\s*(\d+)\)\s*\n'
        r'Author:\s*(.*?)\n'
        r'Date:\s*(.*?)\n'
        r'(.*?)\n'
        r'(https?://\S+)\s+\(',
        re.DOTALL
    )
    for m in pattern.finditer(output):
        url      = m.group(7).strip()
        filename = url.split('/')[-1]
        nm       = re.match(r'([^_]+)__([^_]+)__', filename)
        results.append({
            'rank':     int(m.group(1)),
            'title':    m.group(2).strip(),
            'score':    int(m.group(3)),
            'snippet':  m.group(6).strip()[:200],
            'filename': filename,
            'first':    nm.group(2) if nm else '',
            'last':     nm.group(1) if nm else '',
        })
    return {'total': total, 'results': results, 'query': query}

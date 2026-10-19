#!/usr/bin/env python3
"""Diagnostic prudent des taux TopCashback : aucun taux n'est publié par ce test."""
import collections
import concurrent.futures
import json
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; cashback-finder personal rate monitor)',
    'Accept-Language': 'fr-FR,fr;q=0.9',
}

class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.skip += 1
        if tag in ('div', 'p', 'h1', 'h2', 'h3', 'span', 'li', 'br', 'tr'):
            self.parts.append(' ')
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.skip = max(0, self.skip - 1)
        if tag in ('div', 'p', 'h1', 'h2', 'h3', 'span', 'li', 'br', 'tr'):
            self.parts.append(' ')
    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

PATTERNS = [
    re.compile(r"(?i)(jusqu[’']?\s*à\s*)?(\d+(?:[,.]\d{1,2})?)\s*(%|€)\s*(?:de\s*)?cashback\b"),
    re.compile(r"(?i)cashback\s*(?:de\s*)?(jusqu[’']?\s*à\s*)?(\d+(?:[,.]\d{1,2})?)\s*(%|€)\b"),
]

def diagnose(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=18) as response:
            status = response.status
            raw = response.read(1500000)
        if status != 200:
            return url, f'HTTP_{status}', ''
        html = raw.decode('utf-8', 'replace')
        parser = Text()
        parser.feed(html)
        text = ' '.join(''.join(parser.parts).split())
        match = re.search(r'(?i)\bcashback\b', text)
        if not match:
            return url, 'NO_CASHBACK_WORD', f'HTML bytes={len(raw)}, extracted chars={len(text)}'
        section = text[match.start():match.start()+2200]
        candidates = [(m.start(), m.group(0)) for pat in PATTERNS for m in pat.finditer(section)]
        if not candidates:
            # Only expose a short, sanitized excerpt from the public merchant page.
            return url, 'PATTERN_NOT_FOUND', f'excerpt={section[:160]!r}'
        pos, label = min(candidates)
        if pos > 700:
            return url, 'RATE_TOO_FAR', f'position={pos}, candidate={label!r}'
        return url, 'RATE_FOUND', f'candidate={label!r}'
    except urllib.error.HTTPError as exc:
        return url, f'HTTP_{exc.code}', ''
    except urllib.error.URLError as exc:
        return url, 'NETWORK_ERROR', f'{type(exc.reason).__name__}: {str(exc.reason)[:100]}'
    except Exception as exc:
        return url, 'OTHER_ERROR', f'{type(exc).__name__}: {str(exc)[:100]}'

def main():
    urls = json.loads((ROOT / 'topcashback-merchants.json').read_text(encoding='utf-8'))
    # Limiter le diagnostic aux 12 premieres pages, pour eviter 1221 requetes inutiles.
    sample = urls[:12]
    print(f'DIAGNOSTIC: {len(sample)} pages sur {len(urls)}; aucune modification des taux', flush=True)
    counts = collections.Counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for url, reason, details in pool.map(diagnose, sample):
            counts[reason] += 1
            print(f'{reason} | {url} | {details}', flush=True)
    print('RESUME:', dict(counts), flush=True)
    print('Aucun fichier topcashback-rates.json modifie.', flush=True)

if __name__ == '__main__':
    main()

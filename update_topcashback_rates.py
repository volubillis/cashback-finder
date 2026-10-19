#!/usr/bin/env python3
"""Collecteur prudent des taux TopCashback, compatible avec le workflow existant.

Les taux ne sont publiés que lorsqu'une valeur est explicitement reliée au
cashback dans le bloc marchand. Une page ambiguë conserve son ancien taux.
"""
import concurrent.futures
import datetime
import json
import re
import unicodedata
import urllib.error
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Accept-Language': 'fr-FR,fr;q=0.9',
}

class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.skip += 1
        if not self.skip and tag in ('h1', 'h2', 'h3', 'h4', 'p', 'div', 'li', 'tr', 'td', 'br', 'section'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.skip = max(0, self.skip - 1)
        if not self.skip and tag in ('h1', 'h2', 'h3', 'h4', 'p', 'div', 'li', 'tr', 'td', 'section'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def lines(self):
        return [re.sub(r'\s+', ' ', s).strip() for s in ''.join(self.parts).splitlines() if s.strip()]


def normalize(s):
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '', s.lower())

# The website can render 'Cashback Marchand' with the rate on a nearby line.
# Require a merchant-specific heading to avoid navigation and unrelated offers.
STOP = re.compile(r'(?i)conditions pour b[eé]n[eé]ficier|important [aà] savoir|questions fr[eé]quentes|avis clients')
NUMBER = r'(\d{1,3}(?:[\s\u00a0]\d{3})*(?:[,.]\d{1,2})?)'
DIRECT = re.compile(rf'(?i)(jusqu[’\']?\s*[aà]\s*)?{NUMBER}\s*(%|€|euros?)\s*(?:de\s*)?cashback\b')
REVERSE = re.compile(rf'(?i)cashback\s*(?:de\s*)?(jusqu[’\']?\s*[aà]\s*)?{NUMBER}\s*(%|€|euros?)')


def format_rate(prefix, number, unit):
    try:
        n = float(number.replace(' ', '').replace('\u00a0', '').replace(',', '.'))
    except ValueError:
        return None
    if not 0 < n <= (100 if unit == '%' else 1000):
        return None
    nstr = ('%g' % n).replace('.', ',')
    return ("Jusqu'à " if prefix else '') + nstr + ('% Cashback' if unit == '%' else ' € Cashback')


def merchant_block(lines, url):
    slug = urlparse(url).path.strip('/').split('/')[-1]
    slug_parts = [normalize(p) for p in slug.split('-') if len(normalize(p)) >= 3]
    # A merchant heading is typically "Cashback <merchant>". Require the merchant
    # name, not just the first "cashback" in the navigation.
    starts = []
    for i, line in enumerate(lines):
        low = normalize(line)
        if not re.search(r'(?i)\bcashback\b', line):
            continue
        if slug_parts and not any(p in low for p in slug_parts):
            continue
        if len(line) > 160:
            continue
        starts.append(i)
    if not starts:
        return None
    for start in starts:
        block = []
        for line in lines[start:start+100]:
            if STOP.search(line) and len(block) > 2:
                break
            block.append(line)
            if sum(map(len, block)) > 5500:
                break
        if block:
            yield block


def extract_rate(html, url):
    parser = PageText()
    parser.feed(html)
    lines = parser.lines()
    for block in merchant_block(lines, url) or ():
        # Only accept offers explicitly labelled as cashback. Avoid 10-euro
        # conditions/coupons or arbitrary percentages in the page.
        candidates = []
        for idx, line in enumerate(block[:50]):
            for pat in (DIRECT, REVERSE):
                for match in pat.finditer(line):
                    label = format_rate(*match.groups())
                    if label:
                        candidates.append((idx, label))
            # The amount and 'Cashback' may be split into adjacent elements.
            if idx + 1 < len(block):
                nextline = block[idx+1]
                if len(line) <= 90 and len(nextline) <= 90:
                    for pair in (line+' '+nextline, nextline+' '+line):
                        for pat in (DIRECT, REVERSE):
                            for match in pat.finditer(pair):
                                label = format_rate(*match.groups())
                                if label:
                                    candidates.append((idx, label))
        # Some merchant pages put the cashback amount immediately below the
        # merchant heading without repeating the word "Cashback". Restrict this
        # fallback to the first two short lines after that heading.
        if not candidates:
            for idx in range(1, min(3, len(block))):
                line = block[idx]
                if len(line) > 55:
                    continue
                for match in re.finditer(r"(?i)(jusqu[’']?\s*[aà]\s*)?(\d+(?:[,.]\d{1,2})?)\s*(%|€|euros?)", line):
                    label = format_rate(*match.groups())
                    if label:
                        candidates.append((idx, label))
        # Multiple different offers (e.g. new/existing customer) cannot be
        # summarized by an arbitrary first amount. Keep existing rate instead.
        distinct = set(label for _, label in candidates)
        if len(distinct) == 1:
            return distinct.pop(), 'ok'
        if len(distinct) > 1:
            return None, 'ambiguous'
    return None, 'not_found'


def fetch(url):
    try:
        request = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status != 200:
                return url, None, 'http_' + str(response.status)
            html = response.read(2000000).decode('utf-8', 'replace')
        label, status = extract_rate(html, url)
        return url, label, status
    except urllib.error.HTTPError as e:
        return url, None, 'http_' + str(e.code)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return url, None, 'network_' + type(e).__name__
    except Exception as e:
        return url, None, 'parse_' + type(e).__name__


def main():
    urls = json.loads((ROOT / 'topcashback-merchants.json').read_text(encoding='utf-8'))
    dest = ROOT / 'topcashback-rates.json'
    try:
        old = json.loads(dest.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        old = {}
    previous = old.get('rates', {})
    results = dict(previous)
    counts = Counter()
    verified = 0
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    print(f'Checking {len(urls)} merchant pages (3 parallel requests).', flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for url, label, status in pool.map(fetch, urls):
            counts[status] += 1
            if label:
                results[url] = {'rate': label, 'status': 'ok', 'verified_at': now}
                verified += 1
            elif counts[status] <= 5:
                print(f'SKIP {status}: {url}', flush=True)
    print(f'Verified {verified}/{len(urls)} TopCashback merchant pages', flush=True)
    print('Diagnostic counts:', dict(counts), flush=True)
    minimum = max(10, int(len(urls)*0.05))
    if verified < minimum:
        print(f'WARNING: fewer than {minimum} verified; previous rates retained, no update published', flush=True)
        return
    dest.write_text(json.dumps({'checked_at': now, 'verified_this_run': verified,
                                'merchants_checked': len(urls), 'rates': results},
                               ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('Published validated rates; previous values preserved for skipped merchants.', flush=True)

if __name__ == '__main__':
    main()

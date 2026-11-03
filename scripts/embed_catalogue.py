"""Keep the deployed HTML self-contained for both GitHub Pages and Acer's HTML sync."""
import argparse
from pathlib import Path
import re

root=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
path=root/'index.html';html=path.read_text(encoding='utf-8');script=(root/'catalogue.js').read_text(encoding='utf-8')
if '</script' in script.lower():raise SystemExit('Unexpected closing script tag in catalogue source')
block='<script data-catalogue-app>\n'+script+'\n</script>'
pattern=r'<script data-catalogue-app>[\s\S]*?</script>|<script src="catalogue\.js"></script>'
updated,count=re.subn(pattern,lambda _:block,html)
if count!=1:raise SystemExit('Expected exactly one catalogue application block')
if args.check:
    if updated!=html:raise SystemExit('Embedded catalogue differs from catalogue.js; run scripts/embed_catalogue.py')
    print('Self-contained HTML matches catalogue.js')
else:
    path.write_text(updated,encoding='utf-8');print('Self-contained HTML updated')

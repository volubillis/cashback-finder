#!/usr/bin/env python3
"""Daily conservative TopCashback rate collector; preserves prior valid values.
Rate detection is intentionally strict; unmatched pages are skipped, not guessed.
"""
import concurrent.futures, datetime, json, os, re, time, urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parent
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; cashback-finder personal rate monitor)','Accept-Language':'fr-FR,fr;q=0.9'}
class Text(HTMLParser):
    def __init__(self): super().__init__();self.out=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','noscript'):self.skip+=1
        if tag in ('div','p','h1','h2','h3','span','li','br','tr'):self.out.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript'):self.skip=max(0,self.skip-1)
        if tag in ('div','p','h1','h2','h3','span','li','br','tr'):self.out.append('\n')
    def handle_data(self,data):
        if not self.skip:self.out.append(data)

# Strictly only read amounts expressly marked Cashback, not incidental conditions.
PATTERNS=[
 re.compile(r"(?i)(jusqu[’']?\s*à\s*)?(\d+(?:[,.]\d{1,2})?)\s*(%|€)\s*(?:de\s*)?cashback\b"),
 re.compile(r"(?i)cashback\s*(?:de\s*)?(jusqu[’']?\s*à\s*)?(\d+(?:[,.]\d{1,2})?)\s*(%|€)\b")
]
def fetch(url):
 try:
  req=urllib.request.Request(url,headers=HEADERS)
  with urllib.request.urlopen(req,timeout=18) as res:
   if res.status!=200:return url,None
   html=res.read(1500000).decode('utf-8','replace')
  parser=Text();parser.feed(html)
  txt=' '.join(''.join(parser.out).split())
  # Limit to primary page heading and first 2500 chars: avoid unrelated FAQ, coupons and conditions.
  m=re.search(r'(?i)\bcashback\b',txt)
  if not m:return url,None
  section=txt[m.start():m.start()+2200]
  candidates=[]
  for pat in PATTERNS:
   for match in pat.finditer(section):
    prefix,number,unit=match.groups()
    number=number.replace(',','.')
    if not 0<float(number)<=1000:continue
    value=number.replace('.',',')
    label=("Jusqu'à " if prefix else '')+value+(' %' if unit=='%' else ' €')+' Cashback'
    candidates.append((match.start(),label))
  if not candidates:return url,None
  # Only trust a rate in the opening part of the cashback block.
  pos,label=min(candidates)
  if pos>700:return url,None
  return url,label
 except Exception as exc:
  print('SKIP',url,type(exc).__name__,str(exc)[:100],flush=True)
  return url,None

def main():
 urls=json.loads((ROOT/'topcashback-merchants.json').read_text())
 dest=ROOT/'topcashback-rates.json'
 try:old=json.loads(dest.read_text())
 except (OSError,ValueError):old={}
 previous=old.get('rates',{})
 results=dict(previous)
 ok=0
 # Modest concurrency; do not retry failed pages or bypass anti-bot measures.
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  for url,rate in pool.map(fetch,urls):
   if rate:
    results[url]={'rate':rate,'status':'ok','verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    ok+=1
 print(f'Verified {ok}/{len(urls)} TopCashback merchant pages',flush=True)
 # Prevent silently publishing mass-corrupted results. Existing values remain available.
 if ok<max(10,int(len(urls)*0.05)):
  print('WARNING: unusually low success rate; existing rates retained, no new update published',flush=True)
  return
 dest.write_text(json.dumps({'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
   'verified_this_run':ok,'merchants_checked':len(urls),'rates':results},ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()

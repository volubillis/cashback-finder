import json,re,datetime,urllib.request
from html.parser import HTMLParser
from pathlib import Path
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.parts=[];self.skip=0
 def handle_starttag(self,t,a):
  if t in ('script','style'):self.skip+=1
  if t in ('h1','h2','h3','p','div','tr','li','span','td','br'):self.parts.append('\n')
 def handle_endtag(self,t):
  if t in ('script','style'):self.skip=max(0,self.skip-1)
  if t in ('h1','h2','h3','p','div','tr','li','span','td','br'):self.parts.append('\n')
 def handle_data(self,d):
  if not self.skip:self.parts.append(d)
urls={'Carrefour':'https://www.topcashback.fr/carrefour/','Courses U':'https://www.topcashback.fr/courses-u/','Uber':'https://www.topcashback.fr/uber/'}
offers=[]
for name,url in urls.items():
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept-Language':'fr-FR'})
  with urllib.request.urlopen(req,timeout=25) as response:html=response.read(2500000).decode('utf-8','replace')
  p=Parser();p.feed(html);text=''.join(p.parts)
  m=re.search(r'Cashback\s+'+re.escape(name)+r'\b',text,re.I)
  if not m:raise ValueError('Section cashback absente')
  section=re.split(r'Conditions pour bénéficier|Important à savoir',text[m.end():],maxsplit=1,flags=re.I)[0][:4000]
  amounts=[float(v.replace(',','.')) for v in re.findall(r'(?<![\d.,])(\d+(?:[.,]\d{1,2})?)\s*€',section)]
  active=any(abs(a-10)<0.001 for a in amounts)
  offers.append({'name':name,'url':url,'active':active,'amount_eur':10 if active else None,'status':'ok','observed_amounts_eur':amounts[:20]})
 except Exception as e:
  print(name,str(e));offers.append({'name':name,'url':url,'active':False,'amount_eur':None,'status':'unavailable'})
Path('topcashback-alerts.json').write_text(json.dumps({'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'offers':offers},ensure_ascii=False,indent=2))

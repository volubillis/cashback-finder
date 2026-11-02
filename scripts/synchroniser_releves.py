#!/usr/bin/env python3
"""Synchronise uniquement le comparateur statique depuis les releves verifies."""
import json, re, unicodedata
from pathlib import Path
from urllib.parse import urlparse, parse_qs

root=Path(__file__).resolve().parent.parent
site=root/"index.html"
html=site.read_text(encoding="utf-8")
m=re.search(r"const SEED=(\\[.*?\\]);const ",html,re.S)
if not m: raise SystemExit("SEED introuvable")
records=json.loads(m.group(1))
updates=json.loads((root/"data/maj-2026-11-02.json").read_text(encoding="utf-8"))["updates"]
rows=json.loads((root/"data/verifications-2026-11-02.json").read_text(encoding="utf-8"))["rows"]
def norm(s):
 s=unicodedata.normalize("NFKD",str(s or ""))
 return "".join(c for c in s.casefold() if c.isalnum())
def uid(url,p):
 if not url:return ""
 u=urlparse(url)
 if p=="rp":return parse_qs(u.query).get("affiliate_id",[""])[0]
 if p=="rr":return u.path.rstrip("/").split("/")[-1]
 return u.netloc.lower()+u.path.rstrip("/").lower()
byname={}
for r in records:byname.setdefault(norm(r.get("name")),[]).append(r)
counts={"updated":0,"already":0,"unmatched":0}
for u in updates:
 candidates=byname.get(norm(u["name"]),[])
 if len(candidates)!=1:
  counts["unmatched"]+=1
  continue
 r=candidates[0]; field=u["field"]
 if r.get(field)==u["value"]:counts["already"]+=1
 elif r.get(field,"")==u.get("previous",""):
  r[field]=u["value"];counts["updated"]+=1
 else:counts["unmatched"]+=1
cfg={"rp":("rp","rpDate","rpId",None),"rr":("rr","rrDate","rrId","rrUrl"),"tc":("tc","tcDate",None,"tcUrl"),"wi":("wi","wiDate",None,"wiUrl")}
dated={}
for p,(name,date,idfield,urlfield) in cfg.items():
 names={norm(n) for n,u in rows[p] if n}
 ids={uid(u,p) for n,u in rows[p] if u};ids.discard("")
 count=0
 for r in records:
  if not r.get(name):continue
  ok=norm(r.get(name)) in names
  if idfield and r.get(idfield):ok=ok or str(r[idfield]) in ids
  if urlfield and r.get(urlfield):ok=ok or uid(r[urlfield],p) in ids
  if ok:
   r[date]="2026-11-02";count+=1
 dated[p]=count
if len(records)!=4000:raise SystemExit("Nombre de marchands inattendu")
if min(dated.values())<1000:raise SystemExit("Correspondances insuffisantes : "+str(dated))
new=html[:m.start(1)]+json.dumps(records,ensure_ascii=False,separators=(",",":"))+html[m.end(1):]
site.write_text(new,encoding="utf-8")
print("Modifications",counts,"Dates",dated)

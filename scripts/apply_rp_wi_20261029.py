import json
from pathlib import Path
p=Path("index.html");s=p.read_text(encoding="utf-8")
a=s.index("const SEED=")+len("const SEED=");b=s.index("];",a)+1
rows=json.loads(s[a:b])
new=[
("Hailo Shop","6728fee97b89908996677d61","https://storage.effinity.fr/merchants/660024929/imgs/logos/Hailo_Logo-032424000861.png"),
("Maison Vayrou","6ae2c9adf16319fb29a385b7","https://cdn.kwanko.com/v/dyn/na/na/logos/prog/20/p80749-120x60.png?cb=1776954515"),
("Nacon FR","6ae2c9adf16319fb29a385b8","https://cdn.kwanko.com/v/dyn/na/na/logos/prog/20/p81159-120x60.png?cb=1790697010"),
("Lytess FR","6ae2ca31f16319fb29a385c6","https://ui.awin.com/images/upload/merchant/profile/131636.png")]
def key(v):return str(v or "").casefold().replace(" fr","").strip()
added=[]
for name,ident,logo in new:
 matches=[r for r in rows if ident in str(r.get("rpId","")).split(";")]
 if not matches:
  matches=[r for r in rows if key(r.get("name"))==key(name) or key(r.get("rp"))==key(name)]
 if len(matches)==1:
  r=matches[0]
  if ident not in str(r.get("rpId","")).split(";"):r["rpId"]=";".join(dict.fromkeys([x for x in str(r.get("rpId","")).split(";") if x]+[ident]))
  if not r.get("rp"):r["rp"]=name
  r["rpLogo"]=r.get("rpLogo") or logo
 else:
  rows.append({"name":name,"rp":name,"rpId":ident,"rpLogo":logo,"rpDate":"2026-10-29","match":"A verifier"})
  added.append({"platform":"rp","name":name,"id":ident,"type":"add","date":"2026-10-29"})
for r in rows:
 if r.get("rp"):r["rpDate"]="2026-10-29"
 if r.get("wiUrl","").rstrip("/")=="https://www.widilo.fr/code-promo/lidl":r["wiRate"]="4,9%"
 if r.get("wi"):r["wiDate"]="2026-10-29"
# Explicitly approved absent merchant IDs. Other platform data remain intact.
missing_rp="697448ca55d606cf8ebfb8f7"
for r in rows:
 parts=[x for x in str(r.get("rpId","")).split(";") if x]
 if missing_rp in parts:
  r["rpId"]=";".join(x for x in parts if x!=missing_rp)
  if not r["rpId"]:r["rp"]=""
 if r.get("wiUrl","").rstrip("/")=="https://www.widilo.fr/code-promo/biocoop":
  r["wi"]="";r["wiUrl"]="";r["wiRate"]=""
rows=[r for r in rows if any(r.get(k) for k in ("rp","rr","tc","wi"))]
s=s[:a]+json.dumps(rows,ensure_ascii=False,separators=(",",":"))+s[b:]
p.write_text(s,encoding="utf-8")
Path("updates/report-rp-wi-2026-10-29.json").write_text(json.dumps({"date":"2026-10-29","rp_added":added,"wi_rate_updated":"Lidl 4,9%","wi_empty_rates_preserved":True,"rp_missing_id":missing_rp,"wi_missing":"Biocoop"},ensure_ascii=False,indent=2),encoding="utf-8")

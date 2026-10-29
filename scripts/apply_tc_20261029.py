import json
from pathlib import Path
p=Path("index.html")
s=p.read_text(encoding="utf-8")
a=s.index("const SEED=")+len("const SEED=")
b=s.index("];",a)+1
rows=json.loads(s[a:b])
rates={
"amazon-prime-video": "Jusqu'à 3,50 € Cashback",
"famille-mary": "Jusqu'à 10% Cashback",
"joybuy": "Jusqu'à 10% Cashback",
"macpaw": "Jusqu'à 50% Cashback",
"vantrue": "Jusqu'à 18% Cashback",
"vistaprint": "Jusqu'à 8% Cashback"
}
changed=[]
removed=[]
for r in rows:
 url=str(r.get("tcUrl") or "").rstrip("/").split("/")[-1].lower()
 if r.get("tc") and (r.get("tc") in ("Chronopost","Savelys") or url in ("chronopost","savelys")):
  removed.append(r["tc"])
  for f in ("tc","tcRate","tcUrl","tcLogo","tcDesc","tcDate"):
   r[f]=""
 elif r.get("tc"):
  name=str(r.get("tc") or "").lower()
  expected={
   "amazon prime video":"amazon-prime-video",
   "famille mary":"famille-mary",
   "joybuy":"joybuy",
   "macpaw":"macpaw",
   "vantrue dashcam":"vantrue",
   "vistaprint":"vistaprint"
  }.get(name)
  if expected and expected in rates:
   old=r.get("tcRate")
   r["tcRate"]=rates[expected]
   r["tcDate"]="2026-10-29"
   changed.append([r.get("tc"),old,r["tcRate"]])
rows=[r for r in rows if any(r.get(f) for f in ("rp","rr","wi","tc"))]
s=s[:a]+json.dumps(rows,ensure_ascii=False,separators=(",",":"))+s[b:]
p.write_text(s,encoding="utf-8")
Path("updates/report-tc-2026-10-29.json").write_text(json.dumps({"removed":removed,"rates":changed},ensure_ascii=False,indent=2),encoding="utf-8")
print("REMOVED",removed,"CHANGED",changed)

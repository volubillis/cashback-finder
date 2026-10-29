import json
from pathlib import Path
p=Path("index.html")
s=p.read_text(encoding="utf-8")
a=s.index("const SEED=")+len("const SEED=")
b=s.index("];",a)+1
rows=json.loads(s[a:b])
for r in rows:
    if r.get("tc")=="Savelys":
        for field in ("tc","tcRate","tcDate","tcUrl","tcLogo","tcDesc"):
            r[field]=""
s=s[:a]+json.dumps(rows,ensure_ascii=False,separators=(",",":"))+s[b:]
event="const TC_SAVELYS_REMOVAL_28=[{platform:'tc',name:'Savelys',id:'',type:'remove',date:'2026-10-28'}];\n"
if "TC_SAVELYS_REMOVAL_28" not in s:
    s=s.replace("const CHANGE_STORAGE=",event+"const CHANGE_STORAGE=",1)
    s=s.replace("const combined=[...TC_CHANGES_20261027,","const combined=[...TC_SAVELYS_REMOVAL_28,...TC_CHANGES_20261027,",1)
migration="""try{
 const flag='tc_savelys_removed_20261028';
 if(localStorage.getItem(flag)!=='1'){
  for(const r of records)if(r.tc==='Savelys'){
   for(const f of ['tc','tcRate','tcDate','tcUrl','tcLogo','tcDesc'])r[f]='';
  }
  localStorage.setItem(STORAGE,JSON.stringify(records));
  localStorage.setItem(flag,'1');
 }
}catch(e){console.warn('Savelys migration',e)}
"""
if "tc_savelys_removed_20261028" not in s:
    s=s.replace("let page=0;const PAGE_SIZE=",migration+"let page=0;const PAGE_SIZE=",1)
p.write_text(s,encoding="utf-8")

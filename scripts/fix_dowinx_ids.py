import json
from pathlib import Path
p=Path('index.html');t=p.read_text()
a=t.index('const SEED=')+11;b=t.index('];',a)+1
v=json.loads(t[a:b])
for x in v:
 if x.get('name')=='Dowinx':x['rrId']='59118;60320'
p.write_text(t[:a]+json.dumps(v,ensure_ascii=False,separators=(',',':'))+t[b:])

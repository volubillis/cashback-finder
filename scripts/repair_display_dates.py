from pathlib import Path
p=Path("index.html")
s=p.read_text(encoding="utf-8")
d=chr(36)
for platform, field, date in [
 ("Réductions Privées","rpDate","28/10/2026"),
 ("Remises & Réductions","rrDate","28/10/2026"),
 ("Widilo","wiDate","28/10/2026")
]:
 old=platform+" ("+date+")"
 dynamic=platform+" ("+d+"{esc((x."+field+"||'Date inconnue').split('-').reverse().join('/'))})"
 s=s.replace(old,dynamic)
p.write_text(s,encoding="utf-8")

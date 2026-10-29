from pathlib import Path
p=Path("index.html")
s=p.read_text(encoding="utf-8")
s=s.replace("Réductions Privées (26/10/2026)", "Réductions Privées (28/10/2026)")
s=s.replace("Remises & Réductions (26/10/2026)", "Remises & Réductions (28/10/2026)")
p.write_text(s, encoding="utf-8")

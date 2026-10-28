#!/usr/bin/env python3
"""Compare platform snapshots without inventing new merchants from aliases or duplicate rows.

Usage:
  python scripts/compare_platform_snapshots.py rp old.csv new.csv index.html
  python scripts/compare_platform_snapshots.py rr old.csv new.csv index.html

This report is read-only: no card, alias, event history, or cashback rate is modified.
Absences are candidates for manual verification, never automatic deletions.
"""
import csv
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse, parse_qs

def key(s):
    t = unicodedata.normalize("NFKD", str(s or ""))
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in t if not unicodedata.combining(c)).lower())

def split(s):
    return [v.strip() for v in re.split(r"[;,|]", str(s or "")) if v.strip()]

def load_csv(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def row_parts(platform, r):
    if platform == "rp":
        name = (r.get("styles_item__header__QUAOK") or r.get("marchand") or "").strip()
        url = r.get("styles_item__bottom__RIGw9 href") or ""
        ident = parse_qs(urlparse(url).query).get("affiliate_id", [""])[0]
    elif platform == "rr":
        name = (r.get("marchand") or r.get("nom_a_verifier") or "").strip()
        url = r.get("col-md-3 href") or ""
        ident = url.rstrip("/").rsplit("/", 1)[-1] if url else ""
    else:
        raise ValueError("Supported platforms: rp, rr")
    return name, ident

def read_reference(index_path):
    text = Path(index_path).read_text(encoding="utf-8")
    marker = "const MERCHANT_REFERENCE=Object.freeze("
    start = text.index(marker) + len(marker)
    ref = json.loads(text[start:text.index(");", start)])
    marker = "const SEED="
    start = text.index(marker) + len(marker)
    seed = json.loads(text[start:text.index("];", start)+1])
    return seed, ref

def analyze(platform, oldfile, newfile, index):
    seed, ref = read_reference(index)
    aliases = ref.get("canonicalAliases", {})
    never = {frozenset((key(a), key(b))) for a,b in ref.get("neverMerge", [])}
    alias_to_canonical = {}
    for canonical, variants in aliases.items():
        for value in [canonical] + list(variants):
            alias_to_canonical[key(value)] = key(canonical)

    def canonical(v):
        return alias_to_canonical.get(key(v), key(v))

    # Historical platform identifiers and every known per-card alias win over spelling.
    id_to_cards = defaultdict(set)
    name_to_cards = defaultdict(set)
    for i, card in enumerate(seed):
        for ident in split(card.get(platform + "Id")):
            id_to_cards[ident].add(i)
        names = [card.get("name"), card.get(platform), card.get("rp"), card.get("rr"),card.get("tc"),card.get("wi")]
        for field in ("rrAliases","wiAliases","tcAliases"):
            names += card.get(field, []) or []
        for name in names:
            for v in split(name):
                if v: name_to_cards[canonical(v)].add(i)

    def identity(name, ident):
        if ident and len(id_to_cards.get(ident, ())) == 1:
            return "card:" + str(next(iter(id_to_cards[ident])))
        candidates = name_to_cards.get(canonical(name), set())
        candidates = {i for i in candidates if frozenset((key(name),key(seed[i].get("name")))) not in never}
        if len(candidates) == 1:
            return "card:" + str(next(iter(candidates)))
        # Same canonical name across multiple provider IDs must still count once.
        return "name:" + canonical(name) if not candidates else "ambiguous:" + canonical(name)

    def groups(path):
        found = defaultdict(lambda: {"names":set(), "ids":set()})
        for r in load_csv(path):
            name, ident = row_parts(platform,r)
            if not name: continue
            group = found[identity(name,ident)]
            group["names"].add(name)
            if ident: group["ids"].add(ident)
        return found

    old, new = groups(oldfile), groups(newfile)
    def report(groups, ids):
        return [{"canonical_key":k,"names":sorted(groups[k]["names"]),"ids":sorted(groups[k]["ids"])}
                for k in sorted(ids)]
    return {"platform":platform,"old_unique":len(old),"new_unique":len(new),
            "potential_additions":report(new, new.keys()-old.keys()),
            "absences_for_manual_review":report(old, old.keys()-new.keys()),
            "present":len(old.keys() & new.keys()),
            "warning":"Do not publish additions or deletions until aliases and IDs are verified."}

if __name__ == "__main__":
    if len(sys.argv)!=5:
        sys.exit("Usage: compare_platform_snapshots.py rp|rr old.csv new.csv index.html")
    print(json.dumps(analyze(*sys.argv[1:]),ensure_ascii=False,indent=2))

#!/usr/bin/env python3
"""Apply supplied CSV snapshots to the old static catalogue, preserving other platforms.

Dates describe the supplied source observation. Absence from one snapshot is flagged,
never treated as proof of removal. Input is validated completely before any write.
"""
import argparse
import copy
import csv
import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT=Path(__file__).resolve().parent.parent
PLATFORMS=('rp','rr','tc','wi')
FIELDS={
 'rp':('rp','rpId','rpLogo','rpDate'),
 'rr':('rr','rrId','rrLogo','rrUrl','rate','rrDate'),
 'tc':('tc','tcRate','tcUrl','tcLogo','tcDesc','tcDate'),
 'wi':('wi','wiRate','wiUrl','wiLogo','wiDate','wiAliases','wiUrls','wiRateDate','wiRateMissingSince'),
}

def encode(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')

def read_constant(html,name):
    start=html.index('const '+name+'=')+len('const '+name+'=')
    return json.JSONDecoder().raw_decode(html[start:])[0]

def replace_constant(html,name,value):
    start=html.index('const '+name+'=')+len('const '+name+'=')
    _,length=json.JSONDecoder().raw_decode(html[start:])
    return html[:start]+encode(value)+html[start+length:]

def key(value):
    value=''.join(c for c in unicodedata.normalize('NFD',str(value or '')) if not unicodedata.combining(c)).lower().replace('&',' et ')
    value=re.sub(r'\b(www|https|http)\b',' ',value)
    value=re.sub(r'[^a-z0-9]+',' ',value)
    value=re.sub(r'\b(france|francais|francaise|officiel|official|boutique|store|site)\b',' ',value)
    result=re.sub(r'\s+','',value)
    return 'monoprix' if result=='monoprixcourses' else result

def url_key(value):
    parsed=urlsplit(value or '')
    return parsed.netloc.lower()+parsed.path.rstrip('/').lower()

def identities(row,p):
    ids={'id:'+v.strip() for v in re.split('[;,]',str(row.get(p+'Id') or '')) if v.strip()}
    urls=[row.get(p+'Url')]+(row.get('wiUrls',[]) if p=='wi' else [])
    return ids|{'url:'+url_key(u) for u in urls if u}

def valid_rate(value,p):
    if not value:return p=='wi'
    return bool(re.fullmatch(r"(?:(?:jusqu['’]?\s*à|à partir de)\s*)?\d+(?:[.,]\d+)?\s*(?:%|€|euros?|zł)\s*(?:cashback|remboursés?)?|pas de cashback",value,re.I))

def read_snapshot(path,p,observed):
    with path.open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        columns=[c.strip().lower() for c in (reader.fieldnames or [])]
        required={'tc':{'cat-result href','cat-result-info__name','cat-result-info__rate'},'rr':{'col-md-3 href','percent_text','marchand'},'rp':set(),'wi':set()}[p]
        if not required<=set(columns) or len(set(columns))!=len(columns):raise ValueError(f'{p}: unexpected columns')
        raw=list(reader)
    rows=[];seen={}
    for number,r in enumerate(raw,2):
        if None in r or any(v is None for v in r.values()):raise ValueError(f'{p}: malformed CSV line {number}')
        r={k.strip().lower():v for k,v in r.items()}
        if p=='tc':
            source=dict(name=r['cat-result-info__name'].strip(),tc=r['cat-result-info__name'].strip(),tcRate=r['cat-result-info__rate'].strip(),tcUrl=r['cat-result href'].strip(),tcLogo=r.get('cat-result__logo-wrap src',''),tcDesc=r.get('cat-result-info__desc',''),tcDate=observed)
        elif p=='rr':
            url=r['col-md-3 href'].strip();mid=urlsplit(url).path.rstrip('/').split('/')[-1]
            source=dict(name=r['marchand'].strip(),rr=r['marchand'].strip(),rrId=mid,rrUrl=url,rrLogo=r.get('logo src',''),rate=r['percent_text'].strip(),rrDate=observed)
            if r.get('nom_a_verifier','').strip():raise ValueError(f'{p}: merchant flagged for checking at line {number}')
        elif p=='rp':
            name=(r.get('styles_item__header__quaok') or r.get('marchand') or r.get('nom') or r.get('marchand normalisé') or '').strip()
            url=r.get('styles_item__bottom__rigw9 href','')
            mid=r.get('identifiant(s) affiliation') or parse_qs(urlsplit(url).query).get('affiliate_id',[''])[0]
            source=dict(name=name,rp=name,rpId=mid,rpLogo=r.get('styles_item__image__lq1qq src') or r.get('url du logo',''),rpDate=observed)
        else:
            name=r.get('marchand','').strip();url=r.get('url','').strip()
            source=dict(name=name,wi=name,wiUrl=url,wiRate=r.get('cashback','').strip(),wiLogo=r.get('logo',''),wiDate=observed,wiAliases=[name],wiUrls=[url])
        if not source[p] or not identities(source,p):raise ValueError(f'{p}: missing merchant identity at line {number}')
        url=source.get(p+'Url','')
        expected={'tc':'www.topcashback.fr','rr':'www.remisesetreductions.fr','wi':'www.widilo.fr'}.get(p)
        if expected and (urlsplit(url).scheme!='https' or urlsplit(url).netloc!=expected or urlsplit(url).query):raise ValueError(f'{p}: unexpected source URL line {number}')
        if p!='rp' and not valid_rate(source.get('rate' if p=='rr' else p+'Rate',''),p):raise ValueError(f'{p}: invalid rate line {number}')
        identity=tuple(sorted(identities(source,p)))
        if identity in seen:
            if seen[identity]!=source:raise ValueError(f'{p}: conflicting duplicate line {number}')
            continue
        seen[identity]=source;rows.append(source)
    if len(rows)<1000:raise ValueError(f'{p}: unexpectedly short snapshot: {len(rows)}')
    return rows,{'source_file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'input_rows':len(raw),'unique_rows':len(rows)}

def apply(rows,sources,p,observed,aliases,complete=True):
    def canon(name):return aliases.get(key(name),key(name))
    def names(r):return {canon(n) for n in [r.get('name'),*r.get('mergedNames',[]),*[r.get(platform) for platform in PLATFORMS],*r.get('wiAliases',[]),*r.get('rrAliases',[]),*r.get('tcAliases',[])] if n}
    result={'added':[],'changed':[],'unchanged':0,'missing':[]};matched=set()
    id_index={};name_index={}
    def index_row(row):
        for identity in identities(row,p):
            bucket=id_index.setdefault(identity,[])
            if not any(r is row for r in bucket):bucket.append(row)
        for name in names(row):
            bucket=name_index.setdefault(name,[])
            if not any(r is row for r in bucket):bucket.append(row)
    for row in rows:index_row(row)
    def distinct(candidates):return list({id(r):r for r in candidates}.values())
    for source in sources:
        ids=identities(source,p)
        candidates=distinct(r for identity in ids for r in id_index.get(identity,[]))
        if len(candidates)>1:raise ValueError(f'{p}: ambiguous stable identity: {source["name"]}')
        if not candidates:
            candidates=distinct(r for name in names(source) for r in name_index.get(name,[]) if not r.get(p) or not identities(r,p) or identities(r,p)&ids)
        target=candidates[0] if len(candidates)==1 else None
        new=target is None or not target.get(p)
        if target is None:
            target={'name':source['name'],'match':'Source CSV vérifiée'};rows.append(target)
        repeated=id(target) in matched
        ratefield='rate' if p=='rr' else p+'Rate'
        if repeated and p!='rp' and source.get(ratefield) and target.get(ratefield)!=source.get(ratefield):raise ValueError(f'{p}: conflicting offers for merged merchant: {source["name"]}')
        if target.get(p+'Date','')>observed:raise ValueError(f'{p}: source older than existing data')
        matched.add(id(target))
        oldrate=target.get(ratefield,'');newrate=source.get(ratefield,'')
        if p=='wi':
            if newrate:
                source={**source,'wiRateDate':observed}
                target.pop('wiRateMissingSince',None)
            else:
                source={**source,'wiRate':oldrate,'wiRateDate':target.get('wiRateDate',target.get('wiDate','')) if oldrate else '', 'wiRateMissingSince':observed}
                newrate=oldrate
        if new:result['added'].append({'name':target['name'],'platform_name':source[p],'url':source.get(p+'Url',''),'id':source.get(p+'Id','')})
        elif oldrate!=newrate and p!='rp':result['changed'].append({'name':target['name'],'old':oldrate if valid_rate(oldrate,p) else 'Ancien taux invalide','next':newrate})
        else:result['unchanged']+=1
        for field in FIELDS[p]:
            if field in source:
                if field==p+'Id':target[field]=';'.join(dict.fromkeys([v.strip() for v in re.split('[;,]',str(target.get(field) or '')) if v.strip()]+[source[field]]))
                elif field.endswith(('Aliases','Urls')):target[field]=list(dict.fromkeys([*target.get(field,[]),*source[field]]))
                else:target[field]=source[field]
        aliasesfield=p+'Aliases'
        target[aliasesfield]=list(dict.fromkeys([*target.get(aliasesfield,[]),source[p]]))
        index_row(target)
        target.pop(p+'MissingSince',None)
    for target in rows:
        if complete and target.get(p) and id(target) not in matched:
            target[p+'MissingSince']=observed
            result['missing'].append({'name':target['name'],'url':target.get(p+'Url',''),'last_observed':target.get(p+'Date','')})
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date',required=True)
    parser.add_argument('--partial',action='append',choices=PLATFORMS,default=[],help='Do not infer absences for this partial platform snapshot')
    for p in PLATFORMS:parser.add_argument('--'+p,type=Path)
    args=parser.parse_args();observed=date.fromisoformat(args.date).isoformat()
    # Use explicit supplied observation dates, never the execution host's date.
    path=ROOT/'index.html';html=path.read_text(encoding='utf-8')
    seed=read_constant(html,'SEED');rows=copy.deepcopy(seed)
    reference=json.JSONDecoder().raw_decode(html.split('Object.freeze(',1)[1])[0]
    aliases={key(n):key(canonical) for canonical,names in reference['canonicalAliases'].items() for n in [canonical,*names]}
    published=read_constant(html,'PUBLISHED_DATES');events=read_constant(html,'PUBLISHED_CHANGES');latest=read_constant(html,'TC_LATEST')
    report_path=ROOT/'updates'/f'verified-{observed}.json'
    report=json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {'date':observed,'platforms':{}}
    snapshots={}
    for p in PLATFORMS:
        source=getattr(args,p)
        if source:
            values,metadata=read_snapshot(source,p,observed);snapshots[p]=values
            if published.get(p)==observed and report['platforms'].get(p,{}).get('sha256')==metadata['sha256']:
                continue
            result=apply(rows,values,p,observed,aliases,complete=p not in args.partial)
            report['platforms'][p]={**metadata,'complete':p not in args.partial,**result};published[p]=observed
            events=[e for e in events if not(e.get('platform')==p and e.get('date')==observed)]
            events.extend({'platform':p,'name':e['name'],'id':e.get('id',''),'url':e.get('url',''),'type':'add','date':observed} for e in result['added'])
            if p=='tc':latest={'date':observed,'changes':result['changed']}
    if not snapshots:raise ValueError('No source snapshots supplied')
    for p in PLATFORMS:
        if p not in published:published[p]=max((r.get(p+'Date','') for r in rows if r.get(p)),default='')
    # Every malformed source must have been replaced, rather than silently trimmed.
    invalid=[(r['name'],p) for r in rows for p in ('rr','tc','wi') if r.get(p) and r.get('rate' if p=='rr' else p+'Rate','') and not valid_rate(r.get('rate' if p=='rr' else p+'Rate',''),p)]
    if invalid:raise ValueError('Unresolved malformed published rates: '+str(invalid[:20]))
    for name,value in [('SEED',rows),('PUBLISHED_DATES',published),('PUBLISHED_CHANGES',events),('TC_LATEST',latest)]:html=replace_constant(html,name,value)
    # The report and normalized snapshots contain no temporary tracking query strings.
    target=ROOT/'data'/f'releves-{observed}.json'
    stored=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {'date':observed,'platforms':{}}
    stored['platforms'].update(snapshots)
    stored.setdefault('coverage',{}).update({p:'partial' if p in args.partial else 'complete' for p in snapshots})
    path.write_text(html,encoding='utf-8');report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');target.write_text(encode(stored)+'\n',encoding='utf-8')
    for p,r in report['platforms'].items():print(p,':',r['unique_rows'],'lignes,',len(r['changed']),'variations,',len(r['added']),'ajouts,',len(r['missing']),'absences conservées')

if __name__=='__main__':main()

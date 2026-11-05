// Published observations are authoritative; historical patches never run at startup.
const STORAGE='cashback_catalog_v17', LEGACY_STORAGE='cashback_catalog_v16';
const SITE_STORAGE='cashback_direct_sites_v1';
const VERIFIED_SITES={fnac:'https://www.fnac.com',darty:'https://www.darty.com',boulanger:'https://www.boulanger.com'};
let directSites={...VERIFIED_SITES};
try{directSites={...directSites,...JSON.parse(localStorage.getItem(SITE_STORAGE)||'{}')}}catch(e){}
let records;
let page=0;const PAGE_SIZE=60;const $=id=>document.getElementById(id);const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function norm(s){return String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/&/g,' et ').replace(/\b(www|https|http)\b/g,' ').replace(/[^a-z0-9]+/g,' ').replace(/\b(france|francais|francaise|officiel|official|boutique|store|site)\b/g,' ').replace(/\s+/g,' ').trim()}
function key(s){let k=norm(s).replace(/\s/g,'');return k==='monoprixcourses'?'monoprix':k}
// Référentiel interne invisible dans l'interface, mais consultable dans le code source.
const ALIAS_CANONICAL=new Map();
for(const [canonical,aliases] of Object.entries(MERCHANT_REFERENCE.canonicalAliases))for(const alias of [canonical,...aliases])ALIAS_CANONICAL.set(key(alias),canonical);


const PLATFORMS=['rp','rr','tc','wi'];
const PLATFORM_FIELDS={
 rp:['rp','rpId','rpLogo','rpDate','rpAliases','rpMissingSince'],
 rr:['rr','rrId','rrLogo','rrUrl','rate','rrDate','rrAliases','rrMissingSince'],
 tc:['tc','tcRate','tcUrl','tcLogo','tcDesc','tcDate','tcAliases','tcMissingSince'],
 wi:['wi','wiRate','wiUrl','wiLogo','wiDate','wiAliases','wiUrls','wiRateDate','wiRateMissingSince','wiMissingSince']
};
function clone(value){return JSON.parse(JSON.stringify(value));}
function validDate(value){return /^\d{4}-\d{2}-\d{2}$/.test(value||'')&&!Number.isNaN(Date.parse(value+'T12:00:00Z'))&&new Date(value+'T12:00:00Z').toISOString().slice(0,10)===value;}
function today(){return new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Paris',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());}
function observationDate(){const date=$('observationDate').value;if(!validDate(date)||date>today())throw Error('Choisis une date de relevé valide, qui ne soit pas dans le futur.');return date;}
function urlKey(value){try{const u=new URL(value);return u.hostname.toLowerCase()+u.pathname.replace(/\/+$/,'').toLowerCase();}catch(e){return '';}}
function identities(row,p){return [...new Set([
 ...String(row[p+'Id']||'').split(/[;,]/).filter(Boolean).map(v=>'id:'+v.trim()),
 ...[row[p+'Url'],...(p==='wi'?row.wiUrls||[]:[])].filter(Boolean).map(v=>'url:'+urlKey(v))
 ])];}
function nameKeys(row){return [...new Set([row.name,...(row.mergedNames||[]),...PLATFORMS.map(p=>row[p]),...(row.rrAliases||[]),...(row.tcAliases||[]),...(row.wiAliases||[])].filter(Boolean).map(n=>key(canonicalName(n)||n)))];}
function merchantIndex(rows,p){
 const ids=new Map(),names=new Map();
 const add=(map,key,row)=>{if(!map.has(key))map.set(key,new Set());map.get(key).add(row);};
 const addRow=row=>{for(const id of identities(row,p))add(ids,id,row);for(const name of nameKeys(row))add(names,name,row);};
 for(const row of rows)addRow(row);return {ids,names,addRow};
}
function findMerchant(rows,source,p,index=merchantIndex(rows,p)){
 const ids=identities(source,p);const exact=[...new Set(ids.flatMap(id=>[...(index.ids.get(id)||[])]))];
 if(exact.length===1)return exact[0];if(exact.length>1)throw Error('Identifiant marchand ambigu : '+source.name);
 const names=nameKeys(source);const named=[...new Set(names.flatMap(name=>[...(index.names.get(name)||[])]))];
 const eligible=named.filter(r=>!r[p]||!identities(r,p).length||!ids.length||identities(r,p).some(v=>ids.includes(v)));
 return eligible.length===1?eligible[0]:null;
}
function validRate(raw,p){
 const text=String(raw||'').trim();
 if(!text)return p==='wi';
 if(/https?:|[<>]/i.test(text))return false;
 return /^(?:(?:jusqu['’]?\s*à|à partir de)\s*)?\d+(?:[.,]\d+)?\s*(?:%|€|euros?|zł)\s*(?:cashback|remboursés?)?$/i.test(text)||/^pas de cashback$/i.test(text);
}
function loadCatalogue(){
 const rows=consolidateMerchants(clone(SEED));let saved;
 try{saved=JSON.parse(localStorage.getItem(STORAGE)||localStorage.getItem(LEGACY_STORAGE)||'null');}catch(e){}
 if(Array.isArray(saved))for(const source of saved){
  if(!source||typeof source!=='object'||typeof source.name!=='string')continue;
  for(const p of PLATFORMS){
   const date=source[p+'Date'],rate=p==='rr'?source.rate:source[p+'Rate'];
   if(!source[p]||!validDate(date)||date>today()||date<=(PUBLISHED_DATES[p]||'')||(p!=='rp'&&!validRate(rate,p)))continue;
   let dest=findMerchant(rows,source,p);
   if(!dest){dest={name:canonicalName(source.name)||source.name};rows.push(dest);}
   if(date<=(dest[p+'Date']||''))continue;
   for(const field of PLATFORM_FIELDS[p]){if(source[field]!==undefined)dest[field]=clone(source[field]);else delete dest[field];}
   dest.mergedNames=[...new Set([...(dest.mergedNames||[]),...(source.mergedNames||[]),source.name])];
  }
 }
 try{localStorage.setItem(STORAGE,JSON.stringify(rows));}catch(e){}
 return rows;
}
function applySnapshot(current,platform,observations,date){
 const rows=clone(current),seen=new Set(),index=merchantIndex(rows,platform);
 for(const source of observations){
  const rate=platform==='rr'?source.rate:source[platform+'Rate'];
  if(!source[platform]||!identities(source,platform).length)throw Error('Marchand sans identifiant : '+source.name);
  if(platform!=='rp'&&!validRate(rate,platform))throw Error('Taux non reconnu : '+source.name+' — '+rate);
  let dest=findMerchant(rows,source,platform,index);
  if(!dest){dest={name:canonicalName(source.name)||source.name};rows.push(dest);}
  if(seen.has(dest)&&platform!=='rp'&&(platform==='rr'?dest.rate:dest[platform+'Rate'])!==rate)throw Error('Offres contradictoires pour le marchand fusionné : '+source.name);
  seen.add(dest);
  if((dest[platform+'Date']||'')>date)throw Error('Le relevé est plus ancien que les données de '+dest.name+'.');
  for(const field of PLATFORM_FIELDS[platform]){if(source[field]!==undefined){if(field===platform+'Id')dest[field]=[...new Set([...String(dest[field]||'').split(/[;,]/).filter(Boolean),...String(source[field]).split(/[;,]/).filter(Boolean)])].join(';');else dest[field]=clone(source[field]);}}
  dest[platform+'Aliases']=[...new Set([...(dest[platform+'Aliases']||[]),source[platform]])];
  dest[platform+'Date']=date;delete dest[platform+'MissingSince'];
  index.addRow(dest);
 }
 for(const row of rows)if(row[platform]&&!seen.has(row)&&(row[platform+'Date']||'')<=date)row[platform+'MissingSince']=date;
 return rows;
}
function observationNotes(row){
 let text=PLATFORMS.filter(p=>row[p]&&row[p+'MissingSince']).map(p=>'<p class="muted observation-note">'+esc({rp:'Réductions Privées',rr:'Remises & Réductions',tc:'TopCashback',wi:'Widilo'}[p])+ ' : non retrouvé dans le relevé du '+esc(row[p+'MissingSince'].split('-').reverse().join('/'))+' ; dernière observation conservée.</p>').join('');
 if(row.wi&&row.wiRateMissingSince)text+='<p class="muted observation-note">Widilo : aucun taux fourni dans le relevé du '+esc(row.wiRateMissingSince.split('-').reverse().join('/'))+(row.wiRate?' ; dernière valeur connue'+(row.wiRateDate?' du '+esc(row.wiRateDate.split('-').reverse().join('/')):' conservée'):'')+'.</p>';
 return text;
}

records=loadCatalogue();

function canonicalName(name){return ALIAS_CANONICAL.get(key(name))||''}
function sameMerchant(a,b){if(!a||!b)return false;const ca=canonicalName(a),cb=canonicalName(b);if(ca||cb)return (ca||a)===(cb||b);return key(a)===key(b)}
function mergeMerchantFields(dest,src){
  dest.mergedNames=[...new Set([...(dest.mergedNames||[]),dest.name,...(src.mergedNames||[]),src.name].filter(Boolean))];
  for(const f of ['rpId','rrId']){
    const ids=[...String(dest[f]||'').split(/[;,]/),...String(src[f]||'').split(/[;,]/)].map(v=>v.trim()).filter(Boolean);
    if(ids.length)dest[f]=[...new Set(ids)].join(';');
  }
  for(const field of ['rp','rr','tc','wi']){
    if(!dest[field]&&src[field]){
      for(const f of field==='rp'?['rp','rpLogo','rpDate']:field==='rr'?['rr','rrLogo','rrUrl','rate','rrDate']:field==='tc'?['tc','tcRate','tcUrl','tcLogo','tcDesc','tcDate']:['wi','wiRate','wiUrl','wiDate'])if(src[f]!==undefined)dest[f]=src[f];
    }
  }
  for(const f of ['rrAliases','tcAliases','wiAliases','wiUrls']){
    const merged=[...(dest[f]||[]),...(src[f]||[])];if(merged.length)dest[f]=[...new Set(merged.filter(Boolean))];
  }
  for(const f of ['rpId','rrId','rpLogo','rrLogo','rrUrl','rate','tcRate','tcUrl','tcLogo','tcDesc','wiRate','wiUrl'])if(!dest[f]&&src[f])dest[f]=src[f];
}
function consolidateMerchants(rows){
 const output=[],byCanonical=new Map();
 for(const r of rows){
   const names=[r.name,r.rp,r.rr,r.tc,r.wi,...(r.rrAliases||[]),...(r.tcAliases||[]),...(r.wiAliases||[])].filter(Boolean);
   const canonical=names.map(canonicalName).find(Boolean);
   if(!canonical){output.push(r);continue}
   let dest=byCanonical.get(canonical);
   if(!dest){dest={...r,name:canonical,mergedNames:[...new Set([...(r.mergedNames||[]),r.name])]};byCanonical.set(canonical,dest);output.push(dest)}
   else mergeMerchantFields(dest,r);
 }
 return output;
}
function clean(s){return String(s||'').trim().replace(/\s+/g,' ')}
function rrName(url){try{let f=decodeURIComponent(new URL(url).pathname.split('/').pop()||'');return f.replace(/\.(png|jpe?g|gif|webp|svg)$/i,'').replace(/_?\d*x\d+.*$/i,'').replace(/_\d+$/,'').replace(/[_-]+/g,' ').trim()}catch(e){return ''}}
function parseCSV(text){
 text=String(text).replace(/^\uFEFF/,'');
 const firstLine=text.split(/\r?\n/,1)[0];let quoted=false,commas=0,semicolons=0;
 for(let i=0;i<firstLine.length;i++){if(firstLine[i]==='"'){if(quoted&&firstLine[i+1]==='"')i++;else quoted=!quoted;}else if(!quoted){if(firstLine[i]===',')commas++;if(firstLine[i]===';')semicolons++;}}
 const delimiter=semicolons>commas?';':',';let rows=[],row=[],field='';quoted=false;
 for(let i=0;i<text.length;i++){
  const c=text[i];
  if(c==='"'){if(quoted&&text[i+1]==='"'){field+='"';i++;}else quoted=!quoted;}
  else if(c===delimiter&&!quoted){row.push(field);field='';}
  else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(field);if(row.some(x=>x.trim()))rows.push(row);row=[];field='';}
  else field+=c;
 }
 if(quoted)throw Error('CSV invalide : guillemet non fermé.');
 row.push(field);if(row.some(x=>x.trim()))rows.push(row);if(!rows.length)return [];
 const headers=rows.shift().map(s=>s.trim().toLowerCase());
 if(new Set(headers).size!==headers.length)throw Error('CSV invalide : colonnes dupliquées.');
 return rows.map((values,index)=>{if(values.length!==headers.length)throw Error('CSV invalide à la ligne '+(index+2)+' : nombre de colonnes inattendu.');return Object.fromEntries(headers.map((h,i)=>[h,values[i]]));});
}

function rpExtract(rows){let out=[];for(const r of rows){let name=r['styles_item__header__quaok']||r['marchand normalisé']||r['nom(s) extrait(s)']||r['marchand']||r['nom'];let url=r['styles_item__bottom__rigw9 href']||'';let id=r['identifiant(s) affiliation']||'';try{if(url)id=id||new URL(url).searchParams.get('affiliate_id')||''}catch(e){}if(name)out.push({name:clean(name),id,logo:r['styles_item__image__lq1qq src']||r['url du logo']||'',date:observationDate()})}return out}
function rrExtract(rows){let out=[];for(const r of rows){let url=r['col-md-3 href']||r['lien marchand r&r']||'';let logo=r['logo src']||r['logo r&r']||'';let name=r['marchand']||r['nom extrait r&r']||rrName(logo);if(!name)continue;let id='';try{id=new URL(url).pathname.split('/').pop()}catch(e){}out.push({name:clean(name),id,logo,url,rate:r['percent_text']||r['taux annoncé r&r']||'',date:observationDate()})}return out}
function unique(arr){let m=new Map();for(const x of arr){let k=x.id||key(x.name);if(k&&!m.has(k))m.set(k,x)}return [...m.values()]}
function officialUrl(x){let u=directSites[key(x.name)]||directSites[key(x.rp)]||directSites[key(x.rr)]||directSites[key(x.wi)]||'';try{let parsed=new URL(u);return ['https:','http:'].includes(parsed.protocol)?parsed.href:''}catch(e){return ''}}
function searchCompact(s){return norm(s).replace(/\s+/g,'')}
function editDistance(a,b,limit){if(Math.abs(a.length-b.length)>limit)return limit+1;let prev=Array.from({length:b.length+1},(_,i)=>i);for(let i=1;i<=a.length;i++){let curr=[i],min=curr[0];for(let j=1;j<=b.length;j++){let v=Math.min(prev[j]+1,curr[j-1]+1,prev[j-1]+(a[i-1]===b[j-1]?0:1));curr[j]=v;min=Math.min(min,v)}if(min>limit)return limit+1;prev=curr}return prev[b.length]}
function searchRank(x,query){if(!query)return 0;let q=norm(query),compact=searchCompact(query);if(!compact)return 0;
let names=[...(x.wiAliases||[]),x.wi,x.name,x.rp,x.rr,x.tc,...(x.rrAliases||[])].filter(Boolean);
let best=Infinity;
for(let name of names){let normalized=norm(name),k=searchCompact(name);
if(k===compact)best=Math.min(best,0);
else if(k.startsWith(compact))best=Math.min(best,1);
else if(k.includes(compact))best=Math.min(best,2);
else if(normalized.includes(q))best=Math.min(best,2);
else if(compact.length>=4){
let max=compact.length<=5?1:compact.length<=9?2:3;
let variants=[k,...normalized.split(' ').map(searchCompact)].filter(v=>v.length>=3);
for(let v of variants){if(Math.abs(v.length-compact.length)<=max&&editDistance(compact,v,max)<=max)best=Math.min(best,3)}
}}
return best}

const CATEGORY_STORAGE='cashback_user_categories_v1';
let userCategories=[];
try{const v=JSON.parse(localStorage.getItem(CATEGORY_STORAGE)||'[]');if(Array.isArray(v))userCategories=v.filter(c=>c&&typeof c.id==='string'&&typeof c.name==='string'&&Array.isArray(c.members)).map(c=>({...c,members:c.members.filter(k=>typeof k==='string')}));}catch(e){}
let categoryMerchant=null;
function categoryKeys(x){return [...new Set(['name:'+key(x.name),...(x.mergedNames||[]).map(n=>'name:'+key(n)),...(String(x.rpId||'').split(/[;,]/).filter(Boolean).map(v=>'rp:'+v.trim())),...(String(x.rrId||'').split(/[;,]/).filter(Boolean).map(v=>'rr:'+v.trim())),...([x.tcUrl,x.wiUrl,...(x.wiUrls||[])].filter(Boolean).map(v=>'url:'+v))])];}
function merchantCategories(x){const keys=categoryKeys(x);return userCategories.filter(c=>keys.some(k=>c.members.includes(k)));}
function categoryMatches(x){const id=$('categoryFilter').value;const cats=merchantCategories(x);return !id||(id==='__none'?!cats.length:cats.some(c=>c.id===id));}
function persistCategories(){try{localStorage.setItem(CATEGORY_STORAGE,JSON.stringify(userCategories));return true;}catch(e){$('categoryStatus').textContent="Impossible d’enregistrer : le stockage du navigateur est indisponible.";return false;}}
function renderCategoryFilter(){const select=$('categoryFilter'),value=select.value;select.innerHTML='<option value="">Toutes les catégories</option><option value="__none">Sans catégorie</option>'+userCategories.map(c=>'<option value="'+esc(c.id)+'">'+esc(c.name)+'</option>').join('');select.value=value==='__none'||userCategories.some(c=>c.id===value)?value:'';}
function categoryCard(x){const index=records.indexOf(x);return '<div class="category-badges">'+merchantCategories(x).map(c=>'<span class="category-badge">'+esc(c.name)+'</span>').join('')+'</div><button type="button" class="button merchant-category-button" data-category-merchant="'+index+'">Classer</button>';}
function refreshCategoryDialog(){const choices=$('categoryChoices');choices.replaceChildren();const assigned=categoryMerchant?merchantCategories(categoryMerchant).map(c=>c.id):[];for(const c of userCategories){
 const row=document.createElement('div');row.className='category-row';
 const label=document.createElement('label');
 if(categoryMerchant){const checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=assigned.includes(c.id);checkbox.dataset.categoryId=c.id;label.append(checkbox,document.createTextNode(' '));}
 label.append(document.createTextNode(c.name));row.append(label);
 const rename=document.createElement('button');rename.type='button';rename.className='button';rename.textContent='Renommer';rename.onclick=()=>{const input=document.createElement('input');input.className='search';input.value=c.name;input.maxLength=80;input.setAttribute('aria-label','Nouveau nom');const save=document.createElement('button');save.type='button';save.className='button';save.textContent='Valider';save.onclick=()=>{const name=input.value.trim();if(!name||userCategories.some(other=>other.id!==c.id&&key(other.name)===key(name))){$('categoryStatus').textContent='Choisis un nom non vide et unique.';return;}c.name=name;persistCategories();renderCategoryFilter();refreshCategoryDialog();render();};row.replaceChildren(input,save);input.focus();};row.append(rename);
 const remove=document.createElement('button');remove.type='button';remove.className='button';remove.textContent='Supprimer';remove.onclick=()=>{userCategories=userCategories.filter(v=>v.id!==c.id);persistCategories();renderCategoryFilter();refreshCategoryDialog();page=0;render();};row.append(remove);choices.append(row);
}if(!userCategories.length)choices.textContent='Aucune catégorie. Crée ta première catégorie ci-dessus.';
 $('saveMerchantCategories').hidden=!categoryMerchant;
 $('categoryMerchantNote').textContent=categoryMerchant?'Classer « '+categoryMerchant.name+' » dans une ou plusieurs catégories.':'Créez, renommez ou supprimez vos catégories. Les marchands restent conservés.';
}
function openCategories(merchant){categoryMerchant=merchant;$('categoryStatus').textContent='';$('categoryName').value='';refreshCategoryDialog();$('categoryDialog').showModal();}
$('manageCategories').onclick=()=>openCategories(null);
$('createCategory').onclick=()=>{const name=$('categoryName').value.trim();if(!name||userCategories.some(c=>key(c.name)===key(name))){$('categoryStatus').textContent='Choisis un nom non vide et unique.';return;}userCategories.push({id:'cat_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,9),name,members:[]});persistCategories();$('categoryName').value='';$('categoryStatus').textContent='Catégorie créée.';renderCategoryFilter();refreshCategoryDialog();render();};
$('categoryName').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();$('createCategory').click();}});
$('saveMerchantCategories').onclick=()=>{if(!categoryMerchant)return;const keys=categoryKeys(categoryMerchant),chosen=new Set([...$('categoryChoices').querySelectorAll('input[data-category-id]:checked')].map(x=>x.dataset.categoryId));for(const c of userCategories){c.members=c.members.filter(k=>!keys.includes(k));if(chosen.has(c.id))c.members.push(...keys);c.members=[...new Set(c.members)];}if(persistCategories()){$('categoryDialog').close();page=0;render();}};
$('categoryFilter').addEventListener('change',()=>{page=0;render();});
$('results').addEventListener('click',e=>{const button=e.target.closest('[data-category-merchant]');if(button){const merchant=records[Number(button.dataset.categoryMerchant)];if(merchant)openCategories(merchant);}});
renderCategoryFilter();

function filtered(){let selected=['rp','rr','tc','wi'].filter((k,i)=>['rpCheck','rrCheck','tcCheck','wiCheck'][i] && $([ 'rpCheck','rrCheck','tcCheck','wiCheck'][i]).checked),q=$('search').value.trim();let items=records.filter(x=>selected.every(k=>Boolean(x[k]))&&categoryMatches(x)).map(x=>({x,rank:searchRank(x,q)})).filter(v=>v.rank!==Infinity);const order=$('sort').value;
items.sort((u,v)=>{
if(order==='cashback-asc'||order==='cashback-desc'){
const a=cashbackSortValue(u.x),b=cashbackSortValue(v.x);
if(a.known!==b.known)return a.known?-1:1;
const direction=order==='cashback-asc'?1:-1;
if(a.pct!==b.pct)return direction*(a.pct-b.pct);
if(a.eur!==b.eur)return direction*(a.eur-b.eur);
return u.x.name.localeCompare(v.x.name,'fr');
}
return q&&u.rank!==v.rank?u.rank-v.rank:u.x.name.localeCompare(v.x.name,'fr')*(order==='za'?-1:1);
});return items.map(v=>v.x)}
function cashbackSortValue(x){
let pct=x.rp?20:0,eur=0,known=Boolean(x.rp);
for(const [active,raw] of [[x.rr,x.rate],[x.tc,x.tcRate]]){
if(!active)continue;
const str=String(raw||'').replace(/\u00a0/g,' ').trim();
for(const m of str.matchAll(/(\d+(?:[.,]\d+)?)\s*(%|€|euros?)/gi)){
const n=Number(m[1].replace(',','.'));
if(!Number.isFinite(n))continue;
known=true;
if(m[2]==='%')pct+=n;else eur+=n;
}
}
return {pct,eur,known};
}
function cashbackTotal(x){
const fmt=n=>new Intl.NumberFormat('fr-FR',{maximumFractionDigits:2}).format(n);
let pct=x.rp?20:0,eur=0,unknown=[],upTo=false;
for(const [active,raw,label] of [[x.rr,x.rate,'R&R'],[x.tc,x.tcRate,'TopCashback']]){
if(!active)continue;let str=String(raw||'').replace(/\u00a0/g,' ').trim();if(/jusqu[’']?\s*à/i.test(str))upTo=true;
let matches=[...str.matchAll(/(\d+(?:[.,]\d+)?)\s*(%|€|euros?)/gi)];
if(!matches.length){unknown.push(label);continue}
// A single advertised rate is not necessarily stackable or guaranteed.
for(const m of matches){let n=Number(m[1].replace(',','.'));if(!Number.isFinite(n))continue;if(m[2]==='%')pct+=n;else eur+=n}
}
let parts=[];if(pct)parts.push(fmt(pct)+' %');if(eur)parts.push(fmt(eur)+' €');
if(!parts.length&&!unknown.length)return '';
let label='Total indicatif'+(upTo?' (jusqu’à)':'')+' : '+(parts.join(' + ')||'non calculable');
if(unknown.length)label+=' + taux '+unknown.join(', ')+' non renseigné';return label;
}
function render(){let rp=records.filter(x=>x.rp).length,rr=records.filter(x=>x.rr).length,tc=records.filter(x=>x.tc).length,wi=records.filter(x=>x.wi).length,both=records.filter(x=>x.rp&&x.rr&&x.tc&&x.wi).length;let selected=[['rpCheck','Réductions Privées'],['rrCheck','Remises & Réductions'],['tcCheck','TopCashback'],['wiCheck','Widilo']].filter(([id])=>$(id).checked).map(([,name])=>name);let title=selected.length===0?'Tous les marchands':selected.length===1?'Marchands '+selected[0]:'Marchands communs';$('modeLabel').textContent=selected.length>1?'Intersection des plateformes sélectionnées':selected.length===1?'Catalogue de la plateforme sélectionnée':'Ensemble des quatre catalogues';$('resultTitle').textContent=title;let data=filtered();$('rpCount').textContent=rp.toLocaleString('fr-FR');$('rrCount').textContent=rr.toLocaleString('fr-FR');$('tcCount').textContent=tc.toLocaleString('fr-FR');$('wiCount').textContent=wi.toLocaleString('fr-FR');$('bothCount').textContent=both.toLocaleString('fr-FR');$('shownCount').textContent=data.length.toLocaleString('fr-FR');$('resultSubtitle').textContent=data.length+' résultat(s)';let totalPages=Math.ceil(data.length/PAGE_SIZE);page=Math.max(0,Math.min(page,totalPages-1));let subset=data.slice(page*PAGE_SIZE,(page+1)*PAGE_SIZE);$('results').innerHTML=subset.length?subset.map(x=>`<article class="merchant"><div class="name">${esc(x.name)}</div><div class="description">${esc(x.tcDesc||'')}</div><div class="tags">${x.rp?`<span class="tag">Réductions Privées (${esc((x.rpDate||'Date inconnue').split('-').reverse().join('/'))}) <strong>20 %</strong></span>`:''}${x.rr?`<span class="tag green">Remises & Réductions (${esc((x.rrDate||'Date inconnue').split('-').reverse().join('/'))}) <strong>${esc(x.rate||'Taux non renseigné')}</strong></span>`:''}${x.tc?`<span class="tag purple">TopCashback (${esc((x.tcDate||'Date inconnue').split('-').reverse().join('/'))}) <strong>${esc(x.tcRate||'Taux non renseigné')}</strong></span>`:''}${x.wi?`<span class="tag orange">Widilo (${esc((x.wiDate||'Date inconnue').split('-').reverse().join('/'))}) <strong>${esc(x.wiRate||'Taux non fourni')}</strong></span>`:''}</div><div class="cashback-total">${esc(cashbackTotal(x))}</div>${observationNotes(x)}${categoryCard(x)}${officialUrl(x)?`<a class="small" href="${esc(officialUrl(x))}" target="_blank" rel="noopener noreferrer">Site officiel ↗</a>`:`<a class="small" href="${esc("https://www.google.com/search?btnI=1&q="+encodeURIComponent(x.name+" site officiel"))}" target="_blank" rel="noopener noreferrer" title="Recherche Google avec option J’ai de la chance (redirection non garantie)">Trouver le site via Google ↗</a>`}</article>`).join(''):'<div class="empty">Aucun marchand pour ces critères.</div>';$('pager').innerHTML=totalPages>1?`<button class="button" id="prev" ${page===0?'disabled':''}>← Précédent</button><span class="muted">Page ${page+1} / ${totalPages}</span><button class="button" id="next" ${page>=totalPages-1?'disabled':''}>Suivant →</button>`:'';if($('prev'))$('prev').onclick=()=>{page--;render();window.scrollTo({top:300,behavior:'smooth'})};if($('next'))$('next').onclick=()=>{page++;render();window.scrollTo({top:300,behavior:'smooth'})}}
$('clearPlatforms').onclick=()=>{for(const id of ['rpCheck','rrCheck','tcCheck','wiCheck'])$(id).checked=false;page=0;render()};
for(const id of ['rpCheck','rrCheck','tcCheck','wiCheck','search','sort'])$(id).addEventListener(id==='search'?'input':'change',()=>{page=0;render()});$('toggleImport').onclick=()=>$('imports').classList.toggle('hidden');
const sitePanel=document.createElement('div');sitePanel.className='panel';sitePanel.innerHTML='<h3>Liens directs des marchands</h3><p>Importer un CSV avec deux colonnes : <strong>Marchand</strong> et <strong>Site officiel</strong>. Seules les adresses renseignées sont affichées. Les modifications restent dans ce navigateur ; pour publier les liens à tous, il faut les intégrer au fichier HTML du dépôt GitHub.</p><input type="file" id="siteFile" accept=".csv,text/csv"> <button class="button" id="siteImport">Importer les sites officiels</button><p id="siteMessage" class="muted"></p>';
$('imports').appendChild(sitePanel);
$('siteImport').onclick=async()=>{let f=$('siteFile').files[0];if(!f)return $('siteMessage').textContent='Choisis un CSV.';let rows=parseCSV(await f.text()),count=0;for(let r of rows){let n=r['marchand']||r['nom']||r['merchant']||'',u=r['site officiel']||r['url officielle']||r['url']||'';try{let v=new URL(u);if(n&&['https:','http:'].includes(v.protocol)){directSites[key(n)]=v.href;count++}}catch(e){}}try{localStorage.setItem(SITE_STORAGE,JSON.stringify(directSites))}catch(e){}$('siteMessage').textContent=count+' adresse(s) enregistrée(s) localement.';render()};$('resetBtn').onclick=()=>{if(!confirm('Restaurer les données initiales ?'))return;records=clone(SEED);localStorage.setItem(STORAGE,JSON.stringify(records));tcRateChanges=TC_LATEST.changes.slice();tcRateDate=TC_LATEST.date.split('-').reverse().join('/');localStorage.removeItem(TC_RATE_CHANGES_STORAGE);renderTcRateChanges();$('importMessage').textContent='Données initiales restaurées.';page=0;render()};
function tcExtract(rows,date){return rows.map(r=>({name:clean(r['cat-result-info__name']),rate:clean(r['cat-result-info__rate']),url:r['cat-result href']||'',logo:r['cat-result__logo-wrap src']||'',desc:r['cat-result-info__desc']||'',date})).filter(r=>r.name);}
const TC_CHANGES_20261027=[{"platform":"tc","name":"OUIGO","id":"","type":"add","date":"2026-10-27"},{"platform":"tc","name":"Varsity Base","id":"","type":"add","date":"2026-10-27"},{"platform":"tc","name":"Weekendesk","id":"","type":"add","date":"2026-10-27"}];
const PLATFORM_CHANGES_20261027=[{"platform":"rp","name":"Maison Amour","id":"6aded51ca7d4f41774ef76b5","type":"add","date":"2026-10-27"},{"platform":"rp","name":"Lunazone FR","id":"6ae02725c27574ced3d396d9","type":"add","date":"2026-10-27"},{"platform":"rp","name":"Scento","id":"6ae0272cc27574ced3d396ef","type":"add","date":"2026-10-27"},{"platform":"wi","name":"Ava & May","id":"","type":"add","date":"2026-10-27"},{"platform":"wi","name":"Qonto","id":"","type":"add","date":"2026-10-27"},{"platform":"rp","name":"High","id":"6936af1fa8beb28ede6e5c4e","type":"remove","date":"2026-10-27"},{"platform":"rp","name":"Omy maison","id":"672453861966b5e36bd41b37","type":"remove","date":"2026-10-27"},{"platform":"rp","name":"Thecoolrepublic.Com","id":"696f02d18a6c96c927592093","type":"remove","date":"2026-10-27"}];
const TC_SAVELYS_REMOVAL_28=[{platform:'tc',name:'Savelys',id:'',type:'remove',date:'2026-10-28'}];
const CHANGE_STORAGE='cashback_changes_v1';
const CHANGE_INITIAL=[['Momox shop','','add','tc'],['Alpiniste','','add','tc'],['GlobalExam','','add','tc'],['Yves Rocher Belgique','','add','tc'],['Piècesauto.fr','35731','add'],['Jardins Anims','35903','add'],['Interiorlabels','47229','add'],['Confiserie des Arcades / Maison Thomas','54826','add'],['Richart','60324','add'],['Monkeymum','36351','remove']].map(([name,id,type,platform])=>({platform:platform||'rr',name,id,type,date:'2026-10-20'}));
const TC_NORAUTO_20261021=[{platform:'tc',name:'Norauto',id:'',type:'add',date:'2026-10-21'}];
const RP_CHANGES_20261021=[{"platform":"rp","name":"Ferryhopper","id":"6ad6eca7d0b2f4d23d0bc0d9","type":"add","date":"2026-10-21"},{"platform":"rp","name":"HiBike","id":"6ad6ecacd0b2f4d23d0bc0f0","type":"add","date":"2026-10-21"},{"platform":"rp","name":"Poedagar","id":"6ad83e2aa9e119936b6a3243","type":"add","date":"2026-10-21"},{"platform":"rp","name":"Clairage Déco","id":"6a4c7f260d6e51f8fe39837c","type":"remove","date":"2026-10-21"},{"platform":"rp","name":"Mack International","id":"68a69bd43135d43f44a69a1f","type":"remove","date":"2026-10-21"}];
const RR_CHANGES_20261021=[{platform:'rr',name:'Clairage Déco',id:'60700',type:'remove',date:'2026-10-21'}];
const TC_CHANGES_20261021=[
...[{"platform":"tc","name":"Shein","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"ALL - Accor Live Limitless","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"trivago","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Hotelscom","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Expedia","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Tripcom","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Parc Astérix","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Holidu","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Getyourguide","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Trainline","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Autodoc","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Pneus.fr","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"ManoMano","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Loberon","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Zooplus","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Vevor","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Bultex","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Costway","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Maisons du monde","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Plenitude","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"EDF","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"France Abonnements","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Roblox","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Startselect","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Lego","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Myphotobook","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Direct Volley","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"365 Rider","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Basket Center","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Puma","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Illy","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"L'Or Espresso","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Bonne Maman","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Vestiaire Collective","id":"","type":"remove","date":"2026-10-21"},{"platform":"tc","name":"Mova","id":"","type":"remove","date":"2026-10-21"},{"platform":"tc","name":"PrivacyHawk","id":"","type":"remove","date":"2026-10-21"}],
{platform:"tc",name:"BforBank",id:"",type:"remove",date:"2026-10-21"},
...[{"platform":"tc","name":"L'olivier Assurance Habitation","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"La Banque Postale - Assurance Santé","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Meilleurtaux Assurance Auto","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"L'olivier Assurance","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Remitly","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Lemonade","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Meilleurtaux Assurance Habitation","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Western Union","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Coinbase","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Achat or et argent","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"CHANGE DE LA BOURSE","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"BforBank","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Ulygo","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Crypto.com","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"La Banque Postale - Assurance Habitation","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Kraken","id":"","type":"add","date":"2026-10-21"},{"platform":"tc","name":"Meilleurtaux Assurance Prêt","id":"","type":"add","date":"2026-10-21"}],
  {platform:'tc',name:'Patolo',id:'',type:'add',date:'2026-10-21'},
  ...['Starlink','Tennis Point','Ahead Nutrition'].map(name=>({platform:'tc',name,id:'',type:'add',date:'2026-10-21'})),
  ...['Republicain Lorrain','DNA','le Bien Public',"L'Est Republicain"].map(name=>({platform:'tc',name,id:'',type:'remove',date:'2026-10-21'}))
];
// L'historique intégré reste la source de référence, même si le navigateur a stocké [].
let changeHistory;
try {
  const saved=JSON.parse(localStorage.getItem(CHANGE_STORAGE)||'null');
  const local=Array.isArray(saved)?saved:[];
  const combined=[...PUBLISHED_CHANGES,...TC_SAVELYS_REMOVAL_28,...TC_CHANGES_20261027,...RP_CHANGES_20261021,...RR_CHANGES_20261021,...TC_NORAUTO_20261021,...TC_CHANGES_20261021,...local,...CHANGE_INITIAL];
  const seen=new Set();
  changeHistory=combined.filter(c=>{const k=[c.platform,c.id||c.name,c.type,c.date].join('|');if(seen.has(k))return false;seen.add(k);return true;}).slice(0,1000);
} catch(e) {changeHistory=[...PUBLISHED_CHANGES,...TC_CHANGES_20261027,...RP_CHANGES_20261021,...RR_CHANGES_20261021,...TC_NORAUTO_20261021,...TC_CHANGES_20261021,...CHANGE_INITIAL];}

// Ajout issu du relevé Widilo du 20 octobre 2026, conservé avec les historiques locaux.
if(!changeHistory.some(c=>c.platform==='wi'&&c.name==='Emergent IA'&&c.type==='add'&&c.date==='2026-10-20'))changeHistory.unshift({platform:'wi',name:'Emergent IA',id:'',type:'add',date:'2026-10-20'});
const WI_CHANGES_20261022=[{"platform":"wi","name":"Myphotobook","id":"myphotobook","type":"add","date":"2026-10-22"},{"platform":"wi","name":"MyPOS","id":"mypos","type":"add","date":"2026-10-22"},{"platform":"wi","name":"Myposter","id":"myposter","type":"add","date":"2026-10-22"},{"platform":"wi","name":"Myprotein","id":"myprotein","type":"add","date":"2026-10-22"},{"platform":"wi","name":"My Protein Belgique","id":"myprotein-belgique","type":"add","date":"2026-10-22"},{"platform":"wi","name":"Myriam K","id":"myriam-k","type":"add","date":"2026-10-22"},{"platform":"wi","name":"Mytheresa","id":"mytheresa","type":"add","date":"2026-10-22"},{"platform":"wi","name":"Mytrip","id":"mytrip","type":"add","date":"2026-10-22"},{"platform":"wi","name":"MyVariations","id":"myvariations","type":"add","date":"2026-10-22"},{"platform":"wi","name":"Myvitamins","id":"myvitamins","type":"add","date":"2026-10-22"}];
for(const event of WI_CHANGES_20261022){if(!changeHistory.some(c=>c.platform===event.platform&&c.date===event.date&&c.type===event.type&&(c.id===event.id||c.name===event.name)))changeHistory.unshift(event);}
const RR_REMOVALS_20261022=[{"platform": "rr", "name": "Curls Matter", "id": "61840", "type": "remove", "date": "2026-10-22"}, {"platform": "rr", "name": "Olara", "id": "58368", "type": "remove", "date": "2026-10-22"}];
for(const event of RR_REMOVALS_20261022){if(!changeHistory.some(c=>c.platform===event.platform&&c.id===event.id&&c.type===event.type&&c.date===event.date))changeHistory.unshift(event);}

const WI_ADDITIONS_20261023=[{platform:'wi',name:'Ava & May',id:'ava-may',type:'add',date:'2026-10-23'},{platform:'wi',name:'Qonto',id:'qonto',type:'add',date:'2026-10-23'}];
for(const event of WI_ADDITIONS_20261023)if(!changeHistory.some(c=>c.platform==='wi'&&c.type==='add'&&c.date===event.date&&(c.id===event.id||c.name===event.name)))changeHistory.unshift(event);

const CHANGES_20261024=[{"platform":"rp","name":"Médor et Cie","id":"6728feea7b89908996677d8e","type":"remove","date":"2026-10-24"},{"platform":"rr","name":"HiBike","id":"63152","type":"add","date":"2026-10-24"},{"platform":"rr","name":"Ava & May","id":"63153","type":"add","date":"2026-10-24"},{"platform":"rr","name":"Cavissima","id":"63154","type":"add","date":"2026-10-24"}];
for(const event of CHANGES_20261024)if(!changeHistory.some(c=>c.platform===event.platform&&c.id===event.id&&c.type===event.type&&c.date===event.date))changeHistory.unshift(event);
const LIBERNOVO_EVENT={platform:'rr',name:'LiberNovo',id:'63136',type:'add',date:'2026-10-23'};
if(!changeHistory.some(c=>c.platform==='rr'&&String(c.id)==='63136'&&c.type==='add'))changeHistory.unshift(LIBERNOVO_EVENT);
try{localStorage.setItem(CHANGE_STORAGE,JSON.stringify(changeHistory))}catch(e){}
for(const event of PLATFORM_CHANGES_20261027){
 const same=(x,y)=>String(x||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'')===String(y||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
 if(!changeHistory.some(e=>e.platform===event.platform&&e.type===event.type&&(event.id&&e.id===event.id||same(e.name,event.name))))changeHistory.unshift(event);
}
changeHistory.sort((a,b)=>String(b.date||'').localeCompare(String(a.date||'')));
try{localStorage.setItem(CHANGE_STORAGE,JSON.stringify(changeHistory))}catch(e){}
function platformSnapshot(rows,p){let m=new Map();for(const x of rows){if(!x[p])continue;let id=String(x[p+'Id']||'').trim(),k=id?'id:'+id:'name:'+key(x[p]);if(!m.has(k))m.set(k,{name:x.name||x[p],id})}return m}
function recordChanges(before,after,platforms){let changes=[],date=observationDate();for(const p of platforms){let a=platformSnapshot(before,p),b=platformSnapshot(after,p);for(const [k,v] of b)if(!a.has(k))changes.push({platform:p,type:'add',...v,date});for(const [k,v] of a)if(!b.has(k))changes.push({platform:p,type:'remove',...v,date})}changeHistory=[...changes.reverse(),...changeHistory].slice(0,1000);try{localStorage.setItem(CHANGE_STORAGE,JSON.stringify(changeHistory))}catch(e){}}
function canonicalChangeName(c){
 // Retrouver la fiche canonique à partir de l'identifiant de la plateforme.
 const match=records.find(x=>c.id && String(x[c.platform+'Id']||'')===String(c.id));
 if(match && match.name)return match.name;
 // Fallback pour les événements historiques, y compris les marchands retirés.
 const known={'rr:35903':'Jardins Animes','rr:47229':'Interiorlabels.fr','rr:54826':'Confiserie des Arcades - Maison THOMAS FR','rr:35731':'Piècesauto.fr','rr:60324':'Richart'};
 return known[c.platform+':'+c.id]||c.name;
}
function renderChanges(){
 for(const p of ['rp','rr','tc','wi']){
  const ul=$('changes-'+p);ul.replaceChildren();
  const list=changeHistory.filter(c=>c.platform===p).slice(0,10);
  if(!list.length){const li=document.createElement('li');li.textContent='Aucun changement enregistré.';ul.append(li)}
  for(const c of list){
   const li=document.createElement('li'),b=document.createElement('strong'),date=document.createElement('span'),lucky=document.createElement('a');
   const name=canonicalChangeName(c);
   b.style.color=c.type==='add'?'#167347':'#ba3340';
   b.textContent=c.type==='add'?'+ Ajout : ':'− Retrait : ';
   date.className='change-date';date.textContent=c.date+(c.id?' · ID '+c.id:'');
   lucky.className='small';lucky.textContent='Feel lucky ↗';
   lucky.href='https://www.google.com/search?btnI=1&q='+encodeURIComponent(name+' site officiel');
   lucky.target='_blank';lucky.rel='noopener noreferrer';
   lucky.title='Google : J’ai de la chance — '+name;
   lucky.setAttribute('aria-label','Feel lucky : trouver le site officiel de '+name+' via Google');
   li.append(b,document.createTextNode(name+' · '),lucky,date);ul.append(li);
  }
 }
}
const TC_RATE_CHANGES_STORAGE='cashback_tc_rate_changes_latest_v1';
const TC_RATE_CHANGES_DEFAULT=[{"name":"Hotelscom","old":"10% Cashback","next":"6% Cashback"}];
let tcRateChanges=TC_LATEST.changes.slice(),tcRateDate=TC_LATEST.date.split('-').reverse().join('/');
try{let v=JSON.parse(localStorage.getItem(TC_RATE_CHANGES_STORAGE)||'null');if(v&&Array.isArray(v.changes)&&v.date&&validDate(v.date.split('/').reverse().join('-'))&&v.date.split('/').reverse().join('-')<=today()&&v.date.split('/').reverse().join('-')>TC_LATEST.date){tcRateChanges=v.changes;tcRateDate=v.date||tcRateDate}}catch(e){}
function renderTcRateChanges(){let body=$('tc-rate-changes-body');body.replaceChildren();$('tc-rate-note').textContent='Dernier relevé : '+tcRateDate+' · Les variations précédentes sont remplacées à chaque nouvel import TopCashback.';if(!tcRateChanges.length){let tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=3;td.textContent='Aucune variation de taux détectée lors du dernier import.';tr.append(td);body.append(tr);return}for(let c of tcRateChanges){let tr=document.createElement('tr');for(let v of [c.name,c.old,c.next]){let td=document.createElement('td');td.textContent=v;tr.append(td)}body.append(tr)}}
function tcRateKey(x){let u=String(x.tcUrl||'').trim();if(u){try{return new URL(u).pathname.replace(/\/+$/,'').toLowerCase()}catch(e){}}return key(x.tc||x.name)}
function updateTcRateChanges(before,after){let prior=new Map();for(let x of before)if(x.tc)prior.set(tcRateKey(x),x);let changes=[];for(let x of after){if(!x.tc)continue;let old=prior.get(tcRateKey(x));if(old&&String(old.tcRate||'').trim()!==String(x.tcRate||'').trim())changes.push({name:x.name||x.tc,old:old.tcRate||'—',next:x.tcRate||'—'})}tcRateChanges=changes.sort((a,b)=>a.name.localeCompare(b.name,'fr'));tcRateDate=observationDate().split('-').reverse().join('/');try{localStorage.setItem(TC_RATE_CHANGES_STORAGE,JSON.stringify({date:tcRateDate,changes:tcRateChanges}))}catch(e){}renderTcRateChanges()}
renderTcRateChanges();
$('observationDate').value=today();$('observationDate').max=today();
$('publishedDates').textContent='Derniers relevés intégrés : '+PLATFORMS.map(p=>({rp:'Réductions Privées',rr:'Remises & Réductions',tc:'TopCashback',wi:'Widilo'}[p])+' '+(PUBLISHED_DATES[p]||'date inconnue').split('-').reverse().join('/')).join(' · ');
$('importBtn').onclick=async()=>{
 const selected=PLATFORMS.slice(0,3).filter(p=>$(p+'Files').files.length);
 if(!selected.length){$('importMessage').textContent='Sélectionne au moins un fichier CSV.';return;}
 try{
  const date=observationDate(),before=clone(records);let next=clone(records),counts=[];
  for(const p of selected){
   let parsed=[];for(const f of $(p+'Files').files)parsed.push(...parseCSV(await f.text()));
   const extracted=p==='rp'?rpExtract(parsed):p==='rr'?rrExtract(parsed):tcExtract(parsed,date);
   if(!extracted.length)throw Error('Aucun marchand reconnu dans le fichier '+p+'.');
   const sources=extracted.map(x=>({name:x.name,[p]:x.name,[p+'Date']:date,...(p==='rp'?{rpId:x.id,rpLogo:x.logo}:p==='rr'?{rrId:x.id,rrUrl:x.url,rrLogo:x.logo,rate:x.rate}:{tcUrl:x.url,tcLogo:x.logo,tcDesc:x.desc,tcRate:x.rate})}));
   // Category exports can repeat an identical merchant. Conflicting duplicates must block the import.
   const uniqueSources=new Map();
   for(const source of sources){const id=identities(source,p).join('|');const previous=uniqueSources.get(id);if(previous&&JSON.stringify(previous)!==JSON.stringify(source))throw Error('Doublon contradictoire : '+source.name);uniqueSources.set(id,source);}
   next=applySnapshot(next,p,[...uniqueSources.values()],date);counts.push(uniqueSources.size+' '+p.toUpperCase());
  }
  records=next;
  if(selected.includes('tc'))updateTcRateChanges(before,records);
  recordChanges(before,records,selected);
  try{localStorage.setItem(STORAGE,JSON.stringify(records));$('importMessage').textContent='Import local réussi : '+counts.join(', ')+' — relevé du '+date.split('-').reverse().join('/')+'. Les autres plateformes et les catégories sont conservées.';}catch(e){$('importMessage').textContent='Import effectué, mais le stockage du navigateur est plein : les données ne seront pas conservées après fermeture.';}
  page=0;render();renderChanges();
 }catch(e){$('importMessage').textContent='Import annulé : '+e.message;}
};

$('exportBtn').onclick=()=>{let rows=[['Marchand','Réductions Privées','Remises & Réductions','Nom RP','Nom R&R','ID RP','ID R&R','Site officiel','Taux RP','Taux R&R','TopCashback','Taux TopCashback','Lien TopCashback','Widilo','Nom Widilo','Taux Widilo','Lien Widilo','Total indicatif'],...filtered().map(x=>[x.name,x.rp?'Oui':'Non',x.rr?'Oui':'Non',x.rp,x.rr,x.rpId,x.rrId,officialUrl(x),x.rp?'20%':'',x.rate,x.tc?'Oui':'Non',x.tcRate||'',x.tcUrl||'',x.wi?'Oui':'Non',(x.wiAliases||[]).join(' | '),x.wiRate||'',(x.wiUrls||[]).join(' | '),cashbackTotal(x)])];let csv='\uFEFF'+rows.map(r=>r.map(v=>'"'+String(v??'').replace(/"/g,'""')+'"').join(';')).join('\r\n');let url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));let a=document.createElement('a');a.href=url;a.download='marchands_cashback_filtres.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};render();renderChanges();

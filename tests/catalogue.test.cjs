const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const scripts=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(m=>m[1]);
const snapshot=JSON.parse(fs.readFileSync(path.join(root,'data/releves-2026-11-03.json'),'utf8'));
function load(initial={}){
 const nodes=new Map(),storage=new Map(Object.entries(initial));
 function element(id=''){
  if(nodes.has(id))return nodes.get(id);
  const e={id,value:'',checked:['rpCheck','rrCheck'].includes(id),style:{},dataset:{},files:[],classList:{toggle(){},add(){},remove(){}},addEventListener(){},append(){},appendChild(){},replaceChildren(){},setAttribute(){},querySelectorAll(){return []},focus(){},click(){},showModal(){},close(){}};
  nodes.set(id,e);return e;
 }
 const context=vm.createContext({console,URL,Intl,Blob,setTimeout(){},confirm(){return true},window:{scrollTo(){}},localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},document:{getElementById:element,querySelectorAll(){return []},createElement:t=>element('created-'+Math.random()),createTextNode:t=>({textContent:t})}});
 for(const script of scripts)vm.runInContext(script,context,{timeout:20000});
 const get=code=>JSON.parse(vm.runInContext('JSON.stringify('+code+')',context));
 return {get,run:code=>vm.runInContext(code,context),nodes,element,storage,context};
}
async function main(){
 const fresh=load();
 const records=fresh.get('records');
 for(const p of Object.keys(snapshot.platforms)){
  for(const source of snapshot.platforms[p]){
   const match=records.filter(r=>p==='rp'||p==='rr'?String(r[p+'Id']||'').split(';').includes(source[p+'Id']):p==='wi'?[r.wiUrl,...(r.wiUrls||[])].includes(source.wiUrl):r.tcUrl===source.tcUrl);
   assert.equal(match.length,1,p+': identity remains unique for '+source.name);
   assert.equal(match[0][p+'Date'],'2026-11-03',p+': observation date survives startup');
   if(p!=='rp'&&source[p==='rr'?'rate':p+'Rate'])assert.equal(match[0][p==='rr'?'rate':p+'Rate'],source[p==='rr'?'rate':p+'Rate'],p+': source rate survives startup for '+source.name);
  }
 }
 assert(records.some(r=>r.mergedNames?.length),'canonical aliases remain consolidated');
 assert(fresh.nodes.get('tc-rate-note').textContent.includes('03/11/2026'));
 const stale=fresh.get('clone(SEED)');for(const r of stale){for(const p of ['rp','rr','tc','wi'])if(r[p])r[p+'Date']='2026-10-26';r.tcRate='99% Cashback';r.rate='99% remboursés';}
 const categories='[{"id":"cat_test","name":"Mes favoris","members":["name:aliexpress","rr:4334"]}]';
 const legacy=load({cashback_catalog_v16:JSON.stringify(stale),cashback_user_categories_v1:categories,cashback_direct_sites_v1:'{"aliexpress":"https://example.org/"}'});
 assert.deepEqual(legacy.get('records'),records,'legacy catalogue cannot revert published observations');
 assert.equal(legacy.storage.get('cashback_user_categories_v1'),categories,'categories remain untouched');
 assert.equal(legacy.get("directSites.aliexpress"),'https://example.org/','personal official links survive');
 assert.deepEqual(fresh.get('parseCSV("Marchand;Taux\\r\\nFnac;3%")'),[{marchand:'Fnac',taux:'3%'}]);
 assert.deepEqual(fresh.get('parseCSV('+JSON.stringify('name,description\nFnac,"a,b"')+')'),[{name:'Fnac',description:'a,b'}]);
 assert.throws(()=>fresh.run('parseCSV('+JSON.stringify('a,b\n"unclosed,x')+')'),/guillemet/);
 assert.throws(()=>fresh.run('parseCSV("a,b\\n1,2,3")'),/colonnes/);
 assert.equal(fresh.get('validRate(\'8% Cashback"https://example.org/\',"tc")'),false);
 assert.equal(fresh.get('validRate("5zł remboursés","rr")'),true,'foreign currencies are preserved without being converted to euros');
 assert.equal(fresh.get('validDate("2026-02-30")'),false);
 assert.equal(fresh.get('SEED.find(r=>r.tcMissingSince)?.tcMissingSince'),'2026-11-03','absent merchants are flagged instead of removed');
 const before=JSON.stringify(fresh.get('records'));
 assert.throws(()=>fresh.run('applySnapshot(records,"tc",[{name:"Broken",tc:"Broken",tcUrl:"https://www.topcashback.fr/broken/",tcRate:"bad"}],"2026-11-03")'),/Taux/);
 assert.equal(JSON.stringify(fresh.get('records')),before,'failed snapshots do not mutate the catalogue');
 fresh.element('rrFiles').files=[{text:async()=> 'marchand,col-md-3 href,percent_text\nThalasseo France,https://www.remisesetreductions.fr/Merchant/4334,16% remboursés'}];
 await fresh.nodes.get('importBtn').onclick();
 const imported=fresh.get('records');
 const otherFields=r=>Object.fromEntries(Object.entries(r).filter(([k])=>k.startsWith('rp')||k.startsWith('tc')||k.startsWith('wi')));
 assert.deepEqual(imported.map(otherFields),records.map(otherFields),'R&R import preserves RP, TC and Widilo fields and dates');
 assert.equal(imported.find(r=>r.rrId==='4334').rate,'16% remboursés');
 assert.equal(imported.find(r=>r.rrId==='4334').rrDate,'2026-11-03');
 const reload=load(Object.fromEntries(fresh.storage));
 assert.equal(reload.get('records.find(r=>r.rrId==="4334").rate'),snapshot.platforms.rr.find(r=>r.rrId==='4334').rate,'published source wins over conflicting local data with same date');
 console.log('PASS: all supplied source rows and dates, legacy storage, preserved categories and links, CSV validation, transactional imports, aliases and absent merchants.');
 console.log('Published platform dates:',fresh.get('PUBLISHED_DATES'));
 console.log('Rendered merchant count:',records.length);
}
main().catch(error=>{console.error(error);process.exitCode=1;});

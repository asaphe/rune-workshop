'use strict';
let worldState=null,worldSelected=null,worldHistory=[],worldBaseline='';
window.worldMode=false;
const worldSnapshot=()=>JSON.stringify({containers:worldState?.containers,texts:worldState?.texts||[],settings:worldState?.settings});
const worldDirty=()=>!!worldState&&worldSnapshot()!==worldBaseline;
function setWorldMode(on){
 window.worldMode=on;
 $('worldView').hidden=!on;$('welcome').hidden=on||!!state;$('editor').hidden=on||!state;
 document.querySelector('.topbar .toolbar').hidden=on;
 $('worldWorkspace').classList.toggle('active',on);$('characterWorkspace').classList.toggle('active',!on);
}
$('worldWorkspace').onclick=()=>setWorldMode(true);$('characterWorkspace').onclick=()=>setWorldMode(false);
function worldRemember(){worldHistory.push(worldSnapshot());if(worldHistory.length>50)worldHistory.shift()}
function worldChanged(){worldControls();renderContainers();renderContainerGrid()}
function worldControls(){
 $('worldUndo').disabled=!worldHistory.length;$('worldExport').disabled=!worldState;
 $('worldSave').disabled=!worldState?.canSave||!worldDirty();
 if(worldState){
  $('worldSaveHelp').textContent=worldState.saveHelp;
  $('worldName').textContent=worldState.name;
  $('worldStatus').textContent=(worldDirty()?'● Unsaved world changes':'✓ No unsaved world changes')+' · Generation '+worldState.generation+' · '+worldState.containers.length+' player-created containers';
 }
}
function containerArea(c){return Math.floor(c.position[0]/200)+','+Math.floor(c.position[2]/200)}
function areaLabel(key){const [x,z]=key.split(',').map(Number);return 'X '+x*200+' to '+(x+1)*200+' · Z '+z*200+' to '+(z+1)*200}
function creatorLabel(c){
 if(c.creatorName)return c.creatorName;
 const ids=[...new Set(worldState.containers.map(c=>c.creator))].sort();
 return 'Unknown player '+(ids.indexOf(c.creator)+1);
}
function worldFilters(){
 const creators=[...new Map(worldState.containers.map(c=>[c.creator,c])).values()];
 $('containerCreator').closest('label').hidden=creators.length<2;
 $('containerCreator').innerHTML='<option value="">All creators</option>'+creators.map(c=>'<option value="'+esc(c.creator)+'">'+esc(creatorLabel(c))+'</option>').join('');
 $('containerArea').innerHTML='<option value="">All areas</option>'+[...new Set(worldState.containers.map(containerArea))].sort().map(key=>'<option value="'+key+'">'+areaLabel(key)+'</option>').join('');
}
function containerTitle(c){return readable((c.name||'Container').replace(/^piece_chest_/,'').replace(/^wood$/,'Wood chest'))+' · #'+(Number(c.id)+1)}
function renderContainers(){
 const q=$('containerSearch').value.toLowerCase();
 const rows=worldState.containers.filter(c=>(!$('containerCreator').value||c.creator===$('containerCreator').value)&&(!$('containerArea').value||containerArea(c)===$('containerArea').value)).filter(c=>(containerTitle(c)+' '+c.position.map(v=>Math.round(v)).join(' ')+' '+(c.items||[]).map(i=>itemName(i)+' '+i.prefab).join(' ')).toLowerCase().includes(q));
 if(!rows.some(c=>c.id===worldSelected)){worldSelected=rows[0]?.id;renderContainer()}
 $('containerList').innerHTML=rows.length?rows.map(c=>'<button class="container-row '+(c.id===worldSelected?'active':'')+'" data-container="'+c.id+'"><strong>'+esc(containerTitle(c))+'</strong><small>X '+Math.round(c.position[0])+' · Y '+Math.round(c.position[1])+' · Z '+Math.round(c.position[2])+'</small><small>'+(c.error?'Unsupported inventory':c.items.length+' item stacks')+'</small></button>').join(''):'<p class="muted">No matching containers.</p>';
}
let containerItemSelected=0;
function containerSize(c){const items=c.items||[];return {width:Math.max(c.size?.width||5,...items.map(i=>i.grid_x+1)),height:Math.max(c.size?.height||2,...items.map(i=>i.grid_y+1))}}
function freeContainerSlot(c){
 if(!c.size)return null;
 for(let y=0;y<c.size.height;y++)for(let x=0;x<c.size.width;x++)if(!c.items.some(i=>i.grid_x===x&&i.grid_y===y))return {x,y};
 return null;
}
function renderContainerGrid(){
 const c=worldState?.containers.find(c=>c.id===worldSelected);if(!c||!$('containerGrid'))return;
 if(c.error)return;const dim=containerSize(c);let html='';
 for(let y=0;y<dim.height;y++)for(let x=0;x<dim.width;x++){
  const n=c.items.findIndex(i=>i.grid_x===x&&i.grid_y===y),i=c.items[n];
  html+=`<button type="button" class="slot ${i?'':'empty'} ${n>=0&&n===containerItemSelected?'selected':''}" data-container-slot="${n}" aria-label="${i?esc(itemName(i))+'; quantity '+i.stack:'Empty slot '+(x+1)+', row '+(y+1)}">${i?icon(i)+`<span class="item-name">${esc(itemName(i))}</span><span class="stack">${i.stack}</span>`:'＋'}</button>`;
 }
 $('containerGrid').style.gridTemplateColumns=`repeat(${dim.width},minmax(65px,1fr))`;
 $('containerGrid').innerHTML=html;
 const chosen=c.items[containerItemSelected],maxButton=$('containerEditor').querySelector('[data-container-max]');
 if(maxButton){const limit=chosen&&itemsById[chosen.prefab]?.maxStack;maxButton.disabled=!limit||chosen.stack>=limit}
}
function renderContainer(){
 const c=worldState?.containers.find(c=>c.id===worldSelected);
 if(!c){$('containerEditor').innerHTML='<p class="muted">Choose a container to view its contents.</p>';return}
 if(c.error){$('containerEditor').innerHTML='<p>'+esc(c.error)+'</p>';return}
 if(containerItemSelected>=c.items.length)containerItemSelected=c.items.length-1;
 const n=containerItemSelected,i=c.items[n],dim=containerSize(c),space=freeContainerSlot(c),limit=i&&itemsById[i.prefab]?.maxStack;
 const field=(label,k,value,max)=>`<div class="field"><label>${label}<input aria-label="Container item ${label}" data-world-item="${n}" data-world-field="${k}" type="number" min="${k==='durability'?0:1}" max="${max}" step="${k==='durability'?'any':'1'}" value="${value}"></label></div>`;
 $('containerEditor').innerHTML=`<div class="section-title"><div><h2>${esc(containerTitle(c))}</h2><p class="muted">${c.items.length} / ${dim.width*dim.height} slots occupied</p></div><button id="worldClearFlags">Clear item cheat flags</button></div><div class="container-grid-scroll"><div id="containerGrid" class="inventory-grid"></div></div>${!c.size?'<p class="muted">Container capacity is unknown. Adding and duplicating are unavailable.</p>':''}<div class="container-item-panel">${i?`<div class="world-item-name">${icon(i)}<h3>${esc(itemName(i))}</h3></div><div class="item-actions"><button data-container-max ${!limit||i.stack>=limit?'disabled':''}>Max stack${limit?' ('+limit+')':''}</button><button data-container-duplicate ${!space?'disabled':''}>Duplicate</button><button data-world-delete="${n}" class="danger">Delete</button></div>${!space&&c.size?'<p class="muted">Container is full.</p>':''}${!limit?'<p class="muted">Stack limit is unknown for this item.</p>':''}<div class="form-grid">${field('Quantity','stack',i.stack,65535)}${field('Quality','quality',i.quality,65535)}${field('Durability','durability',i.durability,21474836)}</div>`:'<p class="muted">Select a stack to edit it, or add an item.</p>'}</div><form id="worldAddForm" class="world-add"><h3>Add an item</h3><label>Item<input id="worldAddPrefab" list="worldItemChoices" placeholder="Type an item name or prefab…" required></label><datalist id="worldItemChoices">${(catalog?.items||[]).map(i=>'<option value="'+esc(i.prefab)+'">'+esc(i.name)+'</option>').join('')}</datalist><button ${!space?'disabled':''}>Add item</button></form>`;
 renderContainerGrid();
 $('worldClearFlags').disabled=!c.items.some(i=>i.cheated);
 $('worldClearFlags').onclick=()=>{worldRemember();c.items.forEach(i=>i.cheated=false);worldChanged();renderContainer()};
 $('worldAddForm').onsubmit=e=>{
  e.preventDefault();const text=$('worldAddPrefab').value,info=catalog.items.find(i=>i.prefab===text||i.name===text),slot=freeContainerSlot(c);
  if(!info)return toast('Choose an item from the catalogue.',true);
  if(!slot)return toast('No empty slots available.',true);
  worldRemember();c.items.push({prefab:info.prefab,prefab_hash:info.hash,stack:1,quality:1,durability:100,grid_x:slot.x,grid_y:slot.y,world_level:0,variant:0,picked_up:false,equipped:false,crafter_id:'0',crafter_name:'',custom_data:{},cheated:false});
  containerItemSelected=c.items.length-1;worldChanged();renderContainer();
 };
}
$('containerEditor').addEventListener('click',e=>{
 const b=e.target.closest('button');if(!b)return;
 const c=worldState?.containers.find(c=>c.id===worldSelected);if(!c)return;
 if(b.dataset.containerSlot!==undefined){containerItemSelected=Number(b.dataset.containerSlot);renderContainer();return}
 const i=c.items[containerItemSelected];if(!i)return;
 if(b.hasAttribute('data-container-max')){
  const limit=itemsById[i.prefab]?.maxStack;if(!limit||i.stack>=limit)return;
  worldRemember();i.stack=limit;worldChanged();renderContainer();
 }
 if(b.hasAttribute('data-container-duplicate')){
  const slot=freeContainerSlot(c);if(!slot)return toast('No empty slots available.',true);
  worldRemember();const duplicate=clone(i);duplicate.grid_x=slot.x;duplicate.grid_y=slot.y;c.items.push(duplicate);containerItemSelected=c.items.length-1;worldChanged();renderContainer();
 }
});
function commitWorldInput(e){
 const el=e.target,k=el.dataset.worldField;if(!k)return;
 const c=worldState.containers.find(c=>c.id===worldSelected),i=c.items[Number(el.dataset.worldItem)];
 let value=Number(el.value);
 if(!el.checkValidity()||!Number.isFinite(value)){el.value=i[k]+(['grid_x','grid_y'].includes(k)?1:0);toast('Enter a valid value.',true);return}
 if(['grid_x','grid_y'].includes(k))value--;
 if(['grid_x','grid_y'].includes(k)&&c.items.some(other=>other!==i&&(k==='grid_x'?value: i.grid_x)===other.grid_x&&(k==='grid_y'?value:i.grid_y)===other.grid_y)){el.value=i[k]+1;toast('That slot is occupied.',true);return}
 if(i[k]===value)return;worldRemember();i[k]=value;worldChanged();
}
$('containerEditor').addEventListener('change',commitWorldInput);
$('containerEditor').addEventListener('focusout',commitWorldInput);
$('containerEditor').addEventListener('click',e=>{const b=e.target.closest('[data-world-delete]');if(!b)return;const c=worldState.containers.find(c=>c.id===worldSelected);worldRemember();c.items.splice(Number(b.dataset.worldDelete),1);worldChanged();renderContainer()});
$('containerList').onclick=e=>{const b=e.target.closest('[data-container]');if(b){worldSelected=b.dataset.container;containerItemSelected=0;renderContainers();renderContainer()}};
$('containerSearch').oninput=renderContainers;$('containerCreator').onchange=renderContainers;$('containerArea').onchange=renderContainers;
$('worldUndo').onclick=()=>{if(!worldHistory.length)return;Object.assign(worldState,JSON.parse(worldHistory.pop()));worldChanged();renderContainer();renderWorldExtras()};
async function openWorld(path){
 if(worldDirty()&&!confirm('Discard unsaved world changes and open another world?'))return;
 busy(true,'Reading world containers…');
 try{
  worldState=await(await api('/api/world/open',{path})).json();if(worldState.warning)toast(worldState.warning,true);worldBaseline=worldSnapshot();worldHistory=[];worldSelected=worldState.containers[0]?.id;containerItemSelected=0;
  $('worldPath').value=worldState.path;$('worldContents').hidden=false;worldFilters();worldChanged();renderContainer();renderWorldExtras();
 }catch(e){$('worldStatus').textContent=e.message;toast(e.message,true)}finally{busy(false)}
}
$('worldOpenForm').onsubmit=e=>{e.preventDefault();openWorld($('worldPath').value)};
$('worldRecent').onclick=e=>{const b=e.target.closest('[data-world-path]');if(b)openWorld(b.dataset.worldPath)};
const worldPayload=()=>({session:worldState.session,changes:worldState.containers.filter(c=>!c.error).map(c=>({id:c.id,items:c.items})),texts:(worldState.texts||[]).map(t=>({id:t.id,text:t.text})),settings:worldState.settings});
$('worldSave').onclick=async()=>{
 busy(true,'Backing up and saving the world…');
 try{
  const result=await(await api('/api/world/save',worldPayload())).json();
  worldState=result.world;worldBaseline=worldSnapshot();worldHistory=[];worldChanged();renderContainer();renderWorldExtras();
  $('worldSaveHelp').textContent=result.unchanged?'No changes to save.':'Saved generation '+result.generation+'. Full backup: '+result.backup+(result.warning?' '+result.warning:'');
  if(result.warning)toast(result.warning,true);else toast(result.unchanged?'No changes to save.':'World saved. Previous generation and backup retained.');
 }catch(e){$('worldSaveHelp').textContent=e.message;toast(e.message,true)}finally{busy(false)}
};
$('worldExport').onclick=async()=>{
 busy(true,'Preparing world ZIP…');
 try{
  const blob=await(await api('/api/world/export',worldPayload())).blob(),a=document.createElement('a');
  a.href=URL.createObjectURL(blob);a.download=worldState.name+'-edited.zip';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),30000);
  toast('World exported. The original world was not changed.');
 }catch(e){toast(e.message,true)}finally{busy(false)}
};
window.addEventListener('beforeunload',e=>{if(worldDirty()){e.preventDefault();e.returnValue=''}});
(async()=>{try{const worlds=await(await api('/api/worlds')).json();$('worldRecent').innerHTML=worlds.map(w=>'<button class="world-recent" data-world-path="'+esc(w.path)+'">'+esc(w.name)+' <small>'+(w.cloud?'Steam Cloud · export only':'Local')+'</small></button>').join('')}catch(e){$('worldStatus').textContent=e.message}})();


const worldSettingLabels={
 nobuildcost:['Free-build · No build cost','Build without spending materials. This does not unlock every recipe or remove crafting costs.'],
 passivemobs:['Passive enemies','Enemies generally leave you alone until provoked.'],
 teleportall:['Allow all portal items','Allow normally restricted materials through portals.'],
 playerevents:['Player-based raids','Use player progress when selecting raids.'],
 fire:['Fire hazards','Allow the game’s fire-hazard rules.']
};
function renderWorldSettings(){
 const settings=worldState.settings;
 $('resetWorldSettings').disabled=!settings||JSON.stringify(settings)===JSON.stringify(JSON.parse(worldBaseline).settings);
 $('worldSettings').innerHTML=settings?Object.entries(worldSettingLabels).map(([key,[label,help]])=>'<div class="world-setting"><div><label for="setting-'+key+'">'+label+'</label><p class="muted">'+help+'</p></div><select id="setting-'+key+'" data-world-setting="'+key+'"><option value="false" '+(!settings[key]?'selected':'')+'>Off</option><option value="true" '+(settings[key]?'selected':'')+'>On</option></select></div>').join(''):'<p class="muted">'+esc(worldState.settingsError||'Settings are unavailable for this metadata version.')+'</p>';
}
function renderWorldTexts(){
 const q=$('worldTextSearch').value.toLowerCase();
 const entries=(worldState.texts||[]).filter(t=>(t.text+' '+t.kind+' '+t.position.map(v=>Math.round(v)).join(' ')).toLowerCase().includes(q));
 $('worldTexts').innerHTML=entries.length?entries.map(t=>'<div class="panel world-text-card"><label for="world-text-'+t.id+'">'+(t.kind==='portal'?'Portal tag':'Sign text')+'</label><p class="muted">X '+fmt(t.position[0])+' · Y '+fmt(t.position[1])+' · Z '+fmt(t.position[2])+'</p><input id="world-text-'+t.id+'" data-world-text="'+t.id+'" maxlength="500" value="'+esc(t.text)+'"></div>').join(''):'<p class="muted">No matching player-created portals or signs in this save.</p>';
}
function renderWorldExtras(){renderWorldSettings();renderWorldTexts()}
$('worldSections').onclick=e=>{
 const b=e.target.closest('[data-world-section]');if(!b)return;
 for(const key of ['containers','texts','settings'])$('world'+key[0].toUpperCase()+key.slice(1)+'Section').hidden=b.dataset.worldSection!==key;
 document.querySelectorAll('[data-world-section]').forEach(x=>x.classList.toggle('active',x===b));
};
$('worldTextSearch').oninput=renderWorldTexts;
function commitWorldText(e){
 const id=e.target.dataset.worldText;if(id===undefined)return;
 const t=worldState.texts.find(t=>t.id===id),value=e.target.value;
 if(t.text===value)return;
 worldRemember();t.text=value;worldControls();
}
$('worldTexts').addEventListener('change',commitWorldText);
$('worldTexts').addEventListener('focusout',commitWorldText);
$('worldSettings').onchange=e=>{
 const key=e.target.dataset.worldSetting;if(!key)return;
 worldRemember();worldState.settings[key]=e.target.value==='true';worldControls();renderWorldSettings();
};
$('resetWorldSettings').onclick=()=>{worldRemember();worldState.settings=clone(JSON.parse(worldBaseline).settings);worldControls();renderWorldSettings()};

'use strict';
const $=id=>document.getElementById(id);
let catalog, itemsById={}, state=null, original='', saved='', history=[], future=[], selected=-1, activeTab='inventory', knowledgeKey='known_recipes', pickerMode='add', targetSlot=null, dragIndex=-1;
const clone=x=>JSON.parse(JSON.stringify(x));
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const readable=s=>String(s||'').replace(/([a-z])([A-Z])/g,'$1 $2').replaceAll('_',' ');
const itemInfo=i=>itemsById[i?.prefab]||{name:i?.prefab?readable(i.prefab):`Unknown item ${i?.prefab_hash??''}`,category:'Unknown',icons:[]};
const itemName=i=>itemInfo(i).name;
const icon=(i,cls='')=>{const icons=itemInfo(i).icons||[],name=icons[Math.min(i.variant||0,icons.length-1)];return name?`<img class="${cls}" src="/icons/${name}" alt="" draggable="false">`:'<span class="fallback" aria-hidden="true">◇</span>'};
const fmt=n=>Number(n||0).toLocaleString(undefined,{maximumFractionDigits:1});
const snapshot=()=>JSON.stringify({name:state.name,usedCheats:state.usedCheats,teleportTarget:state.teleportTarget||null,player:state.player,survival:state.survival});
const dirty=()=>state&&snapshot()!==saved;
function toast(message,error=false){$('toast').textContent=message;$('toast').className='toast'+(error?' error':'');$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,error?9000:4000)}
function busy(on,message='Reading your character…'){$('busy').hidden=!on;$('busyText').textContent=message;for(const el of document.querySelectorAll('header,main,dialog'))el.inert=on}
const isBusy=()=>!$('busy').hidden;
async function api(url,data,raw=false,filename=''){const options=data===undefined?{}:{method:'POST',headers:raw?{'Content-Type':'application/octet-stream','X-Filename':encodeURIComponent(filename)}:{'Content-Type':'application/json'},body:raw?data:JSON.stringify(data)};const response=await fetch(url,options);if(!response.ok){const e=await response.json();throw Error(e.error||'Request failed')}return response}
function remember(){history.push(snapshot());if(history.length>80)history.shift();future=[]}
function foodTotals(foods){
 const totals={health:catalog.foodBase.m_baseHP,stamina:catalog.foodBase.m_baseStamina,eitr:0};
 for(const food of foods){
  const info=catalog.foods[food.name];if(!info)return null;
  const scale=Math.pow(Math.max(0,Math.min(1,food.time/info.duration)),0.3);
  for(const key of ['health','stamina','eitr'])totals[key]+=info[key]*scale;
 }
 return totals;
}
function recalculateFoodStats(){
 const total=foodTotals(state.player.foods);
 if(!total){toast('Food stats are unavailable for an unknown food; totals were preserved.',true);return}
 for(const [key,maxKey] of [['health','max_health'],['stamina','max_stamina'],['eitr','max_eitr']]){
  state.player[maxKey]=total[key];state.player[key]=Math.min(state.player[key],total[key]);
 }
}
function mutate(fn){if(isBusy())return;remember();const foods=JSON.stringify(state.player.foods);fn();if(foods!==JSON.stringify(state.player.foods))recalculateFoodStats();render()}
function restore(value){const data=JSON.parse(value);state.teleportTarget=data.teleportTarget;state.name=data.name;state.usedCheats=data.usedCheats;state.player=data.player;state.survival=data.survival;selected=Math.min(selected,state.player.inventory.length-1);render()}
function undo(){if(!history.length)return;future.push(snapshot());restore(history.pop())}
function redo(){if(!future.length)return;history.push(snapshot());restore(future.pop())}
function controls(){const loaded=!!state;for(const id of ['exportBtn','backupsBtn'])$(id).disabled=!loaded;$('saveBtn').disabled=!loaded||!state.canSave;$('saveBtn').title=loaded&&!state.canSave?state.saveBlockedReason||'Reopen using Open character to save to the original file.':'Back up the existing file as .old, then save in its original location';$('undoBtn').disabled=!history.length;$('redoBtn').disabled=!future.length;if(loaded){$('characterSaveHelp').textContent=state.canSave?'Save replaces '+state.sourcePath+' and keeps a backup. Close Valheim before saving.':state.saveBlockedReason||'This uploaded file has no original path. Export to keep your edits, or reopen the local file using Open character for direct saving.';$('dirtyState').textContent=dirty()?'● Unsaved changes':'✓ Ready to explore';$('dirtyState').style.color=dirty()?'var(--gold)':'var(--green)'}}
async function load(fileOrId){if(dirty()&&!confirm('Open another character and discard unsaved changes?'))return;busy(true);try{const response=fileOrId===null?await api('/api/browse',{}):fileOrId?.path?await api('/api/open-path',{path:fileOrId.path}):typeof fileOrId==='string'?await api('/api/load',{id:fileOrId}):await api('/api/open',await fileOrId.arrayBuffer(),true,fileOrId.name);const opened=await response.json();if(opened.cancelled)return;if(opened.directory){showPathFiles(opened);return;}$('openDialog').close();state=opened;$('tombChoices').innerHTML='';history=[];future=[];selected=state.player.inventory.length?0:-1;saved=original=snapshot();$('saveResult').textContent=state.saveBlockedReason||'Local Save requires Valheim to be completely closed.';$('welcome').hidden=true;$('editor').hidden=false;render();toast('Character loaded. Unchanged save verified byte for byte.')}catch(e){if($('openDialog').open)$('pathError').textContent=e.message;else toast(e.message,true)}finally{busy(false)}}
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),10000)}
async function exportCharacter(originalCopy=false){if(!state)return;busy(true,originalCopy?'Preparing original copy…':'Validating your character…');try{const response=await api(originalCopy?'/api/original':'/api/export',originalCopy?{session:state.session}:{session:state.session,name:state.name,usedCheats:state.usedCheats,teleportTarget:state.teleportTarget||null,player:state.player,survival:state.survival});const name=originalCopy?state.filename.replace(/\.fch$/i,'_original.fch'):state.name.replace(/[^\p{L}\p{N}_-]/gu,'_').toLowerCase()+'_edited.fch';download(await response.blob(),name);toast(originalCopy?'Original copy downloaded.':'Character exported. Choose the downloaded copy for your in-game check.')}catch(e){toast(e.message,true)}finally{busy(false)}}
async function recent(){try{const rows=await(await api('/api/characters')).json();$('recentList').innerHTML=rows.length?rows.map(r=>`<button class="recent-row" data-load="${r.id}"><span class="rune">ᛟ</span><span><strong>${esc(readable(r.name))}</strong><small>${esc(r.location)} · ${esc(new Date(r.modified*1000).toLocaleString())} · ${Math.round(r.size/1024)} KB</small></span><span>Open ↗</span></button>`).join(''):'<p class="muted">No characters found in the configured folders. Open a .fch file above.</p>'}catch(e){$('recentList').textContent=e.message}}
function rows(){let count=4;for(const marker of state.player.uniques||[]){const m=/^invrows (\d+)$/.exec(marker);if(m)count=Math.max(count,+m[1])}return Math.min(32,Math.max(count,...state.player.inventory.map(i=>i.grid_y+1)))}
function emptySlot(){for(let y=0;y<rows();y++)for(let x=0;x<8;x++)if(!state.player.inventory.some(i=>i.grid_x===x&&i.grid_y===y))return{x,y};return null}
function summary(){const p=state.player;$('characterName').textContent=state.name;$('fileName').textContent=state.filename+' · '+(state.canSave?'Local':state.sourcePath?'Steam Cloud':'Imported copy');$('characterMeta').textContent=`${state.worlds} world${state.worlds===1?'':'s'} explored · ${p.skills.length} skills · ${p.foods.length} active foods`;$('summary').innerHTML=[['♡','HEALTH',`${fmt(p.health)} <span class="muted">/ ${fmt(p.max_health)}</span>`],['ϟ','STAMINA',`${fmt(p.stamina)} <span class="muted">/ ${fmt(p.max_stamina)}</span>`],['✧','FORSAKEN POWER',esc(catalog.powers[p.guardian_power]||p.guardian_power||'None')],['◈','PROVISIONS',`${p.foods.length} <span class="muted">/ 3 foods</span>`]].map(([glyph,label,value])=>`<div class="stat"><span class="stat-icon" aria-hidden="true">${glyph}</span><div><small>${label}</small><strong>${value}</strong></div></div>`).join('');$('formatLabel').textContent=`Profile ${state.versions[0]} · Player ${state.versions[1]} · Inventory ${state.versions[2]} · Verified on load`}
function render(){if(!state)return;summary();controls();renderInventory();renderSkills();renderCharacter();renderFlags();renderKnowledge();renderRecovery()}
function renderInventory(){$('repairAllItems').disabled=!repairableItems().length;const inv=state.player.inventory, rowCount=rows();$('slotsUsed').textContent=`${inv.length} / ${rowCount*8} slots occupied`;$('extraSlots').textContent=rowCount>4?`${rowCount} inventory rows`:'';let html='';for(let y=0;y<rowCount;y++)for(let x=0;x<8;x++){const idx=inv.findIndex(i=>i.grid_x===x&&i.grid_y===y),i=inv[idx];html+=`<button class="slot ${i?'':'empty'} ${idx>=0&&idx===selected?'selected':''} ${i?.equipped?'equipped':''}" data-slot="${x},${y}" data-index="${idx}" draggable="${!!i}" aria-label="${i?esc(itemName(i))+'; quantity '+i.stack:'Empty slot '+(x+1)+', row '+(y+1)}" title="${i?esc(itemName(i))+' · '+esc(i.prefab):'Double-click to add an item'}">${y===0?`<span class="hotkey">${x+1}</span>`:''}${i?`${i.quality>1?`<span class="quality">★${i.quality}</span>`:''}${icon(i)}<span class="item-name">${esc(itemName(i))}</span>${i.stack>1?`<span class="stack">${i.stack}</span>`:''}`:''}</button>`}$('inventoryGrid').innerHTML=html;renderInspector()}
function field(label,path,value,type='number',extra=''){return `<div class="field"><label for="f-${path.replaceAll('.','-')}">${label}</label><input id="f-${path.replaceAll('.','-')}" data-path="${path}" type="${type}" value="${esc(value)}" ${type==='number'?'step="any" min="0"':''} ${extra}></div>`}
function selectField(label,path,value,options){const opts={...options};if(!(value in opts))opts[value]=value;return `<div class="field"><label for="f-${path.replaceAll('.','-')}">${label}</label><select id="f-${path.replaceAll('.','-')}" data-path="${path}">${Object.entries(opts).map(([v,n])=>`<option value="${esc(v)}" ${String(value)===v?'selected':''}>${esc(n)}</option>`).join('')}</select></div>`}
function renderInspector(){const i=state.player.inventory[selected];if(!i){$('inspector').innerHTML='<div class="inspector-empty"><span class="rune">ᚱ</span><h2>A place for every tool.</h2><p>Select an item to inspect its quality,<br>durability and equipment settings.</p></div>';return}const path=`inventory.${selected}.`;$('inspector').innerHTML=`<div class="item-heading"><div class="big-icon">${icon(i)}</div><div><div class="eyebrow">${esc(itemInfo(i).category)}</div><h2>${esc(itemName(i))}</h2><span class="technical">${esc(i.prefab||i.prefab_hash)}</span></div></div><div class="item-actions"><button data-action="replace">Change item</button><button data-action="duplicate">Duplicate</button><button data-action="max-stack" ${!itemInfo(i).maxStack||i.stack>=itemInfo(i).maxStack?'disabled':''} title="${itemInfo(i).maxStack?'Maximum: '+itemInfo(i).maxStack:'Stack limit unknown'}">Max stack</button><button data-action="delete" class="danger">Delete</button></div><div class="inspector-body"><div class="field-label">Quality</div><div class="quality-row">${[1,2,3,4].map(q=>`<button data-quality="${q}" class="${i.quality===q?'chosen':''}">★ ${q}</button>`).join('')}</div><div class="form-grid">${field('Stack',path+'stack',i.stack,'number','min="1" max="65535"')}${field('Quality level',path+'quality',i.quality,'number','min="1" max="65535"')}${field('Durability',path+'durability',i.durability)}${field('Style / variant',path+'variant',i.variant||0)}</div><label class="check-label"><input type="checkbox" data-path="${path}equipped" ${i.equipped?'checked':''}><span>Equipped</span></label><div class="form-grid">${field('Crafted by',path+'crafter_name',i.crafter_name||'','text')}</div></div><details><summary>ADVANCED ITEM DATA</summary><div class="form-grid">${field('Crafter ID',path+'crafter_id',i.crafter_id||'0','text')}${field('World level',path+'world_level',i.world_level||0)}</div><p class="muted">Custom item data is preserved when you edit.</p></details>`}
function increaseAllSkills(amount){if(!state)return;const skills=state.player.skills.filter(s=>s.id!==0&&s.level<100);if(!skills.length){toast('All learned skills are already at level 100.');return}mutate(()=>{for(const s of skills)s.level=Math.min(100,s.level+amount)});toast(`Increased ${skills.length} learned skills by up to ${amount}.`)}
function renderSkills(){const q=$('skillSearch').value.toLowerCase(),map={...catalog.skills};for(const s of state.player.skills)if(!(s.id in map))map[s.id]=`Unknown skill ${s.id}`;$('skillsGrid').innerHTML=Object.entries(map).filter(([id,n])=>id!=='0'&&n.toLowerCase().includes(q)).map(([id,name])=>{const idx=state.player.skills.findIndex(s=>s.id===+id),s=state.player.skills[idx];return `<div class="skill-card ${s?'':'locked'}"><div class="skill-heading"><h3>${esc(name)}</h3><button data-skill="${id}">${s?'Lock':'Unlock'}</button></div>${s?`<div class="form-grid">${field('Level',`skills.${idx}.level`,s.level,'number','max="100"')}${field('Progress',`skills.${idx}.xp`,s.xp)}</div><div class="skill-increments">${[1,5].map(amount=>`<button type="button" data-increase-skill="${id}" data-amount="${amount}" aria-label="Increase ${esc(name)} by ${amount}" ${s.level>=100?'disabled':''}>+${amount}</button>`).join('')}</div><div class="skill-progress"><i style="width:${Math.max(0,Math.min(100,s.level))}%"></i></div>`:'<p class="muted">Not yet learned. Unlock to set a level.</p>'}</div>`}).join('')}
function renderCharacter(){renderSurvival();const p=state.player;const deathSeconds=p.time_since_death;$('deathTimer').innerHTML=`<div class="form-grid"><div class="field"><label for="deathDays">Days</label><input id="deathDays" data-death-unit="days" type="number" min="0" max="5555" step="1" required value="${Math.floor(deathSeconds/1800)}"></div><div class="field"><label for="deathHours">Hours</label><input id="deathHours" data-death-unit="hours" type="number" min="0" max="23.999999" step="any" required value="${Number(((deathSeconds%1800)/75).toFixed(6))}"></div></div>`;$('deathTimerSummary').textContent='';$('vitals').innerHTML=[['Current health','health'],['Maximum health','max_health'],['Current stamina','stamina'],['Maximum stamina','max_stamina'],['Current Eitr (magic energy)','eitr'],['Maximum Eitr (magic energy)','max_eitr']].map(([l,k])=>field(l,k,p[k])).join('');$('powerForm').innerHTML=selectField('Active power','guardian_power',p.guardian_power,catalog.powers)+field('Cooldown · seconds','guardian_power_cooldown',p.guardian_power_cooldown);$('addFood').disabled=p.foods.length>=3;$('foods').innerHTML=p.foods.length?p.foods.map((f,idx)=>`<div class="food-row">${icon({prefab:f.name})}<div class="food-info"><strong>${esc(itemName({prefab:f.name}))}</strong><small>${esc(f.name)} · ${Math.floor(f.time/60)}m ${Math.round(f.time%60)}s</small></div><input aria-label="${esc(itemName({prefab:f.name}))} time remaining in seconds" type="number" min="0" max="${catalog.foods[f.name]?.duration||10000000}" step="any" data-path="foods.${idx}.time" value="${f.time}"><button data-food-change="${idx}" title="Change food">↔</button><button data-food-delete="${idx}" class="danger" title="Remove food">×</button></div>`).join(''):'<p class="no-food">No active foods. Add something for the road.</p>';$('appearance').innerHTML=field('Character name','name',state.name,'text')+selectField('Model','model_index',p.model_index,{'0':'Male','1':'Female'})+selectField('Hair','hair',p.hair,catalog.hairs)+selectField('Beard','beard',p.beard,catalog.beards)+colorField('Hair color','hair_color',p.hair_color)+colorField('Skin color','skin_color',p.skin_color)}
function colorField(label,key,values){const hex='#'+values.map(n=>Math.round(Math.min(1,Math.max(0,n))*255).toString(16).padStart(2,'0')).join('');return `<div class="field"><label for="color-${key}">${label}</label><input type="color" id="color-${key}" data-color="${key}" value="${hex}"></div>`}
const knowledge={known_recipes:'Recipes',known_material:'Materials',known_stations:'Crafting stations',trophies:'Trophies',known_biomes:'Biomes',uniques:'Discoveries',known_texts:'Lore & texts',shown_tutorials:'Tutorials'};
function renderKnowledge(){const p=state.player;$('knowledgeNav').innerHTML=Object.entries(knowledge).map(([key,label])=>`<button data-knowledge="${key}" class="${key===knowledgeKey?'active':''}">${label}<span>${Object.keys(p[key]||{}).length}</span></button>`).join('');const value=p[knowledgeKey]||[],dict=!Array.isArray(value);$('knowledgeTitle').textContent=knowledge[knowledgeKey];$('knowledgeCount').textContent=`${Object.keys(value).length} entries`;$('knowledgeHelp').textContent=dict?'One entry per line: key = value. Use exact internal game IDs.':'One exact internal game ID per line. Add or remove entries to change what this character knows.';$('knowledgeText').value=dict?Object.entries(value).map(([k,v])=>`${k} = ${v}`).join('\n'):value.join('\n')}
function applyKnowledge(){const lines=$('knowledgeText').value.split('\n').map(s=>s.trim()).filter(Boolean);try{let value;if(['known_stations','known_texts'].includes(knowledgeKey)){value={};for(const line of lines){const i=line.indexOf('=');if(i<1)throw Error('Use key = value for each entry.');const key=line.slice(0,i).trim(),v=line.slice(i+1).trim();if(knowledgeKey==='known_stations'&&(!/^\d+$/.test(v)||+v>1000))throw Error('Station levels must be whole numbers between 0 and 1000.');value[key]=knowledgeKey==='known_stations'?+v:v}}else value=[...new Set(lines)];if(JSON.stringify(state.player[knowledgeKey])!==JSON.stringify(value))mutate(()=>state.player[knowledgeKey]=value)}catch(e){toast(e.message,true)}}
function chooseItem(mode,slot=null){if(!state)return;if(mode==='add'&&!slot&&!emptySlot())return toast('Your inventory is full. Free a slot first.',true);pickerMode=mode;targetSlot=slot;$('pickerTitle').textContent=mode.startsWith('food')?'Choose a provision':mode==='replace'?'Choose replacement gear':'Choose your gear';$('itemSearch').value='';$('category').value='';$('category').hidden=mode.startsWith('food');renderPicker();$('picker').showModal();setTimeout(()=>$('itemSearch').focus(),20)}
function renderPicker(){const q=$('itemSearch').value.toLowerCase(),cat=$('category').value;const foodMode=pickerMode.startsWith('food');const currentFood=foodMode&&pickerMode!=='food-add'?Number(pickerMode.split(':')[1]):-1;const list=catalog.items.filter(i=>(!foodMode||(catalog.foods[i.prefab]&&!state.player.foods.some((f,n)=>n!==currentFood&&f.name===i.prefab)))&&(!cat||i.category===cat)&&(i.name+' '+i.prefab).toLowerCase().includes(q));$('pickerResults').innerHTML=list.length?list.slice(0,180).map(i=>`<button class="catalog-item" data-prefab="${esc(i.prefab)}">${icon(i)}<span><strong>${esc(i.name)}</strong><small>${esc(i.prefab)}</small></span></button>`).join(''):'<p class="muted">No items match. Try another category or search.</p>'}
function pick(prefab){if(pickerMode.startsWith('food')){mutate(()=>{const food={name:prefab,time:catalog.foods[prefab].duration};if(pickerMode==='food-add')state.player.foods.push(food);else state.player.foods[+pickerMode.split(':')[1]]=food})}else if(pickerMode==='replace'){mutate(()=>{const i=state.player.inventory[selected];i.prefab=prefab;i.prefab_hash=itemsById[prefab].hash;i.variant=0})}else{const slot=targetSlot||emptySlot();if(!slot)return toast('No empty slot available.',true);mutate(()=>{state.player.inventory.push({prefab,prefab_hash:itemsById[prefab].hash,grid_x:slot.x,grid_y:slot.y,quality:1,stack:1,durability:100,variant:0,world_level:0,equipped:false,picked_up:true,cheated:false,crafter_name:'',crafter_id:'0',custom_data:{}});selected=state.player.inventory.length-1})}$('picker').close()}
function moveItem(idx,x,y){const inv=state.player.inventory,i=inv[idx];if(!i||(i.grid_x===x&&i.grid_y===y))return;mutate(()=>{const other=inv.find(j=>j.grid_x===x&&j.grid_y===y);if(other){other.grid_x=i.grid_x;other.grid_y=i.grid_y}i.grid_x=x;i.grid_y=y;selected=idx})}
function changeInput(el){const path=el.dataset.path;if(!path)return;let value=el.type==='checkbox'?el.checked:el.type==='number'||path==='model_index'?Number(el.value):el.value;if(el.type==='number'&&(!el.checkValidity()||!Number.isFinite(value))){toast('Enter a valid number within the field limits.',true);return}const parts=path.split('.');let obj=['name','usedCheats'].includes(path)?state:state.player;for(let n=0;n<parts.length-1;n++)obj=obj[parts[n]];const key=parts.at(-1);if(obj[key]===value)return;mutate(()=>obj[key]=value)}
$('openBtn').onclick=$('welcomeOpen').onclick=openPathDialog;$('saveBtn').onclick=saveCharacter;$('file').onchange=()=>{if($('file').files[0])load($('file').files[0]);$('file').value=''};$('refreshBtn').onclick=recent;$('undoBtn').onclick=undo;$('redoBtn').onclick=redo;$('exportBtn').onclick=()=>exportCharacter();$('addItem').onclick=()=>chooseItem('add');$('addFood').onclick=()=>chooseItem('food-add');$('closePicker').onclick=()=>$('picker').close();$('itemSearch').oninput=renderPicker;$('category').onchange=renderPicker;$('skillSearch').oninput=renderSkills;$('skillsPlusOne').onclick=()=>increaseAllSkills(1);$('skillsPlusFive').onclick=()=>increaseAllSkills(5);$('applyKnowledge').onclick=applyKnowledge;$('knowledgeText').onchange=applyKnowledge;
$('tabs').onclick=e=>{const tab=e.target.closest('[data-tab]');if(!tab)return;activeTab=tab.dataset.tab;document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b===tab));for(const key of ['inventory','skills','character','knowledge'])$(key+'View').hidden=key!==activeTab};
document.addEventListener('change',e=>{if(e.target.dataset.path)changeInput(e.target);if(e.target.dataset.color){const value=e.target.value;mutate(()=>state.player[e.target.dataset.color]=[1,3,5].map(i=>parseInt(value.slice(i,i+2),16)/255))}});
document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.load)load(b.dataset.load);if(b.dataset.prefab)pick(b.dataset.prefab);if(b.dataset.knowledge){knowledgeKey=b.dataset.knowledge;renderKnowledge();renderRecovery()}if(b.dataset.quality)mutate(()=>state.player.inventory[selected].quality=+b.dataset.quality);if(b.dataset.skill){const id=+b.dataset.skill,idx=state.player.skills.findIndex(s=>s.id===id);mutate(()=>{if(idx<0)state.player.skills.push({id,level:1,xp:0});else state.player.skills.splice(idx,1)})}if(b.dataset.foodDelete!==undefined)mutate(()=>state.player.foods.splice(+b.dataset.foodDelete,1));if(b.dataset.foodChange!==undefined)chooseItem('food:'+b.dataset.foodChange);if(b.dataset.action==='replace')chooseItem('replace');if(b.dataset.action==='delete')mutate(()=>{state.player.inventory.splice(selected,1);selected=-1});if(b.dataset.action==='duplicate'){const slot=emptySlot();if(!slot)return toast('No empty slots available.',true);mutate(()=>{const item=clone(state.player.inventory[selected]);item.grid_x=slot.x;item.grid_y=slot.y;item.equipped=false;state.player.inventory.push(item);selected=state.player.inventory.length-1})}});
$('inventoryGrid').onclick=e=>{const b=e.target.closest('[data-slot]');if(b){selected=+b.dataset.index;document.querySelectorAll('.slot.selected').forEach(s=>s.classList.remove('selected'));if(selected>=0)b.classList.add('selected');renderInspector()}};
$('inventoryGrid').ondblclick=e=>{const b=e.target.closest('[data-slot]');if(b&&+b.dataset.index<0){const[x,y]=b.dataset.slot.split(',').map(Number);chooseItem('add',{x,y})}};
$('inventoryGrid').ondragstart=e=>{const b=e.target.closest('[data-slot]');dragIndex=+b?.dataset.index;if(dragIndex<0)return e.preventDefault();e.dataTransfer.setData('text/plain',String(dragIndex));e.dataTransfer.effectAllowed='move'};
$('inventoryGrid').ondragover=e=>{if(dragIndex<0)return;e.preventDefault();const b=e.target.closest('[data-slot]');if(b)b.classList.add('drag-over')};
$('inventoryGrid').ondragleave=e=>e.target.closest('[data-slot]')?.classList.remove('drag-over');
$('inventoryGrid').ondrop=e=>{if(dragIndex<0)return;e.preventDefault();e.stopPropagation();const b=e.target.closest('[data-slot]');if(b){const[x,y]=b.dataset.slot.split(',').map(Number);moveItem(dragIndex,x,y)}dragIndex=-1};
document.addEventListener('dragend',()=>{dragIndex=-1;document.querySelectorAll('.drag-over').forEach(b=>b.classList.remove('drag-over'))});
document.addEventListener('dragover',e=>{if(e.dataTransfer.types.includes('Files')){e.preventDefault();document.body.classList.add('dragging-file')}});document.addEventListener('dragleave',e=>{if(!e.relatedTarget)document.body.classList.remove('dragging-file')});document.addEventListener('drop',e=>{document.body.classList.remove('dragging-file');if(e.dataTransfer.files.length){e.preventDefault();if(!isBusy())load(e.dataTransfer.files[0])}});
document.addEventListener('keydown',e=>{if(isBusy()||window.worldMode||['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName))return;if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();e.shiftKey?redo():undo()}if(e.key==='Delete'&&state&&selected>=0&&activeTab==='inventory'&&!$('picker').open){e.preventDefault();mutate(()=>{state.player.inventory.splice(selected,1);selected=-1})}});
window.addEventListener('beforeunload',e=>{if(dirty()){e.preventDefault();e.returnValue=''}});
(async()=>{try{catalog=await(await api('/api/catalog')).json();itemsById=Object.fromEntries(catalog.items.map(i=>[i.prefab,i]));$('category').innerHTML='<option value="">All categories</option>'+[...new Set(catalog.items.map(i=>i.category))].sort().map(c=>`<option>${esc(c)}</option>`).join('');await recent()}catch(e){toast('Could not start the workshop: '+e.message,true)}})();

function renderFlags(){
 const count=state.player.inventory.filter(i=>i.cheated).length;
 $('clearItemFlags').disabled=!count;
 $('clearItemFlags').textContent=`Clear all item cheat flags`;
 $('flagSummary').innerHTML=`<span class="flag-status ${state.usedCheats?'flag-set':'flag-clear'}"><span aria-hidden="true">${state.usedCheats?'!':'✓'}</span> Character cheat flag: <strong>${state.usedCheats?'Set':'Not set'}</strong></span><span class="flag-status ${count?'flag-set':'flag-clear'}">${count} inventory item${count===1?'':'s'} marked as spawned with cheats</span>`;
 $('cheatFlags').innerHTML=`<p class="flag-status ${state.usedCheats?'flag-set':'flag-clear'}">Character cheat flag: <strong>${state.usedCheats?'Set':'Not set'}</strong></p><p class="muted">${count} inventory item${count===1?'':'s'} marked as spawned with cheats.</p><div class="item-actions"><button id="clearCharacterFlag" ${state.usedCheats?'':'disabled'}>Clear character flag</button></div>`;
 $('clearCharacterFlag').onclick=()=>mutate(()=>state.usedCheats=false);

}
$('clearItemFlags').onclick=()=>mutate(()=>state.player.inventory.forEach(i=>i.cheated=false));
document.addEventListener('focusout',e=>{if(e.target.dataset.path&&state)changeInput(e.target)});

async function saveCharacter(){
 if(!state||!state.canSave)return;
 busy(true,'Backing up and saving your character…');
 try{
  const submitted=snapshot();
  const result=await(await api('/api/save',{session:state.session,...JSON.parse(submitted)})).json();
  saved=submitted;controls();
  $('saveResult').textContent=result.unchanged?'No changes to save.':`Saved to ${result.path}. Previous file: ${result.backup}`;
  toast(result.unchanged?'No changes to save.':'Character saved. Previous file retained as .old.');
 }catch(e){toast(e.message,true)}finally{busy(false)}
}

$('closeBackups').onclick=()=>$('backupDialog').close();
$('backupsBtn').onclick=async()=>{
 try{
  const rows=await(await api('/api/backups',{session:state.session})).json();
  $('backupList').innerHTML=rows.length?rows.map(r=>`<div class="panel-heading"><strong>${esc(r.name)}</strong><p class="muted" style="overflow-wrap:anywhere">${esc(r.path)}</p><button data-restore-copy="${r.id}" ${r.valid?'':'disabled'}>${r.valid?'Download restore copy':'Invalid backup'}</button></div>`).join(''):'<p>No editor backups found for this character. A verified backup is created before each changed local save.</p>';
  $('backupDialog').showModal();
 }catch(e){toast(e.message,true)}
};
$('backupList').onclick=async e=>{
 const button=e.target.closest('[data-restore-copy]');if(!button)return;
 try{const response=await api('/api/backup-copy',{session:state.session,id:button.dataset.restoreCopy});download(await response.blob(),state.filename.replace(/\.fch$/i,'')+'.fch');toast('Verified restore copy downloaded.')}catch(e){toast(e.message,true)}
};

function openPathDialog(){
 $('pathError').textContent='';$('pathFiles').innerHTML='';
 if(state?.sourcePath)$('characterPath').value=state.sourcePath;
 $('openDialog').showModal();$('characterPath').focus();$('characterPath').select();
}
function showPathFiles(result){
 $('characterPath').value=result.directory;
 $('pathFiles').innerHTML=result.files.length?'<p class="muted">Choose a character:</p>'+result.files.map(f=>`<button class="recent-row" data-character-path="${esc(f.path)}">${esc(f.name)}</button>`).join(''):'<p class="muted">No .fch character files in this folder.</p>';
}
$('closeOpen').onclick=()=>$('openDialog').close();
$('browseCharacter').onclick=()=>{$('openDialog').close();load(null)};
$('pathForm').onsubmit=async e=>{e.preventDefault();$('pathError').textContent='';$('openPath').disabled=true;try{await load({path:$('characterPath').value})}finally{$('openPath').disabled=false}};
$('pathFiles').onclick=e=>{const b=e.target.closest('[data-character-path]');if(b)load({path:b.dataset.characterPath})};

function renderRecovery(){
 document.querySelectorAll('[data-tomb]').forEach(b=>{const chosen=b.dataset.tomb===state?.teleportTarget;b.textContent=chosen?'Selected for next login':'Teleport here on next login';b.classList.toggle('gold',chosen);b.setAttribute('aria-pressed',String(chosen))});
 $('recoveryStatus').textContent=state?.teleportTarget?'Teleport queued. Save, then enter this same world. Undo cancels the change.':'No teleport queued.';
}
$('scanTombs').onclick=async()=>{
 if(!state)return;
 busy(true,'Finding your tombstones…');
 try{
  const result=await(await api('/api/tombstones',{session:state.session,path:$('recoveryPath').value})).json();
  if(result.warning)toast(result.warning,true);
  if(state.teleportTarget){remember();state.teleportTarget=null;render()}
  $('tombChoices').innerHTML=result.tombstones.length?result.tombstones.map((g,i)=>`<div class="panel-heading"><strong>${esc(result.world)} · Tombstone ${i+1}</strong><p class="muted">Position: ${g.position.map(n=>Math.round(n)).join(', ')} · ${g.items.length} occupied slots</p><p>${g.items.map(x=>`${esc(itemsById[x.prefab]?.name||x.prefab)} ×${x.stack}`).join(' · ')}</p><button data-tomb="${g.id}">Teleport here on next login</button></div>`).join(''):'<p>No nonempty tombstones belonging to this character were found in this world save.</p>';
  renderRecovery();
 }catch(e){toast(e.message,true)}finally{busy(false)}
};
$('tombChoices').onclick=e=>{const b=e.target.closest('[data-tomb]');if(b)mutate(()=>state.teleportTarget=b.dataset.tomb)};
$('recoveryWorlds').onclick=async()=>{
 const output=$('recoveryWorldResults');output.textContent='Looking for worlds…';$('recoveryWorlds').disabled=true;
 try{
  const response=await fetch('/api/worlds');const rows=await response.json();if(!response.ok)throw Error(rows.error||'Could not find worlds.');
  output.innerHTML=rows.length?'<p>Choose the world where you died:</p>'+rows.map(w=>`<button type="button" data-recovery-world="${esc(w.path)}"><strong>${esc(w.name)}</strong> · ${w.cloud?'Steam Cloud':'Local'}</button>`).join(''):'No world saves found in the usual folders. Paste your world save folder path above.';
 }catch(e){output.textContent=e.message}finally{$('recoveryWorlds').disabled=false}
};
$('recoveryWorldResults').onclick=e=>{const b=e.target.closest('[data-recovery-world]');if(!b)return;$('recoveryPath').value=b.dataset.recoveryWorld;$('recoveryWorldResults').textContent='World selected. Click Find my tombstones to scan it.'};

function changeDeathDuration(el){
 if(!state||!el.isConnected||!el.dataset.deathUnit)return;
 if(!el.reportValidity())return;
 const previous=state.player.time_since_death;
 const value=Number(el.value);
 const shown=el.dataset.deathUnit==='days'?Math.floor(previous/1800):Number(((previous%1800)/75).toFixed(6));
 if(value===shown)return;
 const seconds=el.dataset.deathUnit==='days'?value*1800+previous%1800:Math.floor(previous/1800)*1800+value*75;
 if(!Number.isFinite(seconds)||seconds>10000000)return toast('Duration is too large.',true);
 mutate(()=>state.player.time_since_death=seconds);
}
document.addEventListener('change',e=>changeDeathDuration(e.target));
document.addEventListener('focusout',e=>changeDeathDuration(e.target));

$('skillsGrid').addEventListener('click',e=>{
 const button=e.target.closest('[data-increase-skill]');if(!button||!state)return;
 const skill=state.player.skills.find(s=>s.id===Number(button.dataset.increaseSkill));
 if(!skill||skill.level>=100)return;
 const amount=Number(button.dataset.amount);
 if(amount!==1&&amount!==5)return;
 mutate(()=>skill.level=Math.min(100,skill.level+amount));
});

$('inspector').addEventListener('click',e=>{
 const button=e.target.closest('[data-action="max-stack"]');if(!button||!state)return;
 const item=state.player.inventory[selected],limit=item&&itemInfo(item).maxStack;
 if(limit&&item.stack<limit)mutate(()=>item.stack=limit);
});

function maximumItemDurability(item){
 const info=itemsById[item.prefab]?.durability;
 if(!info?.usesDurability)return null;
 const maximum=info.base+Math.max(0,item.quality-1)*info.perLevel;
 return Number.isFinite(maximum)&&maximum>=0?maximum:null;
}
function repairableItems(){
 return (state?.player.inventory||[]).filter(item=>{const maximum=maximumItemDurability(item);return maximum!==null&&item.durability<maximum});
}
function repairAllCharacterItems(){
 const items=repairableItems();if(!items.length)return;
 mutate(()=>items.forEach(item=>item.durability=maximumItemDurability(item)));
 toast(`Repaired ${items.length} item${items.length===1?'':'s'}. Save to keep the changes.`);
}
$('repairAllItems').onclick=repairAllCharacterItems;

let survivalDifficulty=6;
const survivalLabels=['Overall (all play)','Overall (eligible play)','Hammer','Casual','Very easy','Easy','Normal','Hard','Very hard','Hardcore'];
function renderSurvival(){
 const rows=state.survival;
 if(!rows){$('survivalFields').innerHTML='<p>Survival statistics are unavailable for this save format.</p>';return}
 const row=rows[survivalDifficulty];
 $('survivalFields').innerHTML=`<div class="field"><label for="survivalDifficulty">Streak for difficulty</label><select id="survivalDifficulty">${survivalLabels.slice(2).map((name,i)=>`<option value="${i+2}" ${i+2===survivalDifficulty?'selected':''}>${name}</option>`).join('')}</select></div><div class="form-grid"><div class="field"><label for="survivalCurrent">Current streak · days</label><input id="survivalCurrent" type="number" min="0" max="1000000" step="1" value="${row.current}"></div><div class="field"><label for="survivalBest">Best streak · days</label><input id="survivalBest" type="number" min="${row.current}" max="1000000" step="1" value="${row.best}"></div></div>`;
}
$('survivalFields').addEventListener('change',e=>{
 if(e.target.id==='survivalDifficulty'){survivalDifficulty=Number(e.target.value);renderSurvival();return}
 const key={survivalCurrent:'current',survivalBest:'best'}[e.target.id];if(!key)return;
 const value=Number(e.target.value),row=state.survival[survivalDifficulty];
 if(e.target.value.trim()===''||!Number.isInteger(value)||value<0||value>1000000||(key==='best'&&value<row.current)){toast('Use whole days from 0 to 1,000,000. Best streak must be at least the current streak.',true);renderSurvival();return}
 mutate(()=>{const next={...row,[key]:value};next.best=Math.max(next.best,next.current);for(const index of [0,1,survivalDifficulty])state.survival[index]={...next}});
});

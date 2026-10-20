'use strict';
let statisticsProfile=0, statisticsGroup='counters';
const statisticNames={HarvestBerry:'Berries picked',HarvestMushroom:'Mushrooms picked',HarvestCrop:'Crops harvested',HarvestVine:'Vines harvested',HarvestBonus:'Bonus harvests'};
const statisticGroups={counters:'Activity totals',item_pickup_stats:'Items picked up',
 item_craft_stats:'Items crafted',pickable_stats:'Plants harvested',food_eaten_stats:'Food eaten',
 pieces_placed_stats:'Building pieces placed'};
function renderStatistics(){
 const container=$('statisticsFields');
 if(!state.statistics){container.innerHTML='<p>Statistics are unavailable for this save format.</p>';return}
 const values=state.statistics[statisticsProfile][statisticsGroup];
 $('statisticsRecordNote').textContent=`Showing ${survivalLabels[statisticsProfile]}. `+(Object.values(values).some(value=>value!==0)?'Values recorded in this save.':'No activity recorded in this category for this record. Try Overall (all play) or another difficulty.');
 const search=$('statisticsSearch').value.toLowerCase();
 container.innerHTML=Object.entries(values).map(([key,value])=>{
  const label=statisticsGroup==='counters'?(statisticNames[catalog.statLabels[key]]||readable(catalog.statLabels[key])):(itemsById[key]?.name||readable(key));
  return {key,value,label};
 }).filter(row=>(row.label+' '+(catalog.statLabels[row.key]||'')+' '+row.key).toLowerCase().includes(search)).sort((a,b)=>a.label.localeCompare(b.label))
 .map(row=>`<label class="field">${esc(row.label)}<input type="number" min="0" max="16777216" step="1" data-stat-key="${esc(row.key)}" value="${row.value}"></label>`).join('')||
 '<p class="muted">No recorded entries match this category and search.</p>';
}
$('statisticsProfile').innerHTML=survivalLabels.map((label,index)=>`<option value="${index}" ${index===statisticsProfile?'selected':''}>${label}</option>`).join('');
$('statisticsGroup').innerHTML=Object.entries(statisticGroups).map(([key,label])=>`<option value="${key}">${label}</option>`).join('');
$('statisticsProfile').onchange=e=>{statisticsProfile=Number(e.target.value);renderStatistics()};
$('statisticsGroup').onchange=e=>{statisticsGroup=e.target.value;renderStatistics()};
$('statisticsSearch').oninput=renderStatistics;
$('statisticsFields').onchange=e=>{
 const key=e.target.dataset.statKey;if(key===undefined||!state)return;
 const value=e.target.value.trim()===''?NaN:Number(e.target.value);
 if(!Number.isInteger(value)||value<0||value>16777216){toast('Enter a whole number from 0 to 16,777,216.',true);renderStatistics();return}
 mutate(()=>state.statistics[statisticsProfile][statisticsGroup][key]=value);
};

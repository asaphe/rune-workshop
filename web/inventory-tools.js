'use strict';
// Pure helpers: bulk additions are prepared on a copy before touching the save.
const InventoryTools = {
  variantCount(item,catalogue) {
    const count=catalogue[item.prefab]?.variantCount;
    return Number.isInteger(count)&&count>=0?count:null;
  },
  validVariant(item,catalogue,variant) {
    const count=this.variantCount(item,catalogue);
    return count>1&&Number.isInteger(variant)&&variant>=0&&variant<count;
  },
  iconName(item,catalogue) {
    const icons=catalogue[item.prefab]?.icons||[],variant=item.variant??0;
    return Number.isInteger(variant)&&variant>=0&&variant<icons.length?icons[variant]:null;
  },
  maxQuality(item, catalogue) {
    const max=catalogue[item.prefab]?.maxQuality;
    return Number.isInteger(max)&&max>=1&&max<=65535?max:null;
  },
  refinementLimit(item,catalogue) {
    if(catalogue[item.prefab]?.canRefine!==true||!(this.maxQuality(item,catalogue)>1))return null;
    // This is the save format's range, not a claimed in-game refinement cap.
    const d=catalogue[item.prefab]?.durability;
    const durableMax=d?.usesDurability&&d.perLevel>0?Math.floor((21474836-d.base)/d.perLevel)+1:65535;
    return Math.max(1,Math.min(65535,durableMax));
  },
  maxEditableQuality(item,catalogue) {
    return this.refinementLimit(item,catalogue)||this.maxQuality(item,catalogue);
  },
  validQuality(item, catalogue, quality) {
    const max=this.maxEditableQuality(item,catalogue);
    return !!max&&Number.isInteger(quality)&&quality>=1&&quality<=max;
  },
  maximumDurability(item,catalogue) {
    const stats=catalogue[item.prefab]?.durability;
    if(!stats?.usesDurability||!Number.isFinite(stats.base)||!Number.isFinite(stats.perLevel))return null;
    const maximum=stats.base+Math.max(0,item.quality-1)*stats.perLevel;
    return Number.isFinite(maximum)&&maximum>=0?maximum:null;
  },
  syncItemStats(item,catalogue,previous) {
    if(previous&&previous.prefab===item.prefab&&previous.quality===item.quality)return;
    const maximum=this.maximumDurability(item,catalogue);
    if(maximum===null)return;
    item.durability=maximum;
  },
  setQuality(item, catalogue, quality) {
    if (!this.validQuality(item,catalogue,quality) || quality===item.quality) return false;
    const previous={prefab:item.prefab,quality:item.quality};
    item.quality=quality;
    this.syncItemStats(item,catalogue,previous);
    return true;
  },
  weight(item, catalogue) {
    const stats = catalogue[item.prefab]?.weight;
    return stats && Number.isFinite(stats.base) && Number.isFinite(stats.perQuality)
      ? stats.base * item.stack * (1 + (item.quality - 1) * stats.perQuality) : null;
  },
  portalMaterials(inventory, catalogue, rows, count = 1) {
    if (![1, 2].includes(count)) throw Error('Choose one portal or a pair.');
    const result = JSON.parse(JSON.stringify(inventory));
    for (const [prefab, quantity] of [['FineWood',20], ['GreydwarfEye',10], ['SurtlingCore',2]]) {
      const info = catalogue[prefab];
      if (!info || !Number.isInteger(info.maxStack) || info.maxStack < 1)
        throw Error('Portal material data is unavailable.');
      let remaining = quantity * count;
      // Fill ordinary material stacks; never combine custom or marked items.
      for (const item of result) {
        if (item.prefab !== prefab || item.quality !== 1 || item.variant ||
            item.world_level || item.cheated || item.equipped || item.crafter_name ||
            Object.keys(item.custom_data || {}).length) continue;
        const amount = Math.min(remaining, Math.max(0, info.maxStack - item.stack));
        item.stack += amount;
        remaining -= amount;
      }
      while (remaining > 0) {
        let slot;
        for (let y = 0; y < rows && !slot; y++)
          for (let x = 0; x < 8; x++)
            if (!result.some(i => i.grid_x === x && i.grid_y === y)) { slot = {x,y}; break; }
        if (!slot) throw Error('Not enough empty slots for portal materials. Nothing was added.');
        const stack = Math.min(remaining, info.maxStack);
        result.push({prefab, prefab_hash:info.hash, grid_x:slot.x, grid_y:slot.y,
          quality:1, stack, durability:100, variant:0, world_level:0, equipped:false,
          picked_up:true, cheated:false, crafter_name:'', crafter_id:'0', custom_data:{}});
        remaining -= stack;
      }
    }
    return result;
  }
};
if (typeof module !== 'undefined') module.exports = InventoryTools;

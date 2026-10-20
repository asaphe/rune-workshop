'use strict';
// Pure helpers: bulk additions are prepared on a copy before touching the save.
const InventoryTools = {
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

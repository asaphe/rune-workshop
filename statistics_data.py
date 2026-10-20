"""Editable, identified character counters; no achievement-platform writes."""
import copy
import json
import math
from pathlib import Path

NAMES = set(('Deaths CraftsOrUpgrades Builds Jumps EnemyHits EnemyKills EnemyKillsLastHits '
             'ItemsPickedUp Crafts Upgrades PortalsUsed Sleep TreeChops Tree LogChops Logs '
             'MineHits Mines CreatureTamed FoodEaten ArrowsShot TombstonesOpenedOwn '
             'TombstonesOpenedOther DoorsOpened DoorsClosed BeesHarvested SapHarvested '
             'BossKills BossLastHits CraftFood HarvestCrop HarvestBerry HarvestMushroom '
             'HarvestVine HarvestBonus TreasureBuriedFound TreasureDungeonFound '
             'TreasureLocationFound FishHooked FishLost FishCaught TamedPetting TamedCommand').split())
LABELS = {key: name for key, name in json.loads(
    (Path(__file__).parent / 'backend/stat-labels.json').read_text()).items() if name in NAMES}
GROUPS = ('item_pickup_stats', 'item_craft_stats', 'pickable_stats', 'food_eaten_stats', 'pieces_placed_stats')


def public(root):
    profiles = root.get('profiles', [])
    if len(profiles) != 10 or any(len(p.get('stats', [])) != 205 for p in profiles):
        return None
    return [dict(counters={key: p['stats'][int(key)] for key in LABELS},
                 **{key: copy.deepcopy(p.get(key, {})) for key in GROUPS}) for p in profiles]


def apply(root, supplied):
    baseline = public(root)
    if baseline == supplied:
        return
    if baseline is None or not isinstance(supplied, list) or len(supplied) != 10:
        raise ValueError('Statistics are unavailable for this save layout.')
    for index, row in enumerate(supplied):
        old = baseline[index]
        if not isinstance(row, dict) or set(row) != set(old):
            raise ValueError('Unsupported statistics group.')
        for group, values in row.items():
            if not isinstance(values, dict) or set(values) != set(old[group]):
                raise ValueError('Only existing, identified counters can be edited.')
            for key, value in values.items():
                if value == old[group][key] and not isinstance(value, bool):
                    continue
                if (isinstance(value, bool) or not isinstance(value, (float, int)) or
                        not math.isfinite(value) or value < 0 or value > 16777216 or value != int(value)):
                    raise ValueError('Counters must be whole numbers from 0 to 16,777,216.')
                if group == 'counters':
                    root['profiles'][index]['stats'][int(key)] = value
                else:
                    root['profiles'][index][group][key] = value

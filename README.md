# Rune · Local Character Workshop

A local-only browser editor for Valheim character saves (`.fch`) and Valheim 1.0
world saves, built around verified, byte-exact round-trips and retained backups.

## Running

Rune needs Python 3.9 or newer and nothing else (standard library only).

- **Windows:** double-click **Launch Rune.cmd**. It uses a bundled
  `runtime\pythonw.exe` when one is present and otherwise falls back to the
  `pyw` launcher from a [python.org](https://www.python.org/downloads/) install.
- **Any platform, with a console:** `python3 server.py` (Ctrl+C stops it).
  `--port <n>` picks a fixed port and `--no-browser` skips opening a tab.

### Item artwork

Item icons are game artwork and are not part of this repository. Without them
the inventory shows a placeholder glyph per item; everything else works. To get
the icons, put the PNGs extracted from your own Valheim install in
`backend/local-data/item_icons/` (file names are the hashes listed in
`backend/local-data/valheim_items.json`).

## Save and export

**Save** works only with local characters while Valheim is completely closed.
Steam Cloud cache files are read-only here: editing them directly while Steam or
Valheim has cached their size can truncate the save. In Valheim Manage Saves,
move the character to Local, quit the game completely, then reopen that local
character in Rune.

Before a changed save, Rune writes and verifies an exact backup in the
`.rune-backups` folder beside the character. It then atomically replaces the
character file, without a missing-file interval. Every backup ends in `.fch.old`.
External file changes and a running game block saving.

**Backups** lists both current and older editor backups and lets you download a
verified `.fch` restore copy. **Export** downloads the edited character separately.
Export does not mark changes as saved to the original file.

**Open character** uses a local file picker so Save knows the original path.
Characters opened from the detected list also support Save when local. Dropped
files must be reopened through Open character before direct saving.

## Features

Inventory editing with item artwork, quality, quantities, durability, equipment,
move/swap, add/replace/duplicate/delete; one bulk item-cheat-flag clear button;
skills; health, stamina and Eitr; active food timers; appearance and power;
character cheat flag; knowledge; undo/redo.

The food picker lists consumables, so select actual edible foods. Game limits
and food effects are not simulated. Valheim can recalculate maximum stats.
Supports profile/player/inventory versions 46/33/109 and 47/34/110.
No in-game validation has been performed.

Regression tests verify unchanged files, targeted edits, cheat flags, large
IDs, corrupt input, repeated saves/backups, external changes and failed-write
recovery. Tests use private fixture copies in the development workspace.

## Folder contents

- `web`: browser interface
- `backend`: required parser code, item metadata and artwork
- `runtime`: bundled Python (Downloads distribution)
- `licenses`: upstream notices
- `.runtime`: temporary working files, created when running

The server binds only to 127.0.0.1 and makes no external requests. The launcher
runs it in the background. For a console that stops with Ctrl+C, run
`runtime\python.exe server.py` from this directory.

Original browser interface using the patched miskamero/VikingEditor parser
(https://github.com/miskamero/VikingEditor, GPL-3.0). Item labels were prepared
with MerpMB/Valhala's catalogue utility (MIT). License texts are in `licenses`.
Game artwork comes from your installed game. This is not vikingeditor.com.


## World containers

Choose **World** beside Character, then **Containers**. Open a detected world or paste its
folder path. Supports the chunked Valheim 1.0 world formats 40–42 and inventory
formats 109–110. Only containers with a nonzero saved player creator are listed;
world-generated loot containers and containers without that marker are excluded.

Search by container type, coordinates or stored item. Filter locations using a
200-metre X/Z grid. The creator filter appears only when multiple builders are
represented. Names are resolved from available character saves; unmatched IDs
use Unknown player labels. Edit quantities, quality, durability and slots; add
or remove items, clear item cheat flags, and undo changes. Slot coordinates are
one-based in the UI; use the actual container dimensions in game.

**Save world** requires a local world and a closed game. It verifies the loaded
files have not changed, creates a verified full-generation ZIP in the world's
.rune-backups folder, and writes a new generation with its commit marker last.
The old generation is retained. The saved backup path is displayed after saving.
To restore, close Valheim and extract the backup world folder into a separate
location; do not merge it over a newer world generation.

**Export world ZIP** produces a complete edited world snapshot without changing
the source. Steam Cloud caches are export-only. For direct saving, use Valheim
Manage Saves to move the world to Local, quit Valheim completely, and reopen it.

The serializer preserves bytes outside edited inventories. Tests cover real-world
no-op preservation, edited copy readback, backups, write failure/retry, external
changes, and player-created filtering. In-game loading of edited worlds has not
yet been manually verified.


### World settings, portals and signs

The World workspace includes Containers, Portals & signs, and World settings.
Settings offer Free-build (No build cost), passive enemies, all portal items,
player-based raids, and fire hazards. On/Off selectors reflect the opened save.
Save with Free-build On, build in game, then close the game and reopen the
latest world to set it Off again. Other world settings, identity, seed, and
player-history bytes are preserved. Turning it off does not remove buildings.

These controls do not bypass achievement checks. Free-build may block some
achievements while enabled; disabling it does not promise retroactive credit.

Player-created wood/stone portals and signs can be edited, including blank ones.
Changing a portal tag clears the saved link for both sides of its old connection
so the game can resolve matching tags. Text is limited to 500 characters.
Undo covers containers, settings and text together; Undo setting changes restores
only settings from the currently opened/saved baseline.

All changes share the guarded Save world / Export world ZIP workflow.
The character overview also displays why Save is blocked, or the exact local
destination when Save is available.


## Tombstone recovery
After respawning, quit Valheim completely. Open the current local character, then use Character & food > Tombstone recovery. Select the world save folder and scan. The chooser lists nonempty tombstones owned by this character, with positions and item summaries. Select one and Save; enter that same world to appear at its saved location. This edits only the character logout position, with the normal backup and process guards. The world is read-only for recovery; Cloud world folders can be scanned. Cloud characters must be moved to Local in-game first. Use the current save, not an older local duplicate. A changed world requires rescanning. Recovery needs access to the world save (including server worlds). In-game arrival has not been manually tested.

## Contributing, security and licence

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Rune is
distributed under [GPL-3.0](LICENSE) because it includes a patched copy of the
GPL-3.0 VikingEditor parser; third-party notices are in `licenses/`. Rune is not
affiliated with Iron Gate or Coffee Stain. Valheim is a trademark of its owners.

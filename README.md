# Rune · Local Character Workshop

A local-only browser editor for Valheim character saves (`.fch`) and Valheim 1.0
world saves, built around verified, byte-exact round-trips and retained backups.

## Quick setup

### Windows: starting from a GitHub ZIP

1. Download **Code → Download ZIP**, then extract it. Open the extracted folder
   containing `server.py` and **Launch Rune.cmd**; do not run it inside the ZIP.
2. Install **Python 3.9 or newer** from [python.org](https://www.python.org/downloads/windows/)
   if you do not already have it. Keep the Python launcher enabled in the
   installer. You do **not** need Python 3.9 specifically, or any pip packages.
3. Double-click **Launch Rune.cmd**. Rune opens in your browser and runs locally.
4. Before editing, use Valheim's **Manage Saves** to move your **current** character
   or world to **Local**, then quit Valheim completely, including the main menu.
5. In Rune, choose **Open character** or the **World** tab. Select the current
   local save, make your changes, then **Save** or **Save world**.

**The GitHub source ZIP does not include Python or item artwork.** A separately
prepared portable Windows copy may include a `runtime` folder; if yours contains
`runtime/pythonw.exe`, skip step 2. Keep that folder beside `server.py`.
Placeholder diamonds instead of item pictures are expected until you add
[local item artwork](#item-artwork); editing still works.

If two characters have the same name, check their **Local / Steam Cloud** labels
and modification dates. An old local copy may not be the character you currently
play. Moving the current save to Local in the game avoids editing the wrong copy.

### macOS

Install Python 3.9 or newer from [python.org](https://www.python.org/downloads/macos/),
extract the ZIP, then double-click **Launch Rune.command**. See the launch notes
below if macOS blocks the downloaded file. The same Local-save and closed-game
requirements apply.

### After updating Rune

Keep your portable `runtime` folder and locally extracted
`backend/local-data/item_icons` folder when moving to a new download. Relaunch
Rune and use its newly opened browser tab. Refreshing an old tab does not restart
an older server or reload its startup catalog. Save pending edits before restarting.

## Launch options

Rune needs Python 3.9 or newer and nothing else (standard library only).

- **Windows:** double-click **Launch Rune.cmd**. It uses a bundled
  `runtime\pythonw.exe` when one is present and otherwise falls back to the
  `pyw` launcher from a [python.org](https://www.python.org/downloads/) install.
- **macOS:** double-click **Launch Rune.command**. It runs in a Terminal
  window; closing the window stops Rune. A `git clone` copy runs as is. A copy
  downloaded as a ZIP is quarantined: on macOS 15 and later, open it once, then
  allow it under **System Settings → Privacy & Security → Open Anyway** (or run
  `xattr -d com.apple.quarantine "Launch Rune.command"`); on older macOS,
  Control-click the file and choose **Open**. If no Python 3.9+ is found it
  links to the python.org installer.
- **Any platform, with a console:** `python3 server.py` (Ctrl+C stops it).
  `--port <n>` picks a fixed port and `--no-browser` skips opening a tab.

Each launch creates a new access token. The link Rune opens (and prints, and
saves in `.runtime/url.txt`, readable only by you) carries it; the browser keeps
it as a cookie. A tab left open from an earlier launch, or the bare
`http://127.0.0.1:<port>` address, cannot reach your saves: use the new link.

### Where Rune looks for saves

| | Local saves | Steam Cloud cache (read-only) |
|---|---|---|
| Windows | `%USERPROFILE%\AppData\LocalLow\IronGate\Valheim` | `<Steam>\userdata\<account>\892970\remote` |
| macOS (Steam) | `~/Library/Application Support/IronGate/Valheim` | `~/Library/Application Support/Steam/userdata/<account>/892970/remote` |

Each location holds `characters_local`/`worlds_local` (or `characters`/`worlds`
in the Cloud cache). On Windows the Steam folder comes from the registry; set
`RUNE_STEAM_DIR` to point at a different Steam folder on either platform. The
Mac App Store build of Valheim keeps its saves inside its sandbox under
`~/Library/Containers`; Rune does not scan there (macOS would show a privacy
prompt), so paste that folder's path into **Open character** or the world path
field instead.

Direct **Save** needs a check that Valheim is closed, which Rune does on Windows
and macOS. On other platforms Rune can still open and export saves. Quit all
instances of the game and any dedicated server using the save before editing.

### Item artwork

Item icons are game artwork and are not part of this repository. Without them,
the inventory shows placeholder diamonds; all editing features still work.

If you already have a working Rune copy with icons:

1. Copy its entire `backend/local-data/item_icons` folder into the same location
   in your new Rune folder. The PNG files should sit directly inside `item_icons`,
   not in another nested `item_icons` folder.
2. Relaunch Rune and use the newly opened tab. Icons are checked at server startup,
   so refreshing the old page alone is not enough.

For a first installation, this repository currently has **no icon extraction
command or setup wizard**. You need PNGs extracted from your own Valheim install,
with the hash filenames listed in `backend/local-data/valheim_items.json`.
Renaming arbitrary images to item names will not work. You can use Rune with its
placeholders until artwork is available. Do not commit extracted game artwork.

## Save and export

**Save** works only with local characters while Valheim is completely closed.
Steam Cloud cache files are read-only here: editing them directly while Steam or
Valheim has cached their size can truncate the save. In Valheim Manage Saves,
move the character to Local, quit the game completely, then reopen that local
character in Rune.

Before a changed save, Rune writes and verifies an exact backup in the
`.rune-backups` folder beside the character. It then atomically replaces the
character file, without a missing-file interval. Every backup ends in `.fch.old`.
External file changes and a running game block saving. Rune re-reads the file
immediately before replacing it, but it cannot lock out other programs: if Steam
Cloud sync or another editor writes the same save in that final instant, its
write can be overwritten. Keep Steam and other save tools idle while saving.

**Backups** lists both current and older editor backups and lets you download a
verified `.fch` restore copy. **Export** downloads the edited character separately.
Export does not mark changes as saved to the original file.

**Open character** uses a local file picker so Save knows the original path.
Characters opened from the detected list also support Save when local. Dropped
files must be reopened through Open character before direct saving.

## Features

### Character inventory

Select an item in the grid to edit it. You can add, change, move/swap, duplicate,
or delete items and edit their stack, quality, durability and equipment state.

- **Max stack** fills the selected stack to its catalogued limit.
- **Duplicate** copies the selected item into an empty inventory slot.
- **Repair all** restores damaged items to their maximum durability at their
  current quality level. Items with unknown durability data are left unchanged.
- **Clear all item cheat flags** clears item flags in bulk. The character's own
  flag is shown separately in the overview and **Character & food** section.
- **Undo / Redo** lets you review or reverse character edits before saving.

These actions change the editor's pending state. Use **Save** to write changes
back to the local character, or **Export** to make a separate edited copy.

### Skills

Use **+1 / +5** on an individual learned skill or the bulk buttons for all learned
skills. Levels stop at 100 and existing skill progress is preserved. Unlock an
unlearned skill before editing it. These changes support Undo.

The character save does not record the exact skill levels lost on the last
death, so Rune cannot reliably reconstruct them without a suitable earlier save.

### Character & food

Edit health, stamina, **Eitr (magic energy)**, appearance and Forsaken power here.
Choose up to three different active foods using the food replacement buttons.
Replacing a food starts its full duration. Changing foods or their remaining
time recalculates food-based maximum health, stamina and Eitr; it does not refill
current values. Food timers are in seconds. The game may apply additional effects
and recalculate values when you play.

**In-game time since last death** accepts **Days** and **Hours** and converts them
automatically. For example, enter `29` days and `9` hours, then Save. This expresses
the saved gameplay timer using a standard Valheim day; it is not a record of
world-calendar days skipped through sleeping or spent offline.

### Knowledge

The Knowledge tab covers recipes, materials, biomes, trophies and other saved
discoveries. Use the category list to choose what to edit.

### Compatibility and verification

Supports profile/player/inventory versions 46/33/109 and 47/34/110. No in-game
validation has been performed. Regression tests cover unchanged files, targeted
edits, backups and failure handling. See [CONTRIBUTING.md](CONTRIBUTING.md) for
running the tests and supplying optional private save fixtures.

## Folder contents

- `web`: browser interface
- `backend`: required parser code, item metadata and artwork
- `runtime`: optional bundled Python in a prepared portable copy; absent from the source ZIP
- `licenses`: upstream notices
- `.runtime`: temporary working files, created when running

The server binds only to 127.0.0.1 and makes no external requests. The Windows
launcher runs it in the background. For a console that stops with Ctrl+C, run
`runtime\python.exe server.py` (Windows) or `python3 server.py` from this directory.

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
use Unknown player labels.

Select a container to see its inventory grid, then select a stack to edit it:

- **Add item** places a new stack in the next empty slot.
- **Max stack** fills the selected stack to the item's catalogued limit.
- **Duplicate** copies it to the next empty slot. Repeat until the container is full.
- Edit quantity, quality or durability, delete stacks, or clear item cheat flags.
- **Undo** reverses a world edit.

Adding and duplicating are unavailable when a container is full or its capacity
is unknown. Changes remain pending until **Save world** or **Export world ZIP**.

**Save world** requires a local world and a closed game. It verifies the loaded
files have not changed, creates a verified full-generation ZIP in the world's
.rune-backups folder, and writes a new generation with its commit marker last.
The marker is written to a temporary file and renamed into place, so it is
either complete or absent; if a save fails, the files it already wrote are
removed. If an older Rune version left an incomplete marker, Rune opens the
previous complete generation, says so, and the next save writes a complete one.
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
1. After respawning, quit Valheim completely and open your current **local**
   character in Rune.
2. Go to **Character & food → Tombstone recovery**.
3. Click **Find world folders** and choose a world from the visible list, or paste
   the **world save folder** path. This is a folder, not your character `.fch` file.
4. Click **Find my tombstones**. Choose among your remaining nonempty tombstones
   using their positions and item summaries; older graves may also be listed.
5. Select **Teleport here on next login**, then **Save** your character. Enter
   that same world in Valheim.

Tombstones are stored in the world, so the character file alone is not enough.
Rune reads the world without changing it and edits only your character's logout
position. Items remain in the grave, and nearby enemies may still be present.
Cloud world folders can be scanned, but the character must be Local for direct
saving. A changed world requires rescanning. For a server world, you need access
to its save folder. In-game arrival has not been manually tested.

## Troubleshooting

| What you see | What to do |
|---|---|
| “Python 3.9 or newer” when launching | Install Python with its Windows launcher, or use a prepared portable copy containing `runtime/pythonw.exe`. The GitHub ZIP does not include that runtime. |
| Diamonds instead of item pictures | Add your local icon folder, then relaunch Rune. See [Item artwork](#item-artwork). |
| Save is disabled | Read the message above the tabs. Move Cloud saves to Local in Valheim, quit the game, and reopen the local save. Imported/dropped files must be reopened by their file path for direct saving. |
| Edits do not appear in game | Check that you saved rather than only exported, and that the game loads the same Local character/world you edited. Compare names, storage labels and modification dates. |
| “File changed” or “World changed” | Reopen the latest save before editing again; another process or the game updated it. |
| An old browser tab cannot access saves | Use the new browser tab/link opened by the current Rune launch. |
| New features do not appear after an update | Relaunch the updated copy. Refreshing a tab connected to an older server is not sufficient. |
| No worlds are found | Paste the world save folder path. See [Where Rune looks for saves](#where-rune-looks-for-saves) for discovery locations and custom Steam paths. |

## Contributing, security and licence

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Rune is
distributed under [GPL-3.0](LICENSE) because it includes a patched copy of the
GPL-3.0 VikingEditor parser; third-party notices are in `licenses/`. Rune is not
affiliated with Iron Gate or Coffee Stain. Valheim is a trademark of its owners.

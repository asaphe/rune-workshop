# Rune · Local Character Workshop

A local-only editor for Valheim character saves (`.fch`) and Valheim 1.0
world saves, built around verified, byte-exact round-trips and retained backups.

## Quick setup

### Windows: automatic setup (recommended)

1. Choose **Code → Download ZIP**, then **Extract All**. Open the folder
   containing `server.py` and **Launch Rune.cmd**.
2. Double-click **Launch Rune.cmd**. If compatible Python is missing, Rune asks
   before downloading the **official Windows embeddable Python ZIP** from
   python.org. Type **y** to accept, or decline and use manual setup below.
3. Accept **Rune app window setup** to download Microsoft’s WebView2 SDK and build
   the native host. If prompted, install the WebView2 Runtime from Microsoft.
4. Optionally accept **item pictures**. Confirm a detected Valheim installation,
   or select **valheim.exe** in the file picker. Cancel or answer **n** to skip.
5. Rune opens in its own Windows app window (using Microsoft WebView2). Follow [Open your first save](#open-your-first-save).

Setup stays inside Rune's folder, with no administrator access or system install.
It verifies the Python ZIP's SHA-256 before installation. It does not modify your
system Python, PATH, game files or saves. No binaries or artwork are committed.

Automatic setup uses official **Python 3.14.8**, a supported stable release
compatible with the artwork tools, rather than claiming it is the newest Python.
An existing compatible runtime is reused. If it is newer than the artwork tools
support, icon setup offers a separate portable 3.14 runtime for extraction.

Optional icon setup temporarily downloads **UnityPy 1.24.2** and dependencies
from PyPI. Reading game artwork can take several minutes and substantial memory.
It does not install pip or packages into your Python runtime. The editor itself
remains standard-library only. Skipping icons is remembered; run **Setup Rune.cmd**
to add or refresh them later. Quit an existing Rune instance before refreshing
icons, then use the new app window opened by setup.

Download errors show a retry option. Declining Python setup exits; skipping or
failing icons still lets Rune launch with placeholders. Windows PowerShell runs
setup, then exits after starting Python. It does not remain as a service.

### Windows: manual portable Python setup

1. Download a supported stable **Windows embeddable package** from
   [python.org](https://www.python.org/downloads/windows/): 64-bit for Intel/AMD,
   ARM64 for Windows on ARM.
2. Create **runtime** beside `server.py` and extract **all** ZIP contents directly
   into it. `runtime/python.exe` and `runtime/pythonw.exe` must exist. Keep the
   DLLs, standard-library ZIP and `python*._pth` unchanged. No pip setup is needed.
3. Run **Launch Rune.cmd**. You may skip optional artwork setup.

### Open your first save

1. In Valheim, open **Manage Saves** and move your **current** character or world
   to **Local**. Quit Valheim completely, including the main menu.
2. In Rune, choose **Open character** or **World**. Select the current local save.
   For a world, select its save folder; for a character, select its `.fch` file.
3. Make your changes and choose **Save** or **Save world**. Rune backs up the
   original before writing. **Export** creates a separate copy instead.
4. Start Valheim and select that same Local character/world.

If two characters have the same name, check their **Local / Steam Cloud** labels
and modification dates. An old local copy may not be the character you currently
play. Moving the current save to Local in the game avoids editing the wrong copy.

### Optional: use an installed Python on Windows

If you prefer a normal Python installation, install a currently supported stable
Python 3 release from [python.org](https://www.python.org/downloads/windows/)
with the Windows launcher (`pyw`), then double-click **Launch Rune.cmd**.
A `runtime` folder is not required for this route. If the launcher is missing,
you can run `python launch.py` in Command Prompt from the Rune folder instead.
No pip packages are required to run the editor; optional artwork setup downloads its own tools.

**Python 3.9 is the minimum compatibility version, not the recommended version
to install.** For a new setup, use a currently supported stable release.

### macOS

Install a currently supported stable Python 3 release from
[python.org](https://www.python.org/downloads/macos/), extract Rune's ZIP, then
double-click **Launch Rune.command**. See the launch notes below if macOS blocks
the downloaded file. Follow [Open your first save](#open-your-first-save) before
editing. The Windows embeddable Python ZIP does not run on macOS.

### After updating Rune

Keep your portable `runtime` folder and locally extracted
`backend/local-data/item_icons` folder and `item-icons.json` index when moving to a new download. Relaunch
Rune and use its newly opened window. Refreshing an old tab does not restart
an older server or reload its startup catalog. Save pending edits before restarting.

## Launch options

Rune requires Python 3.9 or newer, with no pip packages. For a new setup, use a
currently supported stable Python 3 release. The official Windows embeddable
ZIP works without installation; Windows uses its native file picker, not Tcl/Tk.

- **Windows:** double-click **Launch Rune.cmd**. It checks a local
  `runtime\pythonw.exe` through `launch.py` when present, then checks the
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

### Dedicated Windows app window

Windows launches Rune in its own native WebView2 window. It does not launch
Edge or Chrome, load your personal browser profile, or open external browser windows.
Each instance uses a separate `.runtime/webview2-data/session-*` folder inside
Rune; normal shutdown removes that session data. Your browser history, cookies,
extensions and sign-in are not used.

Close **X** or choose **Quit Rune** to stop the local server and its WebView2
processes. X checks for unsaved edits and waits for an active operation. Quit
allows active server operations to finish before closing the window.

First launch asks before downloading Microsoft's WebView2 SDK (~10 MB) from
NuGet. Setup verifies the pinned checksum and compiles `native/RuneHost.cs` using
the .NET Framework compiler supplied with Windows. The SDK files, license and
compiled host stay under `.runtime`; no binary is committed to the repository.
Windows .NET Framework 4.6.2+ and the **WebView2 Evergreen Runtime** are required.
If the runtime is missing, install it from
[Microsoft](https://developer.microsoft.com/microsoft-edge/webview2/) and relaunch.
WebView2's runtime receives Microsoft updates separately from the Edge browser.

To intentionally use a normal browser tab, run
`runtime\python.exe launch.py --browser` (or `python launch.py --browser`).
In browser mode, use **Quit Rune**; closing a tab does not stop the server.
macOS continues to use browser mode.

### Inventory conveniences

- Inventory and selected-stack **weight** update as you edit quantity and quality.
  Values use the bundled game item data, including quality-dependent weight.
  Unknown/modded items are explicitly excluded from the known total and counted
  as unknown stacks. Weight is a display, not a way to change game item weights.
- **+ Portal materials** adds 20 fine wood, 10 greydwarf eyes and 2 surtling cores
  for one wooden portal. Click again for another. Ordinary existing stacks fill
  first; additional stacks use empty slots. If the full recipe cannot fit,
  nothing changes. One click is one Undo step. Save to apply it in-game.

### Statistics

The character's **Statistics** tab includes survival streaks by difficulty and
identified activity counters, such as berries/mushrooms picked, crafting, fishing
and kills. Select a record (overall or a specific difficulty) and category.
Activity edits affect only that record. Survival streak edits retain their
separate rule: the selected difficulty and both overall streak counters update.
Per-item categories show entries already stored in the save. Undo, Export and
Save include statistics. Unknown counters and other save data are preserved.
Editing a counter does not directly unlock a platform achievement; the game
still evaluates its requirements and eligibility.

### Where Rune looks for saves

| | Local saves | Steam Cloud cache |
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

On Windows, run **Setup Rune.cmd** and accept the artwork step. Choose an
installed Valheim folder, **not** a character/world save folder. Setup reads
`valheim_Data/StreamingAssets/SoftRef/Bundles` and writes PNGs plus an icon index
under `backend/local-data`. Unreadable sprites use placeholders. Failed extraction
preserves the existing artwork and index.

To transfer artwork, copy `backend/local-data/item_icons/` and, if present,
`backend/local-data/item-icons.json`. Quit and relaunch Rune; refreshing an old
tab alone does not reload artwork. Older PNG-only copies still work with the
bundled metadata. Never commit extracted artwork or the local icon index.

## Save and export

**Save** replaces the character file you opened, keeping a verified backup.
Quit Valheim completely first. For characters in Steam's `userdata/.../remote`
cache, also exit Steam completely using **Steam > Exit**; Rune checks both before
writing. After restarting Steam, if a sync conflict appears, keep the edited
local file. Moving the character to Local in Valheim Manage Saves avoids cloud
sync conflicts. Imported files without a source path still require Export.

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
- `runtime`: your extracted official Windows embeddable Python; absent from the source ZIP
- `licenses`: upstream notices
- `.runtime`: temporary working files, created when running

The server binds only to 127.0.0.1 and makes no external requests. The Windows
launcher runs it in the background. For a console that stops with Ctrl+C, run
`runtime\python.exe launch.py` (Windows) or `python3 server.py` from this directory.

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
| “Python 3.9 or newer” when launching | Extract the official embeddable Python ZIP into `runtime`, or use an installed Python with the Windows launcher. 3.9 is the minimum compatibility version, not an installation recommendation. |
| Rune does not open | Check that `runtime/pythonw.exe` exists directly inside `runtime`. From Command Prompt in the Rune folder, run `runtime\python.exe launch.py --check`. A startup error dialog points to `.runtime/startup.log` when available. |
| Diamonds instead of item pictures | Run Setup Rune.cmd, then relaunch Rune. See [Item artwork](#item-artwork). |
| Save is disabled | Read the message above the tabs. Quit Valheim; for Cloud characters, also exit Steam completely. Imported/dropped files must be reopened by their file path for direct saving. |
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

### Survival streak

Statistics has separate current and best survival streaks in whole days. Choose the difficulty you play. Editing updates that difficulty and both overall statistic profiles; other difficulties, cheat flags and the death timer are preserved. Best is raised automatically when current exceeds it. Undo/redo and normal verified Save/backups apply. The separate time-since-death timer controls the death-penalty cooldown and does not advance survival achievement progress. The game still checks achievement eligibility; an unlock is not guaranteed.

## Quitting Rune

Click **Quit Rune** in the header, available in both Character and World. Confirm
that you want to stop this instance. Unsaved character or world edits prompt a
warning; save changes in other tabs first, because quitting affects every tab
connected to the same server. Active server operations finish before Python exits.
The page then tells you to close the tab. Use the launcher to start Rune again.

On Windows, closing the dedicated app window also stops the server. In browser mode, closing a tab alone does not stop the server. Rune requires Python at
runtime, not Node.js; Quit Rune does not terminate unrelated Python, Node.js or
browser processes, nor separate Rune instances.

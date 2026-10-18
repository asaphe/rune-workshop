# Security policy

## Reporting a vulnerability

Report privately through GitHub Security Advisories:
**[Report a vulnerability](https://github.com/asaphe/rune-workshop/security/advisories/new)**

Please do not open a public issue for a security report.

This is a solo-maintained hobby project. Expect an acknowledgement within a week
and a fix or an explicit decision not to fix within a month. There is no paid
support and no SLA.

## Supported versions

Only the current `main` is supported.

## What counts as a vulnerability here

Rune runs a local HTTP server on `127.0.0.1` that reads and rewrites your game
saves. In scope:

- Any way a web page, another local user or a crafted save file can make the
  server read, write or delete a file outside what the person using Rune chose
  (including through DNS rebinding or cross-origin requests).
- Script injection in the browser UI through save contents (character names,
  sign text, crafter names, item IDs).
- A save, backup or world-generation path that can lose or corrupt data, or a
  failure that is reported as a successful save.
- Anything that sends save data or file paths off the machine.

Out of scope:

- Attacks that already require write access to your saves, the Rune folder or
  your Python installation.
- Edits that the game itself rejects or "fixes" on load. Rune does not simulate
  game rules; that is a bug report, not a vulnerability.

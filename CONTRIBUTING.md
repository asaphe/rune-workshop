# Contributing to Rune Workshop

Thanks for considering a contribution.

## Licence and sign-off

Rune includes a patched copy of the GPL-3.0
[VikingEditor](https://github.com/miskamero/VikingEditor) parser, so the project
is distributed under GPL-3.0. Contributions require a
[Developer Certificate of Origin](https://developercertificate.org/) sign-off,
not a CLA:

```sh
git commit -s -m "fix: ..."
```

## Ground rules

- **Never commit save files** (`.fch`, `.fch.old`, world folders) or extracted
  game artwork. `.gitignore` blocks the common names; check `git status` anyway.
- The editor runtime is standard-library only. Windows setup downloads official
  portable Python after consent; macOS uses system Python. Optional artwork
  extraction installs UnityPy into temporary local tools, never the server runtime.
  Changes to setup dependencies need download/extraction tests.
- A change to a serializer or write path needs a test showing an unchanged save
  round-trips byte for byte and an edited one reads back as intended.

## Before opening a PR

```sh
python3 -m unittest discover -s tests -v
for f in web/*.js; do node --check "$f"; done
```

Tests that need real character saves are skipped unless `RUNE_FIXTURES` points
at a folder of private fixture copies (`current-v47.fch`, `backup-v46.fch`,
`other-v46.fch`). Never use your live save folder for this.

## Reporting a security issue

See [SECURITY.md](SECURITY.md).

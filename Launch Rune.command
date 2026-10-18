#!/bin/bash
# Double-click in Finder. Closing this Terminal window (or Ctrl+C) stops Rune.
cd "$(dirname "$0")" || exit 1
for py in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    exec "$py" server.py "$@"
  fi
done
echo "Rune needs Python 3.9 or newer: https://www.python.org/downloads/macos/"
read -r -p "Press Return to close."
exit 1

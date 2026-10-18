"""Launch Rune with visible diagnostics even when pythonw hides the console."""
from pathlib import Path
import contextlib
import os
import runpy
import sys
import traceback

BASE = Path(__file__).resolve().parent


def check_runtime():
    if sys.version_info < (3, 9):
        raise RuntimeError('Use a currently supported Python 3 release (minimum compatible: 3.9).')
    import ctypes
    import ssl
    if os.name == 'nt':
        ctypes.WinDLL('comdlg32')


def main():
    try:
        sys.path.insert(0, str(BASE))
        check_runtime()
        if '--check' in sys.argv:
            print('Python and the native file picker are ready.')
            return 0
        os.chdir(BASE)
        sys.path.insert(0, str(BASE))
        # pythonw has no stdout/stderr. Keep errors, but not the token-bearing URL.
        (BASE / '.runtime').mkdir(exist_ok=True)
        with open(BASE / '.runtime' / 'startup.log', 'w', encoding='utf-8') as errors, open(os.devnull, 'w') as quiet:
            with contextlib.redirect_stderr(errors), contextlib.redirect_stdout(quiet):
                try:
                    runpy.run_path(str(BASE / 'server.py'), run_name='__main__')
                except Exception:
                    traceback.print_exc()
                    raise
        return 0
    except Exception as exc:
        message = ('Rune could not start.\n\n' + str(exc) + '\n\n'
                   'Extract the official Python embeddable ZIP directly into the runtime folder.\n'
                   'Alternatively, install Python with the Windows launcher. See README.md.\n'
                   'If present, see .runtime/startup.log beside Launch Rune.cmd.')
        if sys.stderr is not None:
            print(message, file=sys.stderr)
        if os.name == 'nt' and '--check' not in sys.argv:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, 'Rune startup error', 0x10)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
